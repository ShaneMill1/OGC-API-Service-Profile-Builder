# MetOcean Profile — fidelity and provenance notes

`examples/metocean_profile.yaml` is the **single source of truth** for the
MetOcean Profile for OGC API – EDR (OGC 26-027). It is a complete, declarative
definition from which `oapi-profile-builder` generates every artifact — the
OpenAPI document, the requirements/abstract-test AsciiDoc, and the full
Metanorma OGC document (PDF/HTML). It is intended to **replace** the
hand-authored `.adoc` document workflow, not sit alongside it.

This document is the provenance record for that config: it states what is
reproduced from the authoritative source, and — importantly — the few places
where the generated output **intentionally** deviates from the source, and why.
Everything here is a reviewed, deliberate choice, not an approximation.

- **Source of truth for content:** `github.com/opengeospatial/metocean-ogcapi-environmental-data-retrieval-profile` (AsciiDoc).
- **Tool:** `oapi-profile-builder`, which generates OGC API – EDR Part 3 service-profile artifacts from one YAML config.
- **Prepared with AI assistance; to be reviewed by Shane Mill (NOAA). Internal — not an OGC document.**

## 1. Verbatim content (single source of truth)

All document prose is held **verbatim** in the config and reproduces the source
byte-for-byte (confirmed by diffing the generated `sections/*.adoc` against the
upstream clause files — the diffs are empty). There are no external `.adoc`
dependencies; the YAML carries everything. The generated requirement,
recommendation and conformance **identifiers also match the source exactly**
(`/req/<class>/<name>`, `/rec/<class>/<name>`, `/conf/<class>/<name>` with the
source's bare names — see §2).

- **Abstract, Scope, Conventions, Introduction** — the authored prose (including
  the source's own in-text wording, sub-headings, footnotes, and even its
  typos) is copied exactly into `document_metadata.body`.
- **Annex D** — the NWP Global Deterministic parameter-name matrix is reproduced
  exactly as a table, including the source's literal `Total solid precipitation |
  TODO fix` row (see §3 for how the *data model* handles that placeholder).
- **Bibliography (Annex E)** and **Revision History (Annex F)** — reproduced
  exactly.
- **Annex B (Schemas)** and **Annex C (Examples)** — reproduced as the source
  has them: heading-only placeholders (the upstream document leaves these annexes
  empty pending content; see §5 follow-ups).

## 2. Faithfully modelled (structure and requirements)

- All four requirements classes — Core, Insitu observations, NWP, Data query
  response format — modelled as EDR Part 3 conformance classes in a single
  profile document, with per-collection class membership (`conformance_classes`)
  and class-scoped mandatory data-query sets (`conformance_class_requirements`).
- The document is organised as the source is: front matter, Scope, Conformance,
  References, Terms, Conventions, Introduction, then the four requirements
  classes as clauses 7–10 (each requirement/recommendation introduced by its
  source lead-in sentence), the Abstract Test Suite, and the annexes.
- All 19 normative requirements + matching abstract tests, and all 3
  recommendations (`/rec/core/collection_vertical_extent`,
  `/rec/core/data_query_response_metadata`,
  `/rec/insitu-observations/collection_parameter_names`), grouped by class.
  Recommendations render as Metanorma `[recommendation]` blocks and are excluded
  from the conformance classes — matching the EDR Part 3 intent that only SHALL
  statements are conformance-tested.
- **Identifiers match the source exactly.** Requirement ids use the source's
  bare names (e.g. `collection_data_queries`) and are unique *within a class and
  obligation* rather than globally, so the generated identifiers read
  `/req/<class>/<name>`, `/rec/<class>/<name>` and `/conf/<class>/<name>` — byte
  -identical to the source. This includes names reused across classes
  (`collection_parameter_names` in core, insitu-observations and nwp;
  `collection_data_queries` in insitu-observations and nwp) and the
  requirement/recommendation pair that share `collection_parameter_names` in the
  insitu-observations class (`/req/...` and `/rec/...`).
- Core rules (title ≤ 50 chars; `rel=license`/`text/html`; `OGC:CRS84`;
  `Gregorian` TRS; fixed-list collection identifiers; `/locations`
  FeatureCollection with `id` + `properties.name`; RFC 9457 errors + HTTP 204);
  insitu class (`locations`/`area`/`radius`; radius `within_units ⊇ {m}`;
  `standard_name`/`level` custom dimensions); NWP class (`position`/`cube`;
  `/instances/{instanceId}`; the full Annex D parameter set).
- Document metadata: doc number 26-027, `profile` subtype, draft status, editors
  Håvard Futsæter (MET Norway) and Tom Kralidis (MSC), submitting organizations,
  dates (2026-05-08), keywords, external id.

## 3. Intentional deviations from the source (reviewed)

These are the places where the generated output deliberately does **not** match
the source. Each is a conscious choice, documented so a reviewer understands it.

- **Source-document defects not replicated.** The upstream source contains a few
  errors; the generated output does **not** copy them into the normative model:
  - *Annex D placeholder.* The source lists "Total solid precipitation" with the
    literal short name `TODO fix`. The Annex D **table** reproduces this row
    verbatim (it is source text), but the entry is **excluded from the
    `parameter_names` data model** — `TODO fix` is not a valid parameter
    identifier. All 19 other Annex D parameters are present as parameters. Track
    the upstream fix and add it once defined.
  - *Conformance-class naming inconsistency.* The source's Clause 2 lists only
    three classes and calls one "Observations" (vs "Insitu observations" in
    Clause 8), omitting "Data query response format". The config uses the four
    class identifiers consistently (`core`, `insitu-observations`, `nwp`,
    `data-query-response-format`).
  - *Requirements-class anchor typo.* The source's NWP class file uses the anchor
    `rc_insitu-nwp` (a copy/paste artifact). The config's class key is `nwp`.
  - *Plural/singular mismatch.* The source's
    `/req/insitu-observations/collection_parameter_names` refers to
    `standard_names`/`levels` (plural) while the custom-dimensions requirement
    defines `standard_name`/`level` (singular). The config uses the singular ids.

- **Figure.** The source ships `images/metadata-discovery-workflow.png` but its
  Introduction clause contains no `image::` directive, so the figure is not
  embedded in the generated document either (embedding it would make the clause
  non-verbatim). A ready-to-use, commented-out `figures` scaffold is present in
  the config so the authors can enable it in two steps if they confirm the figure
  belongs in the Introduction — no tooling change needed.

## 4. Scope boundaries (static artifact vs live server)

Some source requirements describe **runtime behaviour** that a static artifact
generator cannot enforce; they are represented faithfully in the requirement and
abstract-test text, but conformance is verified against a live server
(`validate-server` / CITE), not the generated OpenAPI:

| Requirement | Why it is runtime-only |
|---|---|
| `/req/nwp/collection_data_queries` B — "no instance = latest" | Server routing behaviour. |
| `/req/nwp/collection_data_queries` C — `datetime` range → HTTP 400 | Runtime request handling. |
| `/req/data-query-response-format/referencing` — `domain.referencing.system.id` echoes the `crs` query param | Property of a live data response. |
| `/req/insitu-observations/coveragejson_parameters` — `metocean:*` fields on CoverageJSON `parameters` | Property of a live coverage response. |
| `/req/core/error_handling` B — partial-extent queries return the in-extent portion | Runtime query behaviour. |

Separately, a couple of requirements are faithful in the config but not fully
expressible as generated-OpenAPI constraints:

- **`instanceId` format.** `/req/nwp/collection_granularity` C requires RFC3339
  datestamp instance ids. The generator produces the `/instances/{instanceId}`
  path but does not constrain the id format in the OpenAPI.
- **CoverageJSON `metocean:*` injection.** `/req/insitu-observations/coveragejson_parameters`
  is satisfied by an author-supplied CoverageJSON `schema_ref`; the fields are
  not auto-injected.
- **Per-class parameter schemas** *(supported)*. Insitu requires
  `metocean:standard_name`/`metocean:level`/`measurementType`; NWP requires an
  ECMWF short-name `id`. The per-collection `parameter_schema` override marks the
  right fields required in each collection's generated OpenAPI.

## 5. PDF output — same document text, not a byte-identical file

The generated PDF reproduces the source document's content and structure, with
all authored prose verbatim, compiled with the same engine the source uses
(Metanorma `-t ogc`:
`oapi-profile-builder generate --config examples/metocean_profile.yaml --output ./out --pdf`).
The document **text** is byte-faithful; the PDF **binary** is not identical to
one built from the upstream `.adoc`, for reasons intrinsic to the toolchain:

- **No canonical reference PDF exists.** The upstream repo ships source only (no
  release/PDF asset); its PDF is re-built on demand and varies with the
  Metanorma/mn2pdf version and font cache.
- **Minor Metanorma lint deltas**: non-fatal warnings ("table should have title"
  on the Annex D / revision tables; "recommendation has no conformance test" —
  expected, since recommendations are informative). These do not affect content.

The document identifiers (requirement/recommendation/conformance) match the
source exactly (see §2), so there is no longer a text-level difference in the
requirement boxes.

## 6. Follow-ups worth considering

1. Validate `instanceId` as RFC3339 in the generated OpenAPI for NWP collections.
2. Provide a MetOcean CoverageJSON `schema_ref` that injects the `metocean:*`
   parameter fields.
3. Have a MetOcean domain expert confirm the NWP unit / observed-property
   assignments (QUDT units and NERC CF standard names are reasonable fills, not
   values from the source — Annex D gives only names and short names).
4. Track upstream resolution of the Annex D "Total solid precipitation"
   placeholder and add it to `parameter_names` once defined.
5. Fill Annex B (Schemas) and Annex C (Examples) with concrete JSON Schemas /
   worked examples once finalized upstream — the source leaves these as headings.
6. Quiet the remaining non-fatal Metanorma lint warnings (add table titles) if a
   perfectly clean build log is wanted.
