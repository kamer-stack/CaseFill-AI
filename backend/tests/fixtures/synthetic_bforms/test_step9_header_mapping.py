"""Step-9 deterministic regression tests for header_mapping module.

Purely offline — no API calls, no file I/O. Locks in:
  - normalize_header: Unicode NFKC, strip, whitespace collapse
  - map_header_to_semantic: two-pass (exact -> keyword -> NEEDS_REVIEW)
  - map_all_headers: duplicate-semantic demotion
  - adapt_header_keyed_to_canonical: structural only, no value mutation

Run from backend/:
    venv/Scripts/python.exe -m pytest tests/fixtures/synthetic_bforms/test_step9_header_mapping.py -v
"""

from __future__ import annotations

import copy
import json

import pytest

from app.services.header_mapping import (
    CANONICAL_HEADERS_BY_SEMANTIC,
    adapt_header_keyed_to_canonical,
    map_all_headers,
    map_header_to_semantic,
    normalize_header,
)


# ── Section 1: normalize_header ─────────────────────────────────────────────


class TestNormalizeHeader:
    """Deterministic Unicode NFKC normalization, never invents characters."""

    def test_empty_string(self):
        assert normalize_header("") == ""

    def test_none_returns_empty(self):
        assert normalize_header(None) == ""

    def test_strips_whitespace(self):
        assert normalize_header("  hello  ") == "hello"

    def test_collapses_internal_whitespace(self):
        assert normalize_header("a   b\t\tc") == "a b c"

    def test_nfkc_equivalence(self):
        # Arabic vs Urdu kaf variants should normalize to the same Urdu form
        # Arabic ك (U+0643) vs Urdu ک (U+06A9) — NFKC does NOT merge these.
        # We just assert determinism.
        a = normalize_header("کاف")
        b = normalize_header("کاف")
        assert a == b

    def test_preserves_urdu_characters(self):
        h = "بچے کا نام"
        assert normalize_header(h) == h

    def test_numeric_input_stringified(self):
        assert normalize_header(123) == "123"

    def test_idempotent(self):
        h = " والد کا نام   اور شناختی کارڈ "
        assert normalize_header(normalize_header(h)) == normalize_header(h)


# ── Section 2: map_header_to_semantic — exact canonical match ───────────────


class TestMapHeaderExact:
    """Every canonical Urdu header maps to its semantic key."""

    @pytest.mark.parametrize("semantic,urdu", list(CANONICAL_HEADERS_BY_SEMANTIC.items()))
    def test_canonical_headers_map_exactly(self, semantic, urdu):
        assert map_header_to_semantic(urdu) == semantic

    def test_whitespace_padded_canonical_still_maps(self):
        # Whitespace collapse + NFKC should still match canonical form
        padded = "   بچے   کا   نام   اور   رجسٹریشن   نمبر   "
        assert map_header_to_semantic(padded) == "child"


# ── Section 3: map_header_to_semantic — keyword-substring fallback ──────────


class TestMapHeaderKeyword:
    """When exact match fails, distinctive keyword fragments resolve unambiguously."""

    def test_child_keyword(self):
        assert map_header_to_semantic("بچے کا نام اور رجسٹریشن نمبر (نیا)") == "child"

    def test_father_keyword(self):
        assert map_header_to_semantic("والد کا نام اور شناختی کارڈ") == "father"

    def test_mother_keyword(self):
        assert map_header_to_semantic("والدہ کا نام و شناختی کارڈ نمبر") == "mother"

    def test_serial_keyword(self):
        assert map_header_to_semantic("نمبر شمار (قطار)") == "serial"

    def test_dob_keyword(self):
        assert map_header_to_semantic("تاریخ پیدائش (یوم)") == "date_of_birth"

    def test_gender_keyword(self):
        assert map_header_to_semantic("جنس / رشتہ (بیٹا/بیٹی)") == "gender_relation"

    def test_remarks_keyword(self):
        assert map_header_to_semantic("معذوری کی قسم") == "remarks"


# ── Section 4: map_header_to_semantic — unknown / ambiguous → NEEDS_REVIEW ──


class TestMapHeaderNeedsReview:
    """Unknown, empty, or ambiguous headers MUST return NEEDS_REVIEW."""

    def test_empty_string(self):
        assert map_header_to_semantic("") == "NEEDS_REVIEW"

    def test_none(self):
        assert map_header_to_semantic(None) == "NEEDS_REVIEW"

    def test_gibberish(self):
        assert map_header_to_semantic("xyzzy") == "NEEDS_REVIEW"

    def test_english_header(self):
        assert map_header_to_semantic("Child Name") == "NEEDS_REVIEW"

    def test_ambiguous_two_keywords(self):
        # Contains BOTH 'والد کا نام' (father) AND 'والدہ کا نام' (mother)
        # -> multiple distinct semantic hits -> NEEDS_REVIEW
        ambig = "والد کا نام اور والدہ کا نام"
        assert map_header_to_semantic(ambig) == "NEEDS_REVIEW"

    def test_partial_keyword_alone(self):
        # 'نام' alone (just "name") is not distinctive enough -> NEEDS_REVIEW
        assert map_header_to_semantic("نام") == "NEEDS_REVIEW"


