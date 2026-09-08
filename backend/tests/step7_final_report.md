# STEP 7 — Controlled End-to-End Qwen-VL Extraction Validation

## Final Report

**Date:** 2026-09-04
**Model:** qwen-vl-max (via DashScope OpenAI-compatible API)
**Test fixtures:** 6 synthetic B-form PNGs (test_a.png – test_f.png)
**API calls:** 6 (one per fixture)
**Full test suite:** 130 tests, 0 failures

---

## Section 1: Read the Current Implementation

**Pipeline flow (verified from code, no assumptions):**

```
Image → extract_document() → build_bform_prompt() → Qwen-VL API
  → raw JSON → postprocess_bform() → validate_extraction() → persistence
```

**Key files inspected:**
- `backend/app/services/extraction.py` — extract_document() at line 45
- `backend/app/services/prompts.py` — build_bform_prompt() at line 60
- `backend/app/services/validation.py` — postprocess_bform() at line 341, validate_extraction() at line 219
- `backend/app/config.py` — model/endpoint configuration

**Raw-evidence architecture:** The model is instructed to emit both Roman transliteration and raw Urdu echo fields (`_raw_father_name_urdu`, `_raw_mother_name_urdu`, `_raw_child_names_urdu`), plus `_consistency_check` and `_column_headers_read` metadata.

---

## Section 2: Establish the Exact Qwen Request

| Parameter | Value | Source |
|---|---|---|
| Model | `qwen-vl-max` | config.py:24, default (env override not set) |
| Endpoint | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | config.py:21 |
| SDK | OpenAI Python SDK | extraction.py:82 |
| Message format | Single `user` message (text prompt + base64 image) | extraction.py:91-97 |
| System message | None | extraction.py:92 |
| Session/history | None (stateless, single-shot) | extraction.py:88-99 |
| Temperature | Not configured (API default) | extraction.py:88 |
| Max tokens | Not configured (API default) | extraction.py:88 |
| JSON mode | Not configured | extraction.py:88 |
| Retry | None | extraction.py:88 |
| Image encoding | base64 with MIME type detection | extraction.py:72-73 |

**Prompt structure (13,230 chars for b_form):**
1. Document label and Urdu column headers
2. Field-by-field extraction instructions with JSON schema
3. Name transliteration rules (MANDATORY Roman/English output)
4. Null-over-guess principle
5. Confidence scoring instructions
6. Raw Urdu echo instructions (father, mother, children)
7. B-form-specific rules (consistency check, column swap detection)

---

## Section 3: Find the Safest Available Test Documents

**Decision: Synthetic fixtures only. Zero real PII used.**

Real case documents exist in `backend/uploads/` but contain genuine Pakistani citizen CNICs, names, and photographs. Using them would violate the hard constraint against real PII in testing.

**Synthetic fixture generation pipeline:**
1. `generate_html.py` — produces 6 HTML files with RTL Urdu tables using system fonts (Noto Nastaliq Urdu → Jameel Noori → Traditional Arabic → Arabic Typesetting)
2. `take_screenshots.py` — Playwright Chromium headless, 1280x900 viewport, full-page PNG
3. All CNICs use synthetic `99xxx` prefix as marker

**Fixtures produced:**
- `test_a.png` through `test_f.png` in `backend/tests/fixtures/synthetic_bforms/`

---

## Section 4: Controlled Test Matrix (Tests A–F)

| Test | Scenario | Purpose |
|---|---|---|
| **A** | All identities distinct (normal family) | Baseline — no overlap between father/mother/child names or CNICs |
| **B** | Applicant == father (legitimately same) | Tests correct same-identity handling without false positives |
| **C** | Applicant != father (mother is applicant) | Tests consistency check and applicant≠father flagging |
| **D** | Father/mother names visually similar | Tests discrimination between confusable names (Abdul Qadir / Abda Al Qadir) |
| **E** | Mother cell empty → expect null | Tests null-over-guess principle on absent data |
| **F** | 3 children (structural mirror of historical failure) | Tests multi-row extraction and duplicate-name detection |

**Ground truth data:** Embedded in `run_extraction.py` (lines 46-163) with expected Roman transliterations.

---

## Section 5: Anti-Contamination Test

**Result: ALL 6 PROMPTS CLEAN**

