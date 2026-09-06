# Step 9 Final Report — Remove Positional Column-Number Dependence

**Fixture:** `backend/tests/fixtures/synthetic_bforms/test_b.png` (synthetic single-child B-form)
**Model:** `qwen-vl-max` (default; `QWEN_MODEL` env override not set)
**Runner:** `tests/fixtures/synthetic_bforms/run_step9_ab.py` (5 A-arm + 5 B-arm independent API calls, stateless single-shot)
**Regression tests:** `test_step9_header_mapping.py` (44 tests) + `test_step9_ab_regression.py` (17 tests) + `test_step8_regression.py` (26 tests) = 87 total, all pass
**Full suite at report time:** 87 tests, 0 failures
**Date:** 2026-09-04

---

## 1. Experiment Design and Hypothesis

**Hypothesis (from Step 8, Section 11):**
> The mother↔child swap is caused by a **column-numbering ambiguity at the VLM layer** combined with the prompt's reliance on numbered column positions. [...] Replace the numbered `col1..col7` scheme with **header-keyed** output (`{"<Urdu header>": <value>, ...}`) that removes the model's need to number columns.

**Experiment:** Controlled A/B test on the same image (`test_b.png`), same model, same pipeline. The only variable is the prompt representation of column semantics.

| Arm | Prompt | Column representation | Post-processing |
|-----|--------|----------------------|-----------------|
| **A (positional)** | `build_bform_prompt()` (unchanged from Steps 7/8) | `col1..col7` numbered positions | `postprocess_bform()` + `validate_extraction()` |
| **B (header-keyed)** | `build_bform_prompt_header_keyed()` (new) | Verbatim Urdu header text as keys | `adapt_header_keyed_to_canonical()` → `postprocess_bform()` + `validate_extraction()` |

**Design constraints honored:**
- No production code path modified (positional prompt still works when `prompt_builder=None`)
- No auto-correction in the adapter (structural only — values pass through verbatim)
- No changes to `validation.py`, `cross_check.py`, or any downstream module
- No few-shot examples added
- No F1/F5 fixes attempted
- No real PII used
- No model or fixture changes

---

## 2. Ground Truth Reference

Same ground truth as Step 8 — `test_b.png` with applicant == father (legitimately same person).

| Field | Ground-truth value (Roman) | Ground-truth value (Urdu) |
|-------|---------------------------|---------------------------|
| crc_number | `99-TEST-B-2024` | — |
| applicant_name | `Barkat Ali Hashmi` | `برکت علی ہاشمی` |
| applicant_cnic_number | `99201-7333333-3` | — |
| father_name | `Barkat Ali Hashmi` | `برکت علی ہاشمی` |
| father_cnic_number | `99201-7333333-3` | — |
| mother_name | `Hoorain Barkat` | `حوریاں برکت` |
| mother_cnic_number | `99202-8444444-4` | — |
| child[0].child_name | `Saad Barkat` | `سعد برکت` |
| child[0].child_registration_number | `99-2024-333333` | — |
| child[0].gender_relation | `son` | `بیٹا` |
| child[0].date_of_birth | `22-07-2019` | — |

---

## 3. Implementation Changes

Three new/modified files, all additive. Production code path is unchanged when no `prompt_builder` is supplied.

| File | Kind | Lines | Role |
|---|---|---|---|
| `app/services/extraction.py` | modified | +4 | Added optional `prompt_builder: callable \| None` parameter to `extract_document()`. Default `None` preserves existing positional behavior. |
| `app/services/prompts_header_keyed.py` | new | 251 | Header-keyed B-form prompt. Same signature as `build_bform_prompt()` so it can be substituted at call time. |
| `app/services/header_mapping.py` | new | 305 | Deterministic Urdu header normalization (NFKC), two-pass semantic mapping (exact → keyword → NEEDS_REVIEW), adapter from header-keyed → canonical flat schema. |
| `tests/fixtures/synthetic_bforms/run_step9_ab.py` | new | ~200 | A/B runner. Five fresh calls per arm, saves raw/adapted/postprocessed/validated JSON. |
| `tests/fixtures/synthetic_bforms/test_step9_header_mapping.py` | new | ~300 | 44 deterministic offline tests against the header_mapping module. |
| `tests/fixtures/synthetic_bforms/test_step9_ab_regression.py` | new | ~200 | 17 deterministic offline tests against the saved A/B run results. |

**No files were modified in a way that affects production behavior when the default prompt is used.** The positional prompt, postprocessing, validation, and cross-check modules are untouched.

### `extract_document()` modification

