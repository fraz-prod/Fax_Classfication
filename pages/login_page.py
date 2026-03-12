"""
pages/login_page.py
===================
Login Page Object for ECW RPA.

Ported from rishav_files/login_page.py (the confirmed-working version).
Only changes vs original:
  - Replaced clinicalops_rpa_base.logger / redact_credentials with standard logging + local _mask()
  - Fixed imports to use local pages.base_page and top-level constants module
  - All login/Turnstile logic preserved exactly as in rishav_files.

Flow:
  enter_username() -> Next
  enter_password() -> 6s sleep -> _click_verification_overlay() -> wait for Login btn -> click Login bbox
"""

import logging
import time
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from pages.base_page import BasePage
from constants import LoginPageSelectors, NavigationPageSelectors, Timeouts

log = logging.getLogger(__name__)


def _mask(value: str) -> str:
    """Simple credential masking for safe logging (shows first 2 chars + asterisks)."""
    if not value:
        return "***"
    return value[:2] + "*" * max(len(value) - 2, 3)


class LoginPage(BasePage):
    """Page object for ECW login page - Playwright version"""

    def enter_username(self, username: str) -> bool:
        try:
            log.info("=== Step 1: Entering username ===")
            log.info(f"Entering username: {_mask(username)}")

            username_selector = f"#{LoginPageSelectors.USERNAME_FIELD}"
            if not self.type_text(username_selector, username):
                return False

            log.info("Clicking Next button...")
            next_selector = f"#{LoginPageSelectors.NEXT_BUTTON}"
            if not self.click_element(next_selector):
                return False

            log.info("Next button clicked. Waiting for password page to load...")
            return True

        except Exception as e:
            log.error(f"ERROR in enter_username: {e}")
            return False

    def enter_password(self, password: str) -> bool:
        try:
            log.info("=== Step 2: Entering password ===")
            log.info("Waiting for password field...")

            password_selector = f"#{LoginPageSelectors.PASSWORD_FIELD}"
            self.wait_for_element(password_selector, state="visible")

            log.info("Entering password...")
            if not self.type_text(password_selector, password):
                return False

            log.info("Waiting 40 seconds before clicking verification checkbox...")
            time.sleep(60)

            log.info("Clicking verification checkbox...")
            self._click_verification_overlay()

            log.info("Waiting 2 seconds for verification to process...")
            time.sleep(2)

            log.info("Waiting for Log In button to become enabled...")
            login_selector = f"#{LoginPageSelectors.LOGIN_BUTTON}"
            try:
                login_locator = self.page.locator(login_selector)
                # INCREASED TO 60 SECONDS
                login_locator.wait_for(state="visible", timeout=60000)

                self.page.wait_for_function(
                    f"""() => {{
                        const btn = document.querySelector('{login_selector}');
                        return btn && !btn.disabled && btn.offsetParent !== null;
                    }}""",
                    # INCREASED TO 60 SECONDS
                    timeout=60000
                )
                log.info("Log In button is now enabled")
            except PlaywrightTimeoutError:
                log.warning("Login button did not become enabled within timeout, but will try to click anyway")

            try:
                login_locator = self.page.locator(login_selector)
                login_locator.wait_for(state="attached", timeout=5000)
            except Exception:
                pass

            log.info("Clicking Log In button...")

            # Strategy 1: scroll into view then click bounding box center (no offset)
            clicked = False
            try:
                login_locator = self.page.locator(login_selector)
                login_locator.wait_for(state="visible", timeout=self.wait_timeout * 1000)
                login_locator.scroll_into_view_if_needed()
                time.sleep(0.3)

                bbox = login_locator.bounding_box()
                if bbox:
                    click_x = bbox['x'] + (bbox['width'] / 2)
                    click_y = bbox['y'] + (bbox['height'] / 2)
                    log.info(f"Clicking Log In button at ({click_x:.0f}, {click_y:.0f})")
                    self.page.mouse.click(click_x, click_y)
                    time.sleep(0.5)
                    clicked = True
            except Exception as e:
                log.warning(f"Strategy 1 (bbox click) failed: {e}")

            # Strategy 2: Playwright locator.click()
            if not clicked:
                try:
                    login_locator = self.page.locator(login_selector)
                    login_locator.scroll_into_view_if_needed()
                    login_locator.click(timeout=5000)
                    time.sleep(0.5)
                    clicked = True
                    log.info("Log In button clicked via locator.click().")
                except Exception as e:
                    log.warning(f"Strategy 2 (locator.click) failed: {e}")

            # Strategy 3: JavaScript click
            if not clicked:
                try:
                    self.page.evaluate(f"document.querySelector('{login_selector}').click()")
                    time.sleep(0.5)
                    clicked = True
                    log.info("Log In button clicked via JS.")
                except Exception as e:
                    log.error(f"Strategy 3 (JS click) failed: {e}")
                    return False

            log.info("Log In button clicked. Waiting for login to complete...")
            self.handle_license_alert_modal()
            return True

        except Exception as e:
            log.error(f"ERROR in enter_password: {e}")
            return False

    def _click_verification_overlay(self):
        """
        Click the Cloudflare Turnstile checkbox.

        Uses the password field's bounding box as the anchor point and applies
        fixed pixel offsets to land on the Turnstile checkbox. These offsets are
        calibrated for each browser type (camoufox vs other).

        Camoufox offsets (x+40, y+105) confirmed working in rishav_files.
        """
        try:
            password_selector = f"#{LoginPageSelectors.PASSWORD_FIELD}"
            password_locator = self.page.locator(password_selector)
            password_locator.wait_for(state="visible", timeout=10000)

            bbox = password_locator.bounding_box()
            if not bbox:
                log.warning("Could not get password field bounding box")
                return

            log.debug(f"Password field bounding box: {bbox}")
            log.debug(f"Browser type: {self.browser_type}")

            if self.browser_type == "camoufox":
                x_offset = 20
                y_offset = 105
                log.debug("Using Camoufox coordinates for verification checkbox")
            else:
                x_offset = 20
                y_offset = 105
                log.debug("Using Selenium/Playwright coordinates for verification checkbox")

            abs_x = bbox['x'] + x_offset
            abs_y = bbox['y'] + y_offset

            log.info(f"Clicking Turnstile at absolute position ({abs_x:.0f}, {abs_y:.0f})")

            # Place a visible debug marker before clicking (helpful for debugging)
            marker_script = f"""
                var marker = document.createElement('div');
                marker.style.position = 'fixed';
                marker.style.left = '{abs_x}px';
                marker.style.top = '{abs_y}px';
                marker.style.width = '20px';
                marker.style.height = '20px';
                marker.style.borderRadius = '50%';
                marker.style.backgroundColor = 'red';
                marker.style.border = '2px solid yellow';
                marker.style.zIndex = '999999';
                marker.style.color = 'white';
                marker.style.fontSize = '12px';
                marker.style.fontWeight = 'bold';
                marker.style.display = 'flex';
                marker.style.alignItems = 'center';
                marker.style.justifyContent = 'center';
                marker.innerText = '1';
                document.body.appendChild(marker);
            """
            self.page.evaluate(marker_script)
            log.debug(f"Added click marker at ({abs_x}, {abs_y})")

            self.page.wait_for_timeout(500)

            self.page.mouse.click(abs_x, abs_y)

            login_selector = f"#{LoginPageSelectors.LOGIN_BUTTON}"
            try:
                login_locator = self.page.locator(login_selector)
                login_locator.wait_for(state="visible", timeout=10000)
            except PlaywrightTimeoutError:
                pass

        except Exception as e:
            log.warning(f"Verification overlay strategy failed: {e}")

    def verify_login_success(self) -> bool:
        try:
            log.info("Verifying login success...")
            # Wait for the confirmed D jellybean nav button — proves dashboard loaded
            verification_selector = "a#jellybean-panelLink29"
            if self.wait_for_element(verification_selector, timeout=0, state="attached"):
                log.info("Login verified: Dashboard loaded (jellybean D button found).")
                return True
            return False
        except Exception as e:
            log.warning(f"Login verification failed: {e}")
            return False

    def login(self, username: str, password: str) -> bool:
        """
        Full login flow: username -> Next -> password -> Turnstile checkbox -> Log In.
        Returns True if login succeeded, False otherwise.
        """
        log.info("Starting ECW login flow...")

        if not self.enter_username(username):
            log.error("Login failed at username step.")
            return False

        if not self.enter_password(password):
            log.error("Login failed at password step.")
            return False

        if not self.verify_login_success():
            log.error("Login failed — dashboard not loaded after login.")
            return False

        log.info("Login successful.")
        return True