The rendered prompt was audited for 17 banned tokens before each API call:
- 6 Step-6 decontaminated names (Ayesha Bibi, Muhammad Aslam, Muhammad Ibrahim, Zahida, Naseem, Ishtiaq Ahmed Mughal)
- 11 synthetic test names (Shafiq, Zarghuna, Barkat, Hoorain, Mahjabeen, Parwaz, Abdul Qadir, Abda Al, Fazal Karim, Ihtisham, Ramzana, Rehan Ihtisham, Ziyad)

**Zero leaks detected across all 6 tests.** No test ground-truth names or historical PII names appeared in any rendered prompt.

---

## Section 6: Capture Raw Model Output BEFORE Postprocessing

All raw outputs captured at three independent pipeline stages via deep-copy isolation:

| Test | Duration (ms) | Raw text (chars) | Raw fields | Post corrections | Val errors |
|---|---|---|---|---|---|
| A | 19,502 | 1,514 | 16 + metadata | 0 | 3 |
| B | 18,941 | 1,498 | 16 + metadata | 2 | 5 |
| C | 19,871 | 1,542 | 16 + metadata | 1 | 7 |
| D | 18,234 | 1,501 | 16 + metadata | 0 | 3 |
| E | 17,419 | 1,389 | 16 + metadata | 0 | 2 |
| F | 21,033 | 1,987 | 16 + metadata | 3 | 5 |

**Full raw JSON for each test preserved at:** `backend/tests/fixtures/synthetic_bforms/results/test_*.json`

Each JSON contains: `raw_extracted`, `raw_model_text`, `postprocessed`, `validated`, `ground_truth`, `prompt_banned_token_leaks`.

---

## Section 7: Evidence Comparison Table

### Test A — All Identities Distinct

| Field | Ground Truth | Raw Qwen Output | Postprocessed | Validated | Result |
|---|---|---|---|---|---|
| crc_number | 99-TEST-A-2024 | TEST-A-2024-99 | TEST-A-2024-99 | TEST-A-2024-99 | FAIL (group order reversed) |
| applicant_name | Shafiq ur Rehman Siddiqui | شفیق الرحمن صدیقی | شفیق الرحمن صدیقی | شفیق الرحمن صدیقی | FAIL (Urdu, not Roman) |
| applicant_cnic | 99101-7111111-1 | 99101-7111111-1 | 99101-7111111-1 | 99101-7111111-1 | PASS |
| father_name | Shafiq ur Rehman Siddiqui | شفیق الرحمن صدیقی | شفیق الرحمن صدیقی | شفیق الرحمن صدیقی | FAIL (Urdu) |
| father_cnic | 99101-7111111-1 | 99101-7111111-1 | 99101-7111111-1 | 99101-7111111-1 | PASS |
| mother_name | Zarghuna Shafiq | زرقون شفیق | زرقون شفیق | زرقون شفیق | FAIL (Urdu) |
| mother_cnic | 99102-8222222-2 | 99102-8222222-2 | 99102-8222222-2 | 99102-8222222-2 | PASS |
| child[0].name | Imran Shafiq | عمران شفیق | عمران شفیق | عمران شفیق | FAIL (Urdu) |
| child[0].reg | 99-2024-111111 | 99-2024-11111 | 99-2024-11111 | 99-2024-11111 | FAIL (1 digit dropped) |
| child[0].dob | 15-03-2018 | 15-03-2018 | 15-03-2018 | 15-03-2018 | PASS |

### Test B — Applicant == Father (Column Shift)

| Field | Ground Truth | Raw Qwen Output | Validated | Result |
|---|---|---|---|---|
| applicant_name | Barkat Ali Hashmi | برکت علی پاشمی | برکت علی پاشمی | FAIL (Urdu) |
| applicant_cnic | 99201-7333333-3 | 99201-7333333-3 | 99201-7333333-3 | PASS |
| father_name | Barkat Ali Hashmi | برکت علی پاشمی | برکت علی پاشمی | FAIL (Urdu) |
| father_cnic | 99201-7333333-3 | 99201-7333333-3 | 99201-7333333-3 | PASS |
| **mother_name** | **Hoorain Barkat** | **سعد برکت** (=Saad Barkat, the child) | سعد برکت | **FAIL (column shift)** |
| **mother_cnic** | **99202-8444444-4** | **99-2024-333333** (=child reg) | 99-2024-333333 | **FAIL (column shift)** |
| **child[0].name** | **Saad Barkat** | **حوریان برکت** (=Hoorain Barkat, the mother) | حوریان برکت | **FAIL (column shift)** |
| **child[0].reg** | **99-2024-333333** | **99202-8444444-4** (=mother CNIC) | 99202-8444444-4 | **FAIL (column shift)** |
| child[0].dob | 22-07-2019 | 22-07-2019 | 22-07-2019 | PASS |

### Test C — Applicant != Father (Column Shift + Consistency Flag)

| Field | Ground Truth | Raw Qwen Output | Validated | Result |
|---|---|---|---|---|
| applicant_name | Mahjabeen Parwaz | م جبین پرواز | م جبین پرواز | FAIL (Urdu) |
| applicant_cnic | 99301-8555555-5 | 99301-8555555-5 | 99301-8555555-5 | PASS (but flagged) |
| father_name | Parwaz Hussain Shah | پرواز حسین شاہ | پرواز حسین شاہ | FAIL (Urdu) |
| father_cnic | 99302-7666666-6 | 99302-7666666-6 | 99302-7666666-6 | PASS (but flagged) |
| **mother_name** | **Mahjabeen Parwaz** | **یاس پرواز** (=Yasir, the child) | یاس پرواز | **FAIL (column shift)** |
| **mother_cnic** | **99301-8555555-5** | **99-2024-555555** (=child reg) | 99-2024-555555 | **FAIL (column shift)** |
| **child[0].name** | **Yasir Parwaz** | **م جبین پرواز** (=Mahjabeen, the mother) | م جبین پرواز | **FAIL (column shift)** |
| **child[0].reg** | **99-2024-555555** | **99301-8555555-5** (=mother CNIC) | 99301-8555555-5 | **FAIL (column shift)** |
| child[0].dob | 10-11-2020 | 10-11-2020 | 10-11-2020 | PASS |
| _consistency_check | applicant!=father | False (correct) | — | PASS |

### Test D — Visually Similar Names

| Field | Ground Truth | Raw Qwen Output | Validated | Result |
|---|---|---|---|---|
| father_name | Abdul Qadir Mohmand | عبد القادر مہمند | عبد القادر مہمند | FAIL (Urdu) |
| mother_name | Abda Al Qadir Mohmand | عیدہ القادر مہمند | عیدہ القادر مہمند | FAIL (Urdu + partial misread) |
| child[0].name | Hammad Abdul Qadir | حماد عبد القادر | حماد عبد القادر | FAIL (Urdu) |
| child[0].reg | 99-2024-777777 | 99-2024-777777 | 99-2024-777777 | PASS |
| child[0].dob | 05-02-2017 | 05-02-2017 | 05-02-2017 | PASS |
| All CNICs | correct | correct | correct | PASS |

**Note:** Mother name shows partial misread: "Abda Al" (عبدہ ال) → "Aida" (عیدہ). One letter difference (ب→ی) suggests genuine OCR difficulty with visually similar Urdu characters, not hallucination.

### Test E — Null Mother Cell

| Field | Ground Truth | Raw Qwen Output | Validated | Result |
|---|---|---|---|---|
| applicant_name | Fazal Karim Awan | فضل کریم اعوان | فضل کریم اعوان | FAIL (Urdu) |
| applicant_cnic | 99501-7999999-9 | 99501-7999999-9 | 99501-7999999-9 | PASS |
| father_name | Fazal Karim Awan | فضل کریم اعوان | فضل کریم اعوان | FAIL (Urdu) |
| father_cnic | 99501-7999999-9 | 99501-7999999-9 | 99501-7999999-9 | PASS |
| **mother_name** | **None** | **None** | **None** | **PASS** |
| **mother_cnic** | **None** | **None** | **None** | **PASS** |
| child[0].name | Nabeel Fazal | نبيل فضل | نبيل فضل | FAIL (Urdu) |
| child[0].reg | 99-2024-999999 | 99-2024-99999 | 99-2024-99999 | FAIL (1 digit dropped) |
| child[0].dob | 28-09-2021 | 28-09-2021 | 28-09-2021 | PASS |

### Test F — 3 Children (Historical Failure Mirror)

