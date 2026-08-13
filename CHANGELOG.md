# CHANGELOG - OGC API - EDR Part 3 Compliance

## [3.6.1] - 2026-08-13

Fixes the self-service GitHub Action workflow when a profile sets `document_metadata.cover.logo`.

### Fixed

- **`action.yml` now installs the `[pdf]` extra unconditionally.** Previously the composite action ran `pip install oapi-profile-builder`, which omits Pillow. Any profile setting `document_metadata.cover.logo` (used by every profile with a cover image) then failed in `build_cover_image` with `ModuleNotFoundError: No module named 'PIL'`, aborting both the plain generate step and the optional `--pdf` step. The action now installs `oapi-profile-builder[pdf]` so cover-image generation succeeds regardless of whether `pdf: 'true'` is set on the workflow input.

## [3.6.0] - 2026-08-06

Aligns the PubSub (EDR Part 2) modelling with multi-transport deployments and refreshes the NWS Connect example.

### Added

- **`amqp1` protocol** on both `PubSubConfig.protocol` and `PubSubServer.protocol`: AsyncAPI protocol identifier for **AMQP 1.0** (e.g. RabbitMQ 4.x native AMQP 1.0), distinct from the AMQP 0-9-1 `amqp` binding. `PubSubServer.protocol` continues to also accept `mqtt`, `kafka`, `ws`, and `wss`.

### Changed

- **Explicit `pubsub.servers` now replace the implicit `production` server.** Previously `build_asyncapi()` always emitted a synthetic `production` server from `broker_host`/`broker_port`/`protocol` *and* appended the listed `servers`. When a profile lists `servers`, the generated AsyncAPI now uses exactly those (keyed by `name`), so a profile can describe its precise transport topology — a native WebSocket `/ws` endpoint plus AMQP 1.0 and MQTT brokers — without a spurious `production` entry. When `servers` is empty the implicit `production` server is still synthesised, so existing single-server profiles are unaffected. The per-server `variables.port` block is no longer emitted (the port is carried inline in `host`).
- **`examples/nws_connect_profile.yaml` is now the single, unified NWS Connect service profile.** It describes **all** collections the NWS Connect service exposes — `water_gauge`, `wwa`, **`space_weather`**, `cwa`, and `states` — with PubSub over `water_gauge`, `wwa`, and `space_weather`. This replaces the previous split where the deployed service advertised three separate per-collection profiles (`water-gauge-profile`, `watches_warnings_advisories`, `space_weather`). Deployed services now reference this one profile document via a `rel: profile` link (see the pygeoapi `config.yaml`), pointing at the copy hosted in this repo (`generated/nws_connect_profile/`) rather than self-hosting a fork. The `pubsub` transports model the real deployment — native `/ws` WebSocket (`ws`/`wss`), AMQP 1.0 on `edr-broker:5672`, and MQTT on `edr-broker:1883`, all authenticated with SASL PLAIN (account email + `wsk_` WebSocket key) — replacing the retired AMQP-over-WebSocket (`205.156.8.80:15670`, `/wifs_wss/`) topology. Added a service-level `description`, `keywords`, and `provider` (NOAA/NWS/MDL) block. Regenerated its artifacts.
- Regenerated `profile.schema.json` from the current models.

## [3.5.0] - 2026-07-17

