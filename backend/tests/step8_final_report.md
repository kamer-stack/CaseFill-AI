# Step 8 Final Report — Reproduce and Isolate the Mother↔Child Column Swap

**Fixture:** `backend/tests/fixtures/synthetic_bforms/test_b.png`
**Model:** `qwen-vl-max` (default; `QWEN_MODEL` env override not set)
**Runner:** `tests/fixtures/synthetic_bforms/run_step8_repeatability.py` (5 independent API calls, stateless single-shot)
**Regression tests:** `tests/fixtures/synthetic_bforms/test_step8_regression.py` (26 tests, all pass)
**Full suite baseline at report time:** 156 tests, 0 failures
**Date:** 2026-09-04

---

## 1. Ground Truth Reference

| Field | Ground-truth value |
|-------|-------------------|
| crc_number | `99-TEST-B-2024` |
| applicant_name | `Barkat Ali Hashmi` (Urdu: `برکت علی ہاشمی`) |
| applicant_cnic_number | `99201-7333333-3` |
| father_name | `Barkat Ali Hashmi` (Urdu: `برکت علی ہاشمی`) |
| father_cnic_number | `99201-7333333-3` |
| mother_name | `Hoorain Barkat` (Urdu: `حوریاں برکت`) |
| mother_cnic_number | `99202-8444444-4` |
| child[0].child_name | `Saad Barkat` (Urdu: `سعد برکت`) |
| child[0].child_registration_number | `99-2024-333333` |
| child[0].gender_relation | `son` |
| child[0].date_of_birth | `22-07-2019` |

The scenario is explicitly "Applicant == father (legitimately same)" — the mother is a distinct person with distinct name and distinct CNIC.

---

## 2. Five-Run Comparison Table

All five runs used the **same image, same prompt template, same model**. Each was an independent stateless API call.

| Field | GT | Run 0 | Run 1 | Run 2 | Run 3 | Run 4 |
|-------|-----|-------|-------|-------|-------|-------|
| crc_number | `99-TEST-B-2024` | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ | `TEST-B-2024-99` ❌ |
| mother_name (Urdu) | `حوریاں برکت` | `سعد برکت` ❌ (child GT) | `حوریان برکت` ✓ | `سعد برکت` ❌ (child GT) | `سعد برکت` ❌ (child GT) | `حوریان بركت` ✓ |
| mother_cnic | `99202-8444444-4` | `99-2024-333333` ❌ (child_reg GT) | `99202-8444444-4` ✓ | `99-2024-333333` ❌ (child_reg GT) | `99-2024-333333` ❌ (child_reg GT) | `99202-8444444-4` ✓ |
| child[0].child_name (Urdu) | `سعد برکت` | `حوریان برکت` ❌ (mother GT) | `سعد بركت` ✓ | `حوریان برکت` ❌ (mother GT) | `حوریان برکت` ❌ (mother GT) | `سعد بركت` ✓ |
| child[0].child_reg | `99-2024-333333` | `99202-8444444-4` ❌ (mother_cnic GT) | `99-2024-333333` ✓ | `99202-8444444-4` ❌ (mother_cnic GT) | `99202-8444444-4` ❌ (mother_cnic GT) | `99-2024-333333` ✓ |
| gender_relation | son | `بٹا` ❌ | `بٹا` ❌ | `بٹا` ❌ | `بٹا` ❌ | `بٹا` ❌ |
| _column_headers_read.col2 | `بچے کا نام...` | `والد کا نام...` ❌ (father) | `بچے کا نام...` ✓ | `والد کا نام...` ❌ | `والد کا نام...` ❌ | `والد کا نام...` ❌ |
| Classification | — | SWAPPED | CORRECT | SWAPPED | SWAPPED | CORRECT values / WRONG headers |
| Duration (ms) | — | 19055 | 23426 | 13569 | 17687 | 15708 |

---

## 3. Swap Frequency

| Outcome | Count | Percentage |
|---------|------:|-----------:|
| Exact mother↔child swap (runs 0, 2, 3) | 3 | 60% |
| Correct values (runs 1, 4) | 2 | 40% |
| Correct values AND correct headers (run 1 only) | 1 | 20% |
| Correct values WITH wrong headers (run 4) | 1 | 20% |

**The swap is stochastic, not deterministic.** The same image, same prompt, same model produced opposite value assignments across runs. This is a model-layer sampling issue, not a prompt-layer or postprocessing-layer bug.

---

## 4. Exact Permutation Analysis

When the swap occurs it is an **atomic 4-field permutation**:

