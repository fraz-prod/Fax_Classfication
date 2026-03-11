"""
verify_setup.py
================
Run this BEFORE main.py to confirm everything is correctly configured.

Pipeline: ECW (Playwright) → PDF local → Mistral OCR (Ollama) → Vertex AI Gemini

Usage:
    python verify_setup.py

Expected output:
    ✅ Python 3.11+
    ✅ All packages installed
    ✅ Ollama running + mistral-small3.1 pulled
    ✅ GOOGLE_CLOUD_PROJECT_ID set
    ✅ Service account key file found
    ✅ Google credentials valid
    ✅ Vertex AI Gemini 1.5 Pro accessible
    🎉 All checks passed — ready to run main.py
"""

import sys
import os

print("\n" + "="*55)
print("   FAX AGENT — SETUP VERIFICATION")
print("="*55)

all_passed = True


def check(label, passed, detail=""):
    global all_passed
    icon = "✅" if passed else "❌"
    print(f"  {icon}  {label}")
    if not passed:
        all_passed = False
        if detail:
            print(f"       → {detail}")


# ── 1. Python version ─────────────────────────────────────
print("\n[ Python ]")
py_ok = sys.version_info >= (3, 11)
check(
    f"Python version: {sys.version.split()[0]}",
    py_ok,
    "Need Python 3.11 or higher — download from python.org"
)

# ── 2. Required packages ──────────────────────────────────
print("\n[ Required Packages ]")
packages = {
    "playwright":               "pip install playwright && playwright install chromium",
    "httpx":                    "pip install httpx",
    "openpyxl":                 "pip install openpyxl",
    "pypdf":                    "pip install pypdf",
    "fitz":                     "pip install PyMuPDF",
    "google.auth":              "pip install google-auth",
    "google.auth.transport":    "pip install google-auth-httplib2",
    "googleapiclient":          "pip install google-api-python-client",
}

for pkg, install_cmd in packages.items():
    try:
        __import__(pkg)
        check(f"{pkg} installed", True)
    except ImportError:
        check(f"{pkg} installed", False, f"Run: {install_cmd}")

# ── 3. Config file ────────────────────────────────────────
print("\n[ Config File ]")
try:
    import config
    check("config.py found", True)
except ImportError:
    check("config.py found", False, "config.py missing from project folder")
    print("\n❌ Cannot continue without config.py")
    sys.exit(1)

# ── 4. ECW credentials ────────────────────────────────────
print("\n[ ECW Configuration ]")
ecw_url_ok = (
    hasattr(config, 'ECW_URL') and
    config.ECW_URL not in ("https://YOUR-ECW-INSTANCE-URL-HERE.com", "", None)
)
ecw_user_ok = (
    hasattr(config, 'ECW_USERNAME') and
    config.ECW_USERNAME not in ("your_username", "", None)
)
ecw_pass_ok = (
    hasattr(config, 'ECW_PASSWORD') and
    config.ECW_PASSWORD not in ("your_password", "", None)
)
check("ECW_URL set in config.py", ecw_url_ok,
      "Fill in ECW_URL in config.py (your ECW web address)")
check("ECW_USERNAME set in config.py", ecw_user_ok,
      "Fill in ECW_USERNAME in config.py")
check("ECW_PASSWORD set in config.py", ecw_pass_ok,
      "Fill in ECW_PASSWORD in config.py")

# ── 5. Ollama + Mistral model ─────────────────────────────
print("\n[ Ollama (Local Mistral OCR) ]")
try:
    import httpx
    resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
    models = [m['name'] for m in resp.json().get('models', [])]
    check("Ollama server is running", True)

    model_name = getattr(config, 'MISTRAL_OCR_MODEL', 'mistral-small3.1')
    model_pulled = any(model_name in m for m in models)
    check(
        f"Model '{model_name}' is pulled",
        model_pulled,
        f"Run: ollama pull {model_name}   (takes ~5 min on first pull)"
    )
    if models:
        print(f"       Available models: {', '.join(models[:5])}")