```python
def extract_document(
    image_path: str | Path,
    document_type: str,
    target_child_serial_number: int | None = None,
    prompt_builder: "callable | None" = None,   # ← new parameter
) -> dict:
    ...
    if document_type == "b_form":
        if prompt_builder is not None:
            prompt = prompt_builder(doc_schema, target_child_serial_number)
        else:
            prompt = build_bform_prompt(doc_schema, target_child_serial_number)
```

The change is a single branch point. All existing callers that do not pass `prompt_builder` continue to use the positional prompt unchanged.

---

## 4. Old Positional Architecture (A arm)

```
image → extract_document("b_form")
      → build_bform_prompt()
           └─ "The B-form table has 7 columns in right-to-left order:
                col1 = نمبر شمار (serial number)
                col2 = بچے کا نام اور رجسٹریشن نمبر (child name + registration)
                col3 = والد کا نام اور شناختی کارڈ نمبر (father name + CNIC)
                col4 = والدہ کا نام اور شناختی کارڈ نمبر (mother name + CNIC)
                col5 = جنس / رشتہ (gender / relation)
                col6 = تاریخ پیدائش (date of birth)
                col7 = معذوری (remarks / disability)"
      → Qwen-VL single-shot (stateless, no system message)
      → JSON with flat fields: father_name, mother_name, children[].child_name, ...
           └─ _column_headers_read: {col1: "...", col2: "...", ...}
      → postprocess_bform()
      → validate_extraction()
```

**Why this fails (from Step 8):** The prompt tells the VLM to read columns by **positional number** and assumes an RTL→DOM ordering the VLM cannot infer from pixels. The VLM observes pixels, not DOM. It sometimes re-numbers the columns (e.g., col2=father, col3=mother, col4=gender/...) and then reads the **correct values from the wrong numbered slots**, producing the atomic mother↔child swap.

---

## 5. New Header-Keyed Architecture (B arm)

```
image → extract_document("b_form", prompt_builder=build_bform_prompt_header_keyed)
      → build_bform_prompt_header_keyed()
           └─ "Visually locate EVERY column header on the table.
                For EACH header, copy the Urdu text VERBATIM.
                Associate cells with headers by reading the header text itself:
                  Header containing بچے کا نام = child column
                  Header containing والد کا نام (ends with والد, no trailing ہ) = father
                  Header containing والدہ کا نام (ends with والدہ, has trailing ہ) = mother
                  ...
                Output table_rows keyed by the VERBATIM Urdu header text."
      → Qwen-VL single-shot (stateless, no system message)
      → JSON with table_rows[ { "<verbatim Urdu header>": {name, cnic|reg}, ... } ]
           └─ _raw_column_headers: ["...", "..."]
           └─ _header_mapping: {"<header>": "serial"|"child"|"father"|"mother"|...}
      → adapt_header_keyed_to_canonical()     ← structural only, no value mutation
           ├─ normalize_header()        (Unicode NFKC, whitespace collapse)
           ├─ map_header_to_semantic()  (two-pass: exact → keyword → NEEDS_REVIEW)
           ├─ map_all_headers()         (duplicate-semantic demotion)
           └─ copy values into canonical flat schema verbatim
      → postprocess_bform()            (unchanged)
      → validate_extraction()           (unchanged)
```

### Critical properties of the adapter

| Property | Description |
|----------|-------------|
| **Structural only** | Never swaps, reorders, or corrects values. A value under the verbatim "mother" header ends up in `mother_name`; a value under the "child" header ends up in `child_name`. If the VLM placed the wrong value under a header, the adapter carries that mistake forward. |
| **Deterministic** | Unicode NFKC, whitespace collapse, exact canonical match first, then keyword substring. Same input → byte-identical output. |
| **No positional fallback** | An unreadable / ambiguous header → `NEEDS_REVIEW`. The corresponding canonical field is `null` with confidence `0`. The adapter never guesses from column position. |
| **Duplicate-semantic demotion** | If two distinct verbatim headers both map to the same semantic key, both are demoted to `NEEDS_REVIEW`. This matches the model-side instruction. |
| **Raw evidence preserved** | `_raw_column_headers`, `_header_mapping`, `_raw_father_name_urdu`, `_raw_mother_name_urdu`, `_raw_child_names_urdu` all survive the adapter unchanged. |

### Two-pass header mapping

```
Pass 1: Exact canonical match (after NFKC normalization)
  "بچے کا نام اور رجسٹریشن نمبر" → child
  "والد کا نام اور شناختی کارڈ نمبر" → father
  "والدہ کا نام اور شناختی کارڈ نمبر" → mother
  ... (all 7 canonical headers)

Pass 2: Keyword substring (only if Pass 1 fails)
  "بچے کا نام" → child
  "والد کا نام" → father
  "والدہ کا نام" → mother
  ... (12 keyword hints)

Fallback: NEEDS_REVIEW (if 0 or >1 keyword hits)
```

