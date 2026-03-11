"""
⚠️  LEGACY FILE — NOT USED IN THE ACTIVE PIPELINE ⚠️
======================================================
This was an early version that used Claude AI (Anthropic API) with
fax screenshots. It is NOT HIPAA-compliant as-is (no BAA with Anthropic).

The active classifier is: gemini_classifier.py
  - Uses Vertex AI (Gemini 1.5 Pro) — covered under Google Cloud BAA
  - Sends OCR plain text only (no images, no raw PDFs)

This file is kept for reference only. Do NOT import or use it.
"""

# Fax Classifier (Legacy — Claude AI / Anthropic)
# See gemini_classifier.py for the current HIPAA-compliant version.

import base64
import json
import logging
import httpx

log = logging.getLogger(__name__)

# The classification prompt — built from your PRD
SYSTEM_PROMPT = """You are a medical fax classification agent for a healthcare clinic.
Your job is to read fax images and classify them into exactly ONE of these categories:

1. BIOLOGICS — Faxes about biologic medications. Keywords: Xolair, Nucala, Tezspire, Dupixent, Fasenra, Renvoque, Rapsido, Ebglyss, Advry, Nemluvio, Andembry, Berinert, Dawnzera, Ekterly, Firazyr, Haegarda, Icatibant, Orladeyo, Ruconest, Sajazir, Takhzyro

2. PRIOR_AUTH — Prior authorization requests. Keywords: Prior Authorization, Authorization Request, Insurance Authorization, PA Request, Cover My Meds

3. LABS — Lab orders or lab results. Keywords: Lab, Lab Order, LabCorp, blood test, diagnostic test

4. MEDICAL_RECORDS — Patient history, medical records, progress notes. Keywords: Medical Record, Patient Record, Progress Notes, Chart Note

5. MEDICATION_AND_IT — Medication refills, medication orders, IT transfer requests. Keywords: Refill Request, Medication Order, IT Transfer, Colorado Allergy and Anaphylaxis, Emergency Care Plan

6. RADIOLOGY — Imaging requests. Keywords: MRI, CT Scan, Ultrasound, Radiology, Imaging Order

IMPORTANT RULES:
- If a fax contains a biologic drug name (like Orladeyo), classify as BIOLOGICS even if it is also a refill request
- If you are unsure, pick the best match and set confidence to LOW
- Never return more than one category

Respond ONLY with valid JSON in this exact format:
{
  "category": "BIOLOGICS",
  "confidence": "HIGH",
  "reason": "Fax contains Orladeyo prescription refill request from Empower Patient Services"
}

Confidence levels: HIGH (very clear), MEDIUM (likely), LOW (uncertain)"""


class FaxClassifier:
    def __init__(self):
        self.api_url = "https://api.anthropic.com/v1/messages"

    def _encode_image(self, image_path: str) -> str:
        """Convert image file to base64 string"""
        with open(image_path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")

    async def classify(self, screenshot_paths: list) -> dict:
        """
        Send fax screenshots to Claude and get classification back.
        Returns dict with category, confidence, reason.
        """
        # Build image content blocks (up to 2 pages)
        content = []

        for i, path in enumerate(screenshot_paths[:2]):  # Max 2 pages
            image_data = self._encode_image(path)
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_data
                }
            })
            content.append({
                "type": "text",
                "text": f"Page {i+1} of the fax is shown above."
            })

        content.append({
            "type": "text",
            "text": "Please classify this fax based on the pages shown. Return only JSON."
        })

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1000,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": content}
            ]
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

        if response.status_code != 200:
            log.error(f"Claude API error: {response.status_code} — {response.text}")
            return {
                "category": "UNKNOWN",
                "confidence": "LOW",
                "reason": f"API error: {response.status_code}"
            }

        data = response.json()
        raw_text = data["content"][0]["text"].strip()

        # Parse the JSON response
        try:
            # Strip markdown code fences if present
            clean = raw_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            return result
        except json.JSONDecodeError:
            log.error(f"Could not parse Claude response: {raw_text}")
            return {
                "category": "UNKNOWN",
                "confidence": "LOW",
                "reason": "Could not parse AI response"
            }
