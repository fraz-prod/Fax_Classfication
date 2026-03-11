"""
pages/base_page.py
==================
Base Page class for ECW RPA — adapted from rishav_files/base_page.py

Changes from original:
  - Replaced clinicalops_rpa_base.logger with standard logging
  - Replaced ..constants import with top-level constants module
  - Kept all robust click/type/wait methods exactly as authored
"""

import logging
import time
import os
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from typing import Optional

from constants import Timeouts

log = logging.getLogger(__name__)


class BasePage:
    """Base class for all page objects with Playwright functionality"""

    def __init__(self, page: Page,
                 wait_timeout: int = Timeouts.DEFAULT_WAIT,
                 browser_type: str = "camoufox"):
        self.page = page
        self.wait_timeout = wait_timeout
        self.browser_type = browser_type

    # ── Element helpers ───────────────────────────────────────────────────

    def wait_for_element(self, selector: str,
                         timeout: Optional[int] = None,
                         state: str = "attached"):
        timeout_ms = self.wait_timeout * 1000 if timeout is None else timeout * 1000
        locator = self.page.locator(selector)
        locator.wait_for(state=state, timeout=timeout_ms)
        return locator

    def click_element(self, selector: str,
                      scroll_first: bool = True,
                      wait_after: float = 0.5) -> bool:
        """
        Click an element. Falls back to JavaScript click if Playwright click fails.
        Returns True on success, False on failure.
        """
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=self.wait_timeout * 1000)

            if scroll_first:
                locator.scroll_into_view_if_needed()
                time.sleep(0.3)

            try:
                locator.click(timeout=self.wait_timeout * 1000)
                time.sleep(wait_after)
                return True
            except Exception as e1:
                log.warning(f"Regular click failed: {e1}. Trying JavaScript click...")
                try:
                    self.page.evaluate(f"document.querySelector('{selector}').click()")
                    time.sleep(wait_after)
                    return True
                except Exception as e2:
                    log.warning(f"JavaScript click also failed: {e2}")
                    return False

        except PlaywrightTimeoutError as e:
            log.warning(f"Element not found for clicking: {selector}. Error: {e}")
            return False
        except Exception as e:
            log.error(f"Error clicking element: {selector}. Error: {e}")
            return False

    def type_text(self, selector: str, text: str,
                  clear_first: bool = True,
                  wait_after: float = 0.5) -> bool:
        """Fill a text field. Clears existing content first by default."""
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="visible", timeout=self.wait_timeout * 1000)

            if clear_first:
                try:
                    locator.clear(timeout=5000)
                except Exception:
                    pass

            locator.fill(text, timeout=10000)
            time.sleep(wait_after)
            return True
        except PlaywrightTimeoutError as e:
            log.warning(f"Playwright fill failed (possibly disabled or hidden). Trying JS fallback. Error: {e}")
            try:
                self.page.evaluate(f"""
                    const el = document.querySelector('{selector}');
                    if (el) {{
                        el.value = '{text}';
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                """)
                time.sleep(wait_after)
                return True
            except Exception as js_e:
                log.error(f"JS fallback typing also failed: {js_e}")
                return False
        except Exception as e:
            log.error(f"Error typing text into: {selector}. Error: {e}")
            return False

    def scroll_into_view(self, selector: str):
        locator = self.page.locator(selector)
        locator.scroll_into_view_if_needed()

    def wait_for_invisibility(self, selector: str,
                              timeout: Optional[int] = None,
                              raise_on_timeout: bool = False) -> bool:
        timeout_ms = (timeout or self.wait_timeout) * 1000
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="hidden", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            if raise_on_timeout:
                raise
            return False

    def is_element_present(self, selector: str) -> bool:
        try:
            return self.page.locator(selector).count() > 0
        except Exception:
            return False

    def get_element_text(self, selector: str) -> Optional[str]:
        try:
            locator = self.page.locator(selector)
            locator.wait_for(state="attached", timeout=self.wait_timeout * 1000)
            return locator.text_content()
        except PlaywrightTimeoutError:
            return None

    def navigate_to(self, url: str):
        log.info(f"Navigating to: {url}")
        self.page.goto(url, wait_until="domcontentloaded")
        time.sleep(3)

    # ── Screenshot ────────────────────────────────────────────────────────

    def get_screenshot_path(self, filename: str) -> str:
        screenshot_dir = "/app/screenshots" if os.path.exists("/.dockerenv") else "screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        return os.path.join(screenshot_dir, filename)

    # ── Error detection ───────────────────────────────────────────────────

    def _is_connection_error(self, error: Exception) -> bool:
        error_str = str(error).lower()
        indicators = [
            "target closed", "connection closed", "session closed",
            "browser closed", "web view not found", "no such window"
        ]
        return any(ind in error_str for ind in indicators)

    # ── License Alert modal (ECW-specific) ────────────────────────────────

    def handle_license_alert_modal(self):
        """
        ECW sometimes shows a 'License Alert' modal after login.
        This method detects it and clicks the close button.
        Polls up to 20 times (every 500 ms = 10 s max).
        """
        try:
            log.debug("Checking for License Alert modal (waiting 4 s)...")
            time.sleep(4)

            modal_found = False
            for attempt in range(20):
                result = self.page.evaluate("""
                    (() => {
                        const modals = document.querySelectorAll('div.modal-dialog');
                        for (const modal of modals) {
                            const title = modal.querySelector('h4.modal-title');
                            if (title && title.textContent.trim() === 'License Alert') {
                                const closeBtn = modal.querySelector('button.close[data-dismiss="modal"]');
                                if (closeBtn && closeBtn.offsetParent !== null) {
                                    return { found: true, visible: true };
                                }
                            }
                        }
                        return { found: false, visible: false };
                    })();
                """)

                if result and result.get("found") and result.get("visible"):
                    modal_found = True
                    log.info("License Alert modal detected — clicking close...")
                    click_result = self.page.evaluate("""
                        (() => {
                            const modals = document.querySelectorAll('div.modal-dialog');
                            for (const modal of modals) {
                                const title = modal.querySelector('h4.modal-title');
                                if (title && title.textContent.trim() === 'License Alert') {
                                    const closeBtn = modal.querySelector('button.close[data-dismiss="modal"]');
                                    if (closeBtn) { closeBtn.click(); return true; }
                                }
                            }
                            return false;
                        })();
                    """)
                    if click_result:
                        log.info("License Alert modal closed.")
                    else:
                        log.warning("Modal found but close click failed.")
                    return

                self.page.wait_for_timeout(500)

            if not modal_found:
                log.debug("No License Alert modal — continuing.")

        except Exception as e:
            log.warning(f"handle_license_alert_modal error: {e}")
