"""
ecw_bot.py
==========
ECW Browser Automation — High-level orchestrator.

Uses the Page Object Model (pages/ package):
  - BrowserManager  : launches Camoufox stealth browser (or Playwright fallback)
  - LoginPage       : handles two-step ECW login + verification checkbox
  - BasePage        : used by fax-inbox operations for robust click/wait helpers

Flow:
  launch() -> login() -> open_fax_inbox() -> select_date()
  -> get_fax_list() -> [for each fax] download_fax_pdf() -> send_fax_to_staff_group()
  -> close()
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from urllib.parse import urlparse

import httpx

from pages.browser_manager import BrowserManager
from pages.login_page import LoginPage
from pages.base_page import BasePage
from constants import NavigationPageSelectors, StaffDialogSelectors, Timeouts
import config

log = logging.getLogger(__name__)


class ECWBot:
    """
    High-level ECW browser automation bot.

    Coordinates BrowserManager + LoginPage + BasePage to drive
    ECW's fax inbox: log in, iterate faxes, download PDFs, and
    route them to staff groups.
    """

    def __init__(self):
        self.browser_manager = BrowserManager(
            headless=False,       # Set True once fully tested
            wait_timeout=Timeouts.DEFAULT_WAIT
        )
        self.page = None
        self.base = None          # BasePage helper for fax-inbox actions
        self.screenshot_dir = "screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs("logs", exist_ok=True)

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def launch(self):
        """Start the browser (sync call wrapped for async main)."""
        log.info("Launching browser via BrowserManager...")
        loop = asyncio.get_event_loop()
        self.page = await loop.run_in_executor(None, self.browser_manager.start_driver)
        self.base = BasePage(
            self.page,
            wait_timeout=Timeouts.DEFAULT_WAIT,
            browser_type="camoufox"
        )
        log.info("Browser launched.")

    async def login(self):
        """Navigate to ECW and perform two-step login."""
        log.info("Navigating to ECW and logging in...")
        loop = asyncio.get_event_loop()

        # Navigate to ECW URL
        await loop.run_in_executor(
            None,
            self.browser_manager.navigate_and_wait_for_login,
            config.ECW_URL
        )

        # Two-step login via LoginPage
        login_page = LoginPage(
            self.page,
            wait_timeout=Timeouts.LOGIN,
            browser_type="camoufox"
        )
        success = await loop.run_in_executor(
            None,
            login_page.login,
            config.ECW_USERNAME,
            config.ECW_PASSWORD
        )
        if not success:
            raise RuntimeError("ECW login failed — check credentials and selectors.")

        log.info("Logged in to ECW.")

    async def close(self):
        """Close the browser cleanly."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.browser_manager.quit_driver)
        log.info("Browser closed.")

    # ── Fax Inbox Navigation ───────────────────────────────────────────────

    async def open_fax_inbox(self):
        """Click the jellybean button and select 'Fax Inbox - Web Mode'."""
        loop = asyncio.get_event_loop()

        log.info("Waiting 15 seconds for dashboard to fully load before clicking jellybean...")
        await asyncio.sleep(15)

        log.info("Clicking jellybean button via JavaScript to ensure event listener fires...")
        await loop.run_in_executor(
            None,
            self.page.evaluate,
            f"document.querySelector('{NavigationPageSelectors.JELLYBEAN_BUTTON}').dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true, view: window}}))"
        )
        await asyncio.sleep(2)

        await loop.run_in_executor(
            None,
            self.base.click_element,
            NavigationPageSelectors.FAX_INBOX_ITEM
        )
        await asyncio.sleep(2)
        log.info("Fax Inbox Web Mode opened.")

    async def select_date(self, date: datetime):
        """Fill the date picker with today's date."""
        date_str = date.strftime(config.ECW_DATE_FORMAT)
        loop = asyncio.get_event_loop()

        await loop.run_in_executor(
            None,
            self.base.type_text,
            NavigationPageSelectors.DATE_INPUT,
            date_str
        )
        await asyncio.sleep(0.5)
        self.page.keyboard.press("Enter")
        await asyncio.sleep(2)
        log.info(f"Date selected: {date_str}")

    async def get_fax_list(self) -> list:
        """Return all fax row elements from the inbox table."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self.base.wait_for_element,
            NavigationPageSelectors.FAX_ROW,
            Timeouts.FAX_INBOX,
            "attached"
        )
        fax_rows = self.page.locator(NavigationPageSelectors.FAX_ROW).all()
        log.info(f"Found {len(fax_rows)} fax rows.")
        return fax_rows

    # ── PDF Download ───────────────────────────────────────────────────────

    async def download_fax_pdf(self, fax_element) -> bytes:
        """
        Click a fax row, wait for the PDF preview iframe to load,
        extract the iframe src URL, and download the PDF bytes using
        the browser's session cookies (authenticated, HIPAA-safe).

        Returns raw PDF bytes, or b"" on failure.
        """
        try:
            # Step 1: Click the fax row
            await asyncio.get_event_loop().run_in_executor(
                None, fax_element.click
            )
            await asyncio.sleep(2)
            self.page.wait_for_load_state("networkidle", timeout=15000)
            log.info("  Fax row clicked — waiting for PDF preview iframe...")

            # Step 2: Wait for iframe to appear
            try:
                self.page.wait_for_selector(
                    NavigationPageSelectors.FAX_PREVIEW,
                    timeout=Timeouts.PDF_PREVIEW * 1000
                )
            except Exception:
                log.warning(
                    f"  PDF preview iframe not found. "
                    f"Check FAX_PREVIEW selector: "
                    f"'{NavigationPageSelectors.FAX_PREVIEW}'"
                )
                return b""

            # Step 3: Read iframe src
            pdf_url = self.page.eval_on_selector(
                NavigationPageSelectors.FAX_PREVIEW,
                "el => el.src || el.getAttribute('src') || ''"
            )
            if not pdf_url or pdf_url.strip() in ("", "about:blank"):
                pdf_url = self.page.eval_on_selector(
                    NavigationPageSelectors.FAX_PREVIEW,
                    "el => el.getAttribute('data-src') || ''"
                )

            if not pdf_url or pdf_url.strip() in ("", "about:blank"):
                log.error(
                    "  PDF iframe src is empty. ECW may load PDF lazily — "
                    "try adding a longer sleep or update FAX_PREVIEW selector."
                )
                return b""

            # Step 4: Make absolute URL if needed
            if pdf_url.startswith("/"):
                parsed = urlparse(config.ECW_URL)
                pdf_url = f"{parsed.scheme}://{parsed.netloc}{pdf_url}"

            log.info(f"  PDF URL: {pdf_url[:80]}...")

            # Step 5: Copy session cookies
            cookies = self.page.context.cookies()
            cookie_header = "; ".join(
                f"{c['name']}={c['value']}" for c in cookies
            )

            # Step 6: Download PDF via httpx
            async with httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
                verify=False   # ECW often has self-signed SSL certs
            ) as client:
                response = await client.get(
                    pdf_url,
                    headers={
                        "Cookie": cookie_header,
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                        ),
                        "Referer": self.page.url,
                    }
                )

            if response.status_code != 200:
                log.error(f"  PDF download failed: HTTP {response.status_code}")
                return b""

            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and len(response.content) < 100:
                log.warning(
                    f"  Response may not be a PDF "
                    f"(Content-Type: {content_type}, "
                    f"size: {len(response.content)} bytes)"
                )

            log.info(f"  PDF downloaded: {len(response.content):,} bytes")
            return response.content

        except Exception as e:
            log.error(f"  download_fax_pdf error: {e}", exc_info=True)
            return b""

    # ── Send to Staff ──────────────────────────────────────────────────────

    async def send_fax_to_staff_group(self, category: str) -> bool:
        """
        Click the person/send icon on the fax row, type the group name
        in the 'Send To Staff' dialog, pick from autocomplete, click OK.
        """
        group_name = config.CATEGORY_TO_FOLDER.get(category)
        if not group_name:
            log.warning(f"  No group mapping for category: {category}")
            return False

        try:
            # Click send icon
            send_icon = self.page.locator(StaffDialogSelectors.SEND_ICON)
            if send_icon.count() == 0:
                log.error("  'Send To Staff' icon not found on fax row.")
                return False
            send_icon.click()
            await asyncio.sleep(1.5)

            # Wait for dialog
            self.page.wait_for_selector(
                StaffDialogSelectors.DIALOG,
                timeout=Timeouts.DIALOG * 1000
            )
            log.info("  'Send To Staff' dialog opened.")

            # Type group name
            staff_input = self.page.locator(StaffDialogSelectors.SEARCH_INPUT)
            if staff_input.count() == 0:
                log.error("  Staff search input not found.")
                await self._cancel_dialog()
                return False

            staff_input.click()
            staff_input.fill("")
            staff_input.type(group_name, delay=80)
            log.info(f"  Typed: '{group_name}'")
            await asyncio.sleep(1.5)

            # Pick from dropdown
            items = self.page.locator(StaffDialogSelectors.DROPDOWN_ITEM).all()
            matched = False
            for item in items:
                text = item.inner_text()
                if group_name.lower() in text.lower():
                    item.click()
                    log.info(f"  Selected: '{text.strip()}'")
                    matched = True
                    await asyncio.sleep(0.5)
                    break

            if not matched:
                log.warning(f"  '{group_name}' not found in dropdown — cancelling.")
                await self._cancel_dialog()
                return False

            # Click OK
            ok_btn = self.page.locator(StaffDialogSelectors.OK_BUTTON)
            if ok_btn.count() > 0:
                ok_btn.click()
                log.info(f"  Fax sent to: {group_name}")
                await asyncio.sleep(1.5)
                return True
            else:
                log.error("  OK button not found in dialog.")
                return False

        except Exception as e:
            log.error(f"  send_fax_to_staff_group error: {e}")
            await self._cancel_dialog()
            return False

    async def _cancel_dialog(self):
        """Click Cancel to dismiss Send To Staff dialog if it's open."""
        try:
            cancel = self.page.locator(StaffDialogSelectors.CANCEL_BUTTON)
            if cancel.count() > 0:
                cancel.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass
