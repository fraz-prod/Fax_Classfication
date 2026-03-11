"""
Gemini Classifier via Vertex AI
=================================
HIPAA COMPLIANCE:
- Uses Vertex AI (NOT Google AI Studio / generativelanguage API)
- Vertex AI is covered under Google Cloud BAA
- Only PLAIN TEXT (OCR output) is sent — no images, no raw PDFs
- PHI in OCR text is still present but covered under your BAA

SETUP REQUIRED:
  1. Enable Vertex AI API in Google Cloud Console
  2. Create a service account with "Vertex AI User" role
  3. Download service account JSON key
  4. Set path in config.py → GOOGLE_APPLICATION_CREDENTIALS
  5. Sign BAA: console.cloud.google.com → IAM → Data Protection

WHY VERTEX AI (not AI Studio):
- AI Studio has NO BAA → HIPAA violation
- Vertex AI has BAA → HIPAA compliant
- Same Gemini models, different endpoint
"""

import json
import logging
import os
import httpx
import google.auth
import google.auth.transport.requests

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# CLASSIFICATION PROMPT
# Built from real fax examples across all 6 categories.
# Designed for Gemini 1.5 Pro receiving OCR-extracted text.
# ──────────────────────────────────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """
You are a medical fax classification agent for a specialty allergy and asthma healthcare clinic.

Your job is to read OCR-extracted text from an incoming fax and classify it into EXACTLY ONE
of the six categories below. Follow the rules strictly and return only valid JSON.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY 1: BIOLOGICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESCRIPTION:
  Faxes related to biologic medications — including prescriptions, refill requests,
  treatment authorization, patient consent forms, infusion therapy documentation,
  and copay assistance forms from biologic specialty providers.

DRUG NAME KEYWORDS (any one of these = BIOLOGICS):
  Xolair, Nucala, Tezspire, Dupixent, Fasenra, Renvoque, Rapsido, Ebglyss,
  Advry, Nemluvio, Andembry, Berinert, Dawnzera, Ekterly, Firazyr, Haegarda,
  Icatibant, Orladeyo, Ruconest, Sajazir, Takhzyro

SENDER/COMPANY KEYWORDS:
  Altus Biologics, Empower Patient Services, Optime Care, specialty pharmacy,
  infusion center, biologics provider

DOCUMENT TYPE KEYWORDS:
  biologic therapy, infusion therapy, Refill Request Form (when drug is a biologic),
  Patient Consent for infusion, Consent to Treatment, Authorization to Communicate
  Protected Health Information, Copay Assistance, biologic prescription

REAL EXAMPLE SIGNALS SEEN IN YOUR FAXES:
  - "Orladeyo Capsule 150 MG" → BIOLOGICS
  - "Altus Biologics" letterhead with "Consent for Infusion Therapy" → BIOLOGICS
  - "Tezspire" written in consent form → BIOLOGICS
  - "Empower Patient Services" sending a refill request for a biologic drug → BIOLOGICS
  - "Copay Assistance" form from a biologics company → BIOLOGICS
  - "biologic therapy prescribed by your physician" → BIOLOGICS

RULE: If ANY biologic drug name is present, classify as BIOLOGICS — even if the
      document is also a refill request, consent form, or prior auth form.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY 2: PRIOR_AUTH
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESCRIPTION:
  Faxes requesting or following up on insurance prior authorization (PA) for
  medications or treatments. Includes both pharmacy-initiated and insurer-initiated
  PA requests, CoverMyMeds follow-ups, and Medicaid PA forms.

PLATFORM KEYWORDS (any one = PRIOR_AUTH):
  CoverMyMeds, Cover My Meds, go.covermymeds.com, Albertsons, Albertsons Pharmacy

DOCUMENT TYPE KEYWORDS:
  Prior Authorization, Prior Auth, PA Request, Authorization Request,
  Insurance Authorization, Pharmacy Prior Authorization Form,
  Prior Authorization Follow Up, Prior Authorization Assistance

