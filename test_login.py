import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

from pages.browser_manager import BrowserManager
from pages.login_page import LoginPage
from constants import Timeouts
import config

def main():
    bm = BrowserManager(headless=False)
    page = bm.start_driver()

    bm.navigate_and_wait_for_login(config.ECW_URL)

    lp = LoginPage(page, wait_timeout=Timeouts.LOGIN, browser_type="camoufox")
    success = lp.login(config.ECW_USERNAME, config.ECW_PASSWORD)

    print("LOGIN SUCCESS:" if success else "LOGIN FAILED — check logs above")
    page.screenshot(path="login_debug.png", full_page=True)
    
    input("Press Enter to close browser...")
    bm.quit_driver()

if __name__ == "__main__":
    main()