Addresses the MetOcean EDR Profile (OGC 26-027, Draft) gap analysis (issue #10) — targeted additions to close the incremental gaps against the profile's requirements classes, plus support for modelling a multi-class profile document in one config. All new fields are opt-in and config is backward compatible; existing profiles validate and generate unchanged (generated OpenAPI error/locations responses do change — see below).


### Changed

- **RFC 9457 error responses** (MetOcean `/req/core/error_handling`, the most consequential gap): the generated OpenAPI now serves 4xx/5xx errors as `application/problem+json` using an RFC 9457 Problem Details schema (`type`, `title`, `status`, `detail`, `instance`) instead of the previous custom `{code, description}` / `application/json` schema. EDR data-query operations also declare a `204` (No Content) response for empty results inside the extent.
- **Constrained `/locations` response schema** (`/req/core/locations_query_response_format`): the locations query 200 response is now a GeoJSON `FeatureCollection` (`application/geo+json`) whose features require a string `id`; additional required feature properties (e.g. `name`) are driven by `locations_feature_required_properties`.

### Added

- **`collection_title_max_length`**: when set, every collection title must be present and within the limit (`/req/core/collection_title`, e.g. 50 characters).
- **`require_license_link`** / **`license_link_type`**: require a `rel='license'` link (defaulting to `type='text/html'`) on every collection (`/req/core/collection_license`).
- **`required_data_queries`**: data-query types every collection must define, enforcing the mandatory data-query sets (`/req/*/collection_data_queries`).
- **`radius_within_units_required`**: unit tokens each radius query's `within_units` must contain, e.g. `['m']` (`/req/core/collection_radius_data_query`).
- **`locations_feature_required_properties`**: feature properties marked required in the generated `/locations` response schema.
- **Conformance-class-scoped constraints** — model a single profile document that spans several EDR Part 3 requirements classes (as the MetOcean profile does):
  - **`conformance_class_requirements`** (profile-level): a map of class short name → constraints (`required_data_queries`, `radius_within_units_required`), applied only to collections that opt into the class.
  - **`collection.conformance_classes`**: the class short names a collection implements (e.g. `[core, insitu-observations]`). Drives which class-scoped requirements are enforced, round-trips into `profile_config.json`, and is surfaced as `x-conformance-classes` on the collection operation in the generated OpenAPI.
  - The flat `required_data_queries` / `radius_within_units_required` fields still apply to every collection; class-scoped constraints are additive on top, so single-class profiles are unaffected.
- **Per-collection `parameter_schema`**: `Collection.parameter_schema` (optional) overrides the profile-level `parameter_schema` for a single collection in the generated OpenAPI. Precedence is collection → profile → built-in default. This lets collections in one profile carry different parameter constraints — e.g. an insitu collection requiring `metocean:standard_name`/`metocean:level`/`measurementType` while an NWP collection requires an ECMWF short-name `id`.
- **Multi-class requirements/conformance documents**: `Requirement.conformance_class` (optional). When any requirement sets it, the generated AsciiDoc/PDF is organised into one requirements class and one conformance class per key — each with its own class URI under `spec_uri_base`, its own `requirements/<class>/` and `abstract_tests/<class>/` folders, and all classes included in order in the Requirements and Abstract Test Suite sections. When unset on all requirements, the generator keeps its single-class (`core`) layout, so existing profiles' generated documents are unchanged.
- **`examples/metocean_profile.yaml`**: a reverse-engineered MetOcean EDR Profile (OGC 26-027), transcribed from the authoritative AsciiDoc source. One document modelling the Core, Insitu observations, NWP, and Data-query-response-format classes as four EDR Part 3 conformance classes — an insitu collection (locations/area/radius) and an NWP `weather_forecast` collection (instances + position/cube) enforced per class, the full Annex D ECMWF NWP parameter matrix, and all 19 normative requirements + abstract tests grouped by class. Divergences from the source are recorded in `docs/metocean-profile-differences.md`.
- The `insitu_observations_profile.yaml` example now opts into the flat Core constraints to demonstrate a MetOcean-aligned single-class configuration; regenerated its artifacts and `profile.schema.json`.

## [3.4.1] - 2026-07-17

Maintenance release — CI and release tooling only; no functional changes to the builder.

### Changed

- **Per-release GitHub Release notes**: the Release workflow now builds the release body from the matching `CHANGELOG.md` section for the tag (plus install and GitHub Actions usage snippets), so each release describes its own changes instead of repeating a static template.

### Fixed

- **Artifact-regeneration race**: the profile-artifact CI job now installs the builder from the checked-out source (`pip install .`) instead of the published PyPI package. Previously it raced the Release workflow's PyPI publish and could commit stale generated artifacts back to `main` (this had rolled back the 3.4.0 paging `limit` parameter on the non-DGIWG examples, now restored).
- README and hosted docs updated to document the 3.4.0 fields (cover layout controls, `doc_pub_date`, the structural layout opt-ins, submitting-organizations rebrand, and `paging`).

## [3.4.0] - 2026-07-17

Addresses a second round of DGIWG (Met Office) feedback on the generated PDF and profile YAML.

### Added

- **Cover-page layout controls** under `document_metadata.cover`: `logo_width`, `logo_y` (logo size and vertical position), `tagline_font_size`, `title_font_size`, and `bold_edition` (render the edition line in bold). Lets a profile match an SDO's front-page layout without code changes.
- **`document_metadata.doc_pub_date`**: explicit publication date (long format on the cover, e.g. "16 July 2026"). Takes precedence over `publication_date` for the cover and the Metanorma `:published-date:`.
- **`document_metadata.suppress_section_divider_pages`**: remove the standalone full-page section-divider pages from the PDF (structural, opt-in).
- **`document_metadata.inline_section_headers`**: render Level 1/2 section headings inline with their title (e.g. "1 Scope", "i Abstract") instead of the OGC circled-number layout (structural, opt-in).
- **`document_metadata.suppress_bibliography_indent`**: reflow both Normative References and the non-normative Bibliography as flush paragraphs, removing the OGC hanging indent that placed the title under the authors (structural, opt-in).
- **Submitting-Organizations rebrand**: when `copyright_holder` is set to a non-OGC organisation, the flavor's auto-generated "…submitted this Document to the Open Geospatial Consortium (OGC)" sentence is rebranded to name that organisation (e.g. DGIWG) via a targeted PDF-stylesheet override, so no residual OGC text remains in the preface.
- **`paging`** (profile-level `PagingConfig`): `enabled`, `default_limit`, `max_limit`. When enabled, the generated OpenAPI adds a validated `limit` query parameter to Features `/items` endpoints (collection-level and instance-level).

### Changed

- **`suppress_design_elements` scope clarified**: the debrand switch now controls only *decorative* OGC styling (crossing-lines motif, circled clause numbers, title underlines) plus section-divider page recolouring. It no longer removes divider pages, inline the headers, or reflow the bibliography — those are independent structural opt-ins (`suppress_section_divider_pages`, `inline_section_headers`, `suppress_bibliography_indent`). This keeps the default OGC document's divider pages and standard layout intact; only profiles that explicitly opt in (e.g. DGIWG) drop them.
- **DGIWG example profiles** (`nwp_radar`, `nwp_earth_observations_lightning`) updated with the new cover layout controls, `doc_pub_date`, the structural layout opt-ins, and the final DGIWG namespace `spec_uri_base: http://www.dgiwg.org/std/edr/1.0` (conformance/requirement URIs now resolve under `.../conf/<profile-name>`).
- Regenerated all example artifacts (OpenAPI, profile config, AsciiDoc, and the DGIWG PDFs).
- Regenerated `profile.schema.json` from the current models.

### Internal

- Extracted the OpenAPI paging `limit` parameter into `_paging_limit_param()` / `_with_paging_limit()` helpers to remove three duplicated inline definitions.

## [3.3.0] - 2026-07-13

### Added

- **PDF design-element suppression (`suppress_design_elements`)**: single switch to strip the OGC flavor's decorative crossing-lines motif, circled clause numbers, and title underlines via a consolidated PDF stylesheet override. Produces a plainer document style suitable for rebranding (e.g. DGIWG). Also available as individual flags: `suppress_crossing_lines`, `plain_section_numbers`, `suppress_title_underlines`.
- **Every-page PDF watermark (`page_watermark`)**: renders diagonal semi-transparent text (e.g. "DRAFT") on every PDF page via the stylesheet override, distinct from the cover-only watermark.
- **Section-divider page rebranding**: when debranding or using a custom `page_background`, the section-divider pages switch from the OGC navy to a light background with readable (dark) numbers and titles.
- **PDF font overrides (`body_font`, `header_font`, `monospace_font`)**: set the body, heading, and monospace typeface (e.g. "Source Sans Pro") without a custom Metanorma flavor. Also available via the structured `fonts` block (maps to `:body-font:`, `:header-font:`, `:monospace-font:`).
- **Custom cover fonts (`cover.font_regular`, `cover.font_bold`, `cover.font_italic`)**: the generated cover image can now use a profile-specified typeface (file path or fontconfig family name) instead of the bundled DejaVu Sans.
- **Cover watermark (`cover.watermark`)**: optional diagonal watermark stamped on the generated cover image.
- **Terms and Definitions (`document_metadata.terms`)**: profile-supplied glossary entries appended to the Terms and Definitions section, each with a definition and optional source.
- **PyPI publish job** added to the GitHub Actions release workflow (trusted publishing via `pypa/gh-action-pypi-publish`).

### Changed

- **Consolidated PDF stylesheet override**: the previous single-purpose `logo_override.xsl` has been replaced by `pdf_override.xsl`, which merges all XSL template overrides (logo suppression, crossing lines, section numbers, title underlines, watermark, body font) into one file referenced by `:pdf-stylesheet-override:`.
- **`compile_pdf` now accepts the profile** so custom fonts declared in `document_metadata` can be pre-installed into the fontist cache before Metanorma compilation.
- **Cover font resolution** refactored: uses fontconfig (`fc-match`) to resolve family names to font files, with cascading fallback to DejaVu Sans.
- **`profile.schema.json` regenerated** to reflect all new model fields.
- Regenerated example profile artifacts (`nwp_earth_observations_lightning_profile`, `nwp_radar`) with DGIWG branding updates (design-element suppression, Source Sans Pro fonts, DRAFT watermark, submitters list).

### Fixed

- `cli.py`: `compile_pdf` call now passes the profile object so font pre-installation works correctly.

## [3.2.1] - 2026-07-02

### Fixed

- **`validate-server` no longer tests a hardcoded `/openapi` path.** The location of the OpenAPI document is not fixed by the OGC API standards — it is discoverable via the landing page link with `rel="service-desc"`, so implementations may serve it at `/openapi`, `/openapi.json`, `/api`, etc. `validate-server` now fetches the landing page, resolves the actual `service-desc` document location, and remaps the placeholder `/openapi` path in the generated OpenAPI to match the live server before running schemathesis. If the link cannot be resolved to a same-origin path, `/openapi` is excluded from the run instead of producing a false failure. This lives entirely in server validation, so collection-only profiles need no service-level path configuration. Resolves [issue #9](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/issues/9).

## [3.2.0] - 2026-07-02

### Added

- **`document_metadata.copyright_holder`**: sets Metanorma `:copyright-holder:`, which also replaces the PDF footer organisation name (e.g. "OPEN GEOSPATIAL CONSORTIUM" → "DGIWG").
- **`document_metadata.boilerplate`**: replaces the page-ii legal boilerplate (copyright / license / legal notice / feedback) via `:boilerplate-authority:`, so a rebranded document carries no OGC legal text. Unset fields are synthesised from `copyright_holder`.
- **`document_metadata.suppress_flavor_logo`**: removes the OGC logo from the preface/legal page via a targeted PDF-stylesheet override. Together with `cover`, `colors`, `copyright_holder`, `boilerplate` and `spec_uri_base`, the PDF can be fully rebranded (e.g. DGIWG) with no residual OGC branding.
- **`document_metadata.cover`**: custom PDF cover-page branding. When `cover.logo` is set, the builder renders a replacement cover page (logo + the document's title, number, edition and date) and instructs Metanorma to use it in place of the built-in OGC cover via `:coverpage-image:` + `:presentation-metadata-full-coverpage-replacement:`. Optional `tagline`, `background`, and `text_color`. Requires Pillow (`pip install 'oapi-profile-builder[pdf]'`).
- **`document_metadata.colors`**: PDF colour-scheme overrides mapped to Metanorma `:presentation-metadata-color-*:` attributes (body text, cover text, titles, page background, table header/row colours). Lets a profile recolour the PDF (e.g. to a DGIWG palette) without a custom Metanorma flavor.
- **`extent.vertical.positive`** (`up` | `down`): declares the direction in which vertical extent values increase, per the CF Conventions `positive` attribute. Addresses inconsistent ordering of vertical intervals across providers — pressure levels in particular are sometimes listed top-to-bottom and sometimes bottom-to-top, with no way to tell which from the VRS alone. Surfaces in the generated OpenAPI collection schema.
- **`extent_requirements.require_vertical_direction`**: when `true`, every collection with a vertical extent must declare `extent.vertical.positive`. Lets a profile mandate one consistent vertical-ordering convention instead of leaving it per-collection.

### Fixed

- Added the missing `output_formats` reference section to the README (it existed in `docs/index.md` but not the README, which was raised as a documentation gap).

## [3.1.0] - 2026-06-26

### Added

- **`provider`** (profile-level, optional per-collection): structured service provider / responsible party (name, url, and a contact block with email/phone/hours/instructions/address/postalcode/city/country). Surfaces in the OpenAPI `info.contact` (name/url/email plus `x-` extensions) and as a "Point of Contact" section in the generated document.
- **`classification`** (profile-level, optional per-collection): security classification (`level` + `system`, e.g. NATO RESTRICTED). Surfaces as a banner in the document Abstract and as `info.x-classification` in the OpenAPI.
- **`metadata_date` / `resource_service_publish_date` / `resource_default_locale`** (profile-level, optional per-collection): provenance metadata, surfaced as `info.x-metadata-date` / `info.x-resource-publish-date` / `info.x-default-locale`.
- **`spec_uri_base`** (profile-level): configurable base URI for the requirements and conformance class identifiers. Defaults to the OGC API - EDR Part 3 namespace; set it to publish under a different SDO namespace (e.g. DGIWG). Drives the OpenAPI `x-ogc-profile` link, the requirements/conformance AsciiDoc identifiers, and the conformance section.
- **`default_output_format`** (per data query): when set, the generated OpenAPI `f` parameter for that query carries the corresponding media type as its `default` (GET parameter and POST request body). Validated to be one of the query's `output_formats`.
- **`crs` shorthand** (per data query): a plain list of CRS URIs under `variables`, accepted as an alternative to `crs_details` and validated against `extent_requirements.supported_crs`.
- **`document_metadata` expansion**: `doc_type`, `status` (Metanorma `:status:`/`:docstage:`), `submission_date`/`approval_date`/`publication_date` (mapped to `:received-date:`/`:issued-date:`/`:published-date:`), `notice` (front-matter notice paragraph), structured `submitters` (name + affiliation + role for the page iv table), and `normative_references` (appended to the References section). `doc_subtype` now also accepts `profile`.

### Fixed

- Regenerated `profile.schema.json` from the current models — it was stale and still documented the removed `allowed_crs`/`crs_pattern` fields.
- Migrated `examples/nws_connect_profile.yaml` to the current `extent_crs`/`extent_trs` format (it still used the removed flat `allowed_crs`/`allowed_trs` keys and failed validation).
- README validation-rules table updated to reference the current `extent_crs`/`supported_crs` fields instead of the removed flat keys.

---

## [3.0.1] - 2026-05-13

### Fixed

- **Stale import in `cli.py`**: `validate-server` command crashed with `ModuleNotFoundError: No module named 'ogc_edr_profile'` due to a leftover import from the old package name. Fixed to `oapi_profile_builder.server_validation`.

---



### Breaking Change — `extent_requirements` CRS/TRS/VRS fields restructured

The flat `allowed_crs`, `crs_pattern`, `allowed_trs`, `trs_pattern`, `allowed_vrs`, `vrs_pattern` fields on `ExtentRequirements` have been replaced with a cleaner two-level structure that separates two distinct concerns:

- **`extent_crs` / `extent_trs` / `extent_vrs`** — constrain the single CRS/TRS/VRS value used to *express* the extent (`extent.spatial.crs`, `extent.temporal.trs`, `extent.vertical.vrs`). Typically just CRS84 / Gregorian.
- **`supported_crs` / `supported_trs` / `supported_vrs`** — constrain the list of CRS/TRS/VRS values the service *supports* for queries (the top-level `crs` array and `data_queries.*.variables.crs_details`). Usually broader than the extent constraint.

Each constraint is a `CrsConstraint` object with either `allowed: list[str]` (exact enum) or `pattern: str` (regex) — not both.

This directly resolves the ambiguity raised in [issue #7](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/issues/7) where `crs_pattern` was only available within `extent` and there was no way to apply a regex to the top-level `crs` array or `crs_details` independently.

**Migration:**

```yaml
# Before (2.x)
extent_requirements:
  minimum_bbox: [-180, -90, 180, 90]
  allowed_crs:
    - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
  allowed_trs:
    - "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"

# After (3.0)
extent_requirements:
  minimum_bbox: [-180, -90, 180, 90]
  extent_crs:
    allowed:
      - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
  extent_trs:
    allowed:
      - "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"
  # Optionally add supported_crs for query CRS constraints:
  # supported_crs:
  #   pattern: "^(http://www\\.opengis\\.net/def/crs/OGC/1\\.3/CRS84|http://www\\.opengis\\.net/def/crs/EPSG/.*)$"
```

---



### Fixed

- **`parameter_names` is now optional** (`models.py`): edr-pydantic marks `parameter_names` as a required field on `Collection`, but OGC API - EDR Part 3 allows a profile to define the *schema* for parameter objects via `parameter_schema` without mandating any specific parameter names in the profile document itself. The `Collection` override in `models.py` now types `parameter_names` as `Optional[Parameters]` (default `None`), so omitting it is valid. All existing profiles with `parameter_names` defined continue to work unchanged.

### Usage

```yaml
# Define the schema for parameters without listing any specific ones
parameter_schema:
  type: object
  required: [observedProperty, unit]
  properties:
    observedProperty:
      type: object
    unit:
      type: object

collections:
  - id: my_collection
    # parameter_names omitted — valid when parameter_schema is set
    links: ...
    extent: ...
```

---



### Added

- **Service-level `description` and `keywords` fields** (`models.py`, `generate.py`):
  - New `ServiceProfile.description: str | None` — a human-readable description of the service profile. Surfaces in the OpenAPI `info.description` (replacing the hardcoded string) and as a property in the landing page response schema.
  - New `ServiceProfile.keywords: list[str]` — service-level keywords describing what the profile provides (query types, parameter names, domain terms). Surfaces in `info.x-keywords` and as a `keywords` property in the landing page response schema, with a `contains` constraint so conformance tools can verify the keywords are present.
  - These are distinct from `document_metadata.keywords`, which are for the OGC PDF/AsciiDoc header.
  - `_landing_page_schema()` updated to accept and embed `title`, `description`, and `keywords`.

### Usage

```yaml
name: my_profile
title: My EDR Profile
description: Brief description of what this service profile provides.
keywords:
  - lightning
  - cube
  - radius
```

---



### Fixed

- **Null temporal interval bounds** (`models.py`): edr-pydantic 0.7.x rejected `null` as a temporal interval bound, but OGC API - EDR explicitly allows open-ended intervals (e.g. `["2020-01-01T00:00:00Z", null]` meaning "from 2020 to present"). Fixed by overriding `Temporal` and `Extent` from edr-pydantic with `TemporalWithNullBounds` and `ExtentWithNullBounds`, and wrapping `EDRCollection` in our own `Collection` subclass that uses the null-aware extent. The upstream fix has been flagged for edr-pydantic.
- **OpenAPI temporal interval schema** (`generate.py`): Updated the generated OpenAPI schema for `temporal.interval` items to use `oneOf: [date-time string, null]` to correctly reflect that null bounds are valid.

### Added

- **Configurable POST support for EDR data query endpoints** (`models.py`, `generate.py`):
  - New `ServiceProfile.allow_post_queries: bool` field (default `False`). When `True`, generates `POST` operations alongside `GET` for all EDR data query endpoints (`position`, `area`, `radius`, `cube`, `trajectory`, `corridor`, `items`, `locations`). The POST request body mirrors the GET query parameters as a JSON object, allowing clients to submit large geometries that would exceed URL length limits.
  - New `Collection.post_queries: bool | None` field for per-collection override. `None` inherits the profile-level default; `True`/`False` overrides explicitly.
  - New `_POST_BODY_SCHEMAS` dict and `_post_operation()` helper in `generate.py`.

### Usage

```yaml
# Enable POST for all collections in the profile
allow_post_queries: true

# Or override per-collection
collections:
  - id: large_geometry_collection
    post_queries: true
  - id: simple_collection
    post_queries: false
```

---

## [Unreleased] - 2025-01-30

### Added - OGC API - EDR Part 3 Compliance

#### New Models (`src/ogc_edr_profile/models.py`)
- `ExtentRequirements`: Profile-level extent restrictions with CRS/TRS/VRS validation
- `OutputFormat`: Output format definitions with schema references

#### New ServiceProfile Fields
- `required_conformance_classes`: Conformance classes implementations must declare (defaults to EDR Core)
- `extent_requirements`: Profile-level extent restrictions
- `output_formats`: Profile-level output format definitions with schema references
- `collection_id_pattern`: Regex pattern for valid collection IDs

#### New Validators
- `validate_parameter_completeness()`: Ensures all parameters have `unit` and `observedProperty` (per REQ_parameter-names)
- `validate_pubsub_conformance()`: Auto-adds Part 2 requirement when pubsub is present (per REQ_pubsub)

### Changed

#### OpenAPI Generation (`src/ogc_edr_profile/generate.py`)
- **BREAKING**: `servers` array now always empty (per REQ_publishing) - profile OpenAPI is implementation-independent
- Landing page response schema now requires `profile` link relation (per REQ_publishing)
- Conformance endpoint response schema now specifies required conformance classes (per REQ_api)
- Added `_landing_page_schema()` function
- Added `_R200_CONFORMANCE` response schema
- Updated `_core_paths()` to accept profile parameter

#### Documentation (`README.md`)
- Added "OGC API - EDR Part 3 Compliance" section
- Documented new configuration fields
- Updated `server_url` description (now for documentation only)
- Added compliance matrix

### Migration Guide

#### For Profile Authors

1. **Add units to all parameters** (now required):
   ```yaml
   parameter_names:
     temp:
       observedProperty:
         label: Temperature
       unit:              # REQUIRED
         label: Celsius
         symbol: C
   ```

2. **Remove manual Part 2 requirements** (auto-added when `pubsub` present)

3. **Regenerate OpenAPI documents**:
   ```bash
   ogc-edr-profile generate --config my_profile.yaml --output ./output
   ```

#### For Implementation Developers

1. **Add profile link to landing page**:
   ```json
   {
     "links": [
       {
         "href": "http://www.opengis.net/spec/ogcapi-edr-3/1.0/req/my_profile",
         "rel": "profile"
       }
     ]
   }
   ```

2. **Declare all required conformance classes** at `/conformance`

### Compliance Matrix

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| REQ_modspec | ✅ | AsciiDoc structure follows ModSpec |
| REQ_edr-conformant | ✅ | Uses edr-pydantic for authoritative EDR models |
| REQ_parameter-names | ✅ | Validator ensures unit, observedProperty specified |
| REQ_root | ✅ | Landing page schema requires profile link |
| REQ_publishing | ✅ | OpenAPI servers empty, profile link required |
| REQ_api | ✅ | Conformance endpoint specifies required classes |
| REQ_extent | ✅ | ExtentRequirements model with CRS/TRS/VRS rules |
| REQ_output-format | ✅ | OutputFormat model with schema references |
| REQ_pubsub | ✅ | Auto-adds Part 2 requirement, AsyncAPI generated |
| REQ_collectionid | ✅ | collection_id_pattern field for restrictions |

### Testing

All tests passing:
- ✅ Model validation
- ✅ OpenAPI generation (servers empty, profile link present)
- ✅ Parameter validation (catches missing units)
- ✅ PubSub auto-requirement

### References

- OGC API - EDR Part 1: Core (19-086r6)
- OGC API - EDR Part 3: Service Profiles (draft)
- Redmine ticket: `/tmp/ogc-edr-profile-alignment-issues.textile`
