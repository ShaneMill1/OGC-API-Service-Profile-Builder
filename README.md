# OGC API Service Profile Builder

Authoritative tooling for creating OGC API Service Profiles (EDR, Features), built on Pydantic and [edr-pydantic](https://github.com/KNMI/edr-pydantic).

## Overview

Profile structure is defined as Pydantic models (`src/oapi_profile_builder/models.py`). Instantiating a `ServiceProfile` validates the entire profile — cross-model validators catch referential errors — before any files are written.

Collections use `edr-pydantic`'s authoritative `Collection` model directly, meaning a profile config is simultaneously a valid EDR collection descriptor and a Part 3 profile definition.

## Installation

```bash
pip install oapi-profile-builder
```

---

## Workflow

<img width="1001" height="721" alt="OGC API Service Profile Builder - Pydantic Validation Architecture drawio" src="https://github.com/user-attachments/assets/092c3dfc-549e-41b0-8a92-af0b89689950" />


### 1. Author a Profile Config

A profile config is a YAML or JSON file. Start with the minimal example:

```bash
cp examples/minimal_profile.yaml my_profile.yaml
```

The minimal valid config:

```yaml
name: my_profile
title: My EDR Profile

# OGC API - EDR Part 3 compliance fields (recommended)
required_conformance_classes:
  - "http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core"

extent_requirements:
  minimum_bbox: [-180, -90, 180, 90]
  allowed_crs:
    - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

output_formats:
  - name: GeoJSON
    media_type: application/geo+json
    schema_ref: https://geojson.org/schema/FeatureCollection.json

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
    parameter_names:
      temp:
        type: Parameter
        observedProperty:
          label: Temperature
        unit:              # REQUIRED per OGC API - EDR Part 3
          label: Celsius
          symbol: C
#Example requirement and abstract test for asciidoc/PDF
requirements:
  - id: items-endpoint
    statement: The service SHALL provide a /collections/water_gauge/items endpoint.
    parts:
      - The service SHALL return GeoJSON FeatureCollection.
      - Each feature SHALL include gauge_height property.

abstract_tests:
  - id: items-endpoint
    requirement_id: items-endpoint
    steps:
      - Send GET request to /collections/water_gauge/items.
      - Verify response Content-Type is application/geo+json.
      - Verify each feature contains gauge_height property.
```

See [`examples/minimal_profile.yaml`](examples/minimal_profile.yaml) for a complete working example and [`examples/nwsviz_profile.yaml`](examples/nwsviz_profile.yaml) for a full profile with 13 collections, 3 processes, requirements, abstract tests, and document metadata.

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

### 3. Compile OGC PDF

Requires Docker. Shells out to the official `metanorma/metanorma` image — no Ruby or LaTeX install needed.

```bash
oapi-profile-builder generate \
  --config my_profile.yaml \
  --output ./my_profile \
  --pdf
```

The `document_metadata` block in the profile config drives the Metanorma document header:

```yaml
document_metadata:
  doc_number: "24-nwsviz"
  doc_subtype: implementation
  copyright_year: 2026
  editors:
    - Shane Mill
  submitting_orgs:
    - NOAA/NWS/MDL
  keywords:
    - ogcdoc
    - OGC API
    - EDR
    - NWSViz
    - service profile
  external_id: http://www.opengis.net/doc/dp/ogcapi-edr-nwsviz/1.0
```

Produces `my_profile/document.pdf` — a fully compliant OGC `draft-standard` PDF with Abstract, Preface, Scope, Conformance, References, Terms, Requirements class, and normative Abstract Test Suite annex.

### 4. Validate Against a Live Server

```bash
oapi-profile-builder validate-server \
  --config my_profile.yaml \
  --url https://edr-api-desi-c.mdl.nws.noaa.gov \
  --max-examples 3
```

Results:

```
Operations:  100 selected / 106 total
Tested:      47
Test cases:  1002 generated, 1002 passed

No issues found in 49.51s
```

Use `--stateful` to additionally test job lifecycle endpoints (`/jobs/{jobId}`, `DELETE /jobs/{jobId}`) via POST `/execution` chaining.

Add `collection_examples` to your config to supply real `instanceId` values for schemathesis path parameters:

```yaml
collection_examples:
  my_collection:
    instanceId: "2025-04-02T00:00:00Z"
```

### 5. OGC CITE Conformance Testing

#### EDR Conformance Testing

Run the official OGC API - EDR Part 1 conformance test suite (ets-ogcapi-edr10):

```bash
oapi-profile-builder cite-test \
  --url https://edr-api-desi-c.mdl.nws.noaa.gov \
  --report ./cite_results
```

Results:

```
OGC API - EDR CITE Results
  Passed:  76/84
  Failed:  0
  Skipped: 8

✓ All CITE tests passed.
```

The tool automatically:
- Clones and builds ets-ogcapi-edr10 from GitHub on first run
- Caches Docker image (`ogccite/ets-ogcapi-edr10:local`) for subsequent runs
- Runs TestNG tests via `docker exec`
- Supports localhost testing with `--network host` mode
- Generates JSON report with detailed test results

The skipped tests are optional features not implemented by the server.

#### Features Conformance Testing

Run the official OGC API - Features Part 1 conformance test suite (ets-ogcapi-features10):

```bash
oapi-profile-builder cite-test-features \
  --url https://api.example.com \
  --report ./cite_features_results
```

Results:

```
OGC API - Features CITE Results
  Passed:  639/712
  Failed:  18
  Skipped: 55

✗ 18 test(s) failed.
```

The tool automatically:
- Pulls pre-built Docker image (`ogccite/ets-ogcapi-features10:latest`) from Docker Hub
- Runs TestNG tests via `docker exec`
- Supports localhost testing with `--network host` mode
- Generates JSON report with detailed test results

The skipped tests are optional features not implemented by the server.

---

## Config Reference

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Lowercase identifier using only `a-z`, `0-9`, `_`. Used in OGC URIs and OpenAPI `operationId`s. e.g. `water_gauge` |
| `title` | `string` | yes | Human-readable profile title |
| `version` | `string` | no | Profile version. Defaults to `1.0` |
| `server_url` | `string` | no | Base URL of the live server (for documentation only - not used in profile OpenAPI per OGC API - EDR Part 3) |
| `collections` | `list` | yes | One or more EDR collections (see below) |
| `processes` | `list` | no | OGC API Processes to include in the OpenAPI (see below) |
| `requirements` | `list` | no | Normative requirements (see below) |
| `abstract_tests` | `list` | no | Conformance tests — each must reference a valid requirement `id` (see below) |
| `pubsub` | `object` | no | OGC API - EDR Part 2 PubSub configuration (see below) |
| `collection_examples` | `object` | no | Map of collection id → example parameter values (e.g. `instanceId`) for server validation |
| `document_metadata` | `object` | no | Metanorma document header fields for PDF compilation (see below) |
| `required_conformance_classes` | `list[string]` | no | Conformance classes that implementations must declare. Defaults to EDR Core |
| `extent_requirements` | `object` | no | Profile-level extent restrictions (see below) |
| `output_formats` | `list` | no | Profile-level output format definitions with schema references (see below) |
| `collection_id_pattern` | `string` | no | Regex pattern for valid collection IDs |

---

### `collections[]`

Each collection uses the [edr-pydantic](https://github.com/KNMI/edr-pydantic) `Collection` schema — the same model an EDR server returns at `/collections/{id}`. Key fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | yes | Collection identifier |
| `title` | `string` | no | Human-readable collection name |
| `description` | `string` | no | Collection description |
| `links` | `list` | yes | At minimum a `self` link |
| `extent.spatial.bbox` | `list` | yes | Bounding box as `[[minLon, minLat, maxLon, maxLat]]` |
| `extent.spatial.crs` | `string` | yes | CRS URI, typically `http://www.opengis.net/def/crs/OGC/1.3/CRS84` |
| `data_queries` | `object` | no | Which EDR query types this collection supports |
| `output_formats` | `list` | no | Supported output format labels e.g. `GeoJSON`, `CoverageJSON` |
| `parameter_names` | `object` | no | Map of parameter id → `Parameter` object |

#### `data_queries`

Supported keys: `items` · `position` · `area` · `radius` · `cube` · `trajectory` · `corridor` · `locations` · `instances`

```yaml
data_queries:
  position:
    link:
      href: https://example.com/collections/water_gauge/position
      rel: data
      variables:
        query_type: position
        output_formats:
          - CoverageJSON
  items:
    link:
      href: https://example.com/collections/water_gauge/items
      rel: data
      variables:
        query_type: items
        output_formats:
          - GeoJSON
```

#### `parameter_names`

**Note:** Per OGC API - EDR Part 3 requirements, all parameters must specify `unit` and `observedProperty`. The tool validates this automatically.

```yaml
parameter_names:
  gauge_height:
    type: Parameter
    observedProperty:
      label: Gauge Height
    unit:
      label: feet
      symbol: ft
```

---

### `extent_requirements`

Profile-level extent restrictions per OGC API - EDR Part 3 REQ_extent.

| Field | Type | Required | Description |
|---|---|---|---|
| `minimum_bbox` | `list[float]` | yes | Minimum spatial bounds `[minLon, minLat, maxLon, maxLat]` |
| `allowed_crs` | `list[string]` | no | Enumerated list of valid CRS values |
| `crs_pattern` | `string` | no | Regular expression defining valid CRS string patterns |
| `allowed_trs` | `list[string]` | no | Enumerated list of valid TRS values |
| `trs_pattern` | `string` | no | Regular expression defining valid TRS string patterns |
| `allowed_vrs` | `list[string]` | no | Enumerated list of valid VRS values |
| `vrs_pattern` | `string` | no | Regular expression defining valid VRS string patterns |

**Note:** Either `allowed_crs` or `crs_pattern` must be specified.

```yaml
extent_requirements:
  minimum_bbox: [-180, -90, 180, 90]
  allowed_crs:
    - "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    - "http://www.opengis.net/def/crs/EPSG/0/4326"
  allowed_trs:
    - "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"
```

---

### `output_formats[]`

Profile-level output format definitions with schema references per OGC API - EDR Part 3 REQ_output-format.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Format name (e.g., GeoJSON, CoverageJSON) |
| `media_type` | `string` | yes | MIME type (e.g., application/geo+json) |
| `schema_ref` | `string` | no | URL to schema definition |

```yaml
output_formats:
  - name: GeoJSON
    media_type: application/geo+json
    schema_ref: https://geojson.org/schema/FeatureCollection.json
  - name: CoverageJSON
    media_type: application/prs.coverage+json
    schema_ref: https://schemas.opengis.net/ogcapi/edr/1.0/openapi/schemas/coverageJSON.yaml
```

---

### `required_conformance_classes[]`

Conformance classes that implementations must declare at `/conformance` per OGC API - EDR Part 3 REQ_api.

Defaults to:
```yaml
required_conformance_classes:
  - "http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core"
```

Add additional conformance classes as needed:
```yaml
required_conformance_classes:
  - "http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core"
  - "http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/oas30"
  - "http://www.opengis.net/spec/ogcapi-edr-2/1.0/conf/pubsub"
```

---

### `processes[]`

OGC API Processes to expose in the generated OpenAPI. Each entry produces `/processes/{id}` and `/processes/{id}/execution` paths, plus `/processes`, `/jobs`, `/jobs/{jobId}`, and `/jobs/{jobId}/results`.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | yes | Process identifier e.g. `edr-zarr-difference` |
| `title` | `string` | no | Human-readable process name |
| `description` | `string` | no | Process description |
| `output_content` | `object` | no | OpenAPI content map for the 200 response. Defaults to `application/json` |

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

### `requirements[]`

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | yes | Lowercase, hyphen-separated. Must match `^[a-z0-9][a-z0-9\-]*$` |
| `statement` | `string` | yes | One-sentence normative statement |
| `parts` | `list[string]` | yes | One or more SHALL/MUST clauses |

```yaml
requirements:
  - id: position-coveragejson
    statement: The position query SHALL return CoverageJSON.
    parts:
      - The service SHALL provide a /collections/{id}/position endpoint.
      - The response Content-Type SHALL be application/prs.coverage+json.
```

---

### `abstract_tests[]`

Every `requirement_id` must match an existing requirement `id` — the model validator will reject the profile if not.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | `string` | yes | Must equal `requirement_id` |
| `requirement_id` | `string` | yes | The `id` of the requirement this test validates |
| `steps` | `list[string]` | yes | Ordered test steps |

```yaml
abstract_tests:
  - id: position-coveragejson
    requirement_id: position-coveragejson
    steps:
      - Send GET request to /collections/{id}/position?coords=POINT(lon lat).
      - Verify the response Content-Type is application/prs.coverage+json.
```

---

### `pubsub`

When present, an `asyncapi.yaml` is generated.

| Field | Type | Default | Description |
|---|---|---|---|
| `broker_host` | `string` | `localhost` | Message broker hostname |
| `broker_port` | `integer` | `5672` | Broker port (1–65535) |
| `protocol` | `string` | `amqp` | One of `amqp`, `mqtt`, `kafka` |
| `filters` | `list` | `[]` | Subscription filters |

Each filter: `name` (required), `description` (required), `type` (one of `string`, `number`, `array`, `boolean`, default `string`).

---

### `document_metadata`

Controls the Metanorma document header when compiling a PDF with `--pdf`.

| Field | Type | Required | Description |
|---|---|---|---|
| `doc_number` | `string` | yes | OGC document number e.g. `24-nwsviz` |
| `doc_subtype` | `string` | yes | One of `implementation`, `best-practice`, `engineering-report` |
| `editors` | `list[string]` | yes | Editor names |
| `submitting_orgs` | `list[string]` | yes | Submitting organization names |
| `keywords` | `list[string]` | no | Document keywords |
| `copyright_year` | `integer` | no | Defaults to current year |
| `external_id` | `string` | no | OGC external document URI |

---

## OGC API - EDR Part 3 Compliance

This tool implements the requirements of OGC API - EDR Part 3: Service Profiles (draft standard):

### Key Compliance Features

1. **Profile OpenAPI Document** (REQ_publishing)
   - Generated OpenAPI has empty `servers` array (profile is implementation-independent)
   - Landing page schema requires `profile` link relation
   - Profile URI advertised in `x-ogc-profile` info field

2. **Conformance Classes** (REQ_api)
   - `/conformance` endpoint schema specifies required conformance classes
   - Defaults to EDR Core, customizable via `required_conformance_classes`

3. **Parameter Names** (REQ_parameter-names)
   - Validates that all parameters specify `unit` and `observedProperty`
   - Automatically enforced during profile validation

4. **Extent Requirements** (REQ_extent)
   - Profile-level `extent_requirements` specify minimum bounds
   - CRS/TRS/VRS restrictions via enumerated lists or regex patterns

5. **Output Formats** (REQ_output-format)
   - Profile-level `output_formats` with schema references
   - Links to JSON Schema, XML Schema, or format specifications

6. **Pub/Sub** (REQ_pubsub)
   - Automatically adds Part 2 conformance requirement when `pubsub` is present
   - AsyncAPI document specifies channels and payloads

### Profile Types

The tool supports both:
- **Class 1 Profiles**: Restrictive profiles that constrain EDR Core
- **Class 2 Profiles**: Extended profiles that add custom requirements (e.g., processes)

Both remain compliant with EDR Core - extensions are optional, not mandatory.

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
│       ├── cite.py              # OGC CITE test suite orchestration
│       └── cli.py               # CLI entry point
├── examples/
│   ├── water_gauge.yaml         # Minimal example profile config
│   └── nwsviz_profile.yaml      # Full NWSViz profile: 13 collections, 3 processes, PDF metadata
├── profile.schema.json          # Machine-readable JSON Schema for profile configs
└── pyproject.toml
```

## Standards

- OGC API - EDR Part 1: Core
- OGC API - EDR Part 2: PubSub
- OGC API - EDR Part 3: Service Profiles (draft)
- OGC API - Processes Part 1
- OpenAPI 3.0 / AsyncAPI 3.0
- Metanorma/AsciiDoc documentation format

## License

Apache — See [LICENSE](LICENSE) for details.

## Contact

- **Author**: Shane Mill (NOAA/NWS/MDL)
- **Email**: shane.mill@noaa.gov
- **Issues**: https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/issues