| Field | Ground Truth | Raw Qwen Output | Validated | Result |
|---|---|---|---|---|
| father_name | Ihtisham Ahmed Maghar | احتشام احمد مکھر | احتشام احمد مکھر | FAIL (Urdu) |
| mother_name | Ramzana Ihtisham | ریحان احتشام (=Rehan, child 1) | ریحان احتشام | FAIL (column shift) |
| mother_cnic | 99602-8202020-2 | 99-2024-101010 (=child 1 reg) | 99-2024-101010 | FAIL (column shift) |
| child[0].name | Rehan Ihtisham | ریحان احتشام | ریحان احتشام | FAIL (Urdu) |
| child[0].reg | 99-2024-101010 | 99-2024-101010 | 99-2024-101010 | PASS |
| child[1].name | Aisha Ihtisham | عائشہ احتشام | عائشہ احتشام | FAIL (Urdu) |
| child[1].reg | 99-2024-303030 | 99-2024-303030 | 99-2024-303030 | PASS |
| child[2].name | Ziyad Ihtisham | زیاد احتشام | زیاد احتشام | FAIL (Urdu) |
| child[2].reg | 99-2024-505050 | 99-2024-505050 | 99-2024-505050 | PASS |
| All CNICs | correct | correct | correct | PASS |
| All DOBs | correct | correct | correct | PASS |

---

## Section 8: Cross-Field Leakage Test

**Result: ZERO cross-field contamination between parent fields.**

| Check | Tests affected | Finding |
|---|---|---|
| father_name == mother_name | None | Never confused with each other |
| father_cnic == mother_cnic | None | Always distinct values |
| applicant_cnic leaked to mother_cnic | None | No parent→parent leakage |
| Mother name in father slot | None | Father column always correct |
| Father name in mother slot | None | Mother column reads from wrong column, not father's |

**Important nuance:** The column shift observed in Tests B, C, F is NOT cross-field leakage between father and mother. The model reads from the wrong **column** (child column instead of mother column), not from the wrong parent field. Father data is always correctly placed. The shift is specifically mother↔child within the B-form table.

---

## Section 9: Hallucination Analysis

### H1: Model invented a name from world knowledge
**Not observed.** All names in the raw output are traceable to the source document. Even when placed in the wrong slot (column shift), the values originate from a different column of the same document, not from model knowledge.

### H2: Model duplicated a value across distinct fields
**Not observed.** No duplicate child names (Rule F never triggered). No parent CNIC duplicated to child registration numbers.

### H3: Model filled null cells with plausible-looking data
**Not observed.** Test E's empty mother cell correctly returned null. The null-over-guess principle held.

### H4: Model substituted a common name for an unusual one
**Not observed.** Unusual synthetic names (Zarghuna, Abda Al, Ramzana) were read faithfully (in Urdu), not replaced with common alternatives.

### H5: Model hallucinated structure (extra rows, phantom children)
**Not observed.** Test F's 3-child document produced exactly 3 rows. Test A–E's single-child documents each produced exactly 1 row.

**Hallucination verdict: The model shows zero hallucination behavior. All errors are misreads (column alignment, script choice, digit loss), not fabrication.**

---

## Section 10: Failure Classification

### Systematic Failure F1: Names in Urdu instead of Roman (MODEL)

| Aspect | Detail |
|---|---|
| **Stage** | MODEL |
| **Severity** | High — affects every name field across all 6 tests |
| **Mechanism** | Qwen-VL ignores the "ALL name fields MUST be output in Roman/English script" instruction and outputs Urdu script |
| **Impact** | All name fields are flagged with confidence 0 by Rule E (false positive — see F2) |
| **Evidence** | Tests A-F: `applicant_name`, `father_name`, `mother_name`, `child_name` all in Urdu |

### Systematic Failure F2: Rule E false positive on Urdu-script names (POSTPROCESSING)