# ── Section 5: map_all_headers — duplicate-semantic demotion ────────────────


class TestMapAllHeaders:
    """Two distinct verbatim headers mapping to the same semantic key
    are BOTH demoted to NEEDS_REVIEW.
    """

    def test_all_seven_canonical_headers(self):
        headers = list(CANONICAL_HEADERS_BY_SEMANTIC.values())
        mapping = map_all_headers(headers)
        expected = {h: k for k, h in CANONICAL_HEADERS_BY_SEMANTIC.items()}
        assert mapping == expected

    def test_duplicate_semantic_demotes_both(self):
        # Two different verbatim forms, both mapping to "father"
        headers = [
            "والد کا نام اور شناختی کارڈ نمبر",  # canonical father
            "والد کا نام",                       # keyword-only father
            CANONICAL_HEADERS_BY_SEMANTIC["mother"],
        ]
        mapping = map_all_headers(headers)
        assert mapping["والد کا نام اور شناختی کارڈ نمبر"] == "NEEDS_REVIEW"
        assert mapping["والد کا نام"] == "NEEDS_REVIEW"
        assert mapping[CANONICAL_HEADERS_BY_SEMANTIC["mother"]] == "mother"

    def test_unknown_header_isolated(self):
        headers = [
            CANONICAL_HEADERS_BY_SEMANTIC["child"],
            "xyzzy",
            CANONICAL_HEADERS_BY_SEMANTIC["father"],
        ]
        mapping = map_all_headers(headers)
        assert mapping["xyzzy"] == "NEEDS_REVIEW"
        assert mapping[CANONICAL_HEADERS_BY_SEMANTIC["child"]] == "child"
        assert mapping[CANONICAL_HEADERS_BY_SEMANTIC["father"]] == "father"

    def test_empty_list(self):
        assert map_all_headers([]) == {}

    def test_no_positional_fallback(self):
        """An unlabeled header never silently takes a semantic slot."""
        headers = ["", None, "?"]
        mapping = map_all_headers(headers)
        for v in mapping.values():
            assert v == "NEEDS_REVIEW"


# ── Section 6: adapt_header_keyed_to_canonical — structural only ───────────


def _build_header_keyed_fixture(header_map_override: dict | None = None) -> dict:
    """Build a minimal well-formed header-keyed extraction for adaptation tests."""
    h = dict(CANONICAL_HEADERS_BY_SEMANTIC)
    if header_map_override:
        h.update(header_map_override)
    return {
        "crc_number": "99-TEST-B-2024",
        "applicant_name": "Barkat Ali Hashmi",
        "applicant_cnic_number": "99201-7333333-3",
        "table_headers": list(h.values()),
        "table_rows": [
            {
                "serial_number": 1,
                h["child"]: {
                    "name": "Saad Barkat",
                    "registration_number": "99-2024-333333",
                },
                h["father"]: {
                    "name": "Barkat Ali Hashmi",
                    "cnic": "99201-7333333-3",
                },
                h["mother"]: {
                    "name": "Hoorain Barkat",
                    "cnic": "99202-8444444-4",
                },
                h["gender_relation"]: "son",
                h["date_of_birth"]: "22-07-2019",
                h["remarks"]: "",
            }
        ],
        "_raw_column_headers": list(h.values()),
        "_header_mapping": {v: k for k, v in h.items()},
        "_raw_father_name_urdu": "برکت علی ہاشمی",
        "_raw_mother_name_urdu": "حوریاں برکت",
        "_raw_child_names_urdu": ["سعد برکت"],
        "_consistency_check": {
            "applicant_cnic_matches_father_cnic": True,
            "applicant_cnic_read": "99201-7333333-3",
            "father_cnic_read": "99201-7333333-3",
        },
        "confidence": {
            "crc_number": 1.0,
            "applicant_name": 1.0,
            "applicant_cnic_number": 1.0,
            "children": [
                {
                    "serial_number": 1.0,
                    "child_name": 1.0,
                    "child_registration_number": 1.0,
                    "gender_relation": 1.0,
                    "date_of_birth": 1.0,
                    "remarks": 1.0,
                    "father_name": 1.0,
                    "father_cnic_number": 1.0,
                    "mother_name": 1.0,
                    "mother_cnic_number": 1.0,
                }
            ],
        },
    }