CONTENT KEYWORDS:
  pharmacy claim rejected, requires prior authorization, claim denied,
  complete the PA, Send to Plan, authorization key, patient waiting for medication,
  Colorado Medicaid Prior Authorization, Medicaid ID

REAL EXAMPLE SIGNALS SEEN IN YOUR FAXES:
  - "CoverMyMeds Prior Authorization Follow Up" header → PRIOR_AUTH
  - "Pharmacy claim for Fluticasone-Salmeterol has been rejected and requires prior authorization" → PRIOR_AUTH
  - "Colorado Department of Health Care Policy & Financing — Pharmacy Prior Authorization Form" → PRIOR_AUTH
  - "Key: BBDT4KEL / Patient Last Name: Carrazco / DOB: 07/21/2015" (CoverMyMeds key format) → PRIOR_AUTH
  - "Complete the PA and click Send to Plan for approval" → PRIOR_AUTH
  - Albertsons or SAV-ON pharmacy sending a PA request → PRIOR_AUTH

RULE: ANY fax from CoverMyMeds platform → always PRIOR_AUTH regardless of drug name.
RULE: A PA form for a biologic drug → PRIOR_AUTH (not BIOLOGICS), unless the fax
      is a prescription/refill/consent — PA forms are always PRIOR_AUTH.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY 3: LABS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESCRIPTION:
  Faxes containing laboratory test orders or laboratory test results, including
  allergy panels, blood work, immunoglobulin levels, and other diagnostic tests.

LAB COMPANY KEYWORDS (any one = LABS):
  LabCorp, LABCORP, Labcorp, UCHealth Laboratories, UCHealth Labs,
  Harmony Lab, Quest Diagnostics, ARUP Laboratories

DOCUMENT TYPE KEYWORDS:
  Patient Report, Lab Report, Clinical Laboratory Results, Final Report,
  Lab Order, Laboratory Order, Lab Results, Specimen Report

TEST TYPE KEYWORDS:
  CBC, CBC With Differential, IgE, Immunoglobulin E, Immunoglobulin G,
  Tryptase, Platelet, WBC, RBC, Hemoglobin, Hematocrit,
  IgE Peanut, IgE Egg, IgE Milk, IgE Almond, IgE Walnut (allergy panels),
  blood test, specimen, venipuncture, serum

CONTENT KEYWORDS:
  Ordering Physician, Specimen ID, Date Collected, Date Received,
  Date Reported, Reference Interval, Current Result and Flag,
  Abnormal, High, Low, Out of Reference Range

REAL EXAMPLE SIGNALS SEEN IN YOUR FAXES:
  - "FROM:LABCORP LCLS BULK TO:+13032322967" in fax header → LABS
  - LabCorp logo with "Patient Report" and CBC results table → LABS
  - "Immunoglobulin E, Total: 463 IU/mL" → LABS
  - IgE allergy panel (IgE Peanut, IgE Egg White, IgE Milk etc.) → LABS
  - UCHealth Laboratories with "Clinical Laboratory Results — IgE Final result" → LABS
  - Harmony Lab sending immunoglobulin E result → LABS
  - Handwritten fax cover page followed by UCHealth lab result page → LABS
    (NOTE: always read beyond cover page — lab result may be on page 2 or 3)

RULE: If fax header shows FROM:LABCORP → always LABS.
RULE: If ANY lab company name appears with test results → LABS.
RULE: Handwritten cover pages forwarding lab results → still LABS (check all pages).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY 4: MEDICAL_RECORDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESCRIPTION:
  Faxes containing patient medical records, clinical notes, patient history,
  or requests for patient chart information.

DOCUMENT TYPE KEYWORDS:
  Medical Record, Medical Records, Patient Record, Patient Records,
  Progress Notes, Progress Note, Chart Note, Patient Chart,
  Chart Note Request, Clinical Summary, Discharge Summary,
  Visit Notes, Encounter Notes, SOAP Notes, History and Physical

