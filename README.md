# 🤖 ECW Fax Downloader

An RPA agent that automatically logs into ECW, retrieves faxes from the inbox, and downloads each PDF locally to your machine.

---

## 🏗️ Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         main.py (Orchestrator)                       │
└───────────┬─────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ECWBot (ecw_bot.py) — Browser Automation                           │
│                                                                     │
│  1. Launch Camoufox browser (stealth mode)                          │
│  2. Navigate to ECW login page                                      │
│  3. Enter username → click Next                                     │
│  4. Enter password                                                  │
│  5. Wait 40s → click Cloudflare Turnstile CAPTCHA checkbox          │
│  6. Click Log In button                                             │
│  7. Verify login (wait for a#jellybean-panelLink29 to appear)       │
│  8. Wait for "Building your user experience" overlay to hide        │
│  9. Hover  D jellybean  (a#jellybean-panelLink29)                   │
│  10. JS click Fax Inbox - Web Mode (a#jellybean-panelLink302)       │
│  11. JS click Fax Inbox           (a#jellybean-panelLink332)        │
│  12. Select today's date in the date picker                         │
│  13. Get list of all fax rows                                       │
└───────────┬─────────────────────────────────────────────────────────┘
            │ For each fax
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PDF Download (ecw_bot.py → pdf_handler.py)                         │
│  - Click fax row to open preview iframe                             │
│  - Extract PDF bytes from iframe src URL                            │
│  - Save to hipaa_local/raw_pdfs/ directory                          │
└───────────┬─────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Logging                                                            │
│  - Record SUCCESS/FAILED status in logs/fax_download_log.xlsx       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
RPA/
│
├── main.py                  ← Entry point — runs the full agent
├── ecw_bot.py               ← ECW browser automation (login + navigation + PDF)
├── pdf_handler.py           ← Local PDF save handler
├── logger.py                ← Excel audit log writer
├── config.py                ← ⚙️ YOUR SETTINGS GO HERE (credentials, URLs)
├── constants.py             ← All ECW UI selectors and timeout values
├── verify_setup.py          ← Run before main.py to check configuration
├── test_login.py            ← Standalone login smoke test
├── requirements.txt         ← Python dependencies
│
├── pages/                   ← Page Object Model (Playwright)
│   ├── __init__.py
│   ├── base_page.py         ← Base class: wait, click, type helpers
│   ├── browser_manager.py   ← Camoufox browser launch and teardown
│   └── login_page.py        ← Login flow: username/password/CAPTCHA
│
├── hipaa_local/             ← Local-only PDF storage (auto-created, gitignored)
└── logs/                    ← Log files + Excel audit log (auto-created)
```

> **`rishav_files/`** — Legacy reference files, not used by the agent.

---

## ✅ Quick Start

### 1 — Install Python 3.11+
Download from https://python.org. Check **"Add Python to PATH"** during install.

### 2 — Install dependencies
```bash
cd C:\path\to\RPA
pip install -r requirements.txt
playwright install chromium
```

### 3 — Fill in config.py
```python
ECW_URL      = "https://your-ecw-url.ecwcloud.com/..."
ECW_USERNAME = "your_username"
ECW_PASSWORD = "your_password"
```

### 4 — Verify setup
```bash
python verify_setup.py
```
All checks should show ✅ before running.

### 5 — Run the agent
```bash
python main.py
```
Watch the browser automate! PDFs are stored in `hipaa_local/raw_pdfs/`. Results saved to `logs/fax_download_log.xlsx`.

---

## 📊 Audit Log

Open `logs/fax_download_log.xlsx`:
- 🟢 **GREEN** — File downloaded successfully
- 🔴 **RED** — Download failed or element timeout

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| CAPTCHA not clicking | Check `y_offset` in `login_page.py` `_click_verification_overlay` |
| Login button not enabling | Increase `time.sleep` before CAPTCHA click (default: 40s) |
| Dashboard overlay hangs | Increase `timeout` on `div#load` hidden wait (default: 60s) |
| Jellybean menu not working | Inspect `a#jellybean-panelLink29/302/332` IDs in browser DevTools |
| PDF preview empty | Update `FAX_PREVIEW` selector in `constants.py` |

---

## ⏰ Schedule Daily (Windows Task Scheduler)
1. Search **Task Scheduler** → Create Basic Task
2. Name: `Fax Agent` | Trigger: Daily at preferred time
3. Action: Start a program → `python` | Arguments: `C:\path\to\RPA\main.py`
4. Click Finish
