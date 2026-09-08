"""
End-to-end API tests for CaseFill-AI.
Tests the full FSO intake flow: auth → create case → upload docs → extract → cross-check → submit → verify.

Run with:  python -m pytest tests/test_e2e.py -v -s
  or:       python tests/test_e2e.py
"""

import json
import os
import sys
import time
from pathlib import Path

import httpx

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
SAMPLE_DOCS_DIR = Path(__file__).parent.parent / "reference" / "original-prototype" / "sample docs"

# ── Helpers ──────────────────────────────────────────────────────────────────────

def ok(label: str):
    print(f"  ✅  {label}")

def fail(label: str, detail: str = ""):
    print(f"  ❌  {label}" + (f" — {detail}" if detail else ""))

def section(title: str):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


class CaseFillTester:
    def __init__(self):
        self.client = httpx.Client(base_url=BASE_URL, timeout=120.0)
        self.token = None
        self.user = None
        self.case_id = None
        self.case_number = None
        self.results = {"passed": 0, "failed": 0, "skipped": 0}
        self.extractions = {}  # doc_type → extracted data
        self.cross_checks = []

    def record(self, passed: bool, label: str, detail: str = ""):
        if passed:
            self.results["passed"] += 1
            ok(label)
        else:
            self.results["failed"] += 1
            fail(label, detail)

    def headers(self):
        h = {}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    # ── Step 1: Auth ─────────────────────────────────────────────────────────────

    def test_auth(self):
        section("1. AUTHENTICATION")

        # Health check
        r = self.client.get("/api/health")
        self.record(r.status_code == 200, "Backend health check", f"status={r.status_code}")

        # Sign in as FSO (Tariq Mehmood)
        r = self.client.post("/api/auth/signin", json={
            "cnic": "36302-9876543-1",
            "password": "password123",
        })
        self.record(r.status_code == 200, "FSO sign-in (Tariq Mehmood)", f"status={r.status_code}")

        if r.status_code == 200:
            data = r.json()
            self.token = data["token"]
            self.user = data["user"]
            self.record(self.user["role"] == "fso", f"User role is 'fso' (got '{self.user['role']}')")
            self.record(self.user["name"] == "Tariq Mehmood", f"User name correct: {self.user['name']}")
        else:
            print("  ⛔ Cannot continue without auth. Aborting.")
            sys.exit(1)

        # Verify session
        r = self.client.get("/api/auth/me", headers=self.headers())
        self.record(r.status_code == 200, "Session token valid (/api/auth/me)")

        # CAPTCHA
        r = self.client.get("/api/auth/captcha")
        self.record(r.status_code == 200, "CAPTCHA endpoint works")
        if r.status_code == 200:
            cap = r.json()
            self.record("svg" in cap and "<svg" in cap["svg"], "CAPTCHA returns valid SVG")

    # ── Step 2: Create Case ──────────────────────────────────────────────────────

    def test_create_case(self):
        section("2. CREATE CASE")

        r = self.client.post("/api/cases", json={"submission_source": "fso_manual"},
                             headers=self.headers())
        self.record(r.status_code == 200, "Create draft case", f"status={r.status_code}")

        if r.status_code == 200:
            data = r.json()
            self.case_id = data["case_id"]
            self.case_number = data["case_number"]
            self.record(data["status"] == "draft", f"Case status is 'draft'")
            self.record(self.case_number.startswith("OFSP-"), f"Case number format: {self.case_number}")
            ok(f"Case ID: {self.case_id}")
            ok(f"Case Number: {self.case_number}")
        else:
            print("  ⛔ Cannot continue without case. Aborting.")
            sys.exit(1)

        # Verify case details
        r = self.client.get(f"/api/cases/{self.case_id}", headers=self.headers())
        self.record(r.status_code == 200, "GET case details")
        if r.status_code == 200:
            case = r.json()
            doc_types = list(case.get("documents", {}).keys())
            self.record(len(doc_types) == 8, f"8 document slots created (got {len(doc_types)})")
            self.record(all(case["documents"][dt]["status"] == "empty" for dt in doc_types),
                        "All slots start as 'empty'")

    # ── Step 3: Upload & Extract Each Document ───────────────────────────────────

    def test_upload_and_extract(self):
        section("3. UPLOAD & EXTRACT DOCUMENTS")

        # Map sample docs to doc_types
        doc_uploads = [
            ("child_picture", "child_pic.png"),
            ("result_card", "test_result_card.png"),
            ("b_form", "test_bform.png"),
            ("death_certificate", "test_death_certificate.png"),
            ("mother_cnic", "test_mother_cnic.png"),
            ("father_cnic", "test_father_cnic.png"),
        ]

        for doc_type, filename in doc_uploads:
            print(f"\n  ── {doc_type} ({filename}) ──")
            filepath = SAMPLE_DOCS_DIR / filename

            if not filepath.exists():
                self.record(False, f"File exists: {filename}", "File not found")
                continue

            # Upload
            with open(filepath, "rb") as f:
                r = self.client.post(
                    f"/api/cases/{self.case_id}/documents",
                    data={"doc_type": doc_type},
                    files={"file": (filename, f, "image/png")},
                    headers=self.headers(),
                )
            upload_ok = r.status_code == 200
            self.record(upload_ok, f"Upload {doc_type}", f"status={r.status_code}" if not upload_ok else "")

            if not upload_ok:
                print(f"    Response: {r.text[:200]}")
                continue

            upload_data = r.json()
            self.record("image_url" in upload_data, f"Upload returns image_url: {upload_data.get('image_url')}")

            # Extract
            extract_body = {"doc_type": doc_type}
            if doc_type == "b_form":
                extract_body["target_child_serial_number"] = 1

            print(f"    ⏳ Running Qwen-VL extraction (this may take 10-30s)...")
            r = self.client.post(
                f"/api/cases/{self.case_id}/extract",
                json=extract_body,
                headers=self.headers(),
            )
            extract_ok = r.status_code == 200
            self.record(extract_ok, f"Extract {doc_type}", f"status={r.status_code}" if not extract_ok else "")

            if not extract_ok:
                print(f"    Response: {r.text[:300]}")
                continue

            ext_data = r.json()
            self.extractions[doc_type] = ext_data.get("extracted", {})

            # Verify model is Qwen-VL (not Gemini)
            model_used = ext_data.get("model", "unknown")
            is_qwen = "qwen" in model_used.lower()
            is_not_gemini = "gemini" not in model_used.lower()
            self.record(is_qwen, f"Model is Qwen-VL: {model_used}")
            self.record(is_not_gemini, f"NOT Gemini: {model_used}")

            # Verify extraction has data
            extracted = ext_data.get("extracted", {})
            has_data = len(extracted) > 0
            self.record(has_data, f"Extraction returned data ({len(extracted)} fields)")

            duration = ext_data.get("duration_ms", 0)
            ok(f"Duration: {duration}ms")

            # Show key extracted fields
            if doc_type == "child_picture":
                print(f"    quality_check: {extracted.get('quality_check')}")
            elif doc_type == "result_card":
                print(f"    child_name: {extracted.get('child_name')}")
                print(f"    school_name: {extracted.get('school_name')}")
                print(f"    class_grade: {extracted.get('class_grade')}")
            elif doc_type == "b_form":
                print(f"    crc_number: {extracted.get('crc_number')}")
                print(f"    father_name: {extracted.get('father_name')}")
                print(f"    father_cnic_number: {extracted.get('father_cnic_number')}")
                print(f"    mother_name: {extracted.get('mother_name')}")
                print(f"    mother_cnic_number: {extracted.get('mother_cnic_number')}")
                children = extracted.get("children", [])
                print(f"    children count: {len(children)}")
                for i, c in enumerate(children):
                    print(f"      [{i}] {c.get('child_name')} (serial={c.get('serial_number')})")
            elif doc_type == "death_certificate":
                print(f"    deceased_name: {extracted.get('deceased_name')}")
                print(f"    date_of_death: {extracted.get('date_of_death')}")
                print(f"    registration_number: {extracted.get('registration_number')}")
            elif doc_type == "mother_cnic":
                print(f"    name: {extracted.get('name')}")
                print(f"    cnic_number: {extracted.get('cnic_number')}")
            elif doc_type == "father_cnic":
                print(f"    name: {extracted.get('name')}")
                print(f"    cnic_number: {extracted.get('cnic_number')}")

        # Text-only slots
        print(f"\n  ── address (text-only) ──")
        r = self.client.put(
            f"/api/cases/{self.case_id}/fields",
            json={"doc_type": "address", "field_path": "full_address",
                  "new_value": "House #14, Street 3, Mohalla Gulzar-e-Madina, Multan"},
            headers=self.headers(),
        )
        self.record(r.status_code == 200, "Save address (text-only)")

        print(f"\n  ── mother_education (text-only) ──")
        r = self.client.put(
            f"/api/cases/{self.case_id}/fields",
            json={"doc_type": "mother_education", "field_path": "education_level",
                  "new_value": "primary"},
            headers=self.headers(),
        )
        self.record(r.status_code == 200, "Save mother_education (text-only)")

    # ── Step 4: Cross-Checks ─────────────────────────────────────────────────────

    def test_cross_checks(self):
        section("4. CROSS-DOCUMENT VALIDATION")

        r = self.client.post(
            f"/api/cases/{self.case_id}/cross-check",
            headers=self.headers(),
        )
        self.record(r.status_code == 200, "Run cross-checks", f"status={r.status_code}")

        if r.status_code != 200:
            print(f"  Response: {r.text[:300]}")
            return

        data = r.json()
        checks = data.get("checks", [])
        self.cross_checks = checks
        ok(f"Cross-checks returned: {len(checks)} checks")

        # Analyze each check
        for check in checks:
            label = check.get("label", "?")
            status = check.get("status", "?")
            detail = check.get("detail", "")
            sim = check.get("similarity")

            status_icons = {
                "MATCH": "🟢",
                "SIMILAR": "🟡",
                "MISMATCH": "🔴",
                "NEEDS_REVIEW": "🟠",
                "DIFFERENT_SCRIPT": "🔵",
            }
            icon = status_icons.get(status, "⚪")
            sim_str = f" (sim={sim:.3f})" if sim is not None else ""
            print(f"    {icon} {label}: {status}{sim_str}")
            if detail:
                print(f"      {detail}")

        # Verify cross-check logic
        has_any_check = len(checks) > 0
        self.record(has_any_check, "At least 1 cross-check returned")

        # Check that we have the expected check types
        check_labels = [c["label"] for c in checks]
        expected_checks = [
            "Father CNIC number",
            "Mother CNIC number",
            "Father name (B-form vs CNIC)",
            "Father name (B-form vs Death cert)",
        ]
        for expected in expected_checks:
            found = any(expected in label for label in check_labels)
            self.record(found, f"Expected check present: {expected}")

        # Count statuses
        status_counts = {}
        for c in checks:
            s = c.get("status", "UNKNOWN")
            status_counts[s] = status_counts.get(s, 0) + 1
        ok(f"Status distribution: {json.dumps(status_counts)}")

    # ── Step 5: Review & Edit Fields ─────────────────────────────────────────────

    def test_review_and_edit(self):
        section("5. REVIEW SCREEN & FIELD EDITING")

        # Get full case with extractions
        r = self.client.get(f"/api/cases/{self.case_id}", headers=self.headers())
        self.record(r.status_code == 200, "GET case for review")

        if r.status_code == 200:
            case = r.json()
            docs = case.get("documents", {})

            done_count = sum(1 for d in docs.values() if d.get("status") == "done")
            self.record(done_count >= 6, f"{done_count} documents with status 'done' (expected ≥6)")

            # Verify image URLs work
            for doc_type, doc in docs.items():
                if doc.get("imageUrl"):
                    img_r = self.client.get(doc["imageUrl"], headers=self.headers())
                    self.record(img_r.status_code == 200, f"Image accessible: {doc_type} → {doc['imageUrl']}")
                    break  # Just test one to save time

        # Test field editing (manual correction)
        r = self.client.put(
            f"/api/cases/{self.case_id}/fields",
            json={"doc_type": "result_card", "field_path": "child_name",
                  "new_value": "Test Child (edited)"},
            headers=self.headers(),
        )
        self.record(r.status_code == 200, "Manual field edit on result_card.child_name")

        # Verify edit persisted
        r = self.client.get(f"/api/cases/{self.case_id}", headers=self.headers())
        if r.status_code == 200:
            case = r.json()
            rc = case.get("documents", {}).get("result_card", {})
            extracted = rc.get("extracted_json", {})
            if isinstance(extracted, dict):
                edited_val = extracted.get("child_name", "")
                self.record("edited" in edited_val.lower() or "Test Child" in edited_val,
                            f"Edit persisted: child_name='{edited_val}'")

        # Revert the edit
        r = self.client.put(
            f"/api/cases/{self.case_id}/fields",
            json={"doc_type": "result_card", "field_path": "child_name",
                  "new_value": self.extractions.get("result_card", {}).get("child_name", "Unknown")},
            headers=self.headers(),
        )
        self.record(r.status_code == 200, "Revert field edit")

    # ── Step 6: Submit Case ──────────────────────────────────────────────────────

    def test_submit(self):
        section("6. SUBMIT CASE")

        # Submit with acknowledgment
        r = self.client.post(
            f"/api/cases/{self.case_id}/submit",
            json={"acknowledgment": "E2E test: all documents reviewed, cross-checks noted."},
            headers=self.headers(),
        )
        self.record(r.status_code == 200, "Submit case", f"status={r.status_code}" if r.status_code != 200 else "")

        if r.status_code == 200:
            data = r.json()
            self.record(data.get("success") is True, "Submit returns success=true")
            status = data.get("status", "")
            self.record(status in ("pending_verification", "unassigned"),
                        f"Case status after submit: {status}")

            routing = data.get("routing", {})
            ok(f"Routing: region={routing.get('regionId')}, confidence={routing.get('confidence')}, "
               f"city={routing.get('detectedCityOrDistrict', routing.get('detectedCity'))}")

            dup_check = data.get("duplicate_check", {})
            ok(f"Duplicate check: {json.dumps(dup_check)}")
        else:
            print(f"  Response: {r.text[:300]}")

        # Verify case is no longer draft
        r = self.client.get(f"/api/cases/{self.case_id}", headers=self.headers())
        if r.status_code == 200:
            case = r.json()
            self.record(case["status"] != "draft", f"Case status updated: {case['status']}")
            self.record(case.get("submitted_at") is not None, "submitted_at timestamp set")
            self.record(case.get("compiled_json") is not None or case.get("compiled") is not None,
                        "Compiled record saved")

    # ── Step 7: FSO Verification ─────────────────────────────────────────────────

    def test_fso_verify(self):
        section("7. FSO VERIFICATION")

        # Verify the case
        r = self.client.patch(
            f"/api/cases/{self.case_id}/verify",
            json={"status": "verified", "notes": "E2E test: home visit confirmed, all docs match."},
            headers=self.headers(),
        )
        self.record(r.status_code == 200, "Verify case as FSO", f"status={r.status_code}" if r.status_code != 200 else "")

        if r.status_code == 200:
            # Check final status
            r = self.client.get(f"/api/cases/{self.case_id}", headers=self.headers())
            if r.status_code == 200:
                case = r.json()
                self.record(case["status"] == "verified", f"Final status: {case['status']}")
                self.record(case.get("verified_at") is not None, "verified_at timestamp set")

    # ── Step 8: Stats ────────────────────────────────────────────────────────────

    def test_stats(self):
        section("8. STATS & ADMIN")

        r = self.client.get("/api/stats", headers=self.headers())
        self.record(r.status_code == 200, "Stats endpoint")
        if r.status_code == 200:
            stats = r.json()
            ok(f"Stats: {json.dumps(stats, indent=2)[:300]}")

        # List cases
        r = self.client.get("/api/cases", headers=self.headers())
        self.record(r.status_code == 200, "List all cases")
        if r.status_code == 200:
            cases = r.json().get("cases", [])
            ok(f"Total cases in system: {len(cases)}")

    # ── Step 9: Qwen-VL Extraction Quality Audit ────────────────────────────────

    def test_extraction_quality(self):
        section("9. EXTRACTION QUALITY AUDIT (Qwen-VL vs Gemini)")

        # Confirm all extractions used Qwen model
        r = self.client.get(f"/api/cases/{self.case_id}", headers=self.headers())
        if r.status_code != 200:
            self.record(False, "Cannot audit — case fetch failed")
            return

        case = r.json()
        docs = case.get("documents", {})
        all_qwen = True
        any_gemini = False

        for doc_type, doc in docs.items():
            model = doc.get("model", "")
            if model:
                if "qwen" not in model.lower():
                    all_qwen = False
                    fail(f"{doc_type} used non-Qwen model: {model}")
                if "gemini" in model.lower():
                    any_gemini = True

        self.record(all_qwen, "ALL extractions used Qwen-VL (not Gemini)")
        self.record(not any_gemini, "NO extractions used Gemini")

        # Check extraction field completeness
        field_checks = {
            "child_picture": ["quality_check"],
            "result_card": ["child_name", "school_name", "class_grade"],
            "b_form": ["crc_number", "father_name", "father_cnic_number", "mother_name", "mother_cnic_number", "children"],
            "death_certificate": ["deceased_name", "date_of_death"],
            "mother_cnic": ["name", "cnic_number"],
            "father_cnic": ["name", "cnic_number"],
        }

        for doc_type, expected_fields in field_checks.items():
            doc = docs.get(doc_type, {})
            extracted = doc.get("extracted_json", {})
            if not isinstance(extracted, dict):
                continue
            missing = [f for f in expected_fields if f not in extracted]
            self.record(len(missing) == 0, f"{doc_type} has all expected fields" +
                        (f" (missing: {missing})" if missing else ""))

    # ── Run All ──────────────────────────────────────────────────────────────────

    def run(self):
        print("=" * 60)
        print("  CaseFill-AI End-to-End Test Suite")
        print("=" * 60)
        print(f"  Backend: {BASE_URL}")
        print(f"  Sample docs: {SAMPLE_DOCS_DIR}")
        print(f"  Started: {time.strftime('%H:%M:%S')}")

        self.test_auth()
        self.test_create_case()
        self.test_upload_and_extract()
        self.test_cross_checks()
        self.test_review_and_edit()
        self.test_submit()
        self.test_fso_verify()
        self.test_stats()
        self.test_extraction_quality()

        section("FINAL RESULTS")
        p = self.results["passed"]
        f = self.results["failed"]
        s = self.results["skipped"]
        total = p + f + s
        print(f"  ✅ Passed: {p}/{total}")
        print(f"  ❌ Failed: {f}/{total}")
        print(f"  ⏭  Skipped: {s}/{total}")
        print(f"  Finished: {time.strftime('%H:%M:%S')}")
        print("=" * 60)

        return f == 0


if __name__ == "__main__":
    tester = CaseFillTester()
    success = tester.run()
    sys.exit(0 if success else 1)
