# 🤖 Fax Classification Agent

An RPA agent that logs into ECW, retrieves faxes from the inbox, OCRs each PDF locally using Mistral via Ollama, classifies it with Google Vertex AI Gemini, and routes it to the correct staff group — all automatically.

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
│  - Save to hipaa_local/ directory                                   │
└───────────┬─────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FaxClassificationPipeline (pipeline.py)                            │
│                                                                     │
│  OCR — ocr_engine.py                                                │
│  - Split PDF into pages (pdf_handler.py)                            │
│  - Send each page image to Mistral via Ollama (local, on-machine)   │
│  - Extract text per page                                            │
│                                                                     │
│  Classify — gemini_classifier.py                                    │
│  - Send plain OCR text to Vertex AI Gemini 1.5 Pro                  │
│  - Returns: category, confidence, reason                            │
│  - Categories: LAB, REFERRAL, INSURANCE, PRESCRIPTION, OTHER        │
└───────────┬─────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Routing & Logging                                                  │
│  - HIGH/MEDIUM confidence → auto-send to staff group via ECW dialog │
│  - LOW confidence → flagged for manual review                       │
│  - All results saved to logs/fax_classification_log.xlsx            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
RPA/
│
├── main.py                  ← Entry point — runs the full agent
├── ecw_bot.py               ← ECW browser automation (login + navigation + PDF)
├── pipeline.py              ← Full PDF → OCR → Classify pipeline
├── gemini_classifier.py     ← Vertex AI Gemini classifier (HIPAA-covered)
├── ocr_engine.py            ← Local Mistral OCR via Ollama (all on-machine)
├── pdf_handler.py           ← Local PDF save / split / archive
├── logger.py                ← Excel audit log writer
├── classifier.py            ← ⚠️ LEGACY — not used
├── config.py                ← ⚙️ YOUR SETTINGS GO HERE (credentials, URLs)
├── constants.py             ← All ECW UI selectors and timeout values
├── verify_setup.py          ← Run before main.py to check everything works
├── test_login.py            ← Standalone login smoke test
├── requirements.txt         ← Python dependencies
├── classification_prompt.txt ← Gemini classification prompt template
│
├── pages/                   ← Page Object Model (Playwright)
│   ├── __init__.py
│   ├── base_page.py         ← Base class: wait, click, type helpers
│   ├── browser_manager.py   ← Camoufox browser launch and teardown
│   └── login_page.py        ← Login flow: username/password/CAPTCHA
│
├── config/                  ← Google service account credentials (gitignored)
│   └── google_service_account.json
│
├── hipaa_local/             ← Local-only PDF storage (auto-created, gitignored)
├── screenshots/             ← Debug screenshots (auto-created)
└── logs/                    ← Log files + Excel audit log (auto-created)
```

> **`rishav_files/`** — Legacy reference files, not used by the agent.

---

## 🔒 HIPAA Data Flow

```
YOUR MACHINE  (100% local — HIPAA safe)
  ECW fax preview
      │ PDF bytes
      ▼
  hipaa_local/   ← saved on your machine only
      │ page images
      ▼
  Mistral via Ollama  ← runs locally, no internet
      │ plain text (no images, no PHI)
      ▼
GOOGLE VERTEX AI  (covered under signed BAA)
  Gemini 1.5 Pro → classification JSON
      │
      ▼
YOUR MACHINE  ← result returned, fax routed in ECW
```

---

## ✅ Quick Start

### 1 — Install Python 3.11+
Download from https://python.org. Check **"Add Python to PATH"** during install.

### 2 — Install Ollama
Download from https://ollama.com/download, then:
```bash
ollama pull mistral-small3.1
```
This downloads ~7 GB — do it once on a good connection.

### 3 — Install dependencies
```bash
cd C:\path\to\RPA
pip install -r requirements.txt
playwright install chromium
```

### 4 — Set up Google Vertex AI
1. [Google Cloud Console](https://console.cloud.google.com) → create/select project
2. Enable **Vertex AI API**
3. IAM → Service Accounts → Create → grant **"Vertex AI User"** role
4. Download JSON key → save to `config/google_service_account.json`
5. Sign a **BAA**: Console → IAM → Data Protection (required for HIPAA)

### 5 — Fill in config.py
```python
GOOGLE_CLOUD_PROJECT_ID = "your-gcp-project"
ECW_URL      = "https://your-ecw-url.ecwcloud.com/..."
ECW_USERNAME = "your_username"
ECW_PASSWORD = "your_password"
```

### 6 — Verify setup
```bash
python verify_setup.py
```
All checks should show ✅ before running.

### 7 — Run the agent
```bash
python main.py
```
Watch the browser automate! Results saved to `logs/fax_classification_log.xlsx`.

---

## 📊 Audit Log

Open `logs/fax_classification_log.xlsx`:
- 🟢 **GREEN** — High confidence (auto-moved to staff group)
- 🟡 **YELLOW** — Medium confidence (auto-moved, worth spot-checking)
- 🔴 **RED** — Low confidence (flagged for manual review)

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| CAPTCHA not clicking | Check `y_offset` in `login_page.py` `_click_verification_overlay` |
| Login button not enabling | Increase `time.sleep` before CAPTCHA click (default: 40s) |
| Dashboard overlay hangs | Increase `timeout` on `div#load` hidden wait (default: 60s) |
| Jellybean menu not working | Inspect `a#jellybean-panelLink29/302/332` IDs in browser DevTools |
| PDF preview empty | Update `FAX_PREVIEW` selector in `constants.py` |
| Ollama OCR slow | Normal on first run — model loads into RAM (~30s) |
| Vertex AI 403 error | Ensure service account has "Vertex AI User" role |
| Low confidence results | Tune `classification_prompt.txt` |

---

## ⏰ Schedule Daily (Windows Task Scheduler)
1. Search **Task Scheduler** → Create Basic Task
2. Name: `Fax Agent` | Trigger: Daily at preferred time
3. Action: Start a program → `python` | Arguments: `C:\path\to\RPA\main.py`
4. Click Finish
