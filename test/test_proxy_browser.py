#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用 Playwright 浏览器测试代理
访问 Google 并检查出口 IP，验证代理是否正常工作。
"""

import asyncio
from urllib.parse import urlparse
from playwright.async_api import async_playwright

# ── 在此填写要测试的代理 ────────────────────────────────────────
PROXY = "socks5://@127.0.0.1:7890"
# ──────────────────────────────────────────────────────────────

HEADLESS = False          # False = 显示浏览器窗口，方便观察
TIMEOUT   = 30_000        # 页面加载超时（毫秒）


def _parse_proxy(proxy_str: str) -> dict:
    """将代理字符串解析为 Playwright proxy 参数字典。"""
    parsed = urlparse(proxy_str)
    server = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    config: dict = {"server": server}
    if parsed.username:
        config["username"] = parsed.username
    if parsed.password:
        config["password"] = parsed.password
    return config


async def main():
    proxy_config = _parse_proxy(PROXY)
    print(f"代理配置: {proxy_config}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(proxy=proxy_config)
        page = await context.new_page()

        # ── 1. 检查出口 IP ────────────────────────────────────
        print("\n[1/2] 检查出口 IP...")
        try:
            await page.goto("https://api.ipify.org?format=json", timeout=TIMEOUT)
            ip_text = await page.inner_text("body")
            print(f"  出口 IP 信息: {ip_text.strip()}")
        except Exception as e:
            print(f"  ⚠ 获取 IP 失败: {e}")

        # ── 2. 访问 Google ────────────────────────────────────
        print("\n[2/2] 访问 Google...")
        try:
            response = await page.goto("https://www.google.com", timeout=TIMEOUT)
            title = await page.title()
            status = response.status if response else "?"
            print(f"  状态码 : {status}")
            print(f"  页面标题: {title}")
            print(f"  当前 URL: {page.url}")
            print("\n✅ 代理测试通过")
        except Exception as e:
            print(f"\n❌ 访问 Google 失败: {e}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
