"""
constants.py
============
All ECW UI selectors and timeout values in one place.

HOW TO FIND SELECTORS:
  1. Open ECW in Chrome, right-click an element -> Inspect
  2. In DevTools, right-click highlighted HTML -> Copy -> Copy selector
  3. Update any remaining <- INSPECT values below

Selectors marked [rishav] are confirmed from rishav_files.
Selectors marked <- INSPECT are placeholders you MUST update.
"""


class Timeouts:
    """Timeout values in seconds"""
    DEFAULT_WAIT    = 15    # General element wait
    LOGIN           = 30    # Login page load
    FAX_INBOX       = 20    # Fax inbox load
    PDF_PREVIEW     = 15    # PDF iframe appearance
    CLOUDFLARE      = 60    # Cloudflare bypass max wait
    DIALOG          = 10    # Dialog / modal appearance


class LoginPageSelectors:
    """
    ECW V12 login page selectors.

    All fields are element IDs — LoginPage adds '#' prefix.

    Confirmed via live DOM dump:
      - Username: <input id="doctorID">
      - Next: <input type="submit" id="nextStep" value="Next">
      - Password: <input type="password" id="passwordField">
      - Login: <input type="submit" id="Login">
    """
    USERNAME_FIELD  = "doctorID"                    # [live] ID — # added by LoginPage
    NEXT_BUTTON     = "nextStep"                    # [live] ID — # added by LoginPage
    PASSWORD_FIELD  = "passwordField"               # [live] ID — # added by LoginPage
    LOGIN_BUTTON    = "Login"                       # [live] ID — # added by LoginPage


class NavigationPageSelectors:
    """Post-login navigation elements"""

    # Dashboard hamburger menu — confirms login succeeded  [rishav]
    HAMBURGER_MENU  = "#hamburgerMenu"

    # Floating jellybean button that opens the fax/inbox dropdown
    JELLYBEAN_BUTTON = ".floating-button-container .floating-button svg"

    # "Fax Inbox - Web Mode" menu item in the dropdown
    FAX_INBOX_ITEM  = "text=Fax Inbox - Web Mode"

    # Date picker input in the fax inbox                    <- INSPECT
    DATE_INPUT      = "input[name='faxDate']"

    # Each fax row in the inbox table                       <- INSPECT
    FAX_ROW         = "tr.fax-row"

    # The PDF preview iframe                                <- INSPECT
    FAX_PREVIEW     = "iframe#faxPreview"


class StaffDialogSelectors:
    """'Send To Staff' dialog elements"""
    # Person/send icon on the highlighted fax row
    SEND_ICON       = "tr.fax-row.selected .send-staff-icon"    # <- INSPECT
    # Dialog container
    DIALOG          = ".send-to-staff-dialog"                   # <- INSPECT
    # Staff name search input
    SEARCH_INPUT    = ".send-to-staff-dialog input[type='text']"# <- INSPECT
    # Autocomplete dropdown items
    DROPDOWN_ITEM   = ".autocomplete-dropdown li"               # <- INSPECT
    # OK button
    OK_BUTTON       = ".send-to-staff-dialog button:has-text('Ok')"   # <- INSPECT
    # Cancel button
    CANCEL_BUTTON   = ".send-to-staff-dialog button:has-text('Cancel')" # <- INSPECT
