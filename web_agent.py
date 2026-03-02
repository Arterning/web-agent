#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用网页自动化智能体 (Web Agent)

用自然语言描述任务，AI 自主决策并完成网页操作。

使用方法:
    python web_agent.py "去百度搜索Python教程"
    python web_agent.py "去GitHub查看今日trending项目" --start-url https://github.com
    python web_agent.py "搜索最新的AI新闻" --headless
    python web_agent.py "登录我的账号" --secret "邮箱=user@example.com" --secret "密码=mypass123"
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
from typing import Dict, List, Any, Optional, Tuple

import httpx
from playwright.async_api import async_playwright, Page


class WebAgent:
    """通用网页自动化智能体"""

    def __init__(self, api_key: str, api_base: str, task: str,
                 secrets: Optional[Dict[str, str]] = None):
        """
        初始化智能体

        :param api_key: LLM API 密钥
        :param api_base: API 基础 URL
        :param task: 自然语言任务描述
        :param secrets: 敏感信息 {描述: 真实值}，如 {"邮箱": "user@example.com"}
        """
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')
        self.task = task

        # 敏感信息用占位符保护，不直接发给 LLM
        self.secrets = {}           # placeholder -> real_value
        self.secret_labels = {}     # placeholder -> 描述
        if secrets:
            for label, value in secrets.items():
                placeholder = f"SECRET_{uuid.uuid4().hex[:8].upper()}"
                self.secrets[placeholder] = value
                self.secret_labels[placeholder] = label

        self.action_history: List[Dict[str, Any]] = []
        self.messages: List[Dict[str, str]] = []  # 多轮对话历史

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    async def run(self, page: Page, start_url: Optional[str] = None,
                  max_steps: int = 15) -> Dict[str, Any]:
        """
        执行任务

        :param page: Playwright 页面对象
        :param start_url: 起始 URL（可选）
        :param max_steps: 最大步骤数
        :return: 结果字典 {status, message, data, steps}
        """
        print(f"[*] 任务: {self.task}")
        print(f"[*] 最大步骤数: {max_steps}")
        if self.secret_labels:
            labels = ', '.join(self.secret_labels.values())
            print(f"[*] 已注入敏感信息: {labels}")
        print("=" * 60)

        # 初始化系统提示词
        self._init_system_prompt()

        # 导航到起始页面
        if start_url:
            try:
                print(f"[*] 导航到: {start_url}")
                await page.goto(start_url, wait_until='domcontentloaded',
                                timeout=30000)
                await asyncio.sleep(2)
            except Exception as e:
                return {'status': 'error', 'message': f'导航失败: {e}',
                        'data': None, 'steps': 0}

        # 自主决策循环
        for step in range(max_steps):
            print(f"\n{'=' * 60}")
            print(f"[Step {step + 1}/{max_steps}]")
            print(f"{'=' * 60}")

            try:
                # 1. 提取页面信息
                print("[1] 提取页面信息...")
                page_info = await self._extract_page_info(page)
                print(f"    URL: {page_info['url']}")
                print(f"    可交互元素: {len(page_info['elements'])} 个")

                # 2. 询问 AI
                print("[2] 咨询 AI 决策...")
                action = await self._ask_ai(page_info, step)

                if not action:
                    return {'status': 'error', 'message': 'AI 未返回有效指令',
                            'data': None, 'steps': step + 1}

                # 3. 记录操作
                self.action_history.append({
                    'step': step + 1,
                    'action': action,
                    'url': page_info['url']
                })

                # 4. 检查是否完成
                action_type = action.get('type')

                if action_type == 'done':
                    msg = action.get('message', '任务完成')
                    data = action.get('data')
                    print(f"\n[OK] 任务完成: {msg}")
                    if data:
                        print(f"[OK] 提取数据: {json.dumps(data, ensure_ascii=False)[:500]}")
                    return {'status': 'success', 'message': msg,
                            'data': data, 'steps': step + 1}

                if action_type == 'failed':
                    msg = action.get('message', '任务失败')
                    print(f"\n[X] 任务失败: {msg}")
                    return {'status': 'failed', 'message': msg,
                            'data': None, 'steps': step + 1}

                # 5. 执行操作
                print("[3] 执行操作...")
                success = await self._execute_action(page, action,
                                                     page_info['elements'])
                if not success:
                    return {'status': 'error',
                            'message': f'步骤 {step + 1} 执行失败',
                            'data': None, 'steps': step + 1}

                # 6. 等待页面更新
                wait_time = action.get('wait', 2)
                await asyncio.sleep(wait_time)

            except Exception as e:
                print(f"[X] 步骤 {step + 1} 出错: {e}")
                return {'status': 'error', 'message': f'执行出错: {e}',
                        'data': None, 'steps': step + 1}

        return {'status': 'timeout', 'message': f'超过最大步骤数 {max_steps}',
                'data': None, 'steps': max_steps}

    # ------------------------------------------------------------------
    # 页面信息提取
    # ------------------------------------------------------------------

    async def _extract_page_info(self, page: Page) -> Dict[str, Any]:
        """提取当前页面的结构化信息"""
        url = page.url

        # 页面文本
        try:
            page_text = await page.locator('body').inner_text()
        except Exception:
            page_text = ''

        # 页面标题
        try:
            title = await page.title()
        except Exception:
            title = ''

        # 可交互元素
        elements = []
        selector = ('input, button, a[role="button"], select, textarea, '
                     'a[href], [role="tab"], [role="menuitem"], '
                     '[role="option"], [onclick]')

        try:
            locators = await page.locator(selector).all()

            for locator in locators:
                try:
                    if not await locator.is_visible():
                        continue

                    tag = await locator.evaluate('el => el.tagName.toLowerCase()')

                    # 获取显示文本
                    if tag == 'input':
                        text = ''
                    else:
                        try:
                            text = (await locator.inner_text()).strip()
                        except Exception:
                            text = ''

                    # 获取属性
                    attrs = {}
                    for attr in ['id', 'name', 'class', 'type', 'value',
                                 'placeholder', 'aria-label', 'title',
                                 'href', 'role']:
                        try:
                            val = await locator.get_attribute(attr)
                            if val:
                                # href 截断
                                if attr == 'href' and len(val) > 80:
                                    val = val[:80] + '...'
                                # class 截断
                                if attr == 'class' and len(val) > 60:
                                    val = val[:60] + '...'
                                attrs[attr] = val
                        except Exception:
                            continue

                    # 输入框当前值
                    if tag in ['input', 'textarea']:
                        try:
                            current_value = await locator.input_value()
                            if current_value:
                                # 隐藏已填入的敏感信息
                                if current_value in self.secrets.values():
                                    attrs['current_value'] = '[已填写敏感信息]'
                                else:
                                    attrs['current_value'] = current_value[:30]
                        except Exception:
                            pass

                    # select 当前选中值
                    if tag == 'select':
                        try:
                            selected = await locator.evaluate(
                                'el => el.options[el.selectedIndex]?.text')
                            if selected:
                                attrs['selected'] = selected
                        except Exception:
                            pass

                    elements.append({
                        'index': len(elements),
                        'tag': tag,
                        'text': text[:80],
                        'attributes': attrs
                    })

                    # 限制元素数量
                    if len(elements) >= 50:
                        break

                except Exception:
                    continue

        except Exception as e:
            print(f"    提取元素失败: {e}")

        return {
            'url': url,
            'title': title,
            'page_text': page_text[:3000],
            'elements': elements
        }

    # ------------------------------------------------------------------
    # AI 通信
    # ------------------------------------------------------------------

    def _init_system_prompt(self):
        """初始化系统提示词"""
        # 构建敏感信息说明
        secrets_text = ""
        if self.secret_labels:
            lines = []
            for placeholder, label in self.secret_labels.items():
                lines.append(f"- {label}: {placeholder}")
            secrets_text = (
                "\n**可用敏感信息（占位符，执行时自动替换为真实值）:**\n"
                + "\n".join(lines) + "\n"
            )

        system_prompt = f"""你是一个通用网页自动化 AI 助手。用户给你一个任务，你需要通过浏览器操作自主完成。

**用户任务:**
{self.task}
{secrets_text}
**你可以执行的操作（返回 JSON）：**

1. **fill** - 在输入框填写内容
   {{"type": "fill", "element": 0, "value": "要填写的文本", "reason": "原因"}}

2. **click** - 点击元素
   {{"type": "click", "element": 1, "reason": "原因"}}

3. **goto** - 导航到 URL
   {{"type": "goto", "url": "https://example.com", "reason": "原因"}}

4. **scroll** - 滚动页面
   {{"type": "scroll", "direction": "down", "reason": "原因"}}
   direction: "down" | "up"

5. **select** - 选择下拉框选项
   {{"type": "select", "element": 2, "value": "选项值", "reason": "原因"}}

6. **press_key** - 按键
   {{"type": "press_key", "key": "Enter", "reason": "原因"}}
   常用键: Enter, Tab, Escape, Backspace, ArrowDown, ArrowUp

7. **hover** - 悬停在元素上
   {{"type": "hover", "element": 3, "reason": "原因"}}

8. **wait** - 等待一段时间
   {{"type": "wait", "duration": 3, "reason": "原因"}}

9. **done** - 任务完成
   {{"type": "done", "message": "任务完成描述", "data": {{"key": "提取的数据"}}}}
   data 字段可选，用于返回从页面提取到的信息。

10. **failed** - 任务无法完成
    {{"type": "failed", "message": "失败原因"}}

**决策原则:**
1. 每次只返回一个 JSON 操作指令，不要包含其他文本
2. 仔细阅读页面文本和元素列表，理解当前页面状态
3. 参考操作历史，不要重复执行相同操作
4. 如果输入框已有内容（标记 [已填写] 或 [当前值]），不要重复填写
5. 填写敏感信息时，使用占位符（如 SECRET_XXXXXXXX），系统会自动替换
6. 合理判断任务是否已完成，及时返回 done
7. 如果页面出现无法克服的障碍，返回 failed
8. 如果需要搜索，优先使用搜索框 + Enter 键"""

        self.messages = [{"role": "system", "content": system_prompt}]

    def _build_user_message(self, page_info: Dict[str, Any],
                            step: int) -> str:
        """构建每一步发给 AI 的用户消息"""
        # 元素列表
        elements_lines = []
        for el in page_info['elements']:
            attrs_parts = []
            for k, v in el['attributes'].items():
                attrs_parts.append(f'{k}="{v}"')
            attrs_str = ' '.join(attrs_parts)
            text_str = f'"{el["text"]}"' if el['text'] else ''
            elements_lines.append(
                f"  [{el['index']}] <{el['tag']} {attrs_str}> {text_str}")

        elements_str = ('\n'.join(elements_lines)
                        if elements_lines else '(无可交互元素)')

        # 上一步操作摘要
        last_action_str = ""
        if self.action_history:
            last = self.action_history[-1]['action']
            lt = last.get('type')
            lr = last.get('reason', '')
            last_action_str = f"上一步操作: {lt} - {lr}"

        return f"""**步骤 {step + 1}**
{last_action_str}

当前 URL: {page_info['url']}
页面标题: {page_info['title']}

**页面文本:**
{page_info['page_text']}

**可交互元素:**
{elements_str}

请返回下一步操作的 JSON 指令。"""

    async def _ask_ai(self, page_info: Dict[str, Any],
                      step: int) -> Optional[Dict[str, Any]]:
        """询问 AI 下一步操作"""
        user_msg = self._build_user_message(page_info, step)
        self.messages.append({"role": "user", "content": user_msg})

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = await self._call_api(timeout=30.0)
                content = response['choices'][0]['message']['content'].strip()
                print(f"    AI 回复: {content[:200]}...")

                # 记录 AI 回复到对话历史
                self.messages.append({"role": "assistant", "content": content})

                action = self._parse_action(content)
                if action:
                    return action

                # 解析失败时从对话中移除本次回复，让 AI 重试
                self.messages.pop()

            except Exception as e:
                print(f"    API 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)

        # 全部失败，也移除用户消息
        self.messages.pop()
        return None

    async def _call_api(self, timeout: float = 30.0) -> Dict[str, Any]:
        """调用 LLM API"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 控制对话历史长度，防止 token 超限
        # 保留 system + 最近 10 轮
        trimmed = [self.messages[0]]  # system
        trimmed.extend(self.messages[-20:] if len(self.messages) > 21
                       else self.messages[1:])

        payload = {
            "model": "deepseek-chat",
            "messages": trimmed,
            "max_tokens": 800,
            "temperature": 0.3
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
            return resp.json()

    def _parse_action(self, content: str) -> Optional[Dict[str, Any]]:
        """解析 AI 返回的 JSON 指令"""
        try:
            # 移除 markdown 代码块
            text = content
            if '```json' in text:
                text = text.split('```json')[1].split('```')[0].strip()
            elif '```' in text:
                text = text.split('```')[1].split('```')[0].strip()

            action = json.loads(text)

            if 'type' not in action:
                print("    解析失败: 缺少 type 字段")
                return None

            valid_types = {'fill', 'click', 'goto', 'scroll', 'select',
                           'press_key', 'hover', 'wait', 'done', 'failed'}
            if action['type'] not in valid_types:
                print(f"    警告: 未知操作类型 {action['type']}")

            return action

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"    解析 AI 响应失败: {e}")
            return None

    # ------------------------------------------------------------------
    # 操作执行
    # ------------------------------------------------------------------

    async def _execute_action(self, page: Page, action: Dict[str, Any],
                              elements: List[Dict[str, Any]]) -> bool:
        """执行 AI 返回的操作"""
        action_type = action.get('type')
        reason = action.get('reason', '')
        print(f"    类型: {action_type}")
        print(f"    原因: {reason}")

        try:
            if action_type == 'fill':
                return await self._do_fill(page, action)

            elif action_type == 'click':
                return await self._do_click(page, action)

            elif action_type == 'goto':
                url = action.get('url', '')
                if not url:
                    print("    错误: goto 缺少 url")
                    return False
                print(f"    导航到: {url}")
                await page.goto(url, wait_until='domcontentloaded',
                                timeout=30000)
                return True

            elif action_type == 'scroll':
                direction = action.get('direction', 'down')
                delta = -500 if direction == 'up' else 500
                print(f"    滚动: {direction}")
                await page.mouse.wheel(0, delta)
                return True

            elif action_type == 'select':
                return await self._do_select(page, action)

            elif action_type == 'press_key':
                key = action.get('key', 'Enter')
                print(f"    按键: {key}")
                await page.keyboard.press(key)
                return True

            elif action_type == 'hover':
                return await self._do_hover(page, action)

            elif action_type == 'wait':
                duration = action.get('duration', 2)
                print(f"    等待: {duration} 秒")
                await asyncio.sleep(duration)
                return True

            elif action_type in ('done', 'failed'):
                return True

            else:
                print(f"    错误: 不支持的操作类型 {action_type}")
                return False

        except Exception as e:
            print(f"    执行失败: {e}")
            return False

    async def _get_target_locator(self, page: Page,
                                  element_index: int):
        """根据索引获取目标元素的 locator"""
        selector = ('input, button, a[role="button"], select, textarea, '
                     'a[href], [role="tab"], [role="menuitem"], '
                     '[role="option"], [onclick]')
        locators = await page.locator(selector).all()

        visible = []
        for loc in locators:
            if await loc.is_visible():
                visible.append(loc)
            if len(visible) > element_index:
                break  # 已找到足够多的可见元素

        if element_index >= len(visible):
            print(f"    错误: 元素索引 {element_index} 超出范围 "
                  f"(共 {len(visible)} 个可见元素)")
            return None

        return visible[element_index]

    async def _do_fill(self, page: Page, action: Dict[str, Any]) -> bool:
        element_index = action.get('element')
        value = action.get('value', '')

        if element_index is None:
            print("    错误: fill 缺少 element")
            return False

        target = await self._get_target_locator(page, element_index)
        if not target:
            return False

        # 替换敏感信息占位符
        actual_value = value
        if value in self.secrets:
            actual_value = self.secrets[value]
            label = self.secret_labels.get(value, '敏感信息')
            print(f"    填写: [{label}] 到元素 [{element_index}]")
        else:
            print(f"    填写: {value} 到元素 [{element_index}]")

        await target.fill(actual_value)
        return True

    async def _do_click(self, page: Page, action: Dict[str, Any]) -> bool:
        element_index = action.get('element')
        if element_index is None:
            print("    错误: click 缺少 element")
            return False

        target = await self._get_target_locator(page, element_index)
        if not target:
            return False

        print(f"    点击: 元素 [{element_index}]")
        await target.click()
        return True

    async def _do_select(self, page: Page, action: Dict[str, Any]) -> bool:
        element_index = action.get('element')
        value = action.get('value', '')

        if element_index is None:
            print("    错误: select 缺少 element")
            return False

        target = await self._get_target_locator(page, element_index)
        if not target:
            return False

        print(f"    选择: {value} 在元素 [{element_index}]")
        await target.select_option(label=value)
        return True

    async def _do_hover(self, page: Page, action: Dict[str, Any]) -> bool:
        element_index = action.get('element')
        if element_index is None:
            print("    错误: hover 缺少 element")
            return False

        target = await self._get_target_locator(page, element_index)
        if not target:
            return False

        print(f"    悬停: 元素 [{element_index}]")
        await target.hover()
        return True


# ==================================================================
# CLI 入口
# ==================================================================

def parse_secrets(secret_args: Optional[List[str]]) -> Dict[str, str]:
    """解析 --secret 参数，格式: 描述=值"""
    secrets = {}
    if not secret_args:
        return secrets
    for s in secret_args:
        if '=' not in s:
            print(f"[!] 忽略无效 secret 格式（应为 描述=值）: {s}")
            continue
        label, value = s.split('=', 1)
        secrets[label.strip()] = value.strip()
    return secrets


def parse_args():
    parser = argparse.ArgumentParser(
        description='通用网页自动化智能体 - 用自然语言驱动浏览器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''\
示例:
    python web_agent.py "去百度搜索Python教程，告诉我前3条结果"
    python web_agent.py "查看GitHub trending" --start-url https://github.com/trending
    python web_agent.py "登录我的邮箱" --secret "邮箱=user@example.com" --secret "密码=pass123"
    python web_agent.py "搜索AI新闻" --headless --max-steps 20

环境变量:
    MODELS_DEEPSEEK_API_KEY: LLM API 密钥（必需）
    MODELS_DEEPSEEK_API_BASE: API 基础 URL（可选，默认 https://api.deepseek.com）
        ''')

    parser.add_argument('task', help='自然语言任务描述')
    parser.add_argument('--start-url', default=None, help='起始 URL')
    parser.add_argument('--secret', action='append', dest='secrets',
                        help='敏感信息，格式: 描述=值（可多次使用）')
    parser.add_argument('--headless', action='store_true', help='无头模式')
    parser.add_argument('--proxy', default=None, help='代理服务器地址')
    parser.add_argument('--max-steps', type=int, default=15,
                        help='最大步骤数（默认 15）')

    return parser.parse_args()


async def main_async():
    from dotenv import load_dotenv
    load_dotenv()

    args = parse_args()

    api_key = os.getenv("MODELS_DEEPSEEK_API_KEY")
    api_base = os.getenv("MODELS_DEEPSEEK_API_BASE", "https://api.deepseek.com")

    if not api_key:
        print("[-] 错误: MODELS_DEEPSEEK_API_KEY 环境变量未设置")
        print("[*] 请在 .env 文件中设置 API 密钥")
        sys.exit(1)

    # 解析敏感信息
    secrets = parse_secrets(args.secrets)

    print("=" * 60)
    print("    通用网页自动化智能体 (Web Agent)")
    print("=" * 60)
    print(f"[*] 任务: {args.task}")
    if args.start_url:
        print(f"[*] 起始 URL: {args.start_url}")
    print(f"[*] 最大步骤数: {args.max_steps}")
    print(f"[*] 运行模式: {'无头' if args.headless else '有头'}")
    if args.proxy:
        print(f"[*] 代理: {args.proxy}")
    if secrets:
        print(f"[*] 敏感信息: {', '.join(secrets.keys())}")
    print("-" * 60)

    # 创建浏览器
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=args.headless)

        context_opts = {}
        if args.proxy:
            context_opts['proxy'] = {"server": args.proxy}

        context = await browser.new_context(**context_opts)
        page = await context.new_page()

        # 创建智能体并执行
        agent = WebAgent(api_key, api_base, args.task, secrets)
        result = await agent.run(page, start_url=args.start_url,
                                 max_steps=args.max_steps)

        await browser.close()

    # 输出结果
    print("\n" + "=" * 60)
    print(f"[结果] 状态: {result['status']}")
    print(f"[结果] 信息: {result['message']}")
    print(f"[结果] 步骤数: {result['steps']}")
    if result.get('data'):
        print(f"[结果] 数据:")
        print(json.dumps(result['data'], ensure_ascii=False, indent=2))
    print("=" * 60)


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[!] 用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n[-] 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
