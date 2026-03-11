"""
Configuration File
==================
Fill in your credentials and ECW selectors here.

HOW TO FIND SELECTORS:
1. Open ECW in Chrome
2. Right-click on any element → "Inspect"
3. In DevTools, right-click the highlighted HTML → Copy → Copy selector
4. Paste it below
"""

# ─────────────────────────────────────────────
# GOOGLE VERTEX AI  (HIPAA — covered under BAA)
# ─────────────────────────────────────────────
# Sign BAA first: console.cloud.google.com → IAM → Data Protection
GOOGLE_CLOUD_PROJECT_ID  = "your-gcp-project-id"       # ← Replace with your GCP project ID
GOOGLE_CLOUD_LOCATION    = "us-central1"                # Region (keep us-central1 for best Gemini support)
GOOGLE_APPLICATION_CREDENTIALS = "config/google_service_account.json"  # ← Path to your service account key

# ─────────────────────────────────────────────
# LOCAL MISTRAL OCR  (runs 100% on your machine)
# ─────────────────────────────────────────────
# Install: https://ollama.com/download
# Then run: ollama pull mistral-small3.1
OLLAMA_HOST        = "http://localhost:11434"
MISTRAL_OCR_MODEL  = "mistral-small3.1"
ECW_URL = "https://YOUR-ECW-INSTANCE-URL-HERE.com"   # ← Replace with your ECW URL
ECW_USERNAME = "your_username"                         # ← Replace with your username
ECW_PASSWORD = "your_password"                         # ← Replace with your password
ECW_DATE_FORMAT = "%m/%d/%Y"                           # Date format ECW expects


# ─────────────────────────────────────────────
# ECW SELECTORS  (update after inspecting ECW)
# ─────────────────────────────────────────────

# The "D" icon on the top right navigation bar
SELECTOR_ICON_D = "#iconD"  # ← Inspect and replace

# "Fax Inbox Web Mode" menu item in the dropdown
SELECTOR_FAX_INBOX_MENU_ITEM = "text=Fax Inbox Web Mode"

# Date picker input field in fax inbox
SELECTOR_DATE_INPUT = "input[name='faxDate']"  # ← Inspect and replace

# Each fax row in the inbox list
SELECTOR_FAX_ROW = "tr.fax-row"  # ← Inspect and replace

# The PDF preview panel / iframe
SELECTOR_FAX_PREVIEW = "iframe#faxPreview"  # ← Inspect and replace

# ── Send To Staff Dialog ──────────────────────────────────────────────────────

# The person/send icon that appears on the right side of each fax row
# (the blue person icon visible in the screenshot)
SELECTOR_SEND_TO_STAFF_ICON = "tr.fax-row.selected .send-staff-icon"  # ← Inspect and replace

# The 'Send To Staff' dialog container (appears after clicking the icon)
SELECTOR_STAFF_DIALOG = ".send-to-staff-dialog"  # ← Inspect and replace

# The Staff search input box inside the dialog
SELECTOR_STAFF_SEARCH_INPUT = ".send-to-staff-dialog input[type='text']"  # ← Inspect and replace

# Autocomplete dropdown items that appear after typing in the search box
SELECTOR_STAFF_DROPDOWN_ITEM = ".autocomplete-dropdown li"  # ← Inspect and replace

# OK button inside the dialog
SELECTOR_STAFF_DIALOG_OK = ".send-to-staff-dialog button:has-text('Ok')"  # ← Inspect and replace

# Cancel button inside the dialog
SELECTOR_STAFF_DIALOG_CANCEL = ".send-to-staff-dialog button:has-text('Cancel')"  # ← Inspect and replace


# ─────────────────────────────────────────────
# CATEGORY → FOLDER MAPPING
# Map AI category names to exact folder names in ECW's right-click menu
# ─────────────────────────────────────────────
CATEGORY_TO_FOLDER = {
    "BIOLOGICS":        "Group Biologics",
    "PRIOR_AUTH":       "Group PA",
    "LABS":             "Group Labs",
    "MEDICAL_RECORDS":  "Group Medical Records",
    "MEDICATION_AND_IT":"Group MA",
    "RADIOLOGY":        "Group Radiology",
    "UNKNOWN":          None  # Will trigger manual review
}
