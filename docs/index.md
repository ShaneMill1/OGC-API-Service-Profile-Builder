# OGC API - EDR Part 3 Service Profile Generator

Authoritative tooling for creating OGC API - Environmental Data Retrieval (EDR) Part 3 Service Profiles, built on Pydantic and [edr-pydantic](https://github.com/KNMI/edr-pydantic).

## Overview

Profile structure is defined as Pydantic models (`src/oapi_profile_builder/models.py`). Instantiating a `ServiceProfile` validates the entire profile — cross-model validators catch referential errors — before any files are written.

Collections use `edr-pydantic`'s authoritative `Collection` model directly, meaning a profile config is simultaneously a valid EDR collection descriptor and a Part 3 profile definition.

The console command is `oapi-profile-builder` and the importable package is `oapi_profile_builder`.

## Installation

```bash
pip install oapi-profile-builder
# or, for local development:
pip install -e .
```

---

## Workflow

### 1. Author a Profile Config

A profile config is a YAML or JSON file. Copy an example and modify it:

```bash
cp examples/minimal_profile.yaml my_profile.yaml
```

The minimal valid config:

```yaml
name: my_profile
title: My EDR Profile

collections:
  - id: my_collection
    links:
      - href: https://example.com/collections/my_collection
        rel: self
        type: application/json
    extent:
      spatial:
        bbox:
          - [-180, -90, 180, 90]
        crs: "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    parameter_names: {}
```

See [`examples/nwsviz_profile.yaml`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nwsviz_profile.yaml) for a large working config, and [`examples/nwp_radar.yaml`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nwp_radar.yaml) for a DGIWG-style profile exercising the newer fields (`provider`, `classification`, `default_output_format`, per-query `crs`).

### 2. Generate Profile Artifacts

```bash
oapi-profile-builder generate \
  --config my_profile.yaml \
  --output ./my_profile
```

Produces:

```
my_profile/
├── openapi.yaml
├── asyncapi.yaml                        # only when `pubsub` is configured
├── profile_config.json
├── document.adoc                        # Metanorma root document
├── sections/
│   ├── 00-abstract.adoc
│   ├── 01-preface.adoc
│   ├── 02-scope.adoc
│   ├── 03-conformance.adoc
│   ├── 04-references.adoc
│   ├── 05-terms.adoc
│   ├── 06-requirements.adoc
│   └── 07-abstract-tests.adoc
├── requirements/
│   ├── requirements_class_core.adoc
│   └── core/REQ_<id>.adoc
└── abstract_tests/
    ├── ATS_class_core.adoc
    └── core/ATS_<id>.adoc
```

Validate a config without generating output:

```bash
oapi-profile-builder validate --config my_profile.yaml
```

Export the JSON Schema for the profile config:

```bash
oapi-profile-builder schema --output profile.schema.json
```

### 3. Compile OGC PDF

Requires Docker. Shells out to the official `metanorma/metanorma` image — no Ruby or LaTeX install needed.

```bash
oapi-profile-builder generate \
  --config my_profile.yaml \
  --output ./my_profile \
  --pdf
```

The `document_metadata` block drives the Metanorma document header (see the reference below). Produces `my_profile/document.pdf` — an OGC `draft-standard` PDF with Abstract, Preface, Scope, Conformance, References, Terms, Requirements class, and a normative Abstract Test Suite annex.

### 4. Validate Against a Live Server

```bash
oapi-profile-builder validate-server \
  --config my_profile.yaml \
  --url https://your-edr-server.example.com \
  --max-examples 3
```

Use `--stateful` to additionally test job lifecycle endpoints (`/jobs/{jobId}`, `DELETE /jobs/{jobId}`) via POST `/execution` chaining. Add `collection_examples` to your config to supply real `instanceId` values for schemathesis path parameters:

```yaml
collection_examples:
  my_collection:
    instanceId: "2026-04-02T00:00:00Z"
```

### 5. OGC CITE Conformance Testing

Run the official OGC API - EDR Part 1 conformance suite (ets-ogcapi-edr10):

```bash
oapi-profile-builder cite-test \
  --url https://your-edr-server.example.com \
  --report ./cite_results
```

For OGC API - Features:

```bash
oapi-profile-builder cite-test-features \
  --url https://your-edr-server.example.com \
  --report ./cite_features_results
```

---

## Config Reference

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Lowercase `a-z 0-9 _`. Drives OGC URIs and OpenAPI `operationId`s |
| `title` | string | yes | Human-readable profile title |
| `version` | string | no | Defaults to `1.0` |
| `description` | string | no | Surfaces in OpenAPI `info.description` and the landing page schema |
| `keywords` | list | no | Service-level keywords. Surfaces in `info.x-keywords`. Distinct from `document_metadata.keywords` |
| `server_url` | string | no | Documentation only — not written to the profile OpenAPI |
| `provider` | object | no | Service provider / responsible party (see below) |
| `classification` | object | no | Security classification (`level` + `system`) (see below) |
| `metadata_date` | string | no | Metadata update date (ISO 8601). Surfaces as `info.x-metadata-date` |
| `resource_service_publish_date` | string | no | Resource publication date (ISO 8601). Surfaces as `info.x-resource-publish-date` |
| `resource_default_locale` | string | no | Default locale (e.g. `eng`). Surfaces as `info.x-default-locale` |
| `allow_post_queries` | bool | no | When `true`, generate `POST` alongside `GET` for all EDR data queries. Defaults to `false` |
| `collections` | list | yes | One or more EDR collections (see below) |
| `required_conformance_classes` | list | no | Conformance classes implementations must declare. Defaults to EDR Core |
| `extent_requirements` | object | no | Profile-level CRS/TRS/VRS constraints (see below) |
| `output_formats` | list | no | Format name → media type + schema ref mappings |
| `spec_uri_base` | string | no | Base URI for requirement/conformance identifiers. Defaults to the OGC EDR Part 3 namespace; override for another SDO (e.g. DGIWG) |
| `collection_id_pattern` | string | no | Regex all collection IDs must match |
| `parameter_name_pattern` | string | no | Regex all `parameter_names` keys must match |
| `parameter_schema` | object | no | JSON Schema for parameter objects — replaces the default in the generated OpenAPI |
| `collection_title_max_length` | int | no | Require every collection title present and within N characters |
| `require_license_link` / `license_link_type` | bool / string | no | Require a `rel=license` link (of `license_link_type`, default `text/html`) on every collection |
| `required_data_queries` | list | no | Data-query types every collection must define |
| `radius_within_units_required` | list | no | Unit tokens every radius query's `within_units` must contain (e.g. `[m]`) |
| `locations_feature_required_properties` | list | no | Feature properties marked required in the generated `/locations` response (in addition to string `id`) |
| `conformance_class_requirements` | object | no | Per-conformance-class constraints applied only to collections declaring the class (see multi-class section) |
| `processes` | list | no | OGC API Processes to expose in the OpenAPI |
| `requirements` | list | no | Normative requirements for the AsciiDoc/PDF |
| `abstract_tests` | list | no | Conformance tests — each must reference a valid requirement `id` |
| `pubsub` | object | no | OGC API - EDR Part 2 PubSub config — generates `asyncapi.yaml` |
| `collection_examples` | object | no | `{collectionId: {instanceId: "..."}}` — used by `validate-server` |
| `paging` | object | no | Features `/items` paging — adds a validated `limit` query parameter to the OpenAPI (see below) |
| `document_metadata` | object | no | Metanorma PDF header (see below) |

---

### `collections[]`

Each collection uses the [edr-pydantic](https://github.com/KNMI/edr-pydantic) `Collection` schema. Key fields:

| Field | Required | Description |
|---|---|---|
| `id` | yes | Collection identifier |
| `title` / `description` / `keywords` | no | Human-readable metadata |
| `links` | yes | At minimum a `self` link |
| `extent.spatial.bbox` | yes | `[[minLon, minLat, maxLon, maxLat]]` |
| `extent.spatial.crs` | yes | CRS URI — validated against `extent_requirements` |
| `extent.temporal` | no | `interval`, `values`, `trs` |
| `extent.vertical` | no | `interval`, `values`, `vrs` |
| `crs` | no | Full list of CRS values the collection supports |
| `output_formats` | no | Format names this collection supports |
| `data_queries` | no | EDR query types (see below) |
| `parameter_names` | no | Map of parameter id → Parameter object (each needs `unit` + `observedProperty`) |
| `conformance_classes` | no | Profile conformance-class short names this collection implements; surfaced as `x-conformance-classes` in the OpenAPI |
| `parameter_schema` | no | Per-collection JSON Schema for parameter objects, overriding the profile-level `parameter_schema` for this collection only |

`provider`, `classification`, `metadata_date`, `resource_service_publish_date`, and `resource_default_locale` may also be set per-collection to override the profile-root value for that collection.

#### `data_queries`

Supported keys: `items` · `position` · `area` · `radius` · `cube` · `trajectory` · `corridor` · `locations` · `instances`

```yaml
data_queries:
  cube:
    link:
      href: https://example.com/collections/obs/cube
      rel: data
      variables:
        query_type: cube
        output_formats: [CoverageJSON, GeoTIFF]
        # Response format used when `f` is omitted. Must be one of output_formats.
        # Sets the `default` on the generated OpenAPI `f` parameter for this query.
        default_output_format: GeoTIFF
        # Per-query CRS. Either `crs` (shorthand list) or `crs_details`
        # (objects with optional `wkt`). Validated against supported_crs.
        crs:
          - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
  radius:
    link:
      href: https://example.com/collections/obs/radius
      rel: data
      variables:
        query_type: radius
        output_formats: [CoverageJSON]
        within_units: [m, km]
        crs_details:
          - crs: "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
          - crs: "http://www.opengis.net/def/crs/EPSG/0/4326"
```

---

### `extent_requirements`

Constrains CRS, TRS, and VRS across all collections. Validated at build time and embedded in the generated OpenAPI as `enum`/`pattern` constraints.

- `extent_crs` / `extent_trs` / `extent_vrs` — constrain the **single value** used to express the extent (`extent.spatial.crs`, `extent.temporal.trs`, `extent.vertical.vrs`).
- `supported_crs` / `supported_trs` / `supported_vrs` — constrain the **list of values** supported for queries (the top-level `crs` array and per-query `crs`/`crs_details`).

Each constraint uses either `allowed` (exact list) or `pattern` (regex) — not both. At least one of `extent_crs` or `supported_crs` is required.

```yaml
extent_requirements:
  minimum_bbox: [-180, -90, 180, 90]
  extent_crs:
    allowed:
      - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
  supported_crs:
    allowed:
      - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
      - "http://www.opengis.net/def/crs/EPSG/0/4326"
  extent_trs:
    allowed:
      - "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"
```

**Vertical direction:** OGC API - EDR's vertical extent has no field for which way values increase, which is ambiguous for VRS like pressure levels (providers order them top-to-bottom or bottom-to-top inconsistently — pressure increases as altitude decreases). Set `extent.vertical.positive` (`up`/`down`, following the CF Conventions `positive` attribute) on a collection to make the ordering explicit, and set `extent_requirements.require_vertical_direction: true` to make it mandatory across the whole profile.

```yaml
vertical:
  interval:
    - ["1000", "100"]   # hPa, surface to top of atmosphere
  values: ["1000", "850", "700", "500", "300", "100"]
  vrs: "http://www.opengis.net/def/crs/EPSG/0/5798"
  positive: down   # pressure increases downward, toward the surface
```

---

### Multiple conformance classes in one profile

EDR Part 3 profiles are modular: one profile document can define several requirements/conformance classes, and different collections may implement different classes. The MetOcean profile is the canonical example — Core applies everywhere, but only in-situ collections must offer `locations`/`area`/`radius` while NWP collections must offer `position`/`cube`.

Model this with `conformance_class_requirements` (profile level) + `conformance_classes` (per collection). Set `Requirement.conformance_class` to additionally group the generated AsciiDoc/PDF into one requirements class and conformance class per key.

```yaml
collection_title_max_length: 50          # Core rule — applies to every collection
require_license_link: true

conformance_class_requirements:
  insitu-observations:
    required_data_queries: [locations, area, radius]
    radius_within_units_required: [m]
  nwp:
    required_data_queries: [position, cube]

collections:
  - id: insitu-observations
    conformance_classes: [core, insitu-observations]
    parameter_schema: { ... }            # insitu-specific parameter constraints
  - id: weather_forecast
    conformance_classes: [core, nwp]
    parameter_schema: { ... }            # NWP-specific parameter constraints

requirements:
  - id: insitu-collection-data-queries
    conformance_class: insitu-observations
    statement: ...
    parts: [ ... ]
```

When any requirement sets `conformance_class`, the generated document is organised into one requirements class + conformance class per key, each with its own URI and `requirements/<class>/` and `abstract_tests/<class>/` folders. When no requirement sets it, the single-class layout is used. The flat `required_data_queries` / `radius_within_units_required` fields still apply to every collection; class-scoped constraints are additive. See [`examples/metocean_profile.yaml`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/metocean_profile.yaml) for a full profile spanning all four MetOcean classes, and [`docs/metocean-profile-differences.md`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/metocean-profile-differences.md) for how it maps to OGC 26-027.

---

### `output_formats`

Maps format names (used in `data_queries.*.variables.output_formats`) to media types and optional schema references. The `schema_ref` flows into the generated OpenAPI response content — use it to point GeoJSON/CoverageJSON/GeoTIFF at a specific (e.g. DGIWG) schema.

```yaml
output_formats:
  - name: CoverageJSON
    media_type: application/prs.coverage+json
    schema_ref: https://schemas.opengis.net/covjson/1.0/coveragejson.json
  - name: GeoTIFF
    media_type: image/tiff; application=geotiff
    schema_ref: https://www.dgiwg.org/std/geotiff-profile/1.0/schema.json
```

---

### `provider`, `classification`, and provenance metadata

Optional service-level metadata (each may also be set per-collection):

```yaml
provider:
  name: Austrian Military
  url: "https://www.bmlv.gv.at/english/forces/organisation.shtml"
  contact:
    email: presse@bmlvs.gv.at
    phone: "+43 ..."
    hours: Monday to Friday 08:00 - 17:00
    instructions: During hours of Service
    address: "Ministry of Defence, Rossauer Lände 1"
    postalcode: A-1090
    city: Vienna
    country: Austria

classification:
  level: "NATO RESTRICTED (NR)"
  system: NATO

metadata_date: "2026-06-25T07:31Z"
resource_service_publish_date: "2026-06-24T14:10Z"
resource_default_locale: eng
```

- `provider` → OpenAPI `info.contact` (name/url/email; other contact fields as `x-` extensions) and a **Point of Contact** section in the document.
- `classification` → a **security classification banner** in the document Abstract and `info.x-classification`.
- the date/locale fields → `info.x-metadata-date` / `info.x-resource-publish-date` / `info.x-default-locale`.

The profile OpenAPI is implementation-independent (per EDR Part 3 REQ_publishing), so these describe profile/data provenance, not a specific deployment endpoint.

---

### `spec_uri_base`

By default, requirement/conformance identifiers use the OGC EDR Part 3 namespace:

```
http://www.opengis.net/spec/ogcapi-edr-3/1.0/req/<name>
http://www.opengis.net/spec/ogcapi-edr-3/1.0/conf/<name>
```

Set `spec_uri_base` to publish under a different SDO namespace (updates the OpenAPI `x-ogc-profile` link, the requirements/conformance AsciiDoc identifiers, and the conformance section):

```yaml
spec_uri_base: "https://schemas.dgiwg.org/edr/1.0"
```

---

### `requirements[]` and `abstract_tests[]`

Requirements drive the AsciiDoc/PDF output. Each requirement needs `id` (lowercase, hyphenated), `statement`, and at least one `parts` entry. Every abstract test `requirement_id` must reference an existing requirement, and its `id` must equal the `requirement_id`. An optional `conformance_class` groups requirements (and their abstract tests) into separate requirements/conformance classes in the generated document — see the multi-class section above.

```yaml
requirements:
  - id: position-coveragejson
    statement: The position query SHALL return CoverageJSON.
    parts:
      - The service SHALL provide a /collections/{id}/position endpoint.
      - The response Content-Type SHALL be application/prs.coverage+json.

abstract_tests:
  - id: position-coveragejson
    requirement_id: position-coveragejson
    steps:
      - Send GET request to /collections/{id}/position?coords=POINT(lon lat).
      - Verify the response Content-Type is application/prs.coverage+json.
```

---

### `processes[]`

Adds OGC API Processes paths. Each entry produces `/processes/{id}` and `/processes/{id}/execution`, plus `/processes`, `/jobs`, `/jobs/{jobId}`, and `/jobs/{jobId}/results`.

```yaml
processes:
  - id: edr-zarr-difference
    title: EDR Zarr Dataset Difference
    description: Calculates the difference between two EDR Zarr datasets.
    output_content:
      application/zip:
        schema:
          type: object
```

---

### `paging`

Controls Features `/items` paging in the generated OpenAPI. Enabled by default; adds a `limit` query parameter to every `/items` endpoint.

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | Set `false` to omit the `limit` parameter |
| `default_limit` | integer | `10` | OpenAPI schema `default` for `limit` |
| `max_limit` | integer | `10000` | OpenAPI schema `maximum` for `limit` |

---

### `pubsub`

When present, generates `asyncapi.yaml`.

| Field | Type | Default | Description |
|---|---|---|---|
| `broker_host` | string | `localhost` | Message broker hostname (used only when `servers` is empty) |
| `broker_port` | integer | `5672` | Broker port (1–65535, used only when `servers` is empty) |
| `protocol` | string | `amqp` | One of `amqp`, `amqp1`, `mqtt`, `kafka` |
| `collections` | list | all | Collection IDs that support PubSub |
| `filters` | list | `[]` | Subscription filters (`name`, `description`, `type`) |
| `servers` | list | `[]` | Explicit server endpoints (`amqp`, `amqp1`, `mqtt`, `kafka`, `ws`, `wss`). When set, replaces the implicit `production` server built from `broker_host`/`broker_port`/`protocol` |
| `collection_filters` | map | `{}` | Per-collection filter overrides keyed by collection ID |

---

### `document_metadata`

Controls the Metanorma document header when compiling a PDF with `--pdf`.

| Field | Type | Required | Description |
|---|---|---|---|
| `doc_number` | string | yes | OGC document number e.g. `24-nwsviz` |
| `doc_type` | string | no | Metanorma `:doctype:` (default `draft-standard`) |
| `doc_subtype` | string | no | `implementation` (default), `best-practice`, `engineering-report`, `profile` |
| `status` | string | no | Metanorma `:status:`/`:docstage:` (e.g. `swg-draft`, `public-rfc`, `approved`) |
| `editors` | list | no | Editor names |
| `submitters` | list | no | Structured table rows: `name` + `affiliation` + `role` |
| `submitting_orgs` | list | no | Submitting organization names (fallback affiliation) |
| `submission_date` | string | no | `YYYY-MM-DD` → `:received-date:` |
| `approval_date` | string | no | `YYYY-MM-DD` → `:issued-date:` |
| `publication_date` | string | no | `YYYY-MM-DD` → `:published-date:` |
| `notice` | string | no | Notice paragraph rendered in the front matter |
| `normative_references` | list | no | Extra references: `anchor` + `citation` + `title` |
| `keywords` | list | no | Document keywords |
| `copyright_year` | integer | no | Defaults to 2026 |
| `external_id` | string | no | OGC external document URI |
| `colors` | object | no | PDF colour-scheme overrides (hex), mapped to Metanorma `:presentation-metadata-color-*:` |
| `cover` | object | no | Custom cover-page branding: `logo` (path), plus optional `tagline`, `background`, `text_color`. Generates a replacement cover; needs `pip install 'oapi-profile-builder[pdf]'` |
| `copyright_holder` | string | no | Sets `:copyright-holder:` — also replaces the PDF footer organisation name (e.g. "OPEN GEOSPATIAL CONSORTIUM") |
| `boilerplate` | object | no | Replaces the page-ii legal text (`copyright`/`license`/`legal`/`feedback`) via `:boilerplate-authority:` |
| `suppress_flavor_logo` | bool | no | Removes the flavor's (OGC) logo from the preface/legal page via a targeted PDF-stylesheet override |

```yaml
document_metadata:
  doc_number: "DGIWG-NWP-RADAR-001"
  doc_type: draft-standard
  doc_subtype: implementation
  status: approved
  editors:
    - Jane Smith
  submitters:
    - name: Jane Smith
      affiliation: My Organization
      role: editor
  submission_date: "2026-05-01"
  approval_date: "2026-06-15"
  publication_date: "2026-07-01"
  notice: This is a DRAFT standard and is subject to change.
  normative_references:
    - anchor: DGIWG-250
      citation: DGIWG 250
      title: DGIWG GeoTIFF Profile
  copyright_year: 2026
```

The cover-page sub-title is produced by Metanorma from the `doc_type` + `doc_subtype` + `status` combination.

### Custom branding (e.g. DGIWG)

With `--pdf`, the document is compiled through the OGC Metanorma flavor by default. The following `document_metadata` fields rebrand it for another SDO, with no OGC branding left:

- `cover` — replaces the OGC cover with a generated cover (logo + title/number/edition/date). Needs `pip install 'oapi-profile-builder[pdf]'`. Layout is tunable via `cover.{logo_width, logo_y, tagline_font_size, title_font_size, bold_edition}`.
- `doc_pub_date` — publication date shown in long format on the cover (overrides `publication_date`).
- `colors` — recolours titles, tables, cover and backgrounds via `:presentation-metadata-color-*:`.
- `boilerplate` — replaces the page-ii legal text (copyright/license/notice/feedback).
- `copyright_holder` — sets the footer organisation name (replaces "OPEN GEOSPATIAL CONSORTIUM"). Also rebrands the flavor's "Submitting Organizations" sentence away from OGC.
- `suppress_flavor_logo` — removes the OGC logo from the legal page.
- `suppress_design_elements` — removes decorative OGC styling (crossing lines, circled numbers, title rules) and recolours divider pages.

Combined with `spec_uri_base` (requirement/conformance identifier namespace), the result carries only legitimate citations to the OGC standards the profile conforms to. See [`examples/nwp_radar.yaml`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nwp_radar.yaml).

```yaml
document_metadata:
  doc_number: "DGIWG 134"
  doc_pub_date: "2026-07-16"
  copyright_holder: DGIWG
  suppress_flavor_logo: true
  suppress_design_elements: true
  cover:
    logo: assets/dgiwg_logo.png
    tagline: Delivering Military Advantage through multi-national geospatial interoperability
    logo_width: 300
    logo_y: 100
    tagline_font_size: 20
    title_font_size: 40
    edition_date_font_size: 22
    bold_edition: true
  colors:
    cover_text: "#1F3864"
    title: "#1F3864"
    table_header: "#1F3864"
  boilerplate:
    copyright: "Copyright © 2026 DGIWG. All rights reserved."
    license: "Use of this document is subject to the DGIWG terms and conditions."
    legal: "Attention is drawn to the possibility that some elements may be subject to patent rights; DGIWG shall not be held responsible for identifying any such rights."
    feedback: "Comments on this document should be directed to DGIWG."
```

**Structural layout changes (opt-in, independent of `suppress_design_elements`).** The default OGC output keeps its section-divider pages and standard layout; set these only when you want to drop them (e.g. for DGIWG):

- `suppress_section_divider_pages` — removes the standalone full-page section dividers.
- `inline_section_headers` — renders headings inline (`1 Scope`, `i Abstract`) instead of circled numbers.
- `suppress_bibliography_indent` — flattens Normative References and Bibliography (no hanging indent under the authors).

```yaml
document_metadata:
  suppress_section_divider_pages: true
  inline_section_headers: true
  suppress_bibliography_indent: true
```

> `suppress_flavor_logo`, `suppress_design_elements`, the structural opt-ins above, and the submitting-organizations rebrand override OGC-flavor XSL templates and are coupled to that flavor; the other fields use documented Metanorma attributes.

---

## Programmatic Use

```python
from oapi_profile_builder.models import ServiceProfile
from oapi_profile_builder.generate import generate
from pathlib import Path

profile = ServiceProfile.model_validate(config_dict)
generate(profile, Path("./output"))
```

## Repository Structure

```
├── src/
│   └── oapi_profile_builder/
│       ├── models.py            # Authoritative Pydantic schema
│       ├── generate.py          # Validated model → OpenAPI, AsyncAPI, AsciiDoc
│       ├── compile.py           # PDF compilation via metanorma/metanorma Docker image
│       ├── cite.py              # OGC CITE (EDR) test suite orchestration
│       ├── cite_features.py     # OGC CITE (Features) test suite orchestration
│       ├── server_validation.py # schemathesis-based live server validation
│       └── cli.py               # CLI entry point
├── examples/                    # Example profile configs
├── generated/                   # Generated artifacts for each example
├── profile.schema.json          # Machine-readable JSON Schema for profile configs
└── pyproject.toml
```

## Standards

- OGC API - EDR Part 1: Core
- OGC API - EDR Part 2: PubSub
- OGC API - EDR Part 3: Service Profiles (draft)
- OGC API - Processes Part 1
- OpenAPI 3.1 / AsyncAPI 3.0
- Metanorma/AsciiDoc documentation format

## License

MIT — See [LICENSE](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/LICENSE) for details.

## Contact

- **Author**: Shane Mill (NOAA/NWS/MDL)
- **Email**: shane.mill@noaa.gov
- **Issues**: https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/issues