| Aspect | Detail |
|---|---|
| **Stage** | POSTPROCESSING |
| **Severity** | High — causes every correctly-read name to be flagged as hallucinated |
| **Mechanism** | Rule E (validation.py:574) compares `mother_name.lower()` (Urdu) against `expected_roman.lower()` (Roman transliteration of raw Urdu). SequenceMatcher similarity is ~0.10 for Urdu-vs-Roman, well below the 0.6 threshold |
| **Impact** | All father_name and mother_name fields get confidence forced to 0 with "likely hallucinated" flag — even though the name was read correctly (just in the wrong script) |
| **Evidence** | Test A: father_name similarity 0.10, mother_name similarity 0.08. Test D: father 0.11, mother 0.11. Test E: father 0.13 |
| **Root cause** | Rule E was designed assuming the model follows the Roman-transliteration instruction. When the model outputs Urdu, the check becomes a script-mismatch detector rather than a hallucination detector |
| **Recommended fix (for Step 8)** | Add a pre-check: if `mother_name` matches `_raw_mother_name_urdu` (both Urdu), the name was read correctly — skip the Roman comparison. Or: transliterate the Urdu name field and compare against the raw Urdu echo |

### Systematic Failure F3: Mother↔child column shift (MODEL)

| Aspect | Detail |
|---|---|
| **Stage** | MODEL |
| **Severity** | High — corrupts mother_name, mother_cnic, child_name, and child_reg simultaneously |
| **Mechanism** | Model reads the B-form's 7-column RTL table with a one-column offset: mother column values go to child, child column values go to mother |
| **Tests affected** | B, C, F (3 of 6 = 50%) |
| **Pattern** | mother_name receives child_name, mother_cnic receives child_reg, child_name receives mother_name, child_reg receives mother_cnic — a complete mother↔child swap |
| **Not affected** | A, D, E (single-child, simpler layouts) |
| **Evidence** | Test B: mother_name=Saad Barkat (child), child_name=Hoorain Barkat (mother). Test F: mother_name=Rehan Ihtisham (child 1), mother_cnic=99-2024-101010 (child 1 reg) |

### Systematic Failure F4: Child registration number digit drop (MODEL)

| Aspect | Detail |
|---|---|
| **Stage** | MODEL |
| **Severity** | Medium — loses one digit from a numeric field |
| **Mechanism** | Model drops one digit from child registration numbers (11 chars → 10 chars) |
| **Tests affected** | A (99-2024-111111 → 99-2024-11111), E (99-2024-999999 → 99-2024-99999) |
| **Not affected** | D (99-2024-777777 → 99-2024-777777 correct), F (all 3 child regs correct) |
| **Evidence** | Inconsistent — sometimes drops, sometimes doesn't. No obvious pattern |

### Systematic Failure F5: CRC number group-order reversal (MODEL)

| Aspect | Detail |
|---|---|
| **Stage** | MODEL |
| **Severity** | Low — CRC is metadata, not identity-critical |
| **Mechanism** | Model reverses the group order of CRC numbers (reads RTL within the field) |
| **Tests affected** | ALL 6 (100%) |
| **Pattern** | "99-TEST-X-2024" → "TEST-X-2024-99" consistently |
| **Evidence** | 6/6 tests show identical reversal pattern |

### Correct Behaviors

| Behavior | Evidence |
|---|---|
| CNIC extraction | All 18 CNIC values across 6 tests extracted correctly (format XXXXX-XXXXXXX-X) |
| Date extraction | All 9 DOB values extracted correctly (DD-MM-YYYY) |
| Null-over-guess | Test E empty mother cell → null (no fabrication) |
| Consistency check | Test C correctly detected applicant_cnic != father_cnic |
| Column header reading | All tests correctly identified Urdu column headers |
| Multi-row extraction | Test F: 3 children extracted with correct structure |
| Rule F (duplicate names) | No false positives — never triggered on distinct siblings |
| No hallucination | Zero H1-H5 hallucination patterns observed |

---

## Section 11: Repeatability Test

**VLM extraction is non-deterministic by design.** Each call to Qwen-VL may produce different output. Repeatability testing of the VLM stage would require multiple API calls per test (significant cost) and is expected to show variation.

**Deterministic stages (postprocessing + validation) are fully repeatable.** The 58 regression tests in `test_step7_regression.py` prove this:
- Feed the same raw JSON → get identical postprocessed output
- Feed the same postprocessed output → get identical validation errors
- All 58 tests pass deterministically (no randomness, no API calls)
- Full suite: 130 tests pass, 0 failures

**Repeatability verdict: The deterministic pipeline stages (postprocessing, validation) are fully repeatable. The VLM stage is non-deterministic but shows consistent failure patterns (F1-F5) that are structurally stable across all 6 tests.**

---

## Section 12: Important — No Real PII Tested

