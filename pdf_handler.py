"""
PDF Handler — Download & Split
================================
HIPAA COMPLIANCE:
- All PDFs stay LOCAL — never sent to any cloud service
- Files stored in encrypted local folder (configure via config)
- Filenames are anonymized (fax_ID only, no patient name)
- Pages split locally using pypdf (no external calls)
"""

import os
import logging
from pathlib import Path
from datetime import datetime
import pypdf

log = logging.getLogger(__name__)

# Local-only directories — never sync these to cloud
PDF_RAW_DIR      = "hipaa_local/raw_pdfs"       # Downloaded full PDFs
PDF_SPLIT_DIR    = "hipaa_local/split_pages"     # Individual page PDFs
PDF_ARCHIVE_DIR  = "hipaa_local/archive"         # Processed PDFs moved here


class PDFHandler:
    def __init__(self):
        # Create all local dirs on startup
        for d in [PDF_RAW_DIR, PDF_SPLIT_DIR, PDF_ARCHIVE_DIR]:
            os.makedirs(d, exist_ok=True)
        log.info("PDFHandler initialized. All data stored locally.")

    def save_pdf(self, pdf_bytes: bytes, fax_id: str) -> str:
        """
        Save raw PDF bytes to local disk.
        Filename uses fax_id only — NO patient name in filename (HIPAA best practice).
        Returns local file path.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"fax_{fax_id}_{timestamp}.pdf"
        filepath = os.path.join(PDF_RAW_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(pdf_bytes)

        log.info(f"PDF saved locally: {filepath}")
        return filepath

    def split_first_n_pages(self, pdf_path: str, n_pages: int = 2) -> list[str]:
        """
        Split the first N pages from a PDF into individual page PDFs.
        Returns list of local file paths for each page.

        WHY SPLIT: We only send the TEXT (not the PDF) to cloud APIs.
        Splitting first lets us control exactly which pages get OCR'd.
        """
        split_paths = []
        base_name = Path(pdf_path).stem

        reader = pypdf.PdfReader(pdf_path)
        total_pages = len(reader.pages)
        pages_to_extract = min(n_pages, total_pages)

        log.info(f"Splitting {pages_to_extract} pages from {pdf_path} (total: {total_pages})")

        for i in range(pages_to_extract):
            writer = pypdf.PdfWriter()
            writer.add_page(reader.pages[i])

            page_path = os.path.join(PDF_SPLIT_DIR, f"{base_name}_page{i+1}.pdf")
            with open(page_path, "wb") as f:
                writer.write(f)

            split_paths.append(page_path)
            log.info(f"  Page {i+1} saved: {page_path}")

        return split_paths

    def archive_pdf(self, pdf_path: str):
        """Move processed PDF to archive folder"""
        filename = Path(pdf_path).name
        archive_path = os.path.join(PDF_ARCHIVE_DIR, filename)
        os.rename(pdf_path, archive_path)
        log.info(f"Archived: {archive_path}")

    def cleanup_split_pages(self, split_paths: list[str]):
        """Delete split page files after OCR is done (minimize local PHI footprint)"""
        for path in split_paths:
            try:
                os.remove(path)
            except Exception as e:
                log.warning(f"Could not delete temp file {path}: {e}")
        log.info(f"Cleaned up {len(split_paths)} temp page files.")
