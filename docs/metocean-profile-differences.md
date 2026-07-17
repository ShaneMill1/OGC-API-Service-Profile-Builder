# MetOcean Profile — differences between `metocean_profile.yaml` and OGC 26-027

This records every point where `examples/metocean_profile.yaml` (and the
artifacts generated from it) diverges from the authoritative source of the
MetOcean Profile for OGC API – EDR (OGC 26-027, Draft).

- **Source of truth:** `github.com/opengeospatial/metocean-ogcapi-environmental-data-retrieval-profile` (AsciiDoc). This is the text-bearing origin of the scanned OGC 26-027 PDF.
- **Tool:** `oapi-profile-builder`, which generates OGC API – EDR Part 3 service-profile artifacts (OpenAPI 3.1, requirements/tests AsciiDoc, Metanorma PDF) from one YAML config.
- **Prepared with AI assistance; to be reviewed by Shane Mill (NOAA). Internal — not an OGC document.**

Content was rephrased for compliance with licensing restrictions.

## 1. Faithfully represented (no divergence)

- All four requirements classes — Core, Insitu observations, NWP, Data query response format — modelled as EDR Part 3 conformance classes in a single profile document, with per-collection class membership (`conformance_classes`) and class-scoped mandatory data-query sets (`conformance_class_requirements`).
- Core rules: title present and ≤ 50 chars; `rel=license` link with `type=text/html` (CC BY 4.0 for open data); `extent.spatial.crs`/`crs` = `OGC:CRS84`; `extent.temporal.trs` = `Gregorian`; collection identifiers from the fixed value list with optional postfix; `/locations` GeoJSON FeatureCollection with `id` + `properties.name`; RFC 9457 error responses + HTTP 204 empty results.
- Insitu class: mandatory `locations`/`area`/`radius`; radius `within_units ⊇ {m}`; `standard_name` and `level` custom dimensions with the required `reference` strings.
- NWP class: `position`/`cube` queries; `/instances/{instanceId}` model-run granularity; the full Annex D ECMWF short-name parameter matrix.
- Data query response format: CoverageJSON offered on every data query.
- Document metadata: doc number 26-027, `profile` subtype, draft status, editors Håvard Futsæter (MET Norway) and Tom Kralidis (MSC), submitting organizations, dates (2026-05-08), keywords, external id.
- All 19 normative requirements and matching abstract tests transcribed and grouped by class.

## 2. Runtime behaviours — out of scope for a static artifact generator

These are correctly represented in the requirement/abstract-test text but cannot be *enforced* by generated artifacts; they belong to live-server conformance testing (`validate-server` / CITE):

| Requirement | Reason |
|---|---|
| `/req/nwp/collection_data_queries` B — "no instance = latest" | Server routing behaviour. |
| `/req/nwp/collection_data_queries` C — `datetime` range → HTTP 400 | Runtime request handling. |
| `/req/data-query-response-format/referencing` — `domain.referencing.system.id` echoes the `crs` query param | Property of a live data response. |
| `/req/insitu-observations/coveragejson_parameters` — `metocean:*` fields on CoverageJSON `parameters` | Property of a live coverage response, not the profile's static OpenAPI. |
| `/req/core/error_handling` B — partial-extent queries return the in-extent portion | Runtime query behaviour. |

## 3. Tooling limitations (config is faithful; generated schema can't express it)

- **Per-class parameter schemas** *(resolved)*. Insitu requires `metocean:standard_name`, `metocean:level` and `measurementType` on every parameter (`/req/insitu-observations/collection_parameter_names`), while NWP requires an ECMWF short-name `id` and description (`/req/nwp/collection_parameter_names`). The builder now supports a per-collection `parameter_schema` override, so the insitu collection's generated OpenAPI marks the `metocean:*`/`measurementType` fields required and the NWP collection's marks `id` required — the profile-level `parameter_schema` remains the Core baseline for any collection without an override.
- **`instanceId` format not validated.** `/req/nwp/collection_granularity` C requires instance ids to be RFC3339 datestamps. The generator produces the `/instances/{instanceId}` path but does not constrain the id format in the generated OpenAPI.
- **CoverageJSON `metocean:*` injection.** `/req/insitu-observations/coveragejson_parameters` is satisfied only by an author-supplied CoverageJSON `schema_ref`; the fields are not auto-injected.

