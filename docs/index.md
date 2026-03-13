# OGC API - EDR Part 3 Service Profile Generator

Authoritative tooling for creating OGC API - Environmental Data Retrieval (EDR) Part 3 Service Profiles, built on Pydantic and [edr-pydantic](https://github.com/KNMI/edr-pydantic).

## Overview

Profile structure is defined as Pydantic models (`src/ogc_edr_profile/models.py`). Instantiating a `ServiceProfile` validates the entire profile — cross-model validators catch referential errors — before any files are written.

Collections use `edr-pydantic`'s authoritative `Collection` model directly, meaning a profile config is simultaneously a valid EDR collection descriptor and a Part 3 profile definition.

## Installation

```bash
pip install ogc-edr-profile
```

---

## Workflow

### 1. Author a Profile Config

A profile config is a YAML or JSON file. Copy the example and modify it:

```bash
cp examples/nwsviz_profile.yaml my_profile.yaml
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

See [`examples/nwsviz_profile.yaml`](examples/nwsviz_profile.yaml) for a full working config with 13 collections, 3 processes, requirements, abstract tests, `collection_examples`, and `document_metadata`.

### 2. Generate Profile Artifacts

```bash
ogc-edr-profile generate \
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
ogc-edr-profile validate --config my_profile.yaml
```

### 3. Compile OGC PDF

Requires Docker. Shells out to the official `metanorma/metanorma` image — no Ruby or LaTeX install needed.

```bash
ogc-edr-profile generate \
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
ogc-edr-profile validate-server \
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

Run the official OGC API - EDR Part 1 conformance test suite (ets-ogcapi-edr10):

```bash
ogc-edr-profile cite-test \
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

---

## Config Reference

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | yes | Lowercase identifier using only `a-z`, `0-9`, `_`. Used in OGC URIs and OpenAPI `operationId`s. e.g. `water_gauge` |
| `title` | `string` | yes | Human-readable profile title |
| `version` | `string` | no | Profile version. Defaults to `1.0` |
| `server_url` | `string` | no | Base URL of the live server. Populates the OpenAPI `servers` block |
| `collections` | `list` | yes | One or more EDR collections (see below) |
| `processes` | `list` | no | OGC API Processes to include in the OpenAPI (see below) |
| `requirements` | `list` | no | Normative requirements (see below) |
| `abstract_tests` | `list` | no | Conformance tests — each must reference a valid requirement `id` (see below) |
| `pubsub` | `object` | no | OGC API - EDR Part 2 PubSub configuration (see below) |
| `collection_examples` | `object` | no | Map of collection id → example parameter values (e.g. `instanceId`) for server validation |
| `document_metadata` | `object` | no | Metanorma document header fields for PDF compilation (see below) |

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

## Programmatic Use

```python
from ogc_edr_profile.models import ServiceProfile
from ogc_edr_profile.generate import generate
from pathlib import Path

profile = ServiceProfile.model_validate(config_dict)
generate(profile, Path("./output"))
```

## Repository Structure

```
├── src/
│   └── ogc_edr_profile/
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

MIT — See [LICENSE](LICENSE) for details.

## Contact

- **Author**: Shane Mill (NOAA/NWS/MDL)
- **Email**: shane.mill@noaa.gov
- **Issues**: https://github.com/ShaneMill1/OGC-Service-Profile-Creation/issues
