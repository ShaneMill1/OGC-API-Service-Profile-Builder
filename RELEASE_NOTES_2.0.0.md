# Release Notes - Version 2.0.0

## Package Rename + OGC API Service Profile Builder

This major release renames the package to reflect expanded scope (EDR + Features API profiles) and brings full compliance with the OGC API - Environmental Data Retrieval Part 3: Service Profiles specification (draft).

### BREAKING CHANGES

- **Package renamed**: `ogc-edr-profile` → `oapi-profile-builder`
- **CLI command**: `ogc-edr-profile` → `oapi-profile-builder`
- **Module**: `ogc_edr_profile` → `oapi_profile_builder`
- **Parameter Validation**: All parameters in `parameter_names` must now specify `unit` and `observedProperty` fields (per REQ_parameter-names)
- **OpenAPI Servers**: Generated OpenAPI documents now have empty `servers: []` array (per REQ_publishing - profiles are specifications, not implementations)

### Migration

Uninstall the old package first:
```bash
pip uninstall ogc-edr-profile
pip install oapi-profile-builder
```

Update your scripts:
- `ogc-edr-profile generate` → `oapi-profile-builder generate`
- `from ogc_edr_profile import ...` → `from oapi_profile_builder import ...`

### New Features

#### Profile-Level Configuration Fields

- `required_conformance_classes`: Specify which conformance classes implementations must declare
- `extent_requirements`: Define profile-level spatial/temporal restrictions
  - `minimum_bbox`: Minimum bounding box implementations must support
  - `allowed_crs`: List of allowed coordinate reference systems
  - `allowed_trs`: List of allowed temporal reference systems
- `output_formats`: Define output formats with schema references
  - `name`: Format name
  - `media_type`: MIME type
  - `schema_ref`: URL to JSON schema
- `collection_id_pattern`: Regex pattern for collection ID validation

#### Enhanced OpenAPI Generation

- Landing page response schema now requires `profile` link relation
- Conformance endpoint response schema specifies required conformance classes
- Added `x-ogc-profile` field to OpenAPI info section

#### Automatic Requirements

- When `pubsub` configuration is present, automatically adds OGC API - EDR Part 2 conformance requirement

#### Improved Validation

- Strict parameter completeness validation with clear error messages
- Error messages reference specific OGC standard requirements
- Better validation feedback for debugging

### Examples

- **New**: `minimal_profile.yaml` - Minimal working example demonstrating all compliance fields
- **Updated**: `nws_connect_profile.yaml` - Added compliance fields and parameter units
- **Updated**: `nwsviz_profile.yaml` - Added compliance fields

### Documentation

- Added "OGC API - EDR Part 3 Compliance" section to README
- Created comprehensive CHANGELOG.md with migration guide
- Updated all examples to demonstrate new features

### Migration Guide

For existing profiles, you need to:

1. **Add units to all parameters**:
```yaml
parameter_names:
  temp:
    type: Parameter
    observedProperty:
      label: Temperature
    unit:
      label: Celsius
      symbol: C
```

2. **Add compliance fields** (optional but recommended):
```yaml
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
```

3. **Regenerate OpenAPI documents**:
```bash
oapi-profile-builder generate --config my_profile.yaml --output ./output
```

### Standard Compliance

This release implements the following OGC API - EDR Part 3 requirements:

- **REQ_publishing**: Profile OpenAPI documents have empty servers array and require profile link relation
- **REQ_parameter-names**: All parameters must specify unit, observedProperty, and data type
- **REQ_extent**: Profiles can specify minimum spatial/temporal extent requirements
- **REQ_api**: Profiles specify required conformance classes
- **REQ_pubsub**: Profiles with pub/sub automatically require Part 2 conformance

### Installation

```bash
pip install oapi-profile-builder
```

Or upgrade from previous versions:

```bash
pip install --upgrade oapi-profile-builder
```

### Links

- **PyPI**: https://pypi.org/project/oapi-profile-builder/
- **GitHub**: https://github.com/ShaneMill1/OGC-API-Service-Profile-Builder
- **Documentation**: See README.md and CHANGELOG.md
