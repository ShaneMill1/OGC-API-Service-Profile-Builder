# OGC API Service Profile Builder

Generate OGC API - EDR Part 3 Service Profile artifacts from a YAML config — OpenAPI 3.1.0, AsyncAPI, AsciiDoc requirements, and conformance tests.

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

Three working examples are included:

| File | What it shows |
|---|---|
| [`examples/minimal_profile.yaml`](examples/minimal_profile.yaml) | Smallest valid profile — one collection, one requirement |
| [`examples/insitu_observations_profile.yaml`](examples/insitu_observations_profile.yaml) | Full meteorological profile — 8 parameters with QUDT units, CF standard names, metocean extensions, CRS listing, temporal extent, custom dimensions, `parameter_schema` |
| [`examples/nwsviz_profile.yaml`](examples/nwsviz_profile.yaml) | Production profile — 13 collections, 3 OGC API Processes, PDF metadata |

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