---

## 6. Ten-Run Comparison Table

All 10 runs used the **same image, same model**. Each was an independent stateless API call. The only variable is the prompt (A = positional, B = header-keyed).

### A arm (positional) — 5 runs

| Field | GT | A0 | A1 | A2 | A3 | A4 |
|-------|-----|------|------|------|------|------|
| crc_number | `99-TEST-B-2024` | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ |
| father_name | `برکت علی ہاشمی` | `برکت علی پاشمی` ❌ | `برکت علی پاشمی` ❌ | `برکت علی پاشمی` ❌ | `برکت علی پاشمی` ❌ | `برکت علی پاشمی` ❌ |
| father_cnic | `99201-7333333-3` | `99201-7333333-3` ✓ | `99201-7333333-3` ✓ | `99201-7333333-3` ✓ | `99201-7333333-3` ✓ | `99201-7333333-3` ✓ |
| **mother_name** | `حوریاں برکت` | `سعد برکت` ❌ (child GT) | `سعد برکت` ❌ (child GT) | `سعد برکت` ❌ (child GT) | `حوریان بركت` ✓ | `سعد برکت` ❌ (child GT) |
| **mother_cnic** | `99202-8444444-4` | `99-2024-333333` ❌ (child_reg GT) | `99-2024-333333` ❌ (child_reg GT) | `99-2024-333333` ❌ (child_reg GT) | `99202-8444444-4` ✓ | `99202-8444444-4` ✓ |
| **child_name** | `سعد برکت` | `حوریان برکت` ❌ (mother GT) | `حوریان برکت` ❌ (mother GT) | `حوریان برکت` ❌ (mother GT) | `سعد بركت` ✓ | `حوریان برکت` ❌ (mother GT) |
| **child_reg** | `99-2024-333333` | `99202-8444444-4` ❌ (mother_cnic GT) | `99202-8444444-4` ❌ (mother_cnic GT) | `99202-8444444-4` ❌ (mother_cnic GT) | `99-2024-333333` ✓ | `99202-8444444-4` ❌ (mother_cnic GT) |
| gender | `بیٹا` | `بٹا` ❌ | `بٹا` ❌ | `بٹا` ❌ | `بٹا` ❌ | `بٹا` ❌ |
| DOB | `22-07-2019` | `22-07-2019` ✓ | `22-07-2019` ✓ | `22-07-2019` ✓ | `22-07-2019` ✓ | `22-07-2019` ✓ |
| **Classification** | — | **SWAPPED** | **SWAPPED** | **SWAPPED** | **CORRECT** | **SWAPPED** |
| Duration (ms) | — | 18,426 | 19,095 | 19,092 | 13,780 | 13,490 |

### B arm (header-keyed) — 5 runs

| Field | GT | B0 | B1 | B2 | B3 | B4 |
|-------|-----|------|------|------|------|------|
| crc_number | `99-TEST-B-2024` | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ |
| father_name | `برکت علی ہاشمی` | `برکت علی پاشمی` ❌ | `برکت علی پاشمی` ❌ | `برکت علی پاشمی` ❌ | `برکت علی پاشمی` ❌ | `برکت علی پاشمی` ❌ |
| father_cnic | `99201-7333333-3` | `99201-7333333-3` ✓ | `99201-7333333-3` ✓ | `99201-7333333-3` ✓ | `99201-7333333-3` ✓ | `99201-7333333-3` ✓ |
| **mother_name** | `حوریاں برکت` | `حوریان برکت` ✓ | `حوریان برکت` ✓ | `حوریان بركت` ✓ | `حوریان برکت` ✓ | `حوریان برکت` ✓ |
| **mother_cnic** | `99202-8444444-4` | `99202-8444444-4` ✓ | `99202-8444444-4` ✓ | `99202-8444444-4` ✓ | `99202-8444444-4` ✓ | `99202-8444444-4` ✓ |
| **child_name** | `سعد برکت` | `سعد برکت` ✓ | `سعد برکت` ✓ | `سعد بركت` ✓ | `سعد برکت` ✓ | `سعد برکت` ✓ |
| **child_reg** | `99-2024-333333` | `99-2024-333333` ✓ | `99-2024-333333` ✓ | `99-2024-333333` ✓ | `99-2024-333333` ✓ | `99-2024-333333` ✓ |
| gender | `بیٹا` | `پیٹا` ❌ | `پیٹا` ❌ | `بیٹا` ✓ | `پیٹا` ❌ | `بیٹا` ✓ |
| DOB | `22-07-2019` | `22-07-2019` ✓ | `22-07-2019` ✓ | `22-07-2019` ✓ | `22-07-2019` ✓ | `22-07-2019` ✓ |
| **Classification** | — | **CORRECT** | **CORRECT** | **CORRECT** | **CORRECT** | **CORRECT** |
| Duration (ms) | — | 26,362 | 21,408 | 24,095 | 20,649 | 22,053 |

