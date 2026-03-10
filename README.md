# OGC API - EDR Part 3 Service Profile Generator

Authoritative tooling for creating OGC API - Environmental Data Retrieval (EDR) Part 3 Service Profiles, built on Pydantic.

## Overview

Profile structure is defined as Pydantic models (`src/models.py`). Instantiating a `ServiceProfile` validates the entire profile — enums enforce normative OGC values, cross-model validators catch referential errors — before any files are written.

## Repository Structure


```
├── src/
│   ├── models.py     # Authoritative Pydantic schema (ServiceProfile, Collection, Requirement, etc.)
│   ├── generate.py   # Serialization: validated model → OpenAPI, AsyncAPI, AsciiDoc
│   └── cli.py        # CLI entry point
├── examples/
│   └── water_gauge.yaml  # Example profile config
└── requirements.txt
```


## Installation

```bash
pip install -r requirements.txt
```

## Usage

Define your profile in YAML or JSON, then generate:

```bash
python src/cli.py --config examples/water_gauge.yaml --output ./my_profile
```

### Output

```
my_profile/
├── openapi.yaml
├── asyncapi.yaml                        # if pubsub is configured
├── profile_config.json                  # round-trip model export
├── requirements/
│   ├── requirements_class_core.adoc
│   └── core/REQ_<id>.adoc
└── abstract_tests/
    ├── ATS_class_core.adoc
    └── core/ATS_<id>.adoc
```

## Profile Config Schema

Key fields in your YAML/JSON config:

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Lowercase identifier, e.g. `water_gauge` |
| `title` | `string` | Human-readable profile title |
| `collections` | `list` | One or more EDR collections |
| `collections[].query_types` | `enum[]` | `items`, `position`, `area`, `radius`, `cube`, `trajectory`, `corridor`, `locations`, `instances` |
| `collections[].output_formats` | `enum[]` | `GeoJSON`, `CoverageJSON`, `CSV`, `NetCDF`, `GRIB`, `Zarr` |
| `requirements` | `list` | Normative requirements |
| `abstract_tests` | `list` | Conformance tests (each must reference a valid requirement id) |
| `pubsub` | `object` | Optional OGC API - EDR Part 2 PubSub config (AMQP/MQTT/Kafka) |

See [`examples/water_gauge.yaml`](examples/water_gauge.yaml) for a complete example.

## Programmatic Use

```python
from src.models import ServiceProfile
from src.generate import generate
from pathlib import Path

profile = ServiceProfile.model_validate_json(open("my_profile.json").read())
generate(profile, Path("./output"))
```

## Standards

- OGC API - EDR Part 1: Core
- OGC API - EDR Part 2: PubSub
- OGC API - EDR Part 3: Service Profiles (draft)
- OpenAPI 3.0 / AsyncAPI 3.0
- Metanorma/AsciiDoc documentation format

## License

Apache License 2.0 — See [LICENSE](LICENSE) for details.

## Contact

- **Author**: Shane Mill (NOAA/NWS/MDL)
- **Email**: shane.mill@noaa.gov
- **Issues**: https://github.com/ShaneMill1/OGC-Service-Profile-Creation/issues