```
mother_name           ← child_name_GT
mother_cnic_number    ← child_registration_number_GT
child_name            ← mother_name_GT
child_registration_number ← mother_cnic_number_GT
```

No partial swaps were ever observed. In every swap run, **all four** fields swapped simultaneously, and in every correct run, all four fields were in the correct slot. The swap is a single coherent column-assignment decision, not independent per-field errors.

Evidence (runs 0, 2, 3 — identical swap pattern):

```
mother_name:           سعد برکت        (= child GT)
mother_cnic_number:    99-2024-333333  (= child_reg GT, not a valid CNIC)
child[0].child_name:   حوریان برکت     (= mother GT variant)
child[0].child_reg:    99202-8444444-4 (= mother_cnic GT, wrong slot)
```

**Test:** `test_swap_is_atomic_not_partial` — asserts that the 4 swap indicators always agree.

---

## 5. Column Header Evidence

The prompt instructs the model to echo `_column_headers_read` so we can observe which Urdu header the model assigned to each column number.

### 5.1 Swap runs (0, 2, 3) — shifted by +1

```
col1: نمبر شمار                              (serial)           ✓ correct
col2: والد کا نام اور شناختی کارڈ نمبر        (father)           ✗ should be child
col3: والدہ کا نام اور شناختی کارڈ نمبر       (mother)           ✗ should be father
col4: جنس / رشتہ                             (gender)           ✗ should be mother
col5: تاریخ پیدائش                           (DOB)              ✗ should be gender
col6: معذوری                                 (remarks)          ✗ should be DOB
col7: نمبر شمار                              (serial)           ✗ wraps to serial
```

The model enumerated every column **one position right** of the prompt's numbering, skipping the child column entirely and wrapping the serial number around.

### 5.2 Run 1 — the only fully correct run

```
col1: نمبر شمار                               (serial)      ✓
col2: بچے کا نام اور رجسٹریشن نمبر             (child)       ✓
col3: والد کا نام اور شناختی کارڈ نمبر         (father)      ✓
col4: والدہ کا نام اور شناختی کارڈ نمبر        (mother)      ✓
col5: جنس/رشتہ                                (gender)      ✓
col6: تاریخ پیدائش                            (DOB)         ✓
col7: معذوری                                  (remarks)     ✓
```

### 5.3 Run 4 — the decoupling breakthrough

Run 4 reported the **same wrong headers as the swap runs** (col2=father), yet emitted **correct values** (mother_name ≈ mother GT, child_name ≈ child GT). This is the single most informative observation in Step 8:

> Header enumeration and value assignment use **different internal mechanisms** in the model. They can disagree.

**Test:** `test_run_4_has_wrong_headers_but_correct_values`.

---

## 6. RTL / Table Geometry Analysis

The fixture is generated with `table.bform { direction: rtl; }` and `<html lang="ur" dir="rtl">`. The DOM column order in `generate_html.py` matches the prompt's numbering:

| DOM position | Visual position (RTL) | Urdu header | Prompt col# |
|-------------:|----------------------:|-------------|------------:|
| 1st `<th>` | **rightmost** | نمبر شمار (serial) | 1 |
| 2nd `<th>` | 2nd from right | بچے کا نام... (child) | 2 |
| 3rd `<th>` | center | والد کا نام... (father) | 3 |
| 4th `<th>` | 2nd from left | والدہ کا نام... (mother) | 4 |
| 5th `<th>` | 2nd from left | جنس / رشتہ (gender) | 5 |
| 6th `<th>` | near left | تاریخ پیدائش (DOB) | 6 |
| 7th `<th>` | **leftmost** | معذوری (remarks) | 7 |

The prompt (prompts.py:81–94) states:

> *"The B-form table has 7 columns in right-to-left order."*
> *Column 1 = serial, Column 2 = child, Column 3 = father, Column 4 = mother, ...*

This is correct for DOM order under RTL rendering. But a VLM observes **pixels**, not DOM. The ambiguity is in what "right-to-left" means:

- **Interpretation A (intended):** Column numbers follow the DOM/RTL reading direction. col1=rightmost, col2=2nd from right, etc.
- **Interpretation B (what the model actually does):** Column numbers are a standard visual left-to-right enumeration of the columns the model sees in the pixels. col1=leftmost... no, wait — the model always gets col1=serial (rightmost), so this isn't pure LTR.

The empirical behavior matches a third, inconsistent interpretation:

- The model anchors col1 at the **rightmost** column (correct),
- then numbers subsequent columns by moving **leftward** (skipping the child column because it does not visually match the next expected semantic slot),
- producing col2=father, col3=mother, col4=gender, ...