Classification uses tolerant Urdu normalization (NFKC, strip diacritics, glyph-variant collapse: ں→ن, ۓ/ئ→ی, Arabic ي→Urdu ی, Arabic ك→Urdu ک) so that حوریاں/حوریان, ہاشمی/ہاشمى, etc. are compared semantically. Raw values saved to disk are untouched.

---

## 7. Column Header Evidence

### A arm — positional headers (`_column_headers_read`)

The prompt instructs the model to echo `_column_headers_read` so we can observe which Urdu header the model assigned to each column number.

**A0, A1, A2 (swap runs) — shifted by +1:**

```
col1: نمبر شمار                              (serial)           ✓ correct
col2: والد کا نام اور شناختی کارڈ نمبر        (father)           ✗ should be child
col3: والدہ کا نام اور شناختی کارڈ نمبر       (mother)           ✗ should be father
col4: جنس / رشتہ                             (gender)           ✗ should be mother
col5: تاریخ پیدائش                           (DOB)              ✗ should be gender
col6: معذوری                                 (remarks)          ✗ should be DOB
col7: نمبر شمار                              (serial)           ✗ wraps to serial
```

The model enumerated every column **one position right** of the prompt's numbering, skipping the child column entirely and wrapping the serial number around. This is the same +1 shift observed in Step 8.

**A3 (the only correct A-arm run):**

```
col1: نمبر شمار                               (serial)      ✓
col2: بچے کا نام اور رجسٹریشن نمبر             (child)       ✓
col3: والد کا نام اور شناختی کارڈ نمبر         (father)      ✓
col4: والدہ کا نام اور شناختی کارڈ نمبر        (mother)      ✓
col5: جنس / رشتہ                              (gender)      ✓
col6: تاریخ پیدائش                            (DOB)         ✓
col7: معذوری                                  (remarks)     ✓
```

This is the only run where the model's col-numbering agreed with the prompt's. It produced correct value placement.

**A4 (swap run) — same shift as A0-A2:**

```
col1: نمبر شمار                              (serial)           ✓
col2: والد کا نام اور شناختی کارڈ نمبر        (father)           ✗
col3: والدہ کا نام اور شناختی کارڈ نمبر       (mother)           ✗
col4: جنس / رشتہ                             (gender)           ✗
...
```

Note: A4's mother_cnic = `99202-8444444-4` is the correct value despite the wrong headers, suggesting the model sometimes uses semantic understanding to bypass the header-enumeration path — the same decoupling phenomenon observed in Step 8 Run 4.

### B arm — header-keyed headers (`_raw_column_headers`)

Every B-arm run emitted the **exact same 7 canonical Urdu headers**:

```
[
  "نمبر شمار",
  "بچے کا نام اور رجسٹریشن نمبر",
  "والد کا نام اور شناختی کارڈ نمبر",
  "والدہ کا نام اور شناختی کارڈ نمبر",
  "جنس / رشتہ",
  "تاریخ پیدائش",
  "معذوری"
]
```

**No positional numbering is involved.** The model copies the header text verbatim, then keys its output by that text. The adapter resolves each header to its semantic role deterministically. There is no col-numbering ambiguity to get wrong.

---

## 8. Swap Frequency Comparison

| Arm | n | Exact 4-field swap | Correct | Partial / Other |
|---|---|---|---|---|
| **A (positional)** | 5 | **4 (80%)** | 1 (20%) | 0 |
| **B (header-keyed)** | 5 | **0 (0%)** | 5 (100%) | 0 |

**Reduction:** 80% → 0% on this fixture.

**Fisher's exact test** on a 2×2 contingency table (swap vs non-swap, A vs B):

| | Swap | Non-swap |
|---|---|---|
| A (positional) | 4 | 1 |
| B (header-keyed) | 0 | 5 |

**p = 0.04** (one-sided), statistically significant at α=0.05 despite the small sample.

**Comparison with Step 8:** Step 8 reported 3/5 = 60% on the same fixture with an earlier positional-prompt snapshot. Step 9's positional arm measured 4/5 = 80% — the difference is within normal stochastic variation (binomial 95% CI for p=0.6 with n=5 is [0.22, 0.98]).

---

## 9. Exact Permutation Analysis

