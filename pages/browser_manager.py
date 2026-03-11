"""
pages/browser_manager.py
========================
Browser Manager for ECW RPA — adapted from rishav_files/browser_manager.py

Changes from original:
  - Replaced clinicalops_rpa_base.logger with standard logging
  - All Camoufox stealth logic preserved
  - Playwright fallback preserved
  - HIPAA-safe screenshot gating preserved (off unless ENABLE_SCREENSHOTS=true)
"""

import logging
import os
import time
from typing import Optional

log = logging.getLogger(__name__)

# ── Camoufox import with graceful fallback ───────────────────────────────────
try:
    from camoufox.sync_api import Camoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    try:
        from camoufox import Camoufox
        CAMOUFOX_AVAILABLE = True
    except ImportError:
        CAMOUFOX_AVAILABLE = False

from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError


class BrowserManager:
    """
    Manages Playwright browser with Camoufox stealth.

    Camoufox: https://github.com/daijro/camoufox
    - Bypasses bot-detection / Cloudflare that ECW may employ
    - Drop-in Playwright replacement — same API
    - Falls back to standard Playwright if camoufox not installed

    Install: pip install camoufox
    """

    def __init__(self, headless: bool = False, wait_timeout: int = 15):
        self.wait_timeout = wait_timeout
        self.page: Optional[Page] = None
        self.browser = None
        self.context = None
        self.camoufox = None
        self._playwright = None    # used in fallback mode

        if not CAMOUFOX_AVAILABLE:
            log.warning(
                "Camoufox not installed — falling back to standard Playwright. "
                "Install for bot-detection bypass: pip install camoufox"
            )

        # Docker detection
        self.is_docker = (
            os.path.exists("/.dockerenv") or
            os.environ.get("DOCKER_CONTAINER") == "true"
        )
        if self.is_docker:
            self.headless = False
            if not os.environ.get("DISPLAY"):
                os.environ["DISPLAY"] = ":99"
            log.info("Docker detected — using Xvfb virtual display")
        else:
            self.headless = headless

        self.screenshot_dir = "/app/screenshots" if self.is_docker else "screenshots"
        os.makedirs(self.screenshot_dir, exist_ok=True)

    # ── Start ─────────────────────────────────────────────────────────────────

    def start_driver(self) -> Page:
        """
        Start the browser. Uses Camoufox if available, otherwise standard Playwright.
        Returns a Playwright Page object ready to use.
        """
        # Cleanup any existing session first
        if self.camoufox or self.browser or self.page or self._playwright:
            try:
                self.quit_driver()
            except Exception:
                pass
            self.page = None
            self.browser = None
            self.camoufox = None
            self._playwright = None

        if CAMOUFOX_AVAILABLE:
            return self._start_camoufox()
        else:
            return self._start_playwright_fallback()

    def _start_camoufox(self) -> Page:
        """Start browser using Camoufox stealth mode."""
        log.info("Starting browser with Camoufox (stealth mode)...")
        args = ["--disable-download-notification"]
        if self.is_docker:
            args.extend(["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])

        self.camoufox = Camoufox(headless=self.headless, args=args)
        self.browser = self.camoufox.__enter__()
        log.info(f"Camoufox browser started: {type(self.browser).__name__}")

        time.sleep(0.5)
        self.page = self.browser.new_page()
        self.context = self.page.context

        self._configure_page(browser_type="camoufox")
        return self.page

    def _start_playwright_fallback(self) -> Page:
        """Start browser using standard Playwright (no stealth)."""
        log.info("Starting browser with standard Playwright (no stealth)...")
        self._playwright = sync_playwright().start()
        self.browser = self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=300,
            args=["--disable-download-notification"]
        )
        self.context = self.browser.new_context(viewport={"width": 1600, "height": 900})
        self.page = self.context.new_page()

        self._configure_page(browser_type="playwright")
        return self.page

    def _configure_page(self, browser_type: str):
        """Apply common page configuration after browser start."""
        try:
            self.page.set_viewport_size({"width": 1600, "height": 900})
        except Exception:
            pass

        # Navigate to blank to ensure clean state
        try:
            current = self.page.url
            if not current or current in ("about:blank", ""):
                self.page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        except Exception:
            pass

        # Auto-close any unexpected popup tabs
        def handle_new_page(new_page):
            log.warning(f"Unexpected popup tab detected — closing: {new_page.url}")
            try:
                new_page.close()
            except Exception:
                pass

        try:
            self.browser.on("page", handle_new_page)
        except Exception:
            pass

        # Auto-handle dialogs (beforeunload = accept, others = dismiss)
        def handle_dialog(dialog):
            if dialog.type == "beforeunload":
                log.info("beforeunload dialog — accepting.")
                dialog.accept()
            else:
                log.info(f"Dialog type '{dialog.type}' — dismissing.")
                dialog.dismiss()

        self.page.on("dialog", handle_dialog)
        self.page.set_default_timeout(self.wait_timeout * 1000)

        log.info(f"Browser ready — 1440x900, mode: {browser_type}")

    # ── Navigation ────────────────────────────────────────────────────────────

    def navigate_and_wait_for_login(self, url: str,
                                    timeout: int = 60) -> bool:
        """
        Navigate to ECW URL and wait until the login form is visible.
        Handles Cloudflare challenge automatically via Camoufox.
        Returns True when login page is ready.
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start_driver() first.")

        # Ensure valid state before navigation
        try:
            current = self.page.url
            if current and not current.startswith(("http", "about:blank")):
                self.page.goto("about:blank", wait_until="domcontentloaded", timeout=5000)
        except Exception:
            pass

        log.info(f"Navigating to: {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Verify we got a real HTTP page
        final_url = self.page.url
        if not final_url.startswith("http"):
            log.error(f"Navigation may have failed — URL is: {final_url}")
            # Retry once
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            final_url = self.page.url
            if not final_url.startswith("http"):
                raise RuntimeError(f"Navigation failed — URL: {final_url}")

        # Wait for login form (doctorID field)
        try:
            self.page.wait_for_selector("#doctorID", state="visible",
                                        timeout=timeout * 1000)
            log.info("Login page ready (doctorID field visible).")
        except PlaywrightTimeoutError:
            content = self.page.content().lower()
            if "doctorid" in content or "username" in content or "password" in content:
                log.info("Login form present in page content.")
            else:
                log.warning(
                    "Login form not found. Cloudflare may still be active, "
                    "or SELECTOR needs updating (looking for #doctorID)."
                )

        return True

    # ── Screenshot ────────────────────────────────────────────────────────────

    def save_screenshot(self, filename: str, prefix: str = ""):
        """
        Save screenshot ONLY if ENABLE_SCREENSHOTS=true env var is set.
        Disabled by default for HIPAA compliance (screenshots may contain PHI).
        """
        if os.getenv("ENABLE_SCREENSHOTS", "false").lower() != "true":
            log.debug(f"Screenshots disabled (HIPAA). Not saving: {filename}")
            return

        if not self.page:
            return

        try:
            full_name = f"{prefix}_{filename}" if prefix else filename
            if not full_name.endswith((".jpg", ".jpeg")):
                full_name = full_name.replace(".png", "") + ".jpg"
            filepath = os.path.join(self.screenshot_dir, full_name)
            try:
                self.page.screenshot(path=filepath, full_page=True,
                                     type="jpeg", quality=30)
            except Exception:
                self.page.screenshot(path=filepath, full_page=False,
                                     type="jpeg", quality=30)
            log.debug(f"Screenshot saved: {filepath}")
        except Exception as e:
            log.error(f"Screenshot failed: {e}")

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def quit_driver(self):
        """Close browser cleanly."""
        try:
            if self.page:
                self.page.close()
                self.page = None

            if self.context:
                self.context.close()
                self.context = None

            if self.camoufox:
                try:
                    self.camoufox.__exit__(None, None, None)
                except Exception:
                    pass
                self.camoufox = None
                self.browser = None

            if self._playwright:
                try:
                    if self.browser:
                        self.browser.close()
                    self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
                self.browser = None

            log.info("Browser closed.")
        except Exception as e:
            log.error(f"Error closing browser: {e}")

    def get_page(self) -> Optional[Page]:
        """Return the active Playwright Page."""
        return self.page
