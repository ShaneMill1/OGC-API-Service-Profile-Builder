# Comparison: Tool-Generated PDF vs OGC Draft 26-027

Comparison of the tool-generated MetOcean profile PDF against the reverse-engineered
OGC draft document [26-027](https://docs.ogc.org/DRAFTS/26-027.pdf).

- **Tool output:** `generated/metocean_profile/document.pdf` (36 pages)
- **Reference:** OGC Draft 26-027 (63 pages)

## Summary

The tool-generated PDF captures the **normative substance** accurately: all 19 requirements,
4 requirements classes, and 19 abstract tests match one-for-one with the draft. However, the
draft is substantially richer, and much of that content is missing from the tool output.

## What matches

| Item | Status |
|------|--------|
| Cover / external identifier / version / dates / editors | Identical |
| Requirements 1–19 (statements + A/B/C/D parts) | Match near-verbatim |
| 4 requirements classes + 19 abstract tests (A.1–A.19) | Present and correctly mapped |
| Keywords, submitters table, security considerations | Equivalent |

## Bucket 1 — Tooling should replicate (draft has it, tool dropped/simplified it)

| # | Draft content | Tool output | Root cause |
|---|---------------|-------------|------------|
| 1 | Sections **5 Conventions**, **6 Introduction**, and **8/9/10** as named chapters (Insitu, NWP, DQRF each their own chapter) | Collapsed into a single flat "5. Requirements" chapter | Tool does not emit per-requirements-class chapters or narrative sections |
| 2 | **Recommendations** (Rec 1 vertical extent, Rec 2 data-query metadata, Rec 3 measurementType/CF cell methods) | Absent entirely | `profile_config.json` has 0 recommendation-type items; tool models only SHALL requirements |
| 3 | **Section 4.1 Abbreviated terms** (Table 2, ~30 abbreviations) | "No terms and definitions" | `document_metadata.terms = []` — not populated |
| 4 | **Annex B Schemas, Annex C Examples, Annex D NWP parameter matrix (Table D.1), Annex E Revision history, Bibliography** | Only Annex A present | Tool does not generate these annexes; `collection_examples={}`, no revision-history model |
| 5 | **Per-class requirements-class tables** with Dependency/Pre-conditions (e.g. Core depends on EDR Part 1 Core + Collections; Insitu depends on Core + DQRF) | Only IDENTIFIER/CONFORMANCE/TARGET-TYPE shown | Dependency metadata not modeled |
| 6 | **Abstract test detail** — draft tests give concrete HTTP steps, media types, status codes | Tool tests are one-line summaries | Test steps are heavily abbreviated |
| 7 | **Preface / Introduction narrative** — draft Preface has RODEO project narrative | Tool Preface is one generic sentence | Introduction narrative not modeled |

## Bucket 2 — Report to authors (defects in the draft itself)

| # | Issue in OGC Draft 26-027 |
|---|---------------------------|
| 1 | **Annex D typo**: "Total solid precipitation → `TODO fix`" — a literal TODO left in the published draft (Table D.1) |
| 2 | **Typos**: "Norwegian Meteorological Institut" (missing 'e'), "temporal extent of a collction", "reseach", "in english" (lowercase) |
| 3 | **Conformance section mismatch**: §2 lists classes as "Core", "Observations", "Numerical Weather Prediction" — omits "Data query response format" and names it "Observations" instead of "Insitu observations" (inconsistent with §8 and Annex A) |
| 4 | **Req 12 vs ATS mismatch**: Req 12 says `metocean:standard_name`/`metocean:level` values come from custom dimensions with ids `standard_names`/`levels` (plural), but Req 13 / Annex A define the dimension ids as `standard_name`/`level` (singular) |
| 5 | **A.2.2 type mismatch**: ATS says check `metocean:level` "value of type number", but the custom-dimension/level model elsewhere implies string height labels |
| 6 | **Duplicate heading numbering**: "iii." used twice (Security Considerations AND Submitters both numbered iii) |
| 7 | **Annexes B & C are empty** in the draft (headings only) — partly an authoring gap, not only a tooling gap |

## Recommended next steps

1. **Tooling backlog** (Bucket 1): enhance the config schema + generator to model recommendations,
   abbreviated terms, per-class dependency tables, Annex C/D/E, and full abstract-test steps.
2. **Author feedback** (Bucket 2): the `TODO fix`, typos, the §2 conformance-class naming/count
   inconsistency, the singular/plural `standard_name(s)`/`level(s)` mismatch, and the
   `metocean:level` number-vs-string mismatch.