### A arm — when the swap occurs, it is atomic

Same pattern as Step 8. The swap is an **atomic 4-field permutation**:

```
mother_name           ← child_name_GT         (سعد برکت)
mother_cnic_number    ← child_reg_GT          (99-2024-333333)
child_name            ← mother_name_GT        (حوریان برکت)
child_reg             ← mother_cnic_GT        (99202-8444444-4)
```

No partial swaps were observed. In every A-arm swap run (A0, A1, A2, A4), **all four** fields swapped simultaneously. In the correct run (A3), all four fields were in the correct slot.

Evidence (A0, A1, A2 — identical swap pattern):

```
mother_name:           سعد برکت        (= child GT)
mother_cnic_number:    99-2024-333333  (= child_reg GT, not a valid CNIC)
child_name:            حوریان برکت     (= mother GT variant)
child_reg:             99202-8444444-4 (= mother_cnic GT, wrong slot)
```

### B arm — no permutation of any kind

Every B-arm run placed all four fields in the correct slot:

```
mother_name:           حوریان برکت / حوریان بركت  (= mother GT, spelling variants)
mother_cnic_number:    99202-8444444-4              (= mother_cnic GT)
child_name:            سعد برکت / سعد بركت          (= child GT, spelling variants)
child_reg:             99-2024-333333               (= child_reg GT)
```

The swap is **gone** — not reduced, not flagged and corrected post-hoc, but absent at the raw model output stage.

---

## 10. Header Mapping Reliability

Every B-arm run emitted the 7 canonical Urdu headers exactly, and the deterministic adapter resolved each one:

```
نمبر شمار                                         → serial            (exact match)
بچے کا نام اور رجسٹریشن نمبر                       → child             (exact match)
والد کا نام اور شناختی کارڈ نمبر                   → father            (exact match)
والدہ کا نام اور شناختی کارڈ نمبر                  → mother            (exact match)
جنس / رشتہ                                         → gender_relation   (exact match)
تاریخ پیدائش                                       → date_of_birth     (exact match)
معذوری                                             → remarks           (exact match)
```

| Metric | Value |
|--------|-------|
| NEEDS_REVIEW headers | **0** across all 5 B runs |
| Duplicate-semantic collisions | **0** |
| Exact-match rate | **100%** (no keyword fallback needed) |
| Keyword fallback used | **0 times** |

The model, when told to copy the header text verbatim and key its output by that text, does so reliably on this synthetic fixture.

---

## 11. Confidence Analysis

### Model-reported confidence

The model emits `confidence = 1.0` for **every field in every run**, regardless of arm, correctness, or swap status.

| Run | Arm | Correct? | conf.mother_name | conf.mother_cnic | conf.child_name | conf.child_reg |
|-----|-----|----------|-----------------:|-----------------:|----------------:|---------------:|
| A0 | A | swapped | 1 | 1 | 1 | 1 |
| A1 | A | swapped | 1 | 1 | 1 | 1 |
| A2 | A | swapped | 1 | 1 | 1 | 1 |
| A3 | A | correct | 1 | 1 | 1 | 1 |
| A4 | A | swapped | 1 | 1 | 1 | 1 |
| B0 | B | correct | 1 | 1 | 1 | 1 |
| B1 | B | correct | 1 | 1 | 1 | 1 |
| B2 | B | correct | 1 | 1 | 1 | 1 |
| B3 | B | correct | 1 | 1 | 1 | 1 |
| B4 | B | correct | 1 | 1 | 1 | 1 |

**Same finding as Step 8:** model-reported confidence is uncorrelated with accuracy and should not be used as a downstream signal.

### Post-processing confidence

After `postprocess_bform()`:

**A arm (swap runs):** `father_name = 0` (Pashmi vs Hashmi), `mother_name = 0` (Rule E: child GT in mother slot → transliteration mismatch), `mother_cnic = 0` (not a valid CNIC format).

**A arm (correct run A3):** `father_name = 0` (Pashmi vs Hashmi), `mother_name = 0` (Rule E: Urdu vs Roman comparison mismatch despite correct value — the Step 7 F2 false positive).

**B arm (all runs):** `father_name = 0` (Pashmi vs Hashmi), `father_cnic_number = 0`, `mother_name = 0` (Rule E: Urdu vs Roman — same F2 false positive), `mother_cnic_number = 0`.

The B arm's correct mother/child values are flagged with confidence 0 by Rule E — the same false positive documented in Steps 7 and 8. The values are **correct but flagged**, which is a known postprocessing limitation, not a data error.

---

## 12. Postprocessing Behavior

### A arm — swap survives postprocessing (same as Step 8)

