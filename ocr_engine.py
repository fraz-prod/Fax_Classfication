"""
Local Mistral OCR
==================
HIPAA COMPLIANCE:
- Mistral model runs 100% LOCALLY via Ollama
- Zero data leaves your machine during OCR
- Supports handwritten faxes (like the handwritten lab cover sheet)

SETUP REQUIRED:
  1. Install Ollama: https://ollama.com/download
  2. Pull the vision model: ollama pull mistral-small3.1
  3. Ollama runs as a local server at http://localhost:11434

WHY MISTRAL FOR OCR:
- Handles typed AND handwritten medical fax text
- Runs on a standard Windows laptop (8GB+ RAM)
- No API key needed, no data leaves machine
"""

import base64
import json
import logging
import httpx
from pathlib import Path
import pypdf
import fitz  # PyMuPDF — converts PDF pages to images for vision model

log = logging.getLogger(__name__)

OLLAMA_URL    = "http://localhost:11434/api/generate"
MISTRAL_MODEL = "mistral-small3.1"   # Best local Mistral vision model

OCR_PROMPT = """You are a medical document OCR system.
Extract ALL text from this fax page exactly as it appears.
Include all typed and handwritten text.
Preserve section headers, labels, and values.
Do NOT summarize or interpret — just extract raw text.
Output plain text only."""


class LocalMistralOCR:
    def __init__(self):
        self._check_ollama_running()

    def _check_ollama_running(self):
        """Verify Ollama is running locally before starting"""
        try:
            response = httpx.get("http://localhost:11434/api/tags", timeout=5)
            models = [m['name'] for m in response.json().get('models', [])]
            if not any(MISTRAL_MODEL in m for m in models):
                log.warning(
                    f"Model '{MISTRAL_MODEL}' not found in Ollama.\n"
                    f"Run: ollama pull {MISTRAL_MODEL}"
                )
            else:
                log.info(f"Ollama running. Model '{MISTRAL_MODEL}' ready.")
        except Exception:
            log.error(
                "Ollama is NOT running!\n"
                "Start it with: ollama serve\n"
                "Then pull model: ollama pull mistral-small3.1"
            )

    def _pdf_page_to_base64_image(self, pdf_page_path: str) -> str:
        """
        Convert a single-page PDF to a base64 PNG image.
        Mistral vision model needs an image, not raw PDF bytes.
        Uses PyMuPDF (fitz) — runs entirely locally.
        """
        doc = fitz.open(pdf_page_path)
        page = doc[0]

        # Render at 2x resolution for better OCR accuracy on fax quality docs
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        doc.close()

        return base64.b64encode(img_bytes).decode("utf-8")

    def ocr_page(self, pdf_page_path: str) -> str:
        """
        Run local Mistral OCR on a single PDF page.
        Returns extracted text string.
        Data NEVER leaves the machine.
        """
        log.info(f"  Running local OCR on: {Path(pdf_page_path).name}")

        # Convert PDF page to image
        img_b64 = self._pdf_page_to_base64_image(pdf_page_path)

        # Send to local Ollama Mistral
        payload = {
            "model": MISTRAL_MODEL,
            "prompt": OCR_PROMPT,
            "images": [img_b64],
            "stream": False
        }

        try:
            response = httpx.post(
                OLLAMA_URL,
                json=payload,
                timeout=120.0  # OCR can take up to 2 min on first run
            )
            result = response.json()
            text = result.get("response", "").strip()
            log.info(f"  OCR complete. Extracted {len(text)} characters.")
            return text

        except Exception as e:
            log.error(f"  Local OCR failed: {e}")
            return ""

    def ocr_pages(self, pdf_page_paths: list[str]) -> str:
        """
        OCR multiple pages and combine into single text block.
        Returns combined text with page separators.
        """
        all_text = []

        for i, path in enumerate(pdf_page_paths):
            page_text = self.ocr_page(path)
            if page_text:
                all_text.append(f"--- PAGE {i+1} ---\n{page_text}")

        combined = "\n\n".join(all_text)
        log.info(f"  Total OCR text: {len(combined)} characters across {len(pdf_page_paths)} pages")
        return combined