This is not a consistent LTR or RTL enumeration. It is a **semantically-influenced** column numbering that sometimes lands on the right slots (run 1) and sometimes drifts by one position (runs 0/2/3/4).

---

## 7. Prompt Column Semantics Analysis

The prompt (prompts.py:81–151) encodes column semantics in two coupled ways:

1. **A numbered table** mapping `col# → Urdu header → meaning → JSON field` (lines 86–94).
2. **Rules A–G** that reference columns by number with Urdu disambiguators (e.g., Rule D on والد vs والدہ, Rule G forbidding child_registration_number from columns 3/4).

The coupling is the source of the swap:

- The model first enumerates `_column_headers_read.colN = <Urdu header>`.
- Then it uses the prompt's numbered mapping to decide which JSON field to fill.
- When the model's colN→header assignment disagrees with the prompt's colN→field mapping, the values land in the wrong JSON slots even if the model read the cells correctly.

**Rules A, B, G** are structural cross-checks (same-across-rows vs different-across-rows). They are violated when the swap occurs — the model emits a CNIC-formatted number into `child_registration_number` and a non-CNIC into `mother_cnic_number` — but the model's confidence is still 1.0, indicating the rules are not being applied at inference time.

---

## 8. Postprocessing Behavior

Postprocessing (`postprocess_bform` + `validate_extraction`) is run separately on the captured raw output. It **flags** the swap's symptoms but **does not reverse** it.

| Symptom | Postprocessing action | Result after postprocessing |
|---------|----------------------|----------------------------|
| `mother_cnic = 99-2024-333333` (child_reg in CNIC slot) | CNIC format check fires; confidence zeroed to 0 | Value **unchanged**, confidence=0 |
| `child_reg = 99202-8444444-4` (mother_cnic in reg slot) | Rule G sanity check: reg matches a parent CNIC | Value **unchanged** (no swap reversal) |
| `_raw_mother_name_urdu` = `سعد برکت` (child GT echoed verbatim) | Rule E SequenceMatcher 0.6 vs transliteration → low similarity (0.11) | Flag: "likely hallucinated (NEEDS_REVIEW)"; value unchanged |
| `_raw_father_name_urdu` = `برکت علی پاشمی` | Rule E fires (Hashmi vs Pashmi similarity 0.13) | Flag: "likely hallucinated (NEEDS_REVIEW)"; value unchanged |

**Postprocessing is detection-only for this failure.** It cannot swap values back because it has no way to know whether the current assignment is swapped or correct — both look internally consistent once the values are placed.

**Tests:** `test_postprocessing_does_not_reverse_swap`, `test_swap_run_flags_mother_cnic_and_names`, `test_correct_run_1_only_flags_father_name`.

---

## 9. Confidence Analysis

The model emits `confidence = 1.0` for **every field in every run**, regardless of whether the value is correct, swapped, or structurally invalid.

| Run | Correct values? | confidence.mother_name | confidence.mother_cnic_number | confidence.child_name |
|----:|----------------:|----------------------:|-----------------------------:|---------------------:|
| 0 | swapped | 1 | 1 | 1 |
| 1 | correct | 1 | 1 | 1 |
| 2 | swapped | 1 | 1 | 1 |
| 3 | swapped | 1 | 1 | 1 |
| 4 | correct values, wrong headers | 1 | 1 | 1 |

After postprocessing, confidence is zeroed on fields where structural rules fire:

- Swap runs: `confidence.father_name = 0`, `confidence.mother_name = 0`, `confidence.mother_cnic_number = 0`.
- Correct runs: `confidence.father_name = 0` (Hashmi→Pashmi), `confidence.mother_name = 0` (transliteration mismatch on the Urdu echo).

**The model's self-reported confidence is uncorrelated with accuracy and should not be used as a downstream signal.** Only postprocessing-derived confidence is meaningful.

---

## 10. Consistent Errors (Present in All 5 Runs)

These failures are present regardless of swap outcome and were already catalogued in Step 7. Step 8 confirms they are **model-intrinsic and reproducible**.

| Label | Field | Observation | Expected |
|-------|-------|-------------|----------|
| F1 | All name fields | Output in Urdu script despite "NEVER output Urdu/Arabic script" instruction | Roman/English transliteration |
| F5 | crc_number | `TEST-B-2024-99` (reversed) | `99-TEST-B-2024` |
| — | father_name | `برکت علی پاشمی` (پاشمی, Pashmi) | `برکت علی ہاشمی` (ہاشمی, Hashmi) |
| — | gender_relation | `بٹا` (ٹ) | `بیٹا` (ی) — single-character difference |
| — | All confidence | 1.0 across all fields | Calibrated to accuracy |

