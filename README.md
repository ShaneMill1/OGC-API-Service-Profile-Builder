# OGC API Service Profile Builder

Describe an OGC API - EDR Part 3 service profile in one YAML file. The builder validates it and generates everything the profile needs: an OpenAPI definition, an AsyncAPI definition for pub/sub, the requirements and abstract tests, and a publication-ready OGC PDF.

[![PyPI](https://img.shields.io/pypi/v/oapi-profile-builder)](https://pypi.org/project/oapi-profile-builder/)
[![License](https://img.shields.io/badge/license-Apache-blue)](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/LICENSE)

**Full detail:** every command, option and config field is in the [Reference](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/reference.md).

---

## Install

```bash
pip install 'oapi-profile-builder[pdf]'
```

- PDF output (`--pdf`) and the OGC CITE tests run in Docker, so install [Docker](https://docs.docker.com/get-docker/) for those.
- Testing a live server with `validate-server` needs `pip install 'oapi-profile-builder[validate]'`.

## Quick start

```bash
# 1. Start from an example
curl -O https://raw.githubusercontent.com/ShaneMill1/OGC-API-Service-Profile-Builder/main/examples/minimal_profile.yaml

# 2. Check it
oapi-profile-builder validate --config minimal_profile.yaml

# 3. Generate the artifacts (drop --pdf if you don't have Docker)
oapi-profile-builder generate --config minimal_profile.yaml --output ./output --pdf
```

```
output/
├── openapi.yaml          # OpenAPI 3.0 / 3.1 for Swagger UI, Redoc, schemathesis
├── asyncapi.yaml         # only when the profile defines pubsub
├── document.pdf          # the OGC profile document (with --pdf)
├── document.adoc         # its Metanorma source, with sections/, requirements/, abstract_tests/
└── profile_config.json   # the validated profile
```

`validate` and `generate` also print a summary of the profile's requirements, recommendations and permissions. Invalid configs fail with a message naming the field.

## Write a profile

A profile has four parts: identity, the collections a conforming service exposes, the requirements, and the document metadata.

```yaml
name: my_profile                      # lowercase; used in identifiers
title: My EDR Profile

collections:                          # what a conforming service exposes
  - id: temperature
    title: Temperature Observations
    links: [{href: "https://example.com/collections/temperature", rel: self}]
    extent:
      spatial:
        bbox: [[-180, -90, 180, 90]]
        crs: "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
    parameter_names:
      temp:
        type: Parameter
        observedProperty: {label: Air Temperature}
        unit: {label: Celsius, symbol: {value: "°C", type: "http://www.opengis.net/def/uom/UCUM/degC"}}

requirements:                         # SHALL = requirement, SHOULD = recommendation, MAY = permission
  - id: temperature-geojson
    title: GeoJSON response
    description: The temperature collection SHALL return GeoJSON features.
    parts:
      - The response Content-Type SHALL be application/geo+json.

abstract_tests:                       # one per requirement (SHALL)
  - id: temperature-geojson
    requirement_id: temperature-geojson
    steps:
      - Send GET /collections/temperature/items and check the Content-Type.

document_metadata:                    # only needed for the PDF
  doc_number: "26-001"
  editors: [Your Name]
```

The full working version is [`examples/minimal_profile.yaml`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/minimal_profile.yaml). For editor autocompletion and checking, point your YAML editor at [`profile.schema.json`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/profile.schema.json).

## What you can do

| Task | How | Example |
|---|---|---|
| **Constrain implementations**: CRS/TRS, bounding box, required queries, ID and parameter-name patterns, license links | `extent_requirements`, `required_data_queries`, `collection_id_pattern`, … [Reference](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/reference.md#extent_requirements) | [insitu](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/insitu_observations_profile.yaml) |
| **Requirements, recommendations, permissions**: only SHALL is conformance-tested; SHOULD/MAY are informative | `requirements[].level` (inferred from SHALL/SHOULD/MAY). [Reference](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/reference.md#requirement-levels-shall--should--may) | [minimal](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/minimal_profile.yaml), [walkthrough](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/demo-requirements-recommendations.md) |
| **Several conformance classes** in one profile, with class-specific rules | `requirements[].conformance_class`, `conformance_class_requirements`. [Reference](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/reference.md#multiple-conformance-classes-in-one-profile) | [metocean](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/metocean_profile.yaml) |
| **Write the document**: your own text, Markdown, PlantUML diagrams, images and preformatted (ASCII) text in any section | `requirements[].content`, `document_metadata.body`. [Below](#write-the-document) | [documentation content](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/documentation_content_profile.yaml) |
| **Brand the PDF** for another organization (logo, colors, legal page, identifiers) | `document_metadata.cover`, `colors`, `boilerplate`, `spec_uri_base`. [Reference](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/reference.md#document-generation-and-branding) | [DGIWG radar](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nwp_radar.yaml) |
| **Pub/Sub** (AsyncAPI), **OGC API Processes**, **Features paging** | `pubsub`, `processes`, `paging`. [Reference](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/reference.md#pubsub) | [NWS Connect](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nws_connect_profile.yaml), [NWSViz](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nwsviz_profile.yaml) |

### Write the document

The PDF is generated from the config, and you can add your own material anywhere without losing the generated text. A content block has a `format`:

- **`markdown`** for prose, lists and tables.
- **`plantuml`** for a diagram, rendered as a captioned figure.
- **`preformatted`** for ASCII art or console output, reproduced exactly.
- **`asciidoc`** for anything Metanorma supports.

```yaml
requirements:
  - id: temperature-geojson
    title: GeoJSON response
    description: The temperature collection SHALL return GeoJSON features.
    parts: [The response Content-Type SHALL be application/geo+json.]
    content:                                # shown after the requirement
      - format: plantuml
        title: Request flow
        body: "Client -> Service: GET /collections/temperature/items"

document_metadata:
  body:
    section_content:
      scope:                                # added to the end of the Scope section
        - format: preformatted
          title: Collections
          body: |
            temperature  +-- temp (degC)
```

Content can go in any generated section, at its start or end, and in your own clauses and annexes. The [`documentation_content` example](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/documentation_content_profile.yaml) uses every option; see its [compiled PDF](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/generated/documentation_content_profile/document.pdf). Details are in the [Reference](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/reference.md#authored-content-markdown-diagrams-and-your-own-asciidoc).

> In the PDF, a requirement's text is labeled **Statement**, the OGC ModSpec term. You set it with `description`.

## Examples

| Example | Shows |
|---|---|
| [`minimal_profile`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/minimal_profile.yaml) | Smallest valid profile: one collection, one requirement, recommendation and permission |
| [`documentation_content_profile`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/documentation_content_profile.yaml) | Markdown, PlantUML, images and preformatted text in the PDF |
| [`insitu_observations_profile`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/insitu_observations_profile.yaml) | Full meteorological profile: units, CF names, CRS lists, custom dimensions |
| [`metocean_profile`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/metocean_profile.yaml) | The OGC MetOcean profile: four conformance classes, OGC-style clauses and annexes |
| [`nws_connect_profile`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nws_connect_profile.yaml) | Pub/Sub: generates `asyncapi.yaml` |
| [`nwsviz_profile`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nwsviz_profile.yaml) | 13 collections and 3 OGC API Processes |
| [`nwp_radar`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nwp_radar.yaml), [`nwp_earth_observations_lightning_profile`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/examples/nwp_earth_observations_lightning_profile.yaml) | DGIWG-branded PDFs |

The generated output of each example, PDFs included, is in [`generated/`](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/tree/main/generated).

## Test a live server

```bash
# Check a server against the profile's OpenAPI (schemathesis)
oapi-profile-builder validate-server --config my_profile.yaml --url https://my-server.example.com

# Run the official OGC CITE suites (Docker)
oapi-profile-builder cite-test          --url https://my-server.example.com   # EDR Part 1
oapi-profile-builder cite-test-features --url https://my-server.example.com   # Features Part 1
```

## Use it from GitHub

- **Without installing anything:** open an issue with the [Generate profile artifacts](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/issues/new/choose) template and paste your YAML. A workflow replies with the generated files.
- **In your own workflow:**

  ```yaml
  - uses: ShaneMill1/OGC-API-Service-Profile-Builder@main
    with:
      config: my_profile.yaml
      output: ./profile_output
      pdf: true
  ```

Inputs and the issue workflow are described in the [Reference](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/docs/reference.md#github-actions).

## Commands

| Command | Does |
|---|---|
| `generate --config <file> --output <dir> [--pdf]` | Validate and write all artifacts |
| `validate --config <file>` | Validate only |
| `validate-server --config <file> --url <url>` | Test a live server against the profile |
| `cite-test` / `cite-test-features --url <url>` | Run the OGC CITE suites |
| `schema [--output <file>]` | Print the config JSON Schema |

## Use it from Python

```python
from pathlib import Path
from oapi_profile_builder.cli import load_config
from oapi_profile_builder.models import ServiceProfile
from oapi_profile_builder.generate import generate

profile = ServiceProfile.model_validate(load_config(Path("my_profile.yaml")))
generate(profile, Path("./output"))
```

## Standards

[OGC API - EDR Part 1](https://docs.ogc.org/is/19-086r6/19-086r6.html) ·
[Part 2: PubSub](https://docs.ogc.org/DRAFTS/21-009.html) ·
[Part 3: Service Profiles (draft)](https://github.com/opengeospatial/ogcapi-environmental-data-retrieval) ·
[OGC API - Processes](https://docs.ogc.org/is/18-062r2/18-062r2.html) ·
OpenAPI 3.1 · AsyncAPI 3.0 · Metanorma

## License and contact

Apache 2.0, see [LICENSE](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/blob/main/LICENSE). Shane Mill, NOAA/NWS/MDL, shane.mill@noaa.gov. [Issues](https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder/issues).
