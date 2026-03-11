"""
Fax Classification Pipeline
=============================
Full flow:
  PDF (local) → Split pages → Local Mistral OCR → Vertex AI Gemini → Category

HIPAA Data Flow:
  ┌─────────────────────────────────────────────────────┐
  │  YOUR MACHINE (local, HIPAA safe)                   │
  │  ECW → PDF saved → Pages split → Mistral OCR       │
  └─────────────────────────┬───────────────────────────┘
                            │ Plain text ONLY (no PHI images)
                            ▼
  ┌─────────────────────────────────────────────────────┐
  │  GOOGLE VERTEX AI (covered under BAA)               │
  │  OCR text → Gemini 1.5 Pro → Category JSON         │
  └─────────────────────────────────────────────────────┘
"""

import asyncio
import logging
from pdf_handler import PDFHandler
from ocr_engine import LocalMistralOCR
from gemini_classifier import GeminiClassifier
import config

log = logging.getLogger(__name__)


class FaxClassificationPipeline:
    def __init__(self):
        self.pdf_handler   = PDFHandler()
        self.ocr_engine    = LocalMistralOCR()
        self.classifier    = GeminiClassifier(
            project_id=config.GOOGLE_CLOUD_PROJECT_ID,
            location=config.GOOGLE_CLOUD_LOCATION
        )
        log.info("Fax Classification Pipeline ready.")

    async def process_fax(self, fax_id: str, pdf_bytes: bytes) -> dict:
        """
        Full pipeline for a single fax.
        Returns classification result dict.

        Steps:
          1. Save PDF locally (anonymized filename)
          2. Split first 2 pages
          3. Local Mistral OCR on each page
          4. Send combined OCR text to Vertex AI Gemini
          5. Return category + confidence + reason
          6. Cleanup temp files
        """
        log.info(f"\n{'='*50}")
        log.info(f"Processing fax: {fax_id}")
        log.info(f"{'='*50}")

        split_paths = []

        try:
            # ── Step 1: Save PDF locally ──────────────────────────────
            log.info("Step 1: Saving PDF locally...")
            pdf_path = self.pdf_handler.save_pdf(pdf_bytes, fax_id)

            # ── Step 2: Split first 2 pages ───────────────────────────
            log.info("Step 2: Splitting pages...")
            split_paths = self.pdf_handler.split_first_n_pages(pdf_path, n_pages=2)

            if not split_paths:
                log.error("No pages extracted from PDF!")
                return self._error_result(fax_id, "Could not split PDF pages")

            # ── Step 3: Local Mistral OCR ─────────────────────────────
            log.info("Step 3: Running local Mistral OCR (data stays on machine)...")
            ocr_text = self.ocr_engine.ocr_pages(split_paths)

            if not ocr_text.strip():
                log.warning("OCR returned empty text — fax may be blank or unreadable")

            # ── Step 4: Gemini Classification (Vertex AI / BAA) ───────
            log.info("Step 4: Sending OCR text to Vertex AI Gemini for classification...")
            result = await self.classifier.classify(ocr_text)

            # ── Step 5: Add metadata ──────────────────────────────────
            result['fax_id']   = fax_id
            result['ocr_text'] = ocr_text[:500] + "..." if len(ocr_text) > 500 else ocr_text

            log.info(f"✅ Result: {result['category']} | {result['confidence']}")
            log.info(f"   Reason: {result['reason']}")
            log.info(f"   Signals: {result.get('key_signals', [])}")

            # ── Step 6: Archive PDF, cleanup split pages ──────────────
            self.pdf_handler.cleanup_split_pages(split_paths)
            self.pdf_handler.archive_pdf(pdf_path)

            return result

        except Exception as e:
            log.error(f"Pipeline error for fax {fax_id}: {e}", exc_info=True)
            # Cleanup on error
            self.pdf_handler.cleanup_split_pages(split_paths)
            return self._error_result(fax_id, str(e))

    async def process_batch(self, fax_batch: list[dict]) -> list[dict]:
        """
        Process a batch of faxes sequentially.
        Each item in fax_batch: {"fax_id": str, "pdf_bytes": bytes}
        """
        results = []
        total = len(fax_batch)

        for i, fax in enumerate(fax_batch):
            log.info(f"\nBatch progress: {i+1}/{total}")
            result = await self.process_fax(fax["fax_id"], fax["pdf_bytes"])
            results.append(result)

        log.info(f"\nBatch complete. Processed {len(results)} faxes.")
        return results

    def _error_result(self, fax_id: str, reason: str) -> dict:
        return {
            "fax_id": fax_id,
            "category": "UNKNOWN",
            "confidence": "LOW",
            "reason": reason,
            "key_signals": [],
            "action": "MANUAL REVIEW"
        }