---

## 11. Root Cause Hypothesis

The mother↔child swap is caused by a **column-numbering ambiguity at the VLM layer** combined with the prompt's reliance on numbered column positions:

1. The prompt defines `col1..col7` assuming a specific RTL→DOM mapping.
2. The VLM observes pixels. It does not have access to DOM order.
3. The VLM enumerates `_column_headers_read` by walking the visible columns in a direction that is neither purely LTR nor purely RTL, but semantically-influenced.
4. When the model's col-numbering disagrees with the prompt's col-numbering by one position (skipping the child column), the downstream mapping `col2 → child_name` causes the child cell's content to land in the parent slot and vice versa.
5. The swap is atomic because the model makes a **single column-assignment decision** per run; once the enumeration is fixed, all cells follow the same (correct or wrong) mapping.
6. The swap is stochastic because the enumeration itself is a sampled decision, influenced by prompt phrasing, image layout, and sampling temperature.

The Run 4 decoupling (wrong headers, correct values) shows that value assignment can bypass the header-enumeration path entirely — the model sometimes uses semantic understanding of cell contents to choose the right JSON slot, independent of the colN numbering it emits.

---

## 12. Automated Tests

**File:** `backend/tests/fixtures/synthetic_bforms/test_step8_regression.py`
**Count:** 26 tests across 8 test classes
**Result:** All 26 pass; full suite 156/156 pass.

| Class | Tests | What it locks in |
|-------|------:|-----------------|
| `TestSwapFrequency` | 3 | Swap rate 3/5, correct rate 2/5 |
| `TestExactPermutation` | 2 | Swap is atomic (all 4 fields or none) |
| `TestColumnHeaders` | 6 | Per-run header assertions incl. Run 4 decoupling |
| `TestConsistentErrors` | 4 | CRC reversal, Hashmi→Pashmi, Urdu output, بٹا |
| `TestPostprocessingBehavior` | 5 | Flags fire, values unchanged, swap not reversed |
| `TestDeterministicPostprocessing` | 2 | Same input → same postprocessing output |
| `TestConfidenceAnalysis` | 2 | Model confidence always 1.0, postprocessing zeros |
| `TestStep7Consistency` | 2 | Step 8 matches Step 7 saved result |

Run with:

```
cd backend
venv/Scripts/python.exe -m pytest tests/fixtures/synthetic_bforms/test_step8_regression.py -v
```

---

## 13. Recommendations for Step 9

Step 9 has NOT been implemented. The following are recommendations for the next step based on Step 8 findings:

1. **Attack the column-numbering ambiguity in the prompt.** Replace the numbered `col1..col7` scheme with **explicit visual-position anchors** ("rightmost column", "2nd from right", ...) or with **header-keyed** output (`{"<Urdu header>": <value>, ...}`) that removes the model's need to number columns.
2. **Add structural swap-detection to postprocessing.** If `child_registration_number` matches a valid CNIC format AND equals `mother_cnic_number`, and `mother_cnic_number` is non-CNIC but matches the sibling row's registration format, auto-swap and flag. The data contains enough signal to reverse the swap deterministically; postprocessing currently refuses on principle ("will not reconstruct from another CNIC").
3. **Force the model to emit column headers BEFORE values.** Reorder the output JSON so `_column_headers_read` comes first. This makes the enumeration a committed prefix rather than a post-hoc rationalization and may bias the value-assignment path to be consistent with it.
4. **Add few-shot examples** showing the same table with correct colN→header→value mapping. The current prompt is zero-shot on column disambiguation.
5. **Treat F1 (Urdu output) and F5 (CRC reversal) as separate Step 9 workstreams**; Step 8 confirms they are reproducible and orthogonal to the swap.
6. **Do not rely on model-reported confidence** for any downstream decision. Postprocessing-derived confidence is the only meaningful signal.

---

## Appendix A. Raw file index

- `results/step8/run_0.json` — SWAPPED
- `results/step8/run_1.json` — CORRECT (headers and values)
- `results/step8/run_2.json` — SWAPPED
- `results/step8/run_3.json` — SWAPPED
- `results/step8/run_4.json` — CORRECT values, WRONG headers

## Appendix B. Constraints honored

- No production code modified (`app/services/prompts.py`, `extraction.py`, `validation.py`, `cross_check.py` all unchanged by Step 8).
- No F1/F2/F4/F5 fixes attempted.
- No real PII used — all data synthetic via `generate_html.py`.
- No new fixtures added — `test_b.png` alone proved sufficient to isolate the swap.
- Step 9 NOT implemented.
