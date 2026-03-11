"""
ECW Browser Automation Bot
Handles all browser interactions with eClinicalWorks
"""

import asyncio
import os
import logging
from datetime import datetime
from urllib.parse import urlparse
import httpx
from playwright.async_api import async_playwright, Page, Browser
import config

log = logging.getLogger(__name__)


class ECWBot:
    def __init__(self):
        self.playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.screenshot_dir = "screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs("logs", exist_ok=True)

    async def launch(self):
        """Launch Chromium browser"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Set True once tested and working
            slow_mo=500      # Slow down actions so you can watch it work
        )
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(30000)  # 30 second timeout
        log.info("Browser launched.")

    async def login(self):
        """Navigate to ECW and log in"""
        await self.page.goto(config.ECW_URL)
        await self.page.wait_for_load_state("networkidle")

        # Fill in username and password
        # NOTE: Update the selectors below to match ECW's actual login fields
        await self.page.fill('input[name="username"]', config.ECW_USERNAME)
        await self.page.fill('input[name="password"]', config.ECW_PASSWORD)
        await self.page.click('button[type="submit"]')

        await self.page.wait_for_load_state("networkidle")
        log.info("Logged in to ECW.")

    async def open_fax_inbox(self):
        """Click icon D and select Fax Inbox Web Mode from dropdown"""
        # NOTE: Update selector to match the actual "D" icon element
        # Right-click the icon area top right — inspect element in Chrome to get selector
        await self.page.click(config.SELECTOR_ICON_D)
        await asyncio.sleep(1)

        # Click "Fax Inbox Web Mode" from dropdown
        await self.page.click(config.SELECTOR_FAX_INBOX_MENU_ITEM)
        await self.page.wait_for_load_state("networkidle")
        log.info("Fax Inbox Web Mode opened.")

    async def select_date(self, date: datetime):
        """Select date in the fax inbox date picker"""
        date_str = date.strftime(config.ECW_DATE_FORMAT)

        # NOTE: Update selector to match ECW's date input field
        await self.page.fill(config.SELECTOR_DATE_INPUT, date_str)
        await self.page.keyboard.press("Enter")
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        log.info(f"Date selected: {date_str}")

    async def get_fax_list(self) -> list:
        """Get all fax rows from the inbox table"""
        # NOTE: Update selector to match ECW's fax list rows
        await self.page.wait_for_selector(config.SELECTOR_FAX_ROW)
        fax_rows = await self.page.query_selector_all(config.SELECTOR_FAX_ROW)
        log.info(f"Found {len(fax_rows)} fax rows.")
        return fax_rows

    async def open_fax(self, fax_element):
        """Click on a fax to open its preview"""
        await fax_element.click()
        await asyncio.sleep(2)  # Wait for PDF preview to load
        await self.page.wait_for_load_state("networkidle")

    async def download_fax_pdf(self, fax_element) -> bytes:
        """
        Click a fax row to open its PDF preview, then download the PDF
        bytes directly from the ECW iframe src URL.

        Strategy:
          1. Click the fax row → ECW loads PDF in an iframe
          2. Wait for the iframe to appear and its src to be populated
          3. Extract the iframe src URL (ECW serves the PDF via this URL)
          4. Copy the browser's active cookies (keeps auth session alive)
          5. Download the PDF bytes using httpx with those cookies
          6. Return raw bytes to pipeline — PDF never hits disk until
             pdf_handler.save_pdf() is explicitly called (HIPAA safe)

        Returns:
            bytes: raw PDF bytes, or b"" on failure
        """
        try:
            # ── Step 1: Click the fax row to load its preview ──────────
            await fax_element.click()
            await asyncio.sleep(2)
            await self.page.wait_for_load_state("networkidle")
            log.info("  Fax row clicked — waiting for PDF preview iframe...")

            # ── Step 2: Wait for the PDF iframe to appear ───────────────
            try:
                await self.page.wait_for_selector(
                    config.SELECTOR_FAX_PREVIEW,
                    timeout=15000
                )
            except Exception:
                log.warning(
                    "  PDF preview iframe not found within 15s. "
                    f"Check SELECTOR_FAX_PREVIEW in config.py (current: '{config.SELECTOR_FAX_PREVIEW}')"
                )
                return b""

            # ── Step 3: Read the iframe src URL ────────────────────────
            pdf_url = await self.page.eval_on_selector(
                config.SELECTOR_FAX_PREVIEW,
                "el => el.src || el.getAttribute('src') || ''"
            )

            if not pdf_url or pdf_url.strip() in ("", "about:blank"):
                # Some ECW versions embed the viewer differently —
                # try reading data-src or the inner iframe
                pdf_url = await self.page.eval_on_selector(
                    config.SELECTOR_FAX_PREVIEW,
                    "el => el.getAttribute('data-src') || ''"
                )

            if not pdf_url or pdf_url.strip() in ("", "about:blank"):
                log.error(
                    "  PDF iframe found but src is empty or 'about:blank'. "
                    "ECW may load the PDF lazily — try increasing the sleep "
                    "above or update SELECTOR_FAX_PREVIEW."
                )
                return b""

            # Make absolute URL if ECW returns a relative path
            if pdf_url.startswith("/"):
                parsed = urlparse(config.ECW_URL)
                pdf_url = f"{parsed.scheme}://{parsed.netloc}{pdf_url}"

            log.info(f"  PDF URL found: {pdf_url[:80]}...")

            # ── Step 4: Copy browser cookies for authenticated download ─
            cookies = await self.page.context.cookies()
            cookie_header = "; ".join(
                f"{c['name']}={c['value']}" for c in cookies
            )

            # ── Step 5: Download PDF bytes via httpx ───────────────────
            async with httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
                verify=False  # ECW often uses self-signed certs internally
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
                log.error(
                    f"  PDF download failed: HTTP {response.status_code}. "
                    "Check that ECW session is still active."
                )
                return b""

            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and len(response.content) < 100:
                log.warning(
                    f"  Response doesn't look like a PDF "
                    f"(Content-Type: {content_type}, size: {len(response.content)} bytes). "
                    "ECW may have returned an error page."
                )
                return b""

            log.info(f"  ✅ PDF downloaded: {len(response.content):,} bytes")
            return response.content

        except Exception as e:
            log.error(f"  download_fax_pdf error: {e}", exc_info=True)
            return b""

    async def screenshot_fax_preview(self, fax_index: int) -> list:
        """
        Screenshot the first 2 pages of the PDF preview.
        Returns list of screenshot file paths.
        """
        screenshot_paths = []

        # Screenshot the full preview area (adjust selector to the PDF iframe/viewer)
        preview_element = await self.page.query_selector(config.SELECTOR_FAX_PREVIEW)

        if preview_element:
            path = f"{self.screenshot_dir}/fax_{fax_index}_page1.png"
            await preview_element.screenshot(path=path)
            screenshot_paths.append(path)
            log.info(f"  Screenshot saved: {path}")

            # Scroll down to capture page 2 if visible
            await self.page.evaluate(
                f"document.querySelector('{config.SELECTOR_FAX_PREVIEW}').scrollTop += 1000"
            )
            await asyncio.sleep(1)

            path2 = f"{self.screenshot_dir}/fax_{fax_index}_page2.png"
            await preview_element.screenshot(path=path2)
            screenshot_paths.append(path2)
            log.info(f"  Screenshot saved: {path2}")

        else:
            # Fallback: screenshot full page
            log.warning("  Could not find PDF preview element — taking full page screenshot.")
            path = f"{self.screenshot_dir}/fax_{fax_index}_fullpage.png"
            await self.page.screenshot(path=path, full_page=True)
            screenshot_paths.append(path)

        return screenshot_paths

    async def send_fax_to_staff_group(self, category: str):
        """
        Clicks the person/send icon on the fax row to open
        the 'Send To Staff' dialog, types the group name,
        selects from the auto-complete dropdown, and clicks OK.
        """
        group_name = config.CATEGORY_TO_FOLDER.get(category)

        if not group_name:
            log.warning(f"  No group mapping found for category: {category}")
            return False

        try:
            # ── Step 1: Click the person/send icon on the highlighted fax row ──
            # This is the small person icon that appears on the right side of the row
            # NOTE: Inspect the icon in Chrome and update SELECTOR_SEND_TO_STAFF_ICON
            send_icon = await self.page.query_selector(config.SELECTOR_SEND_TO_STAFF_ICON)
            if not send_icon:
                log.error("  Could not find 'Send To Staff' icon on fax row.")
                return False

            await send_icon.click()
            await asyncio.sleep(1.5)

            # ── Step 2: Wait for the 'Send To Staff' dialog to appear ──
            await self.page.wait_for_selector(config.SELECTOR_STAFF_DIALOG, timeout=10000)
            log.info("  'Send To Staff' dialog opened.")

            # ── Step 3: Clear the Staff search box and type the group name ──
            staff_input = await self.page.query_selector(config.SELECTOR_STAFF_SEARCH_INPUT)
            if not staff_input:
                log.error("  Could not find Staff search input field.")
                await self._cancel_dialog()
                return False

            await staff_input.click()
            await staff_input.fill("")           # Clear any existing text
            await staff_input.type(group_name, delay=80)  # Type like a human
            log.info(f"  Typed group name: '{group_name}'")
            await asyncio.sleep(1.5)             # Wait for autocomplete dropdown

            # ── Step 4: Pick the first matching item from the dropdown ──
            dropdown_items = await self.page.query_selector_all(config.SELECTOR_STAFF_DROPDOWN_ITEM)

            matched = False
            for item in dropdown_items:
                text = await item.inner_text()
                if group_name.lower() in text.lower():
                    await item.click()
                    log.info(f"  Selected from dropdown: '{text.strip()}'")
                    matched = True
                    await asyncio.sleep(0.5)
                    break

            if not matched:
                log.warning(f"  Group '{group_name}' not found in dropdown — cancelling.")
                await self._cancel_dialog()
                return False

            # ── Step 5: Click OK to confirm ──
            ok_button = await self.page.query_selector(config.SELECTOR_STAFF_DIALOG_OK)
            if ok_button:
                await ok_button.click()
                log.info(f"  ✅ Fax sent to: {group_name}")
                await asyncio.sleep(1.5)
                return True
            else:
                log.error("  Could not find OK button in dialog.")
                return False

        except Exception as e:
            log.error(f"  Error in send_fax_to_staff_group: {e}")
            await self._cancel_dialog()
            return False

    async def _cancel_dialog(self):
        """Click Cancel if the dialog is open, to avoid getting stuck"""
        try:
            cancel = await self.page.query_selector(config.SELECTOR_STAFF_DIALOG_CANCEL)
            if cancel:
                await cancel.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass

    async def close(self):
        """Close browser cleanly"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