except Exception as e:
    check("Ollama server is running", False,
          "Start Ollama: open the Ollama app, or run 'ollama serve' in a terminal")
    check(f"Model 'mistral-small3.1' is pulled", False,
          "Fix Ollama first, then run: ollama pull mistral-small3.1")

# ── 6. Google Vertex AI config ────────────────────────────
print("\n[ Google Vertex AI Configuration ]")
gcp_project_ok = (
    hasattr(config, 'GOOGLE_CLOUD_PROJECT_ID') and
    config.GOOGLE_CLOUD_PROJECT_ID not in ("your-gcp-project-id", "", None)
)
check("GOOGLE_CLOUD_PROJECT_ID set in config.py", gcp_project_ok,
      "Fill in GOOGLE_CLOUD_PROJECT_ID in config.py")

key_path = getattr(config, 'GOOGLE_APPLICATION_CREDENTIALS',
                   'config/google_service_account.json')
key_file_ok = os.path.exists(key_path)
check(
    f"Service account key file found: {key_path}",
    key_file_ok,
    f"Download JSON key from Google Cloud → save to {key_path}"
)

# ── 7. Live Vertex AI test ────────────────────────────────
if gcp_project_ok and key_file_ok:
    print("\n[ Google Vertex AI Live Test ]")
    try:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        import google.auth
        import google.auth.transport.requests

        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        check("Google credentials valid", True)

        # Test Vertex AI endpoint with a tiny request
        token = credentials.token
        location = getattr(config, 'GOOGLE_CLOUD_LOCATION', 'us-central1')
        url = (
            f"https://{location}-aiplatform.googleapis.com/v1/projects/"
            f"{config.GOOGLE_CLOUD_PROJECT_ID}/locations/{location}"
            f"/publishers/google/models/gemini-1.5-pro:generateContent"
        )
        test_payload = {
            "contents": [{"role": "user", "parts": [{"text": "Reply with one word: ready"}]}],
            "generationConfig": {"maxOutputTokens": 10}
        }
        resp = httpx.post(
            url,
            json=test_payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        if resp.status_code == 200:
            check("Vertex AI Gemini 1.5 Pro accessible", True)
        elif resp.status_code == 403:
            check("Vertex AI Gemini 1.5 Pro accessible", False,
                  "Permission denied — ensure service account has 'Vertex AI User' role")
        elif resp.status_code == 404:
            check("Vertex AI Gemini 1.5 Pro accessible", False,
                  "Project not found — check GOOGLE_CLOUD_PROJECT_ID in config.py")
        else:
            check("Vertex AI Gemini 1.5 Pro accessible", False,
                  f"HTTP {resp.status_code} — check GCP project and API enabled")

    except Exception as e:
        err = str(e)
        if "credentials" in err.lower():
            check("Google credentials valid", False,
                  "Invalid service account JSON — re-download from GCP console")
        else:
            check("Vertex AI connection", False, f"Error: {err[:80]}")
else:
    print("\n[ Google Vertex AI Live Test ]")
    print("  ⏭️  Skipped — fix Google config first")

# ── 8. Local folders ──────────────────────────────────────
print("\n[ Local HIPAA Folders ]")
folders = [
    "hipaa_local/raw_pdfs",
    "hipaa_local/split_pages",
    "hipaa_local/archive",
    "logs",
    "screenshots",
    "config",
]
for folder in folders:
    os.makedirs(folder, exist_ok=True)
    check(f"Folder exists: {folder}/", True)

# ── Final result ──────────────────────────────────────────
print("\n" + "="*55)
if all_passed:
    print("  🎉  All checks passed — ready to run main.py!")
else:
    print("  ⚠️  Some checks failed — fix the ❌ items above")
    print("     Then re-run: python verify_setup.py")
print("="*55 + "\n")