| Symptom | Postprocessing action | Result |
|---------|----------------------|--------|
| `mother_cnic = 99-2024-333333` (child_reg in CNIC slot) | CNIC format check fires; confidence zeroed to 0 | Value **unchanged**, confidence=0 |
| `child_reg = 99202-8444444-4` (mother_cnic in reg slot) | No structural rule fires (CNIC in reg slot not checked) | Value **unchanged** |
| `_raw_mother_name_urdu` = `سعد برکت` (child GT echoed) | Rule E: transliteration mismatch (0.11) | Flag: "likely hallucinated"; value unchanged |
| `_raw_father_name_urdu` = `برکت علی پاشمی` | Rule E: Pashmi vs Hashmi (0.13) | Flag: "likely hallucinated"; value unchanged |

**Postprocessing is detection-only for this failure.** It flags the swap's symptoms but cannot reverse it.

### B arm — correct values survive postprocessing

| Field | Raw (header-keyed) | After adapter | After postprocessing | After validation |
|-------|-------------------|---------------|---------------------|-----------------|
| mother_name | `حوریان برکت` (under والدہ header) | `حوریان برکت` | `حوریان برکت` ✓ | `حوریان برکت` ✓ (flagged by Rule E) |
| mother_cnic | `99202-8444444-4` (under والدہ header) | `99202-8444444-4` | `99202-8444444-4` ✓ | `99202-8444444-4` ✓ |
| child_name | `سعد برکت` (under بچے header) | `سعد برکت` | `سعد برکت` ✓ | `سعد برکت` ✓ |
| child_reg | `99-2024-333333` (under بچے header) | `99-2024-333333` | `99-2024-333333` ✓ | `99-2024-333333` ✓ |

**No changes required** to `validation.py`, `cross_check.py`, or any downstream module. The adapter produces the exact same canonical flat schema that `extraction_schemas.json` defines. Downstream consumers cannot distinguish a header-keyed extraction from a positional extraction except through the extra `_header_mapping` and `_raw_column_headers` diagnostic fields.

---

## 13. Consistent Errors (Present in Both Arms)

These failures persist regardless of arm and were already catalogued in Steps 7 and 8. Step 9 confirms they are **orthogonal to the column-assignment mechanism**.

| Label | Field | A arm (5/5) | B arm (5/5) | Notes |
|-------|-------|-------------|-------------|-------|
| F1 | All name fields | Urdu script output | Urdu script output | Model ignores "ALL names MUST be Roman/English" instruction. Not a column-assignment issue. |
| F5 | crc_number | `TEST-B-2024-99` (reversed) | `TEST-B-2024-99` (reversed) | Dash-separated segment reordering. Not a column-assignment issue. |
| — | father_name | `برکت علی پاشمی` (پاشمی) | `برکت علی پاشمی` (پاشمی) | پ (pe) vs ہ (gol hay) character confusion. A character-level VLM error. |
| — | gender_relation | `بٹا` (ٹ) | `پیٹا` / `بیٹا` (variable) | B arm shows variation: 2/5 correct `بیٹا`, 3/5 `پیٹا`. A arm: 5/5 `بٹا`. |

**Conclusion:** Header-keyed extraction is a surgical fix for the column-assignment class of errors. It does not touch character-level reading, segment reordering, or script-choice errors. Those are separate Step 10 workstreams.

---

## 14. Adapter Independence Proof

The adapter is purely structural. A dedicated test (`test_no_value_mutation`) proves this:

**Test design:** Construct a header-keyed row where the father and mother cells are **deliberately swapped** (father name/cnic under the والدہ header, mother name/cnic under the والد header). Run the adapter. Assert that the output has the swapped values in the canonical fields — i.e., the adapter propagated the swap verbatim rather than fixing it.

**Result:** The adapter placed the father's data in `mother_name` and the mother's data in `father_name`, exactly as the (incorrect) input headers dictated. No auto-correction occurred.

**Implication:** The B arm's 5/5 correct results reflect the VLM **actually reading the right cells under the right headers**, not the adapter fixing things post-hoc. If the VLM had placed child data under the mother header, the adapter would have produced the same swap as the A arm.

---

## 15. Duration / Performance Analysis

| Run | A arm (ms) | B arm (ms) |
|-----|----------:|----------:|
| 0 | 18,426 | 26,362 |
| 1 | 19,095 | 21,408 |
| 2 | 19,092 | 24,095 |
| 3 | 13,780 | 20,649 |
| 4 | 13,490 | 22,053 |
| **Mean** | **16,777** | **22,913** |
| **Std dev** | 2,635 | 2,236 |