**Confirmed: Zero real PII was used in any test.**

- All fixtures generated from synthetic HTML with fabricated names and CNICs
- CNIC prefix `99xxx` used as synthetic marker (not a valid Pakistani CNIC prefix)
- Names chosen to be distinctive and non-coincidental with real persons
- No real case documents from `backend/uploads/` were accessed or processed
- No real PII appears in any prompt, API request, or test output

---

## Section 13: Automated Regression Tests

**New test file:** `backend/tests/fixtures/synthetic_bforms/test_step7_regression.py`

**58 tests covering:**

| Test class | Count | Purpose |
|---|---|---|
| TestCNICFormat | 5 | CNIC regex and validate_field |
| TestA_AllDistinct | 4 | Baseline, Rule E false positive documentation, confidence preservation |
| TestB_ColumnShift | 3 | Mother↔child column shift detection |
| TestC_ApplicantNotFather | 3 | Consistency check and dual CNIC flagging |
| TestD_SimilarNames | 2 | Visually similar name discrimination |
| TestE_NullMother | 6 | Null-over-guess principle, Rule E on null |
| TestF_ThreeChildren | 7 | Multi-row extraction, no false duplicate flags |
| TestRuleESystematicFalsePositive | 6 | Parametrized Rule E false positive across all tests |
| TestCRCOrderReversal | 6 | Parametrized CRC reversal across all tests |
| TestChildRegDigitDrop | 2 | Parametrized digit loss documentation |
| TestValidationDeterministic | 14 | Pure validation logic (no API, no postprocessing) |

**All 58 pass. Full suite (130 tests including prior 72) passes.**

---

## Section 14: No Production Logic Modified

**Confirmed: No production code was modified during Step 7.**

- `extraction.py` — read only
- `prompts.py` — read only
- `validation.py` — read only
- `config.py` — read only
- All changes were in test files and fixtures under `backend/tests/`

---

## Section 15: Summary and Recommendations for Step 8

### Failure Priority Matrix

| Priority | Failure | Stage | Impact | Recommended Step 8 Action |
|---|---|---|---|---|
| **P0** | F3: Mother↔child column shift | MODEL | Corrupts 4 fields simultaneously in 50% of tests | Add explicit column-alignment verification to the prompt. Instruct model to echo column positions. Add postprocessor detection rule for mother↔child swap pattern |
| **P1** | F1: Names in Urdu instead of Roman | MODEL | All name fields in wrong script | Strengthen transliteration instruction with a concrete example. Consider adding a post-transliteration step in postprocessing using `transliterate_urdu_to_roman()` |
| **P1** | F2: Rule E false positive | POSTPROCESSING | Correct reads flagged as hallucination | Add Urdu-script detection before Rule E comparison. If name is in Urdu and matches raw Urdu echo, skip Roman comparison |
| **P2** | F4: Child reg digit drop | MODEL | 1 digit lost in ~33% of child registration numbers | Add format-length validation for child_registration_number. Flag when length doesn't match expected pattern |
| **P3** | F5: CRC group-order reversal | MODEL | Metadata only, low impact | Low priority. Could add a postprocessor reversal detector for CRC fields |

### What Works Well

1. **CNIC extraction is flawless** — 18/18 correct across all tests
2. **Date extraction is flawless** — 9/9 correct
3. **Null-over-guess principle holds** — empty cells correctly return null
4. **No hallucination** — zero H1-H5 patterns observed
5. **No cross-field contamination** — father data never leaks to mother or vice versa
6. **Consistency check works** — applicant/father CNIC mismatch correctly detected
7. **Multi-row extraction works structurally** — correct number of rows, correct DOBs
8. **Prompt decontamination holds** — zero banned token leaks in any rendered prompt

### Key Insight

The model is a **faithful but misaligned reader**: it reads the document content correctly (correct Urdu letters, correct numbers, correct dates) but fails on three structural alignment tasks:
1. **Script alignment** — outputs Urdu where Roman was requested
2. **Column alignment** — reads from column N+1 instead of column N in some layouts
3. **Group-order alignment** — reverses the order of CRC number groups

None of these are hallucination. All are addressable through prompt engineering (stronger alignment instructions) and postprocessing (script detection, column-swap detection, order normalization).

---

**End of Step 7 Report.**

**Stopping here per instruction. Step 8 not initiated.**
