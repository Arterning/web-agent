from playwright.sync_api import sync_playwright
import time

def search_bilibili_on_google():
    """
    使用 Playwright 打开谷歌搜索，搜索bilibili并打开第一个搜索结果
    """
    # 启动 Playwright 上下文
    with sync_playwright() as p:
        # 启动 Chrome 浏览器（headless=False 显示浏览器窗口，True 为无头模式）
        browser = p.chromium.launch(headless=False, slow_mo=500)  # slow_mo 放慢操作速度，便于观察
        # 创建新页面
        page = browser.new_page()
        
        try:
            # 1. 导航到谷歌搜索主页
            page.goto("https://www.google.com")
            
            # 2. 定位搜索框并输入 "bilibili"
            # 谷歌搜索框的定位器（name="q" 是最稳定的定位方式）
            # search_box = page.locator('input[name="q"]')
            search_box = page.locator('textarea').first

            search_box.fill("bilibili")
            
            # 3. 按下回车键提交搜索
            search_box.press("Enter")
            
            # 4. 等待搜索结果加载完成，并定位第一个bilibili相关链接
            # 定位第一个包含bilibili.com的链接（更精准匹配目标网站）
            bilibili_link = page.locator('a[href*="bilibili.com"]').first
            # 等待链接可点击，避免加载未完成导致点击失败
            bilibili_link.wait_for(state="visible")
            
            # 5. 点击链接打开bilibili网站
            bilibili_link.click()
            
            # 等待页面加载完成，停留5秒便于观察结果
            page.wait_for_load_state("networkidle")
            print("成功打开bilibili网站！")
            time.sleep(5)
            
        except Exception as e:
            print(f"执行过程中出现错误: {e}")
        finally:
            # 关闭浏览器
            browser.close()

if __name__ == "__main__":
    search_bilibili_on_google()