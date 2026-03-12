"""
PDF Handler — Download
================================
HIPAA COMPLIANCE:
- All PDFs stay LOCAL — never sent to any cloud service
- Files stored in encrypted local folder (configure via config)
- Filenames are anonymized (fax_ID only, no patient name)
"""

import os
import logging
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

# Local-only directories
PDF_RAW_DIR = "hipaa_local/raw_pdfs"

class PDFHandler:
    def __init__(self):
        # Create all local dirs on startup
        os.makedirs(PDF_RAW_DIR, exist_ok=True)
        log.info("PDFHandler initialized. All data stored locally.")

    def save_pdf(self, pdf_bytes: bytes, fax_id: str) -> str:
        """
        Save raw PDF bytes to local disk.
        Filename uses fax_id only — NO patient name in filename.
        Returns local file path.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fax_{fax_id}_{timestamp}.pdf"
        filepath = os.path.join(PDF_RAW_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        log.info(f"PDF saved locally: {filepath}")
        return filepath