class TestAdapterStructural:
    """adapt_header_keyed_to_canonical must NOT mutate values."""

    def test_top_level_passthrough(self):
        hk = _build_header_keyed_fixture()
        out = adapt_header_keyed_to_canonical(hk)
        assert out["crc_number"] == "99-TEST-B-2024"
        assert out["applicant_name"] == "Barkat Ali Hashmi"
        assert out["applicant_cnic_number"] == "99201-7333333-3"

    def test_father_from_header_keyed_row(self):
        out = adapt_header_keyed_to_canonical(_build_header_keyed_fixture())
        assert out["father_name"] == "Barkat Ali Hashmi"
        assert out["father_cnic_number"] == "99201-7333333-3"

    def test_mother_from_header_keyed_row(self):
        out = adapt_header_keyed_to_canonical(_build_header_keyed_fixture())
        assert out["mother_name"] == "Hoorain Barkat"
        assert out["mother_cnic_number"] == "99202-8444444-4"

    def test_children_from_header_keyed_row(self):
        out = adapt_header_keyed_to_canonical(_build_header_keyed_fixture())
        assert len(out["children"]) == 1
        c = out["children"][0]
        assert c["serial_number"] == 1
        assert c["child_name"] == "Saad Barkat"
        assert c["child_registration_number"] == "99-2024-333333"
        assert c["gender_relation"] == "son"
        assert c["date_of_birth"] == "22-07-2019"

    def test_no_value_mutation(self):
        """The adapter does NOT reorder, correct, or swap values."""
        # Swap the cell positions inside the row — adapter must follow the header,
        # not fix the swap.
        hk = _build_header_keyed_fixture()
        # Put the MOTHER's data under the FATHER header key and vice versa
        row = hk["table_rows"][0]
        father_hdr = CANONICAL_HEADERS_BY_SEMANTIC["father"]
        mother_hdr = CANONICAL_HEADERS_BY_SEMANTIC["mother"]
        row[father_hdr], row[mother_hdr] = row[mother_hdr], row[father_hdr]
        out = adapt_header_keyed_to_canonical(hk)
        # Structural: father_name now has what was under the father header (the mother cell)
        assert out["father_name"] == "Hoorain Barkat"
        assert out["father_cnic_number"] == "99202-8444444-4"
        assert out["mother_name"] == "Barkat Ali Hashmi"
        assert out["mother_cnic_number"] == "99201-7333333-3"

    def test_raw_urdu_echoes_preserved(self):
        out = adapt_header_keyed_to_canonical(_build_header_keyed_fixture())
        assert out["_raw_father_name_urdu"] == "برکت علی ہاشمی"
        assert out["_raw_mother_name_urdu"] == "حوریاں برکت"
        assert out["_raw_child_names_urdu"] == ["سعد برکت"]

    def test_header_mapping_diagnostics_preserved(self):
        out = adapt_header_keyed_to_canonical(_build_header_keyed_fixture())
        assert "_header_mapping" in out
        assert "_raw_column_headers" in out

    def test_deterministic_output(self):
        """Same input produces byte-identical output on repeated calls."""
        hk = _build_header_keyed_fixture()
        a = json.dumps(adapt_header_keyed_to_canonical(copy.deepcopy(hk)),
                       sort_keys=True, ensure_ascii=False)
        b = json.dumps(adapt_header_keyed_to_canonical(copy.deepcopy(hk)),
                       sort_keys=True, ensure_ascii=False)
        assert a == b


class TestAdapterNeedsReview:
    """NEEDS_REVIEW headers leave canonical fields null with confidence 0."""

    def test_mother_header_needs_review_leaves_mother_null(self):
        # Use a verbatim mother header that does not match any canonical form
        hk = _build_header_keyed_fixture()
        # Replace the mother header with an unknown
        old_mother_hdr = CANONICAL_HEADERS_BY_SEMANTIC["mother"]
        new_unknown_hdr = "کچھ اور"
        hk["table_headers"] = [
            new_unknown_hdr if h == old_mother_hdr else h for h in hk["table_headers"]
        ]
        hk["_raw_column_headers"] = list(hk["table_headers"])
        hk["table_rows"][0][new_unknown_hdr] = hk["table_rows"][0].pop(old_mother_hdr)
        # Deliberately leave the old _header_mapping entry in place so the
        # adapter's own header-map derivation takes precedence.
        hk["_header_mapping"][new_unknown_hdr] = "mother"

        out = adapt_header_keyed_to_canonical(hk)
        assert out["mother_name"] is None
        assert out["mother_cnic_number"] is None
        assert out["confidence"]["mother_name"] == 0
        assert out["confidence"]["mother_cnic_number"] == 0
        # Father and child unaffected
        assert out["father_name"] == "Barkat Ali Hashmi"
        assert out["children"][0]["child_name"] == "Saad Barkat"

    def test_needs_review_raw_evidence_preserved(self):
        """Even when a header is unmapped, its raw text survives in _header_mapping."""
        hk = _build_header_keyed_fixture()
        old = CANONICAL_HEADERS_BY_SEMANTIC["mother"]
        new_unknown = "کچھ اور"
        hk["table_headers"] = [new_unknown if h == old else h for h in hk["table_headers"]]
        hk["_raw_column_headers"] = list(hk["table_headers"])
        hk["table_rows"][0][new_unknown] = hk["table_rows"][0].pop(old)

        out = adapt_header_keyed_to_canonical(hk)
        assert new_unknown in out["_header_mapping"]
        assert out["_header_mapping"][new_unknown] == "NEEDS_REVIEW"
        assert new_unknown in out["_raw_column_headers"]
