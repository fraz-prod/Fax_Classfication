# 🤖 Fax Classification Agent — Setup Guide

## Architecture
```
ECW (Playwright) → PDF (local) → Mistral OCR (Ollama) → Vertex AI Gemini → Category
```

## File Structure
```
RPA/
├── main.py                ← Run this to start the agent
├── pipeline.py            ← Full PDF → OCR → Classify pipeline
├── ecw_bot.py             ← Browser automation (ECW navigation + PDF download)
├── gemini_classifier.py   ← Vertex AI Gemini classifier (HIPAA-covered)
├── ocr_engine.py          ← Local Mistral OCR via Ollama (100% on-machine)
├── pdf_handler.py         ← Local PDF save/split/archive
├── logger.py              ← Excel audit log writer
├── classifier.py          ← ⚠️ LEGACY (Claude/Anthropic) — not used
├── config.py              ← YOUR SETTINGS GO HERE
├── verify_setup.py        ← Run before main.py to check everything works
├── requirements.txt       ← Python dependencies
├── hipaa_local/           ← Local-only PDF storage (auto-created)
├── screenshots/           ← Temp screenshots (auto-created)
└── logs/                  ← Log files + Excel audit log (auto-created)
```

---

## ✅ Step 1 — Install Python
Download Python **3.11+** from https://python.org  
During install, **check "Add Python to PATH"**

---

## ✅ Step 2 — Install Ollama (local Mistral OCR)
1. Download from https://ollama.com/download
2. Install and open Ollama
3. In a terminal, pull the vision model:
```
ollama pull mistral-small3.1
```
This downloads ~7GB — do this once over a good connection.

---

## ✅ Step 3 — Install Python dependencies
Open Command Prompt, navigate to this folder:
```
cd C:\path\to\RPA
pip install -r requirements.txt
playwright install chromium
```

---

## ✅ Step 4 — Set up Google Vertex AI
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create or select a project → note the **Project ID**
3. Enable the **Vertex AI API**
4. IAM → Service Accounts → Create → grant **"Vertex AI User"** role
5. Download the JSON key file → save to `config/google_service_account.json`
6. **Sign a BAA**: Console → IAM → Data Protection (required for HIPAA)

---

## ✅ Step 5 — Fill in config.py
Open `config.py` and fill in:
- `GOOGLE_CLOUD_PROJECT_ID` — your GCP project ID
- `ECW_URL` — your ECW web address
- `ECW_USERNAME` / `ECW_PASSWORD` — your ECW login

---

## ✅ Step 6 — Find your ECW selectors (IMPORTANT)
The bot needs to know WHICH elements to click in ECW.

1. Open ECW in Chrome
2. Right-click any element → **Inspect**
3. In DevTools, right-click highlighted HTML → **Copy → Copy selector**
4. Paste into `config.py` next to the matching variable

Do this for each `← Inspect and replace` comment in config.py.

---

## ✅ Step 7 — Verify your setup
```
python verify_setup.py
```
All checks should show ✅ before running main.py.

---

## ✅ Step 8 — Run the agent
```
python main.py
```
Watch the browser automate! Check `logs/fax_classification_log.xlsx` for results.

---

## ✅ Step 9 — Schedule it daily (Windows Task Scheduler)
1. Search "Task Scheduler" in Start menu → Create Basic Task
2. Name: `Fax Agent` | Trigger: Daily at your preferred time
3. Action: Start a program → `python` | Arguments: `C:\path\to\RPA\main.py`
4. Click Finish

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| Bot clicks wrong element | Re-inspect selector in Chrome DevTools |
| PDF preview empty | Update `SELECTOR_FAX_PREVIEW` in config.py |
| Low confidence classifications | Add keywords to `CLASSIFICATION_PROMPT` in `gemini_classifier.py` |
| Ollama OCR slow | Normal on first run — model loads into RAM (~30s) |
| Vertex AI 403 error | Ensure service account has "Vertex AI User" role |

---

## 📊 Reading the Audit Log
Open `logs/fax_classification_log.xlsx`
- 🟢 **GREEN** = High confidence (auto-moved to staff group)
- 🟡 **YELLOW** = Medium confidence (auto-moved, worth spot-checking)
- 🔴 **RED** = Low confidence (flagged for manual review)

---

## 🔒 HIPAA Data Flow
```
YOUR MACHINE (local, HIPAA safe)
  ECW → PDF saved locally → Pages split → Mistral OCR (Ollama)
                                             │
                                    Plain text ONLY (no PHI images)
                                             ▼
GOOGLE VERTEX AI (covered under BAA)
  OCR text → Gemini 1.5 Pro → Category JSON
```
