# OGC API Service Profile Builder

Generate OGC API - EDR Part 3 Service Profile artifacts from a YAML config — OpenAPI 3.1.0, AsyncAPI, AsciiDoc requirements and conformance tests, and a publication-ready Metanorma PDF with optional custom (e.g. DGIWG) branding.

[![PyPI](https://img.shields.io/pypi/v/oapi-profile-builder)](https://pypi.org/project/oapi-profile-builder/)
[![License](https://img.shields.io/badge/license-Apache-blue)](LICENSE)

---

## Quick Start

```bash
pip install oapi-profile-builder

# Copy an example config and edit it
cp examples/minimal_profile.yaml my_profile.yaml

# Validate and generate artifacts
oapi-profile-builder generate --config my_profile.yaml --output ./output
```

That's it. The `output/` directory will contain:

```
output/
├── openapi.yaml          # OpenAPI 3.1.0 — ready for Swagger UI, Redoc, schemathesis
├── profile_config.json   # Round-trip serialized profile
├── document.adoc         # Metanorma root document
├── sections/             # Abstract, Preface, Scope, Conformance, References, Terms
├── requirements/         # Individual REQ_*.adoc files
└── abstract_tests/       # Individual ATS_*.adoc files
```

---

## Example Profiles

Six working examples are included:

| File | What it shows |
|---|---|
| [`examples/minimal_profile.yaml`](examples/minimal_profile.yaml) | Smallest valid profile — one collection, one requirement |
| [`examples/insitu_observations_profile.yaml`](examples/insitu_observations_profile.yaml) | Full meteorological profile — 8 parameters with QUDT units, CF standard names, metocean extensions, CRS listing, temporal extent, custom dimensions, `parameter_schema` |
| [`examples/nws_connect_profile.yaml`](examples/nws_connect_profile.yaml) | PubSub profile — generates `asyncapi.yaml` alongside the OpenAPI |
| [`examples/nwsviz_profile.yaml`](examples/nwsviz_profile.yaml) | Production profile — 13 collections, 3 OGC API Processes, PDF metadata |
| [`examples/nwp_radar.yaml`](examples/nwp_radar.yaml) | **DGIWG-branded** profile — custom cover logo, DGIWG colours/footer/legal page, `default_output_format`, per-query CRS, vertical `positive`, DGIWG namespace |
| [`examples/nwp_earth_observations_lightning_profile.yaml`](examples/nwp_earth_observations_lightning_profile.yaml) | DGIWG lightning profile — same branding, CF units |

---

## CLI Reference

```
oapi-profile-builder generate   --config <file> --output <dir> [--pdf]
oapi-profile-builder validate   --config <file>
oapi-profile-builder validate-server --config <file> --url <url> [--max-examples N] [--stateful]
oapi-profile-builder cite-test  --url <url> [--report <dir>]
oapi-profile-builder cite-test-features --url <url> [--report <dir>]
oapi-profile-builder schema     [--output <file>]
```

### `generate`

Validates the profile config and writes all artifacts to the output directory.

```bash
oapi-profile-builder generate --config my_profile.yaml --output ./output
```

Add `--pdf` to also compile an OGC-compliant PDF via the `metanorma/metanorma` Docker image (Docker required):

```bash
oapi-profile-builder generate --config my_profile.yaml --output ./output --pdf
```

The PDF can be rebranded for another SDO (e.g. DGIWG) — custom cover logo, colours, legal page, footer, and identifier namespace — all from the profile config. See [Document generation and branding](#document-generation-and-branding).

### `validate`

Validates the config without writing any files. Useful in CI before generating.

```bash
oapi-profile-builder validate --config my_profile.yaml
# Profile 'my_profile' is valid.
```

### `validate-server`

Runs [schemathesis](https://schemathesis.io/) against a live server using the profile's generated OpenAPI. Requires `pip install oapi-profile-builder[validate]`.

```bash
oapi-profile-builder validate-server \
  --config my_profile.yaml \
  --url https://my-server.example.com \
  --max-examples 5
```

Supply real `instanceId` values in your config so schemathesis can exercise instance-level paths:

```yaml
collection_examples:
  my_collection:
    instanceId: "2025-04-02T00:00:00Z"
```

### `cite-test` / `cite-test-features`

Runs the official OGC CITE conformance test suites against a live server. Docker and Maven are required for `cite-test` (EDR); Docker only for `cite-test-features`.

```bash
# OGC API - EDR Part 1 (builds ets-ogcapi-edr10 on first run, ~2 min)
oapi-profile-builder cite-test \
  --url https://my-server.example.com \
  --report ./cite_results

# OGC API - Features Part 1 (pulls pre-built image from Docker Hub)
oapi-profile-builder cite-test-features \
  --url https://my-server.example.com \
  --report ./cite_features_results
```

Results:

```
OGC API - EDR CITE Results
  Passed:  76/84
  Failed:  0
  Skipped: 8

✓ All CITE tests passed.
```

---

## GitHub Actions

No local install needed. Add this to any workflow to generate profile artifacts from a config file:

```yaml
name: Generate Profile

on:
  push:
    paths: ['my_profile.yaml']

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate profile artifacts
        uses: ShaneMill1/OGC-API-Service-Profile-Builder@main
        with:
          config: my_profile.yaml
          output: ./profile_output

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: profile-artifacts
          path: ./profile_output/
```

**To download the artifacts:** Actions tab → click the run → scroll to **Artifacts** at the bottom → download the zip.

### Action inputs

| Input | Default | Description |
|---|---|---|
| `config` | — | Path to the profile config YAML (required) |
| `output` | `./profile_output` | Output directory |
| `version` | `latest` | Package version to install |
| `pdf` | `false` | Compile PDF via Metanorma (Docker required on runner) |
| `cite-url` | — | Run OGC CITE tests against this server URL |
| `cite-type` | `edr` | `edr`, `features`, or `both` |

> **CITE + VPN:** The CITE test runner needs to reach the server from GitHub's runners. Servers behind a VPN require a [self-hosted runner](https://docs.github.com/en/actions/hosting-your-own-runners).

---

## Document generation and branding

With `--pdf`, the builder compiles a Metanorma document (`document.adoc` + `sections/`, `requirements/`, `abstract_tests/`) into `document.pdf` using the official `metanorma/metanorma` Docker image. By default this is an OGC `draft-standard` document.

Everything about the document — cover, title-page metadata, legal page, footer, colours, and even the requirement/conformance identifier namespace — is driven from the profile config, so the same tooling can produce a document branded for another SDO such as **DGIWG** with no OGC branding remaining.

| What you want to change | Field | Mechanism |
|---|---|---|
| Cover logo, tagline, fonts, watermark (replaces the OGC cover) | `document_metadata.cover` | Generated cover image via `:coverpage-image:` full replacement |
| Title, doc number, edition, dates, sub-title/status | `title`, `version`, `document_metadata.{doc_number, doc_type, doc_subtype, status, *_date}` | Metanorma document attributes |
| PDF colours (titles, tables, cover, backgrounds) | `document_metadata.colors` | `:presentation-metadata-color-*:` |
| Page-ii legal text (copyright / license / notice) | `document_metadata.boilerplate` | `:boilerplate-authority:` |
| Footer organisation name | `document_metadata.copyright_holder` | `:copyright-holder:` |
| Cover layout (logo size/position, tagline/title size, bold edition) | `document_metadata.cover.{logo_width, logo_y, tagline_font_size, title_font_size, bold_edition}` | Generated cover image |
| Cover date | `document_metadata.doc_pub_date` | Long-format date on the generated cover + `:published-date:` |
| Remove the OGC logo from the legal page | `document_metadata.suppress_flavor_logo` | targeted `:pdf-stylesheet-override:` |
| Remove OGC design (crossing lines, circled numbers, rules, navy divider pages) | `document_metadata.suppress_design_elements` (or the individual `suppress_crossing_lines` / `plain_section_numbers` / `suppress_title_underlines`) | `:pdf-stylesheet-override:` + colour attributes |
| Remove the standalone section-divider pages | `document_metadata.suppress_section_divider_pages` | `:pdf-stylesheet-override:` |
| Inline section headings (`1 Scope` in one line, no circle) | `document_metadata.inline_section_headers` | `:pdf-stylesheet-override:` |
| Flatten reference hanging indent (title under authors) | `document_metadata.suppress_bibliography_indent` | `:pdf-stylesheet-override:` |
| Every-page DRAFT-style watermark (over content) | `document_metadata.page_watermark` | `:pdf-stylesheet-override:` (footer overlay) |
| Requirement / conformance identifier namespace | `spec_uri_base` | derives `req_uri` / `conf_uri` |
| Submitter table, notice paragraph, normative refs, extra terms | `document_metadata.{submitters, notice, normative_references, terms}` | Metanorma attributes / sections |
| Features `/items` paging (`limit` parameter) | `paging.{enabled, default_limit, max_limit}` | OpenAPI query parameter |

Custom branding requires Pillow for the cover image: `pip install 'oapi-profile-builder[pdf]'`. Field-by-field detail is in the [`document_metadata`](#document_metadata) reference below; [`examples/nwp_radar.yaml`](examples/nwp_radar.yaml) is a complete DGIWG-branded example. Omit all of these fields and the output keeps the standard OGC house style.

> The `suppress_flavor_logo`, `suppress_design_elements`/`suppress_*`, `suppress_section_divider_pages`, `inline_section_headers`, `suppress_bibliography_indent`, and `page_watermark` overrides reach into the OGC Metanorma flavor's XSL templates (e.g. `insertLogoPreface`, `insertCrossingLines`, `insertSectionNumInCircle`, `insertFooter`, the `sections` mode, `fmt-title`, and `bibitem-normative-style`) and are coupled to that flavor. Everything else uses documented Metanorma attributes. mn2pdf merges our same-named templates over the flavor's at equal precedence (via `merge_override.xsl`), which is what makes these work; a future metanorma-ogc release could require refreshing the template names. For long-term SDO adoption, a dedicated Metanorma "taste"/flavor is the most durable path.

---

## Profile Config Reference

A profile config is a YAML file. The full JSON Schema is at [`profile.schema.json`](profile.schema.json).

### Minimal valid config

```yaml
name: my_profile          # lowercase, a-z 0-9 _ only
title: My EDR Profile
version: "1.0"
description: Brief description of what this service profile provides.
keywords:
  - my-parameter
  - my-domain

# ── Profile-level constraints ─────────────────────────────────────────────
# Define what any conforming implementation MUST support.
# Validated at build time and embedded in the generated OpenAPI as
# enum/pattern constraints so runtime tools can enforce them.
required_conformance_classes:
  - "http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core"

extent_requirements:
  minimum_bbox: [-180, -90, 180, 90]
  extent_crs:
    allowed:
      - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

output_formats:
  - name: GeoJSON
    media_type: application/geo+json

# ── Reference metadata ────────────────────────────────────────────────────
# Describes the structure of collections a conforming service should expose.
# For dynamic fields (extent intervals, custom dimension values), use the
# full possible range — not a snapshot of current live data.
collections:
  - id: my_collection
    links:
      - href: https://example.com/collections/my_collection
        rel: self
        type: application/json
    extent:
      spatial:
        bbox: [[-180, -90, 180, 90]]
        crs: "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    parameter_names:
      temperature:
        type: Parameter
        observedProperty:
          label: Air Temperature
        unit:
          label: Celsius
          symbol: "°C"

# ── Normative requirements and abstract tests ─────────────────────────────
# Drive the AsciiDoc/PDF output. Tests must reference a valid requirement id.
requirements: []
abstract_tests: []
```

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Lowercase `a-z 0-9 _`. Drives OGC URIs and OpenAPI `operationId`s |
| `title` | string | yes | Human-readable profile title |
| `version` | string | no | Defaults to `"1.0"` |
| `description` | string | no | Human-readable description of the service profile. Surfaces in the OpenAPI `info.description` and the landing page response schema |
| `keywords` | list | no | Service-level keywords (e.g. query types, parameter names, domain terms). Surfaces in `info.x-keywords` and the landing page response schema. Distinct from `document_metadata.keywords`, which are for the OGC PDF header |
| `server_url` | string | no | Documentation only — not written to the profile OpenAPI |
| `provider` | object | no | Service provider / responsible party. Surfaces in OpenAPI `info.contact` and the document Point of Contact (see below) |
| `classification` | object | no | Security classification (`level` + `system`). Surfaces as a document banner and `info.x-classification` |
| `metadata_date` | string | no | Metadata update date (ISO 8601). Surfaces as `info.x-metadata-date` |
| `resource_service_publish_date` | string | no | Resource/service publication date (ISO 8601). Surfaces as `info.x-resource-publish-date` |
| `resource_default_locale` | string | no | Default resource locale (e.g. `eng`). Surfaces as `info.x-default-locale` |
| `allow_post_queries` | bool | no | When `true`, generates `POST` alongside `GET` for all EDR data query endpoints. Defaults to `false` |
| `collections` | list | yes | One or more EDR collections (see below) |
| `required_conformance_classes` | list | no | Conformance classes implementations must declare. Defaults to EDR Core |
| `extent_requirements` | object | no | Profile-level CRS/TRS/VRS constraints (see below) |
| `output_formats` | list | no | Format name → media type + schema ref mappings |
| `collection_id_pattern` | string | no | Regex all collection IDs must match |
| `spec_uri_base` | string | no | Base URI for the requirements/conformance class identifiers. Defaults to the OGC EDR Part 3 namespace; override to publish under another SDO namespace (e.g. DGIWG) |
| `parameter_name_pattern` | string | no | Regex all `parameter_names` keys must match |
| `parameter_schema` | object | no | JSON Schema for parameter objects — replaces the default schema in the generated OpenAPI (see below) |
| `processes` | list | no | OGC API Processes to expose in the OpenAPI |
| `requirements` | list | no | Normative requirements for the AsciiDoc/PDF |
| `abstract_tests` | list | no | Conformance tests — each must reference a valid requirement `id` |
| `pubsub` | object | no | OGC API - EDR Part 2 PubSub config — generates `asyncapi.yaml` |
| `collection_examples` | object | no | `{collectionId: {instanceId: "..."}}` — used by `validate-server` |
| `paging` | object | no | Features `/items` paging — adds a validated `limit` query parameter to the generated OpenAPI (see below) |
| `document_metadata` | object | no | Metanorma PDF header — doc number/type/subtype, status, editors, submitters, dates, notice, normative references (see below) |

---

### `collections[]`

Uses the [edr-pydantic](https://github.com/KNMI/edr-pydantic) `Collection` model — the same schema an EDR server returns at `/collections/{id}`.

> **Service-level vs collection-level fields**
>
> The profile has two distinct levels that serve different purposes — they don't merge or override each other:
>
> - **Service-level fields** (`extent_requirements`, `parameter_schema`, `parameter_name_pattern`, `collection_id_pattern`) define *constraints* that any conforming implementation must satisfy. They are validated at build time and embedded in the generated OpenAPI as schema constraints (enums, patterns) so runtime tools can enforce them against a live server.
>
> - **`collections[]`** provides *reference metadata* — the structure and representative values of collections a conforming service should expose. This mirrors what an EDR server returns at `/collections/{id}` and drives the generated OpenAPI paths and response schemas.
>
> For fields that are inherently dynamic (e.g. `extent.temporal.interval`, `extent.custom[].values`), use representative values that describe the *full possible range*, not a snapshot of current live data. For example, use an open-ended temporal interval `["2020-01-01T00:00:00Z", null]` rather than a specific end date, and list all valid custom dimension values rather than only those currently in the dataset. The `validate-server` command tests API structure and response schema conformance — it does not assert that specific data values in responses match the profile config exactly.

| Field | Required | Description |
|---|---|---|
| `id` | yes | Collection identifier |
| `title` | no | Human-readable name |
| `description` | no | Longer description |
| `links` | yes | At minimum a `self` link |
| `extent.spatial.bbox` | yes | `[[minLon, minLat, maxLon, maxLat]]` |
| `extent.spatial.crs` | yes | CRS URI — validated against `extent_requirements` |
| `extent.temporal` | no | `interval`, `values`, `trs` |
| `extent.vertical` | no | `interval`, `values`, `vrs` |
| `extent.custom` | no | Custom dimensions (e.g. `standard_name`, `level`) |
| `crs` | no | Full list of CRS values this collection supports |
| `output_formats` | no | Format names this collection supports (e.g. `[CoverageJSON, GeoJSON]`) |
| `data_queries` | no | EDR query types: `position`, `area`, `radius`, `cube`, `trajectory`, `corridor`, `locations`, `items`, `instances` |
| `parameter_names` | no | Map of parameter id → Parameter object. All parameters must have `unit` and `observedProperty` |

#### `data_queries` example

```yaml
data_queries:
  position:
    link:
      href: https://example.com/collections/obs/position
      rel: data
      variables:
        query_type: position
        output_formats: [CoverageJSON]
  radius:
    link:
      href: https://example.com/collections/obs/radius
      rel: data
      variables:
        query_type: radius
        output_formats: [CoverageJSON]
        within_units: [m, km]
        # crs_details: per-query CRS support, validated against extent_requirements
        crs_details:
          - crs: "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
          - crs: "http://www.opengis.net/def/crs/EPSG/0/4326"
  cube:
    link:
      href: https://example.com/collections/obs/cube
      rel: data
      variables:
        query_type: cube
        output_formats: [CoverageJSON, GeoTIFF]
        # default_output_format: response format used when the `f` query
        # parameter is omitted. Must be one of output_formats. Sets the
        # `default` on the generated OpenAPI `f` parameter for this query.
        default_output_format: GeoTIFF
        # crs: shorthand for crs_details — a plain list of CRS URIs.
        # Validated against extent_requirements.supported_crs.
        crs:
          - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
          - "http://www.opengis.net/def/crs/EPSG/0/4326"
```

#### `parameter_names` example

```yaml
parameter_names:
  air-temperature-2m:
    type: Parameter
    label: Air Temperature at 2m
    description: Instantaneous air temperature at 2 metres above ground
    observedProperty:
      id: "https://vocab.nerc.ac.uk/standard_name/air_temperature"
      label: Air Temperature
    unit:
      label: Kelvin
      symbol:
        value: K
        type: "https://qudt.org/vocab/unit/K"
    measurementType:
      method: point
      duration: PT0S
```

---

### `extent_requirements`

Constrains CRS, TRS, and VRS values across all collections. Validated at build time and embedded in the generated OpenAPI as `enum` or `pattern` constraints on the collection response schema.

These are **profile-level constraints** — they define what any conforming implementation must support, independent of the specific values a live service happens to have at a given moment.

CRS/TRS/VRS constraints are split into two distinct concerns:

- `extent_crs` / `extent_trs` / `extent_vrs` — constrain the **single value** used to express the extent (`extent.spatial.crs`, `extent.temporal.trs`, `extent.vertical.vrs`). Typically just CRS84 / Gregorian.
- `supported_crs` / `supported_trs` / `supported_vrs` — constrain the **list of values** the service supports for queries (the top-level `crs` array and `data_queries.*.variables.crs_details`). Usually broader than the extent constraint.

Each constraint uses either `allowed` (exact list) or `pattern` (regex) — not both.

```yaml
extent_requirements:
  minimum_bbox: [-180, -90, 180, 90]

  # Extent is always expressed in CRS84
  extent_crs:
    allowed:
      - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

  # Service supports CRS84 plus any EPSG CRS for queries
  supported_crs:
    pattern: "^(http://www\\.opengis\\.net/def/crs/OGC/1\\.3/CRS84|http://www\\.opengis\\.net/def/crs/EPSG/.*)$"
  # or an explicit list:
  # supported_crs:
  #   allowed:
  #     - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
  #     - "http://www.opengis.net/def/crs/EPSG/0/4326"

  extent_trs:
    allowed:
      - "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"
```

At least one of `extent_crs` or `supported_crs` is required. The same applies to TRS and VRS — all are optional individually but at least one CRS constraint must be present.

#### Vertical direction (`positive`)

OGC API - EDR's vertical extent has no field for which way values increase. This is ambiguous for VRS like pressure levels, which different providers order top-to-bottom or bottom-to-top inconsistently (pressure increases as altitude *decreases*). Set `extent.vertical.positive` to `up` or `down` on a collection (following the CF Conventions `positive` attribute) to make the ordering explicit:

```yaml
collections:
  - id: my_collection
    extent:
      spatial: { ... }
      vertical:
        interval:
          - ["1000", "100"]   # hPa, surface to top of atmosphere
        values: ["1000", "850", "700", "500", "300", "100"]
        vrs: "http://www.opengis.net/def/crs/EPSG/0/5798"  # or similar pressure VRS
        positive: down   # pressure increases downward, toward the surface
```

Set `extent_requirements.require_vertical_direction: true` to make `positive` mandatory on every collection with a vertical extent, so a profile can enforce one consistent convention rather than leaving it up to each collection author:

```yaml
extent_requirements:
  minimum_bbox: [-180, -90, 180, 90]
  extent_crs:
    allowed: ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
  require_vertical_direction: true
```

---

### `output_formats`

Maps format names (referenced by `collections[].output_formats` and `data_queries.*.variables.output_formats`) to a media type and, optionally, a schema reference. The `schema_ref` flows into the generated OpenAPI response `content` for that format — use it to point a format at a specific schema (e.g. a DGIWG-published schema for GeoTIFF or CoverageJSON) instead of the tool's built-in default.

```yaml
output_formats:
  - name: CoverageJSON
    media_type: application/prs.coverage+json
    schema_ref: https://schemas.opengis.net/covjson/1.0/coveragejson.json
  - name: GeoJSON
    media_type: application/geo+json
    schema_ref: https://geojson.org/schema/FeatureCollection.json
  - name: GeoTIFF
    media_type: image/tiff; application=geotiff
    # Omit schema_ref until a published schema exists for this format —
    # the requirement/abstract test can still state the standard to conform to.
```

| Field | Required | Description |
|---|---|---|
| `name` | yes | Format name, referenced elsewhere as a string (e.g. `CoverageJSON`) |
| `media_type` | yes | MIME type used as the OpenAPI response `content` key and the `f` parameter value |
| `schema_ref` | no | URL to a JSON Schema (or other schema) for this format. When set, the generated response uses `{"$ref": schema_ref}`; when omitted, a generic/default schema is used |

`schema_ref` is optional — if no schema exists yet for a format (as is currently the case for some binary formats like GeoTIFF), leave it unset and capture the required standard as a normative `requirements[]` entry instead. Add `schema_ref` later once a schema URL exists.

---

### `parameter_schema`

A JSON Schema fragment that replaces the default parameter schema in the generated OpenAPI. Use this to enforce field-level constraints — required fields, QUDT unit URIs, CF standard name URIs, ISO 8601 durations, and custom extension properties.

```yaml
parameter_schema:
  type: object
  required:
    - type
    - observedProperty
    - measurementType
    - label
    - description
    - unit
    - "metocean:standard_name"
    - "metocean:level"
  properties:
    unit:
      type: object
      properties:
        symbol:
          type: object
          properties:
            type:
              type: string
              pattern: "^https://qudt\\.org/vocab/unit/.*$"
    observedProperty:
      type: object
      properties:
        id:
          type: string
          pattern: "^https://vocab\\.nerc\\.ac\\.uk/standard_name/.*$"
    measurementType:
      type: object
      properties:
        duration:
          type: string
          pattern: "^P(\\d+Y)?(\\d+M)?(\\d+D)?(T(\\d+H)?(\\d+M)?(\\d+S)?)?$"
    "metocean:standard_name":
      type: string
    "metocean:level":
      type: number
  additionalProperties: true
```

See [`examples/insitu_observations_profile.yaml`](examples/insitu_observations_profile.yaml) for a complete working example.

---

### `requirements[]` and `abstract_tests[]`

Requirements drive the AsciiDoc/PDF output. Abstract tests must reference a valid requirement `id`.

```yaml
requirements:
  - id: position-coveragejson          # lowercase, hyphens only
    statement: The position query SHALL return CoverageJSON.
    parts:
      - The service SHALL provide a /collections/{id}/position endpoint.
      - The response Content-Type SHALL be application/prs.coverage+json.

abstract_tests:
  - id: position-coveragejson          # must equal requirement_id
    requirement_id: position-coveragejson
    steps:
      - Send GET /collections/{id}/position?coords=POINT(lon lat).
      - Verify Content-Type is application/prs.coverage+json.
```

---

### `processes[]`

Adds OGC API Processes paths to the generated OpenAPI.

```yaml
processes:
  - id: compute-difference
    title: Compute Dataset Difference
    description: Calculates the difference between two datasets.
    output_content:
      application/zip:
        schema:
          type: object
```

Generates: `/processes/compute-difference`, `/processes/compute-difference/execution`, `/jobs`, `/jobs/{jobId}`, `/jobs/{jobId}/results`.

---

### `paging`

Controls Features `/items` paging in the generated OpenAPI. When enabled (the default), a validated `limit` query parameter is added to every `/items` endpoint (collection-level and instance-level).

```yaml
paging:
  enabled: true          # default true; set false to omit the limit parameter
  default_limit: 10      # OpenAPI schema default for limit (default 10)
  max_limit: 100         # OpenAPI schema maximum for limit (default 10000)
```

The emitted parameter is `limit` (`in: query`, `type: integer`, `minimum: 1`, `maximum: <max_limit>`, `default: <default_limit>`).

---

### `pubsub`

When present, generates `asyncapi.yaml` alongside `openapi.yaml`.

```yaml
pubsub:
  broker_host: my-broker.example.com
  broker_port: 5672
  protocol: amqp          # amqp | mqtt | kafka
  collections:
    - my_collection
  filters:
    - name: station
      description: Filter by station ID
      type: string
```

---

### `document_metadata`

Required only when compiling a PDF with `--pdf`. Fields map to Metanorma OGC document attributes.

```yaml
document_metadata:
  doc_number: "25-myprofile"
  doc_type: draft-standard      # Metanorma :doctype: (draft-standard | standard | best-practice | engineering-report | ...)
  doc_subtype: implementation   # implementation | best-practice | engineering-report | profile
  status: approved              # Metanorma :status:/:docstage: (swg-draft | public-rfc | approved | ...)
  editors:
    - Jane Smith
  # submitters: structured table for page iv — each row carries its own affiliation.
  # When provided, takes precedence over the editors/submitting_orgs fallback.
  submitters:
    - name: Jane Smith
      affiliation: My Organization
      role: editor
    - name: Standards Working Group
      affiliation: My SDO
  submitting_orgs:
    - My Organization
  # Title-page dates (YYYY-MM-DD). Omitted dates fall back to {copyright_year}-01-01.
  submission_date: "2026-05-01"   # → :received-date:
  approval_date:   "2026-06-15"   # → :issued-date:
  publication_date: "2026-07-01"  # → :published-date:
  doc_pub_date:    "2026-07-16"   # optional; overrides publication_date for the cover
                                  #   (long-format "16 July 2026") and :published-date:
  # Custom notice paragraph rendered in the front matter. Note: the OGC cover-page
  # legal notice itself is generated by Metanorma from doc_type/status.
  notice: >
    This is a DRAFT standard and is subject to change.
  # Additional normative references appended to the References section.
  normative_references:
    - anchor: DGIWG-250
      citation: DGIWG 250
      title: DGIWG GeoTIFF Profile
  keywords:
    - ogcdoc
    - OGC API
    - EDR
  copyright_year: 2026
  external_id: http://www.opengis.net/doc/dp/my-profile/1.0
```

The cover-page sub-title (e.g. "Draft Standard — Implementation — Approved") is produced by Metanorma from the `doc_type`, `doc_subtype`, and `status` combination.

#### Custom branding (logo + colors)

Two `document_metadata` blocks let you rebrand the PDF (e.g. for DGIWG) without a custom Metanorma flavor:

- **`colors`** — recolours the PDF via Metanorma's `:presentation-metadata-color-*:` attributes. Values are hex colours.
- **`cover`** — replaces the built-in OGC cover page with a generated one: your logo plus the document's title, number, edition and date. Requires Pillow (`pip install 'oapi-profile-builder[pdf]'`). The builder renders `cover.png` into the output directory and points Metanorma at it via `:coverpage-image:` + `:presentation-metadata-full-coverpage-replacement:`.

```yaml
document_metadata:
  doc_number: "DGIWG 134"
  cover:
    logo: assets/dgiwg_logo.png    # path relative to the working directory (or absolute)
    tagline: Delivering Military Advantage through multi-national geospatial interoperability
    background: "#FFFFFF"          # optional cover background (default white)
    text_color: "#1F3864"          # optional cover text colour (default black)
    font_regular: "Source Sans Pro" # optional: .ttf/.otf path OR installed family name (fontconfig)
    font_bold: "Source Sans Pro"    # optional bold face; derived from font_regular when unset
    font_italic: "Source Sans Pro"  # optional italic face for the tagline
    watermark: "DRAFT"             # optional diagonal watermark stamped on the cover
    # --- cover layout (all optional) ---
    logo_width: 200                # target logo width in px (default 420)
    logo_y: 100                    # logo vertical offset from top in px (default 180)
    tagline_font_size: 20          # tagline point size (default 30)
    title_font_size: 40            # title point size (default 54)
    bold_edition: true             # render the "Edition X" line in bold (default false)
  colors:
    text: "#000000"                # body text
    cover_text: "#1F3864"          # cover text / section numbers / ToC
    cover_lines: "#1F3864"         # preface 'crossing lines' element
    title: "#1F3864"               # clause/table/figure titles
    page_background: "#FFFFFF"     # cover + section page background
    table_header: "#1F3864"        # table header background
    table_row_even: "#EEF1F7"      # even table rows
    table_row_odd: "#FFFFFF"       # odd table rows
```

Note: colours work against the normal OGC cover too. The `cover` block does a *full* cover replacement, so the dynamic title/number/edition/date are drawn onto the generated image (which is why the builder composes it rather than relying on Metanorma attributes — logo attributes like `:coverpage-image:` alone are not rendered by the OGC flavor).

#### De-branding the rest of the document (legal page + footer + logo)

Cover + colors handle the front page, but the OGC flavor also stamps its identity on the page-ii legal boilerplate, the page footer, and an OGC logo on the legal page. Three more `document_metadata` fields remove those:

- **`copyright_holder`** — sets `:copyright-holder:`, which also drives the **PDF footer** organisation name (replacing "OPEN GEOSPATIAL CONSORTIUM").
- **`boilerplate`** — replaces the page-ii legal text (copyright / license / legal notice / feedback) via `:boilerplate-authority:`. Any field left unset is synthesised from `copyright_holder`, so no OGC text leaks through.
- **`suppress_flavor_logo`** — removes the OGC logo from the preface/legal page via a targeted PDF-stylesheet override. (Coupled to the OGC Metanorma flavor's XSL.)

```yaml
document_metadata:
  copyright_holder: DGIWG
  suppress_flavor_logo: true
  boilerplate:
    copyright: "Copyright © 2026 Defence Geospatial Information Working Group (DGIWG). All rights reserved."
    license: "Use of this document is subject to the DGIWG terms and conditions."
    legal: "Attention is drawn to the possibility that some elements may be subject to patent rights; DGIWG shall not be held responsible for identifying any such rights."
    feedback: "Comments on this document should be directed to DGIWG."
```

#### Removing the OGC page design (crossing lines, circled numbers, divider pages)

The OGC flavor also draws decorative design elements: the blue "crossing lines with a dot" motif, circled section-divider numbers, a short rule under section titles, and full-navy section-divider pages. One switch removes them all:

- **`suppress_design_elements: true`** — a consolidated switch that:
  - removes the blue crossing-lines + dot motif (on divider/cover pages via a template override; on the Contents/preface pages, which draw the lines inline in the flavor's own colour, by whiting that colour out);
  - renders section numbers as plain text (e.g. `1 Scope`, `i Abstract`) instead of coloured circles;
  - removes the short rule beneath section titles;
  - rebrands the full-navy section-divider pages to a clean white page with a DGIWG-navy (from `colors.title`) plain number and title.

  The individual toggles `suppress_crossing_lines`, `plain_section_numbers`, and `suppress_title_underlines` are still available if you want finer control; `suppress_design_elements` simply turns all three on plus the divider rebrand.

- **`page_watermark`** — stamps a light diagonal watermark (e.g. `DRAFT`) on **every page**, rendered *over* the content including tables. This is distinct from `cover.watermark`, which marks only the generated cover image. The cover page is left unmarked.

```yaml
document_metadata:
  suppress_design_elements: true   # plain numbers, no crossing lines/rules, white divider pages
  page_watermark: DRAFT            # every-page diagonal watermark (over content)
```

With `cover` + `colors` + `copyright_holder` + `boilerplate` + `suppress_flavor_logo` + `suppress_design_elements` (and `spec_uri_base` for the requirement/conformance identifiers), the generated PDF carries no OGC branding — only legitimate citations to the OGC standards the profile conforms to. Omit these fields and you get the standard OGC house style. See [`examples/nwp_radar.yaml`](examples/nwp_radar.yaml).

> These design-element overrides (and the `page_watermark` footer overlay) reach into the OGC Metanorma flavor's XSL template names and are coupled to that flavor; a future metanorma-ogc release could require refreshing them.

#### Structural layout changes (divider pages, inline headers, references)

`suppress_design_elements` only changes *decorative* styling — it keeps the document's structure (standalone section-divider pages, the standard heading layout, and the reference hanging indent) intact. The following are **independent, opt-in** structural changes, so the default OGC output is unaffected unless you set them:

- **`suppress_section_divider_pages: true`** — removes the standalone full-page section dividers, so each section's content follows its heading directly.
- **`inline_section_headers: true`** — renders Level 1/2 headings inline with the title (e.g. `1 Scope`, `i Abstract`) rather than the OGC circled-number layout.
- **`suppress_bibliography_indent: true`** — flattens both the Normative References and the Bibliography so each entry is a single flush paragraph, removing the hanging indent that placed the title under the authors.

```yaml
document_metadata:
  suppress_section_divider_pages: true
  inline_section_headers: true
  suppress_bibliography_indent: true
```

Additionally, when `copyright_holder` is set to a non-OGC organisation, the flavor's auto-generated "Submitting Organizations" sentence ("…submitted this Document to the Open Geospatial Consortium (OGC)") is rebranded to name that organisation instead, so no residual OGC text remains in the preface.

#### Extending Terms and Definitions

Add profile-specific terms (e.g. EDR Part 3 or Pub/Sub terms) appended after the base terms in the Terms and Definitions section:

```yaml
document_metadata:
  terms:
    - term: service profile
      definition: A named, referenceable set of constraints and additional requirements applied to an OGC API - EDR implementation.
      source: "SOURCE: OGC API - EDR Part 3: Service Profiles (draft)"
```

---

### `provider`, `classification`, and provenance metadata

Optional service-level metadata. Each may also be set per-collection (the collection value overrides the profile root for that collection and is round-tripped into `profile_config.json`).

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

Where these surface:

- `provider` → OpenAPI `info.contact` (`name`/`url`/`email`; the remaining contact fields become `x-` extensions) and a **Point of Contact** section in the generated document.
- `classification` → a **security classification banner** in the document Abstract and `info.x-classification` in the OpenAPI.
- `metadata_date` / `resource_service_publish_date` / `resource_default_locale` → `info.x-metadata-date` / `info.x-resource-publish-date` / `info.x-default-locale`.

> The profile OpenAPI is implementation-independent (per EDR Part 3 REQ_publishing), so these describe the profile/data provenance rather than a specific deployment endpoint.

---

### `spec_uri_base`

By default, the requirements class and conformance class identifiers are published under the OGC API - EDR Part 3 namespace:

```
http://www.opengis.net/spec/ogcapi-edr-3/1.0/req/<name>
http://www.opengis.net/spec/ogcapi-edr-3/1.0/conf/<name>
```

Set `spec_uri_base` to publish under a different SDO namespace. This updates the OpenAPI `x-ogc-profile` link, the requirements/conformance AsciiDoc identifiers, and the conformance section:

```yaml
spec_uri_base: "https://schemas.dgiwg.org/edr/1.0"
# → https://schemas.dgiwg.org/edr/1.0/req/<name>
# → https://schemas.dgiwg.org/edr/1.0/conf/<name>
```

---

## Validation Rules

The tool enforces these rules at build time. Violations produce clear error messages.

| Rule | Detail |
|---|---|
| `name` format | Must match `^[a-z0-9_]+$` |
| No duplicate collection IDs | Across the whole profile |
| `extent_requirements` requires CRS spec | At least one of `extent_crs` or `supported_crs` must be set (each uses `allowed` or `pattern`) |
| Collection CRS validated | Each `extent.spatial.crs` checked against `extent_crs`; `crs[]` and `crs_details` checked against `supported_crs` |
| Collection TRS validated | Each `extent.temporal.trs` checked against `extent_trs` |
| `crs_details` / `crs` validated | Each `data_queries.*.variables.crs_details[].crs` and `crs[]` checked against `supported_crs` |
| `default_output_format` validated | Each `data_queries.*.variables.default_output_format` must be one of that query's `output_formats` |
| `require_vertical_direction` enforced | If set, every collection with a vertical extent must declare `extent.vertical.positive` as `up` or `down` |
| Document dates format | `submission_date` / `approval_date` / `publication_date` must be `YYYY-MM-DD` |
| Parameters need `unit` + `observedProperty` | Required by OGC API - EDR Part 3 |
| `parameter_name_pattern` enforced | All `parameter_names` keys must match if set |
| `collection_id_pattern` enforced | All collection IDs must match if set |
| Abstract test IDs match requirements | `requirement_id` must reference an existing requirement |
| Requirement IDs | Must match `^[a-z0-9][a-z0-9\-]*$`, no trailing hyphen |

---

## Programmatic Use

```python
from oapi_profile_builder.models import ServiceProfile
from oapi_profile_builder.generate import generate
from pathlib import Path
import yaml

with open("my_profile.yaml") as f:
    config = yaml.safe_load(f)

profile = ServiceProfile.model_validate(config)  # validates everything
generate(profile, Path("./output"))
```

---

## Standards

- [OGC API - EDR Part 1: Core](https://docs.ogc.org/is/19-086r6/19-086r6.html)
- [OGC API - EDR Part 2: PubSub](https://docs.ogc.org/DRAFTS/21-009.html)
- [OGC API - EDR Part 3: Service Profiles (draft)](https://github.com/opengeospatial/ogcapi-environmental-data-retrieval)
- [OGC API - Processes Part 1](https://docs.ogc.org/is/18-062r2/18-062r2.html)
- OpenAPI 3.1.0 / AsyncAPI 3.0
- Metanorma/AsciiDoc

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Contact

Shane Mill · NOAA/NWS/MDL · shane.mill@noaa.gov  
Issues: https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/issues