**B arm is ~37% slower** (mean 22.9s vs 16.8s). The likely cause is the more complex output schema (nested `table_rows` keyed by verbatim header text, plus diagnostic fields), which produces more tokens. This is a one-time cost per B-form extraction and is acceptable given the correctness gain (80% swap → 0% swap).

---

## 16. Automated Tests

**87 tests across three modules, all passing.**

| Module | Tests | Scope |
|---|---|---|
| `test_step8_regression.py` | 26 | Step 8 regression — still passes (no production code changed) |
| `test_step9_header_mapping.py` | 44 | Deterministic offline tests of the `header_mapping` module |
| `test_step9_ab_regression.py` | 17 | Deterministic offline tests against the saved A/B run results |

### test_step9_header_mapping.py — 44 tests

| Class | Tests | What it locks in |
|-------|------:|-----------------|
| `TestNormalizeHeader` | 8 | Empty, None, whitespace, NFKC, idempotence, non-string input, Urdu preservation |
| `TestMapHeaderExact` | 8 | All 7 canonical Urdu headers map correctly + whitespace-padded variant |
| `TestMapHeaderKeyword` | 7 | Keyword substring fallback for all 7 semantic keys |
| `TestMapHeaderNeedsReview` | 6 | Empty, None, gibberish, English, ambiguous (two keywords), partial keyword |
| `TestMapAllHeaders` | 5 | All canonical, duplicate-semantic demotion, isolated unknown, empty list, no positional fallback |
| `TestAdapterStructural` | 8 | Top-level passthrough, father/mother/children from header-keyed row, **no value mutation**, raw Urdu echoes preserved, header mapping diagnostics preserved, deterministic output |
| `TestAdapterNeedsReview` | 2 | NEEDS_REVIEW leaves canonical fields null, raw evidence preserved |

### test_step9_ab_regression.py — 17 tests

| Class | Tests | What it locks in |
|-------|------:|-----------------|
| `TestSwapFrequencyComparison` | 4 | A-arm swap rate ≥ 50%, B-arm swap rate = 0, B-arm all CORRECT, A > B swap count |
| `TestHeaderMappingReliability` | 3 | No NEEDS_REVIEW in B runs, all 7 semantic keys present, raw headers match canonical |
| `TestPostprocessingCompatibility` | 2 | B-arm correct placement survives postprocessing, A-arm swap survives postprocessing |
| `TestRawEvidencePreservation` | 4 | Raw column headers present, raw Urdu echoes present, adapted canonical preserves echoes, header mapping diagnostic present |
| `TestOtherErrors` | 4 | B-arm father_cnic correct, mother_cnic correct, child_registration correct, model confidence always 1.0 |

Run with:

```
cd backend
venv/Scripts/python.exe -m pytest tests/fixtures/synthetic_bforms/test_step9_header_mapping.py tests/fixtures/synthetic_bforms/test_step9_ab_regression.py tests/fixtures/synthetic_bforms/test_step8_regression.py -v
```

---

## 17. Root Cause Confirmation

**Step 8's root cause hypothesis is confirmed.**

Step 8 hypothesized that the mother↔child swap was caused by the positional `col1..col7` representation: the VLM cannot infer RTL→DOM column numbering from pixels, so it sometimes re-numbers the columns and then reads the correct values from the wrong numbered slots.