## 4. Issues in the source document itself

- **Annex D placeholder.** The NWP parameter matrix lists "Total solid precipitation" with the ECMWF short name literally `TODO fix`. This entry is **omitted** from `parameter_names` (a key of `TODO fix` is not a valid parameter name). All 19 other Annex D parameters are included.
- **Conformance-class naming inconsistency.** Clause 2 (Conformance) lists the classes as "Core", "Observations", and "Numerical Weather Prediction" — only three, and using "Observations" rather than the "Insitu observations" heading used in Clause 8. It also omits "Data query response format", which is defined as a requirements class elsewhere. This config uses the four requirements-class identifiers consistently (`core`, `insitu-observations`, `nwp`, `data-query-response-format`).
- **Requirement-class anchor typo.** The NWP requirements-class file uses the anchor `rc_insitu-nwp` (likely a copy/paste from the insitu class). Not reflected here; the class key is `nwp`.
- **Requirement text plural/singular mismatch.** `/req/insitu-observations/collection_parameter_names` refers to custom dimensions `standard_names`/`levels` (plural) while `/req/insitu-observations/collection_custom_dimensions` defines them as `standard_name`/`level` (singular). This config uses the singular ids from the custom-dimensions requirement.

## 5. Interpretations and approximations (author choices)

- **CRS literal form.** The source uses the CURIE `OGC:CRS84` (e.g. in the referencing requirement). This config uses `OGC:CRS84` verbatim rather than the equivalent URI `http://www.opengis.net/def/crs/OGC/1.3/CRS84` used elsewhere in the tool's examples.
- **QUDT units / CF observed properties for NWP.** Annex D gives only parameter names and ECMWF short names — no units or CF standard names. The units (QUDT URIs) and `observedProperty.id` (NERC CF standard names) assigned to each NWP parameter are reasonable choices, not values from the source, and should be reviewed. Notable approximations: `gh` uses metre (QUDT has no geopotential-metre unit); `tcc` uses `UNITLESS`; `tp` uses metre (ECMWF convention) with CF `lwe_thickness_of_precipitation_amount`.
- **Vertical extent / VRS.** The NWP collection uses `vrs: "Pressure level in hPa"` from the recommended vocabulary in `/rec/core/collection_vertical_extent`; the specific pressure levels are illustrative.
- **Parameter/collection sample values.** Extents (bbox, temporal interval), the insitu parameter set (5 representative parameters), station levels, and example hrefs are illustrative, not prescribed by the source.
- **Conformance-class URIs.** The source states requirements-class URIs (`.../req/<class>`). The generated requirements/conformance classes use `.../req/<class>` and `.../conf/<class>` under `spec_uri_base`; `required_conformance_classes` also lists the EDR Part 1 Core and Collections classes as declared dependencies.
- **Requirement identifier form.** Requirement ids are globally unique and class-prefixed (e.g. `insitu-collection-data-queries`), so the generated identifiers read `/req/insitu-observations/insitu-collection-data-queries` rather than the source's `/req/insitu-observations/collection_data_queries`. Global uniqueness is required by the builder (abstract tests reference requirements by id); the class prefix is redundant but unambiguous. The class grouping, statements, and parts match the source.

## 6. Follow-ups worth considering

1. Optionally validate `instanceId` as RFC3339 in the generated OpenAPI for NWP collections.
2. Provide a MetOcean CoverageJSON `schema_ref` that injects the `metocean:*` parameter fields.
3. Have a MetOcean domain expert confirm the NWP unit/observed-property assignments in §5.
4. Track upstream resolution of the Annex D "Total solid precipitation" placeholder and add it once defined.
