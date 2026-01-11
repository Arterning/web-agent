from playwright.sync_api import sync_playwright
import time

def click_and_input():
    """
    """
    # 启动 Playwright 上下文
    with sync_playwright() as p:
        # 启动 Chrome 浏览器（headless=False 显示浏览器窗口，True 为无头模式）
        browser = p.chromium.launch(headless=False, slow_mo=500)  # slow_mo 放慢操作速度，便于观察
        # 创建新页面
        page = browser.new_page()
        
        try:
            page.goto("http://172.16.1.16:5173/login?")
            
            # 2. 定位搜索框并输入 "bilibili"
            # 谷歌搜索框的定位器（name="q" 是最稳定的定位方式）
            # search_box = page.locator('input[name="q"]')
            username = page.locator('input').first
            username.fill("admin")

            page.locator('input[type="password"]').fill('beida@1234%')

            
            page.locator('text=登录').click()

            
            page.wait_for_load_state("networkidle")
            print("成功打开网站！")
            


            page.locator('text=智能助手').click()
            page.wait_for_load_state("networkidle")


            page.locator('textarea').first.fill("什么是DeepParseX？")
            page.locator('textarea').first.press("Enter")


            time.sleep(5000)
            
        except Exception as e:
            print(f"执行过程中出现错误: {e}")
        finally:
            # 关闭浏览器
            # browser.close()
            pass

if __name__ == "__main__":
    click_and_input()