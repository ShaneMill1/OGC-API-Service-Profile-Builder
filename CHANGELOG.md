# CHANGELOG - OGC API - EDR Part 3 Compliance

## [3.0.0] - 2026-05-13

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