CONTENT KEYWORDS:
  patient history, chief complaint, assessment and plan, diagnosis,
  review of systems, physical examination, past medical history,
  medications list, allergies list, referral notes, transfer summary

REQUEST KEYWORDS:
  Request for Medical Records, Please send records, Records Release,
  Authorization for Release, HIPAA Authorization for Records

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY 5: MEDICATION_AND_IT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESCRIPTION:
  Faxes related to non-biologic medication refills, general medication orders,
  IT (Immunotherapy) transfer requests, Colorado Allergy and Anaphylaxis forms,
  and Emergency Care Plans. This is the "general medication" category — for
  everyday medications NOT classified as biologics.

DOCUMENT TYPE KEYWORDS:
  Medication Refill, Refill Request, Medication Order, Rx Refill,
  IT Transfer, Immunotherapy Transfer, Transfer Request,
  Colorado Allergy and Anaphylaxis, Emergency Care Plan,
  Anaphylaxis Action Plan, Allergy Action Plan,
  EpiPen Order, Epinephrine Order (when NOT a PA form)

CONTENT KEYWORDS:
  please refill, refill authorization, authorize this refill,
  additional refills, do not refill, discontinue order,
  immunotherapy vials, allergy shots, allergy injection,
  transfer patient care, transfer of care

RULE: Refill request for a NON-biologic drug (e.g., regular antihistamine,
      inhaler, EpiPen) → MEDICATION_AND_IT.
RULE: EpiPen / Epinephrine refill request (not a PA form) → MEDICATION_AND_IT.
RULE: If drug is a biologic (see Category 1 drug list) → BIOLOGICS, not this category.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CATEGORY 6: RADIOLOGY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DESCRIPTION:
  Faxes related to imaging orders or radiology results including CT scans,
  MRIs, X-rays, and ultrasounds.

DOCUMENT TYPE KEYWORDS:
  Radiology Report, Imaging Order, Radiology Order, Imaging Request,
  Imaging Results, Radiology Results

SCAN TYPE KEYWORDS:
  MRI, CT Scan, CT, PET Scan, X-Ray, Ultrasound, Echocardiogram,
  Chest X-Ray, Abdominal CT, Sinus CT, Pulmonary CT,
  DEXA Scan, Bone Density Scan

CONTENT KEYWORDS:
  radiologist, imaging center, impression, findings, contrast,
  axial slices, DICOM, order radiology, radiology requisition

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PRIORITY TIEBREAKER RULES (when fax matches multiple categories)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Apply these rules IN ORDER when a fax could match more than one category:

  RULE 1 — BIOLOGICS DRUG NAME WINS:
    If ANY biologic drug name from Category 1 list appears anywhere in the
    fax text (including refill forms, consent forms, PA forms) → BIOLOGICS.
    Exception: CoverMyMeds PA platform faxes → always PRIOR_AUTH.

  RULE 2 — COVERMYMEDS PLATFORM WINS FOR PA:
    If fax is FROM the CoverMyMeds platform (header says "Prior Authorization
    Assistance by CoverMyMeds" or "go.covermymeds.com") → PRIOR_AUTH always.

  RULE 3 — LAB COMPANY HEADER WINS FOR LABS:
    If fax transmission header contains "FROM:LABCORP" or body has LabCorp /
    UCHealth Laboratories logo → LABS, even if cover page is handwritten.

  RULE 4 — READ BEYOND THE COVER PAGE:
    A handwritten or blank cover page does NOT determine category.
    Always classify based on the CONTENT pages (page 2, page 3).

  RULE 5 — SENDER CONTEXT FOR AMBIGUOUS FAXES:
    "Empower Patient Services" or "Optime Care" → likely BIOLOGICS.
    "Albertsons Pharmacy" or "SAV-ON Pharmacy" → likely PRIOR_AUTH.
    Any allergy/asthma clinic cover page forwarding lab results → LABS.

  RULE 6 — REFILL FOR NON-BIOLOGIC = MEDICATION_AND_IT:
    Refill Request Form for a drug NOT on the biologic list → MEDICATION_AND_IT.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REAL EXAMPLES FROM YOUR CLINIC (use these as reference)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ✅ "Orladeyo Capsule 150mg Refill Request" from Empower Patient Services
     → BIOLOGICS (Orladeyo is a biologic drug)

  ✅ "Altus Biologics — Patient Consent for Tezspire Infusion"
     → BIOLOGICS (biologic company + biologic drug Tezspire)

  ✅ "CoverMyMeds Prior Authorization Follow Up — EPINEPHrine 0.15MG"
     → PRIOR_AUTH (CoverMyMeds platform, even though drug is EpiPen)

  ✅ "Colorado Dept of Health Care — Pharmacy Prior Authorization Form — EPINEPHrine"
     → PRIOR_AUTH (PA form, even though drug is EpiPen not a biologic)

  ✅ "FROM:LABCORP — Patient Report — CBC With Differential — IgE Panel"
     → LABS (LabCorp sender, lab results)

  ✅ "Centennial Clinic handwritten cover + UCHealth Laboratories IgE result"
     → LABS (lab result on page 3 overrides blank cover page)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — respond ONLY with this exact JSON, nothing else:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "category": "BIOLOGICS",
  "confidence": "HIGH",
  "reason": "One sentence explaining the top reason for this classification",
  "key_signals": ["signal 1", "signal 2", "signal 3"]
}

