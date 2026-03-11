# 🔐 HIPAA-Safe Pipeline Setup Guide
## Local Mistral OCR + Vertex AI Gemini

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  YOUR WINDOWS MACHINE  (HIPAA safe — no data leaves)    │
│                                                         │
│  ECW RPA Bot                                            │
│      ↓ downloads PDF                                    │
│  pdf_handler.py  →  saves to hipaa_local/raw_pdfs/     │
│      ↓ splits pages                                     │
│  pdf_handler.py  →  hipaa_local/split_pages/           │
│      ↓ converts to image                               │
│  ocr_engine.py   →  Ollama (local Mistral vision)      │
│      ↓ plain text only                                  │
└─────────────────────┬───────────────────────────────────┘
                      │  OCR text only (no images, no PDFs)
                      ▼
┌─────────────────────────────────────────────────────────┐
│  GOOGLE VERTEX AI  (covered under Google Cloud BAA)     │
│                                                         │
│  gemini_classifier.py → Gemini 1.5 Pro                 │
│      ↓ returns JSON                                     │
│  { category, confidence, reason, key_signals }         │
└─────────────────────────────────────────────────────────┘
                      ↓
              ECW Bot → Send to Staff Group
              logger.py → Excel audit log
```

---

## ✅ Step 1 — Install Ollama (Local Mistral OCR)

1. Download from: https://ollama.com/download  (Windows installer)
2. Install and open Ollama
3. Open Command Prompt and run:
```
ollama pull mistral-small3.1
ollama serve
```
4. Verify it works: http://localhost:11434 should show "Ollama is running"

---

## ✅ Step 2 — Set Up Google Vertex AI (Gemini)

### 2a. Create Google Cloud Project
1. Go to: https://console.cloud.google.com
2. Create a new project (e.g. "fax-classifier")
3. Note your **Project ID**

### 2b. Enable Vertex AI API
1. Go to: APIs & Services → Enable APIs
2. Search "Vertex AI API" → Enable

### 2c. Sign the BAA (CRITICAL for HIPAA)
1. Go to: console.cloud.google.com → IAM & Admin → Data Protection
2. Accept Google Cloud HIPAA BAA
3. ⚠️ Do NOT use AI Studio — only Vertex AI is BAA-covered

### 2d. Create Service Account
1. Go to: IAM & Admin → Service Accounts → Create
2. Name: "fax-classifier-sa"
3. Role: "Vertex AI User"
4. Click "Create Key" → JSON → Download
5. Save as: `fax-agent/config/google_service_account.json`

---

## ✅ Step 3 — Configure config.py

Fill in these values:
```python
GOOGLE_CLOUD_PROJECT_ID = "your-actual-project-id"
GOOGLE_CLOUD_LOCATION   = "us-central1"
GOOGLE_APPLICATION_CREDENTIALS = "config/google_service_account.json"
```

---

## ✅ Step 4 — Install Python Dependencies

```
cd C:\path\to\fax-agent
pip install -r requirements.txt
playwright install chromium
```

---

## ✅ Step 5 — Run the Agent

Make sure Ollama is running first, then:
```
python main.py
```

---

## 📁 Local HIPAA Folders (never sync to cloud!)

```
hipaa_local/
├── raw_pdfs/      ← Downloaded fax PDFs (deleted after processing)
├── split_pages/   ← Temp page splits (deleted immediately after OCR)
└── archive/       ← Processed PDFs (keep for audit trail)
```

⚠️ Add `hipaa_local/` to your `.gitignore`
⚠️ Never sync this folder to Google Drive, OneDrive, or Dropbox
⚠️ Consider enabling Windows BitLocker on this drive

---

## 💰 Cost Estimate (20-50 faxes/day)

| Service | Cost |
|---|---|
| Ollama / Mistral local | **$0** — runs on your machine |
| Vertex AI Gemini 1.5 Pro | ~$0.002 per fax = **~$0.10/day** |
| **Total** | **~$3/month** |

---

## 🔧 Troubleshooting

| Problem | Fix |
|---|---|
| "Ollama not running" | Run `ollama serve` in Command Prompt |
| "Model not found" | Run `ollama pull mistral-small3.1` |
| "Vertex AI 403 error" | Check service account has "Vertex AI User" role |
| "Empty OCR text" | Fax may be too low quality — check `hipaa_local/split_pages/` |
| Low confidence results | Add more keywords to `gemini_classifier.py` prompt |