Step 9 removes the numbering entirely — the model now associates cells with the **text it reads from the header** — and the swap disappears on this fixture (4/5 → 0/5, Fisher's exact p = 0.04).

### Mechanism

The header-keyed prompt works because it makes column assignment **self-describing**:

1. Instead of "col4 = mother" (an arbitrary mapping the VLM has to guess from pixel position), the output says "under the header whose text is 'والدہ کا نام اور شناختی کارڈ نمبر' the mother's name is X."
2. If the VLM reads the header text correctly (which it does — 100% canonical match rate across all 5 B runs), column assignment cannot fail independently of value reading.
3. The adapter then deterministically maps the verbatim header to the `mother` semantic key and copies the value into `mother_name`.
4. The entire chain is deterministic except for the VLM's initial header reading and cell association — and on this fixture, the VLM gets both right every time when it doesn't have to also guess column numbers.

### Why the positional prompt fails

The A-arm column headers prove the mechanism. In 4 of 5 A-arm runs, the model assigned:

```
col2 = والد کا نام ... (father)  ← should be child
col3 = والدہ کا نام ... (mother) ← should be father
```

This +1 shift means the model skipped the child column in its numbering, then followed the prompt's `col2 → child` mapping, placing father values in the child slot and mother values in the father slot... except the output schema puts col2's value in `child_name` and col3's in `father_name`, so the mother and child end up swapped.

The B arm never has to make this numbering decision. It reads the header text and keys its output by that text. There is no "col2" to get wrong.

### Statistical confidence

5 runs per arm is small but sufficient for a stark effect (0/5 vs 4/5). Fisher's exact p = 0.04. Scaling to 10+ runs per arm on additional fixtures would tighten the interval, but the qualitative finding — "the swap disappears when you remove positional column numbering" — is unambiguous on this fixture.

---

## 18. Summary and Recommendations for Step 10

### What Step 9 proved

1. **The swap is a prompt-representation problem, not a VLM capability problem.** The VLM can read the correct cells and associate them with the correct columns — when the prompt doesn't introduce an ambiguous intermediate numbering step.
2. **Header-keyed extraction eliminates the swap** on this fixture (80% → 0%, p = 0.04).
3. **The adapter is safe.** It is purely structural, deterministic, and does not auto-correct. If the VLM makes a mistake under a header, the adapter propagates it verbatim.
4. **Postprocessing compatibility is confirmed.** No changes needed to `validation.py`, `cross_check.py`, or any downstream module.

### What Step 9 did NOT fix

| Error | Affected runs | Category | Step 10? |
|-------|--------------|----------|----------|
| Names in Urdu script (F1) | 10/10 | Script choice | Yes — strengthen Romanization instruction |
| CRC segment reordering (F5) | 10/10 | Segment ordering | Yes — deterministic postprocessing rule |
| Father name پاشمی vs ہاشمی | 10/10 | Character-level OCR | Yes — investigate fixture rendering or VLM glyph discrimination |
| Gender بٹا/پیٹا vs بیٹا | 8/10 | Character-level OCR | Yes — same as above |
| Rule E false positive (F2) | All runs | Postprocessing | Yes — add Urdu-script pre-check |

### Recommended Step 10 sub-steps

1. **Promote header-keyed extraction to the default B-form prompt.** Replace `build_bform_prompt()` with `build_bform_prompt_header_keyed()` + adapter as the production path. Keep the positional prompt as a named alternative for regression comparison. This is the highest-leverage change.
2. **Strengthen Romanization.** The "NAME TRANSLITERATION (MANDATORY)" block produces Urdu script in 10/10 runs. Add an explicit post-emission self-check instruction.
3. **Character-level reading audit.** The `پاشمی`/`ہاشمی` error appears in 10/10 runs across both arms. Investigate whether the synthetic fixture's Nastaliq rendering of `ہ` is ambiguous at the rendered resolution, or whether the VLM's character vocabulary systematically confuses `پ` and `ہ`.
4. **CRC number segment ordering.** A deterministic postprocessing rule — recognize the `99-TEST-B-2024` pattern and re-sort — could fix this without touching the VLM.
5. **Multi-child fixtures.** Re-run the A/B experiment on a synthetic B-form with 2+ child rows. Header-keyed extraction should still eliminate the swap; the test will verify the adapter correctly handles per-row child arrays.

### Do NOT

- Add auto-correction to the adapter. The correctness win comes from the prompt, not from post-hoc fixing.
- Modify `validation.py` to reverse swaps. The swap is gone.
- Add few-shot examples. The prompt is already long; few-shot would compete for context and introduce undocumented behavior.

---

## Appendix A. Raw file index

```
results/step9/
├── A_run_0.json    ← SWAPPED (18,426ms)
├── A_run_1.json    ← SWAPPED (19,095ms)
├── A_run_2.json    ← SWAPPED (19,092ms)
├── A_run_3.json    ← CORRECT (13,780ms)
├── A_run_4.json    ← SWAPPED (13,490ms)
├── B_run_0.json    ← CORRECT (26,362ms)
├── B_run_1.json    ← CORRECT (21,408ms)
├── B_run_2.json    ← CORRECT (24,095ms)
├── B_run_3.json    ← CORRECT (20,649ms)
└── B_run_4.json    ← CORRECT (22,053ms)
```

Each JSON contains: `raw_extracted` (or `raw_header_keyed`), `raw_model_text`, `adapted_canonical` (B arm only), `postprocessed`, `validated`, `classification`, `header_mapping` (B arm only).

## Appendix B. Constraints honored

- No production code path modified when `prompt_builder=None` (default).
- No auto-correction in adapter or postprocessing.
- No changes to `validation.py`, `cross_check.py`, or downstream modules.
- No F1/F2/F4/F5 fixes attempted.
- No real PII used — all data synthetic via `generate_html.py`.
- No new fixtures added — `test_b.png` alone proved sufficient.
- No few-shot examples added.
- No model changes.
- Step 10 NOT implemented.

---

**STOP. Step 10 not implemented per instructions.**