category options : BIOLOGICS | PRIOR_AUTH | LABS | MEDICAL_RECORDS | MEDICATION_AND_IT | RADIOLOGY
confidence options: HIGH (obvious match) | MEDIUM (likely match) | LOW (uncertain, needs review)
key_signals: list of 2-4 exact words/phrases from the fax text that triggered this classification

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FAX TEXT TO CLASSIFY:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


class GeminiClassifier:
    def __init__(self, project_id: str, location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.model = "gemini-1.5-pro"
        self.endpoint = (
            f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}"
            f"/locations/{location}/publishers/google/models/{self.model}:generateContent"
        )
        # Load credentials from service account key file
        os.environ.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS",
            "config/google_service_account.json"  # ← path to your key file
        )

    def _get_access_token(self) -> str:
        """Get short-lived access token from service account credentials"""
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return credentials.token

    async def classify(self, ocr_text: str) -> dict:
        """
        Send OCR text to Vertex AI Gemini for classification.
        Only plain text is transmitted — no images, no raw PDFs.
        Covered under Google Cloud BAA.
        """
        if not ocr_text.strip():
            return {
                "category": "UNKNOWN",
                "confidence": "LOW",
                "reason": "Empty OCR text — could not extract content from fax",
                "key_signals": []
            }

        prompt = CLASSIFICATION_PROMPT + ocr_text

        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,      # Low temp = consistent classification
                "maxOutputTokens": 512,
                "responseMimeType": "application/json"
            }
        }

        try:
            token = self._get_access_token()

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    }
                )

            if response.status_code != 200:
                log.error(f"Vertex AI error: {response.status_code} — {response.text}")
                return {
                    "category": "UNKNOWN",
                    "confidence": "LOW",
                    "reason": f"Vertex AI API error: {response.status_code}",
                    "key_signals": []
                }

            data = response.json()
            raw_text = (
                data.get("candidates", [{}])[0]
                    .get("content", {})
                    .get("parts", [{}])[0]
                    .get("text", "")
                    .strip()
            )

            # Parse JSON response
            clean = raw_text.replace("```json", "").replace("```", "").strip()
            result = json.loads(clean)
            log.info(f"  Gemini classified as: {result.get('category')} ({result.get('confidence')})")
            return result

        except json.JSONDecodeError:
            log.error(f"Could not parse Gemini response: {raw_text}")
            return {
                "category": "UNKNOWN",
                "confidence": "LOW",
                "reason": "Could not parse AI response",
                "key_signals": []
            }
        except Exception as e:
            log.error(f"Gemini classification error: {e}")
            return {
                "category": "UNKNOWN",
                "confidence": "LOW",
                "reason": str(e),
                "key_signals": []
            }
