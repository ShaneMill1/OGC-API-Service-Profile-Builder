# =================================================================
#
# Authors: Shane Mill <shane.mill@noaa.gov>
#
# Copyright (c) 2026 Shane Mill
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================
"""
Serialization layer: ServiceProfile → files on disk.

All output is derived from the validated Pydantic model. No raw user input
reaches the filesystem — the model acts as the sanitization boundary.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from edr_pydantic.collections import Collection
from oapi_profile_builder.models import ServiceProfile


class _NoAliasDumper(yaml.Dumper):
    """YAML Dumper that never emits anchors/aliases (&id002 / *id002).

    PyYAML reuses Python object identity to emit anchors when the same dict
    appears in multiple places. This produces valid YAML but confuses many
    OpenAPI tools (Swagger UI, Redoc, validators). Overriding ignore_aliases
    forces every node to be written out in full.
    """

    def ignore_aliases(self, data: object) -> bool:
        return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FEATURES = "https://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml"
_EDR = "https://schemas.opengis.net/ogcapi/edr/1.0/openapi"
_PROCESSES = "https://schemas.opengis.net/ogcapi/processes/part1/1.0/openapi"

_F = {"$ref": "#/components/parameters/f"}
_LANG = {"$ref": "#/components/parameters/lang"}
_DATETIME = {"$ref": f"{_FEATURES}#/components/parameters/datetime"}
_PARAM_NAME = {"$ref": f"{_EDR}/parameters/parameter-name.yaml"}
_Z = {"$ref": f"{_EDR}/parameters/z.yaml"}

_ERR_SCHEMA = {"type": "object", "properties": {"code": {"type": "string"}, "description": {"type": "string"}}}
_ERR_400 = {"description": "Invalid or missing parameter", "content": {"application/json": {"schema": _ERR_SCHEMA}}}
_ERR_404 = {"description": "Not found", "content": {"application/json": {"schema": _ERR_SCHEMA}}}
_ERR_500 = {"description": "Server error", "content": {"application/json": {"schema": _ERR_SCHEMA}}}
_ERR_DEFAULT = {"$ref": "#/components/responses/default"}

_LINK_SCHEMA = {
    "type": "object",
    "required": ["href", "rel"],
    "properties": {
        "href": {"type": "string"},
        "rel": {"type": "string"},
        "type": {"type": "string"},
        "title": {"type": "string"},
    },
}
_LINKS_ARRAY = {"type": "array", "items": _LINK_SCHEMA}

# Landing page response with required profile link per REQ_publishing
def _landing_page_schema(profile_uri: str, title: str = "", description: str = "", keywords: list | None = None) -> dict:
    schema_props: dict = {
        "links": {
            "type": "array",
            "items": _LINK_SCHEMA,
            "contains": {
                "type": "object",
                "required": ["href", "rel"],
                "properties": {
                    "rel": {"const": "profile"},
                    "href": {"const": profile_uri},
                },
            },
        },
    }
    if title:
        schema_props["title"] = {"type": "string", "const": title}
    if description:
        schema_props["description"] = {"type": "string"}
    if keywords:
        schema_props["keywords"] = {
            "type": "array",
            "items": {"type": "string"},
            "contains": {"enum": keywords},
        }

    return {
        "description": "Landing page",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["links"],
                    "properties": schema_props,
                }
            }
        },
    }

_R200_CONFORMANCE = {
    "description": "Conformance classes",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "required": ["conformsTo"],
                "properties": {
                    "conformsTo": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        }
    }
}
_R200_COLLECTION = {"description": "Collection metadata", "content": {"application/json": {"schema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "links": _LINKS_ARRAY}}}}}
_R200_FEATURES = {
    "description": "Feature collection",
    "content": {
        "application/json": {
            "schema": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "const": "FeatureCollection"},
                    "features": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
            }
        }
    },
}

def _coverage_response(coll: Collection, profile: "ServiceProfile | None") -> dict:
    """Build a coverage response dict reflecting the collection's actual output formats."""
    # Collect media_type → schema_ref from profile-level output_formats
    fmt_map: dict[str, str | None] = {}
    if profile:
        for fmt in profile.output_formats:
            fmt_map[fmt.name] = fmt.schema_ref

    # Determine which formats this collection supports
    coll_formats: list[str] = []
    if coll.output_formats:
        coll_formats = list(coll.output_formats)

    content: dict = {}
    if coll_formats:
        for fmt_name in coll_formats:
            schema_ref = fmt_map.get(fmt_name)
            if fmt_name == "CoverageJSON":
                media_type = "application/prs.coverage+json"
                # Also accept the newer media type
                alt_media = "application/vnd.cov+json"
                schema = (
                    {"$ref": schema_ref}
                    if schema_ref
                    else {"$ref": f"{_EDR}/schemas/coverageJSON.yaml"}
                )
                content[media_type] = {"schema": schema}
                content[alt_media] = {"schema": schema}
            elif fmt_name == "GeoJSON":
                media_type = "application/geo+json"
                schema = {"$ref": schema_ref} if schema_ref else {"type": "object"}
                content[media_type] = {"schema": schema}
            elif fmt_name == "NetCDF":
                content["application/netcdf"] = {"schema": {"type": "string", "format": "binary"}}
            else:
                # Generic: look up media type from profile output_formats
                if profile:
                    for pf in profile.output_formats:
                        if pf.name == fmt_name:
                            schema = {"$ref": pf.schema_ref} if pf.schema_ref else {"type": "object"}
                            content[pf.media_type] = {"schema": schema}
                            break
    else:
        # Fallback: CoverageJSON only
        content["application/prs.coverage+json"] = {
            "schema": {"$ref": f"{_EDR}/schemas/coverageJSON.yaml"}
        }

    return {"200": {"description": "Coverage data response", "content": content}}

# ---------------------------------------------------------------------------
# POST request body schemas — one per EDR query type.
# POST mirrors the GET query parameters as a JSON object body, allowing
# clients to submit large geometries or complex filters that would exceed
# URL length limits with GET.  This is consistent with how OGC API - EDR
# implementations (e.g. ECMWF, NWS) handle POST for data queries.
# ---------------------------------------------------------------------------
_POST_BODY_SCHEMAS: dict[str, dict] = {
    "position": {
        "type": "object",
        "required": ["coords"],
        "properties": {
            "coords": {"type": "string", "description": "WKT Point geometry (e.g. POINT(0 51.5))"},
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval (e.g. 2026-01-01T00:00:00Z/2026-12-31T23:59:59Z)"},
            "parameter-name": {"type": "string", "description": "Comma-separated list of parameter names to return"},
            "z": {"type": "string", "description": "Vertical level(s)"},
            "f": {"type": "string", "description": "Response format"},
        },
    },
    "area": {
        "type": "object",
        "required": ["coords"],
        "properties": {
            "coords": {"type": "string", "description": "WKT Polygon geometry"},
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval"},
            "parameter-name": {"type": "string", "description": "Comma-separated list of parameter names to return"},
            "z": {"type": "string", "description": "Vertical level(s)"},
            "f": {"type": "string", "description": "Response format"},
        },
    },
    "radius": {
        "type": "object",
        "required": ["coords", "within", "within-units"],
        "properties": {
            "coords": {"type": "string", "description": "WKT Point geometry"},
            "within": {"type": "number", "description": "Radius distance"},
            "within-units": {"type": "string", "description": "Units for the within parameter (e.g. km)"},
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval"},
            "parameter-name": {"type": "string", "description": "Comma-separated list of parameter names to return"},
            "z": {"type": "string", "description": "Vertical level(s)"},
            "f": {"type": "string", "description": "Response format"},
        },
    },
    "cube": {
        "type": "object",
        "required": ["bbox"],
        "properties": {
            "bbox": {
                "type": "array",
                "description": "Bounding box [minLon, minLat, maxLon, maxLat]",
                "items": {"type": "number"},
                "minItems": 4,
                "maxItems": 6,
            },
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval"},
            "parameter-name": {"type": "string", "description": "Comma-separated list of parameter names to return"},
            "z": {"type": "string", "description": "Vertical level(s)"},
            "f": {"type": "string", "description": "Response format"},
        },
    },
    "trajectory": {
        "type": "object",
        "required": ["coords"],
        "properties": {
            "coords": {"type": "string", "description": "WKT LineString geometry"},
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval"},
            "parameter-name": {"type": "string", "description": "Comma-separated list of parameter names to return"},
            "z": {"type": "string", "description": "Vertical level(s)"},
            "f": {"type": "string", "description": "Response format"},
        },
    },
    "corridor": {
        "type": "object",
        "required": ["coords", "corridor-width"],
        "properties": {
            "coords": {"type": "string", "description": "WKT LineString geometry"},
            "corridor-width": {"type": "number", "description": "Width of the corridor"},
            "corridor-height": {"type": "number", "description": "Height of the corridor"},
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval"},
            "parameter-name": {"type": "string", "description": "Comma-separated list of parameter names to return"},
            "z": {"type": "string", "description": "Vertical level(s)"},
            "f": {"type": "string", "description": "Response format"},
        },
    },
    "items": {
        "type": "object",
        "properties": {
            "bbox": {"type": "string", "description": "Bounding box filter"},
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval"},
            "parameter-name": {"type": "string", "description": "Comma-separated list of parameter names to return"},
            "z": {"type": "string", "description": "Vertical level(s)"},
            "f": {"type": "string", "description": "Response format"},
        },
    },
    "locations": {
        "type": "object",
        "properties": {
            "bbox": {
                "type": "array",
                "description": "Bounding box [minLon, minLat, maxLon, maxLat]",
                "items": {"type": "number"},
                "minItems": 4,
                "maxItems": 6,
            },
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval"},
            "f": {"type": "string", "description": "Response format"},
        },
    },
}


def _post_operation(get_op: dict, query_type: str, coll_id: str, responses: dict) -> dict:
    """Build a POST operation mirroring a GET EDR data query operation."""
    body_schema = _POST_BODY_SCHEMAS.get(query_type, {"type": "object"})
    # Carry over a default output format from the GET operation's `f` parameter
    # so the POST body documents the same default.
    default_f = None
    for p in get_op.get("parameters", []):
        if isinstance(p, dict) and p.get("name") == "f":
            default_f = p.get("schema", {}).get("default")
            break
    if default_f and "properties" in body_schema and "f" in body_schema["properties"]:
        import copy
        body_schema = copy.deepcopy(body_schema)
        body_schema["properties"]["f"]["default"] = default_f
    return {
        "summary": get_op["summary"].replace("query", "query (POST)"),
        "description": get_op.get("description", ""),
        "operationId": get_op["operationId"].replace("Query", "QueryPost").replace("Get", "PostGet"),
        "tags": get_op["tags"],
        "requestBody": {
            "required": True,
            "description": f"Query parameters for {query_type} request",
            "content": {
                "application/json": {
                    "schema": body_schema,
                },
            },
        },
        "responses": responses,
    }


# Parameters keyed by EDR query type
_QUERY_PARAMS: dict[str, list[dict]] = {
    "position": [
        {"$ref": f"{_EDR}/parameters/positionCoords.yaml"},
        _DATETIME, _PARAM_NAME, _Z, _F,
    ],
    "area": [
        {"$ref": f"{_EDR}/parameters/areaCoords.yaml"},
        _DATETIME, _PARAM_NAME, _Z, _F,
    ],
    "radius": [
        {"$ref": f"{_EDR}/parameters/positionCoords.yaml"},
        {"$ref": f"{_EDR}/parameters/within.yaml"},
        {"name": "within-units", "in": "query", "required": True, "description": "Units for the within parameter e.g. km", "schema": {"type": "string"}},
        _DATETIME, _PARAM_NAME, _Z, _F,
    ],
    "cube": [
        {"$ref": f"{_EDR}/parameters/bbox.yaml"},
        _DATETIME, _PARAM_NAME, _Z, _F,
    ],
    "trajectory": [
        {"name": "coords", "in": "query", "required": True, "description": "WKT LineString geometry", "schema": {"type": "string"}},
        _DATETIME, _PARAM_NAME, _Z, _F,
    ],
    "corridor": [
        {"name": "coords", "in": "query", "required": True, "description": "WKT LineString geometry", "schema": {"type": "string"}},
        {"name": "corridor-width", "in": "query", "required": True, "description": "Width of the corridor", "schema": {"type": "number"}},
        {"name": "corridor-height", "in": "query", "description": "Height of the corridor", "schema": {"type": "number"}},
        _DATETIME, _PARAM_NAME, _Z, _F,
    ],
    "items": [
        {"name": "bbox", "in": "query", "description": "Bounding box filter", "schema": {"type": "string"}},
        _DATETIME, _PARAM_NAME, _Z, _F,
    ],
    "locations": [
        {"$ref": f"{_EDR}/parameters/bbox.yaml"},
        _DATETIME, _F,
    ],
    "instances": [_F],
}


def _operation_id(*parts: str) -> str:
    """Build a valid operationId (letters, digits, underscores only).

    Each part is sanitized by splitting on non-alphanumeric characters,
    capitalizing the first letter of each word while preserving the rest,
    then joining everything together.
    """
    import re as _re

    def sanitize(s: str) -> str:
        words = _re.split(r"[^a-zA-Z0-9]+", s)
        return "".join((w[0].upper() + w[1:]) for w in words if w)

    return "".join(sanitize(p) for p in parts)


def _collection_response_schema(coll: Collection,
                                profile: "ServiceProfile | None") -> dict:
    """Build a 200 response schema for a single collection endpoint.

    Includes:
    - CRS constraints from extent_requirements (enum or pattern)
    - TRS/VRS constraints from extent_requirements
    - Full temporal extent schema (interval, values, trs)
    - Collection-level crs array
    - Full parameter_names objects with all fields
    - parameter_name_pattern as propertyNames constraint
    """
    crs_schema: dict = {"type": "string"}       # extent.spatial.crs
    trs_schema: dict = {"type": "string"}       # extent.temporal.trs
    vrs_schema: dict = {"type": "string"}       # extent.vertical.vrs
    supported_crs_schema: dict = {"type": "string"}  # crs[] and crs_details[].crs

    if profile and profile.extent_requirements:
        er = profile.extent_requirements

        def _apply(schema: dict, constraint: "object | None") -> None:
            if constraint is None:
                return
            if getattr(constraint, "allowed", None):
                schema["enum"] = constraint.allowed
            elif getattr(constraint, "pattern", None):
                schema["pattern"] = constraint.pattern

        _apply(crs_schema, er.extent_crs)
        _apply(trs_schema, er.extent_trs)
        _apply(vrs_schema, er.extent_vrs)
        _apply(supported_crs_schema, er.supported_crs)

    # Build parameter_names schema — use profile-supplied schema if present,
    # otherwise fall back to the default EDR Parameter schema.
    if profile and profile.parameter_schema:
        # Deep-copy so we don't mutate the profile model
        import copy
        param_item_schema = copy.deepcopy(profile.parameter_schema)
    else:
        param_item_schema = _parameter_schema()

    param_names_schema: dict = {
        "type": "object",
        "additionalProperties": param_item_schema,
    }
    if profile and profile.parameter_name_pattern:
        param_names_schema["propertyNames"] = {
            "type": "string",
            "pattern": profile.parameter_name_pattern,
        }

    # Build output_formats enum from collection's declared formats
    output_formats_schema: dict = {"type": "array", "items": {"type": "string"}}
    if coll.output_formats:
        output_formats_schema["items"] = {"type": "string", "enum": list(coll.output_formats)}

    # Build crs array schema — use collection-level crs list if present,
    # otherwise apply supported_crs constraint from extent_requirements.
    # supported_crs is distinct from extent_crs: it constrains what the
    # service supports for queries, not how the extent itself is expressed.
    if coll.crs:
        crs_array_schema: dict = {"type": "array", "items": {"type": "string", "enum": list(coll.crs)}}
    else:
        crs_array_schema = {"type": "array", "items": supported_crs_schema}

    schema: dict = {
        "type": "object",
        "required": ["id", "links", "extent"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "links": _LINKS_ARRAY,
            "crs": crs_array_schema,
            "output_formats": output_formats_schema,
            "parameter_names": param_names_schema,
            "extent": {
                "type": "object",
                "required": ["spatial"],
                "properties": {
                    "spatial": {
                        "type": "object",
                        "required": ["bbox", "crs"],
                        "properties": {
                            "bbox": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 4,
                                    "maxItems": 6,
                                },
                            },
                            "crs": crs_schema,
                        },
                    },
                    "temporal": {
                        "type": "object",
                        "properties": {
                            "interval": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {
                                        "oneOf": [
                                            {"type": "string", "format": "date-time"},
                                            {"type": "null"},
                                        ]
                                    },
                                    "minItems": 2,
                                    "maxItems": 2,
                                },
                            },
                            "values": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "trs": trs_schema,
                        },
                    },
                    "vertical": {
                        "type": "object",
                        "properties": {
                            "interval": {
                                "type": "array",
                                "items": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "values": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "vrs": vrs_schema,
                            "positive": {
                                "type": "string",
                                "enum": ["up", "down"],
                                "description": (
                                    "Direction in which vertical extent values increase "
                                    "(CF Conventions 'positive' attribute). Disambiguates "
                                    "interval ordering for VRS such as pressure levels."
                                ),
                            },
                        },
                    },
                    "custom": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "interval", "reference"],
                            "properties": {
                                "id": {"type": "string"},
                                "interval": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "values": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "reference": {"type": "string"},
                            },
                        },
                    },
                },
            },
            "data_queries": {
                "type": "object",
                "description": "Available EDR data query types for this collection",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "link": {
                            "type": "object",
                            "properties": {
                                "href": {"type": "string"},
                                "rel": {"type": "string"},
                                "variables": {
                                    "type": "object",
                                    "properties": {
                                        "query_type": {"type": "string"},
                                        "output_formats": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "default_output_format": {
                                            "type": "string",
                                            "description": "Default output format for this data query when f is omitted",
                                        },
                                        "crs": {
                                            "type": "array",
                                            "description": "CRS values supported by this data query (shorthand for crs_details)",
                                            "items": {"type": "string"},
                                        },
                                        "crs_details": {
                                            "type": "array",
                                            "description": "CRS values supported by this data query",
                                            "items": {
                                                "type": "object",
                                                "required": ["crs"],
                                                "properties": {
                                                    "crs": supported_crs_schema,
                                                    "wkt": {"type": "string"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    }

    return {
        "description": "Collection metadata",
        "content": {"application/json": {"schema": schema}},
    }


def _parameter_schema() -> dict:
    """OpenAPI schema for a single EDR Parameter object."""
    return {
        "type": "object",
        "required": ["type", "observedProperty"],
        "properties": {
            "type": {"type": "string", "const": "Parameter"},
            "id": {"type": "string"},
            "label": {"type": "string"},
            "description": {"type": "string"},
            "data-type": {"type": "string", "enum": ["integer", "float", "string"]},
            "unit": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "symbol": {
                        "oneOf": [
                            {"type": "string"},
                            {
                                "type": "object",
                                "required": ["value", "type"],
                                "properties": {
                                    "value": {"type": "string"},
                                    "type": {"type": "string"},
                                },
                            },
                        ]
                    },
                },
            },
            "observedProperty": {
                "type": "object",
                "required": ["label"],
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
            "measurementType": {
                "type": "object",
                "required": ["method", "duration"],
                "properties": {
                    "method": {"type": "string"},
                    "duration": {"type": "string"},
                },
            },
            "extent": {"type": "object"},
        },
        "additionalProperties": True,
    }


def _f_enum(profile: "ServiceProfile | None") -> list[str]:
    """Allowed values for the `f` (output format) parameter: media types."""
    enum = ["json", "html"]
    if profile:
        for fmt in profile.output_formats:
            if fmt.media_type not in enum:
                enum.append(fmt.media_type)
    return enum


def _format_media_type(profile: "ServiceProfile | None", format_name: str) -> str:
    """Resolve a format name (e.g. 'GeoTIFF') to its media type, falling back to the name."""
    if profile:
        for fmt in profile.output_formats:
            if fmt.name == format_name:
                return fmt.media_type
    return format_name


def _query_default_format(variables: object) -> str | None:
    """Read default_output_format from an EDR query's variables.

    edr-pydantic's Variables defines default_output_format as a real field;
    fall back to model_extra for forward compatibility.
    """
    val = getattr(variables, "default_output_format", None)
    if val is None:
        extra = getattr(variables, "model_extra", None) or {}
        val = extra.get("default_output_format")
    return val


def _f_param(profile: "ServiceProfile | None", variables: object | None) -> dict:
    """Return the `f` parameter for a query.

    When the query's variables declare a default_output_format, an inline `f`
    parameter is returned carrying that media type as its `default`. Otherwise
    the shared component reference is used.
    """
    default_fmt = _query_default_format(variables) if variables is not None else None
    if not default_fmt:
        return _F
    return {
        "name": "f", "in": "query", "required": False,
        "description": (
            "The optional f parameter indicates the output format which the server "
            "shall provide as part of the response document. Defaults to "
            f"{default_fmt} for this query."
        ),
        "schema": {
            "type": "string",
            "enum": _f_enum(profile),
            "default": _format_media_type(profile, default_fmt),
        },
        "style": "form", "explode": False,
    }


def _params_with_default_f(params: list[dict], profile: "ServiceProfile | None",
                           variables: object | None) -> list[dict]:
    """Replace the shared `_F` reference in a params list with a query-specific default."""
    f_param = _f_param(profile, variables)
    if f_param is _F:
        return params
    return [f_param if p is _F else p for p in params]


def _collection_paths(coll: Collection, examples: dict | None = None,
                      profile: ServiceProfile | None = None) -> dict:
    paths: dict = {}
    tag = coll.id
    desc = getattr(coll, "description", None) or coll.id
    base = f"/collections/{coll.id}"

    # Resolve effective POST flag: collection-level overrides profile-level default.
    # Collection.post_queries is None → inherit; True/False → explicit override.
    profile_default = profile.allow_post_queries if profile else False
    include_post = coll.post_queries if coll.post_queries is not None else profile_default

    # Build a collection-specific response schema that includes CRS and
    # parameter-name constraints from the profile's extent_requirements
    # and parameter_name_pattern.
    coll_schema = _collection_response_schema(coll, profile)
    # Build coverage response reflecting this collection's actual output formats
    cov_resp = _coverage_response(coll, profile)

    paths[base] = {"get": {
        "summary": f"Get {coll.title or coll.id} metadata",
        "description": desc,
        "operationId": _operation_id("describe", coll.id, "Collection"),
        "tags": [tag],
        "parameters": [_F, _LANG],
        "responses": {
            "200": coll_schema,
            "400": _ERR_400, "404": _ERR_404, "500": _ERR_500,
        },
    }}

    # Always generate Features paths (items, queryables, schema)
    paths[f"{base}/items"] = {"get": {
        "summary": f"Get {coll.title or coll.id} items",
        "description": desc,
        "operationId": _operation_id("get", coll.id, "Features"),
        "tags": [tag],
        "parameters": [_F, _LANG],
        "responses": {
            "200": _R200_FEATURES,
            "400": _ERR_400, "404": _ERR_404, "500": _ERR_500,
        },
    }}
    paths[f"{base}/items/{{featureId}}"] = {"get": {
        "summary": f"Get {coll.title or coll.id} item by id",
        "description": desc,
        "operationId": _operation_id("get", coll.id, "Feature"),
        "tags": [tag],
        "parameters": [
            {"name": "featureId", "in": "path", "required": True, "description": "Feature identifier", "schema": {"type": "string"}},
            _F, _LANG,
        ],
        "responses": {
            "200": _R200_FEATURES,
            "400": _ERR_400, "404": _ERR_404, "500": _ERR_500,
        },
    }}

    if not coll.data_queries:
        return paths

    dq_map = {name: val for name, val in coll.data_queries if val is not None}
    active = set(dq_map)

    def _vars(query_type: str) -> object | None:
        qv = dq_map.get(query_type)
        return qv.link.variables if qv is not None and qv.link else None

    for qt in active:
        params = _params_with_default_f(_QUERY_PARAMS.get(qt, []), profile, _vars(qt))

        if qt == "instances":
            paths[f"{base}/instances"] = {"get": {
                "summary": f"Get pre-defined instances of {coll.id}",
                "description": desc,
                "operationId": _operation_id("getInstances", coll.id),
                "tags": [tag],
                "parameters": [_F],
                "responses": {
                    "200": _R200_FEATURES,
                    "400": _ERR_400, "500": _ERR_500,
                },
            }}
            instance_id_param = {"$ref": f"{_EDR}/parameters/instanceId.yaml"}
            if examples and "instanceId" in examples:
                instance_id_param = {
                    "name": "instanceId", "in": "path", "required": True,
                    "description": "Instance identifier",
                    "schema": {"type": "string"},
                    "example": examples["instanceId"],
                }
            paths[f"{base}/instances/{{instanceId}}"] = {"get": {
                "summary": f"Get {coll.id} instance",
                "description": desc,
                "operationId": _operation_id("getInstance", coll.id),
                "tags": [tag],
                "parameters": [instance_id_param, _F],
                "responses": {"200": _R200_FEATURES},
            }}
            # instance-level query sub-paths — GET + optional POST
            for sub_qt in (active - {"instances"}):
                sub_params = _params_with_default_f(_QUERY_PARAMS.get(sub_qt, []), profile, _vars(sub_qt))
                get_op = {
                    "summary": f"query {coll.id} instance by {sub_qt}",
                    "description": desc,
                    "operationId": _operation_id("query", sub_qt, "Instance", coll.id),
                    "tags": [tag],
                    "parameters": [instance_id_param, *sub_params],
                    "responses": cov_resp,
                }
                path_ops = {"get": get_op}
                if include_post:
                    path_ops["post"] = _post_operation(get_op, sub_qt, coll.id, cov_resp)
                paths[f"{base}/instances/{{instanceId}}/{sub_qt}"] = path_ops

        elif qt == "items":
            get_op = {
                "summary": f"query {coll.id} by items",
                "description": desc,
                "operationId": _operation_id("queryItems", coll.id),
                "tags": [tag],
                "parameters": params,
                "responses": cov_resp,
            }
            path_ops = {"get": get_op}
            if include_post:
                path_ops["post"] = _post_operation(get_op, "items", coll.id, cov_resp)
            paths[f"{base}/items"] = path_ops

        elif qt == "locations":
            get_locations_op = {
                "summary": f"Get pre-defined locations of {coll.id}",
                "description": desc,
                "operationId": _operation_id("getLocations", coll.id),
                "tags": [tag],
                "parameters": params,
                "responses": {
                    "200": _R200_FEATURES,
                    "400": _ERR_400, "500": _ERR_500,
                },
            }
            path_ops = {"get": get_locations_op}
            if include_post:
                path_ops["post"] = _post_operation(get_locations_op, "locations", coll.id, {"200": _R200_FEATURES, "400": _ERR_400, "500": _ERR_500})
            paths[f"{base}/locations"] = path_ops

            get_location_op = {
                "summary": f"query {coll.id} by location",
                "description": desc,
                "operationId": _operation_id("getLocation", coll.id),
                "tags": [tag],
                "parameters": [
                    {"$ref": f"{_EDR}/parameters/locationId.yaml"},
                    _DATETIME, _PARAM_NAME, _f_param(profile, _vars("locations")),
                ],
                "responses": cov_resp,
            }
            loc_path_ops = {"get": get_location_op}
            if include_post:
                loc_path_ops["post"] = _post_operation(get_location_op, "locations", coll.id, cov_resp)
            paths[f"{base}/locations/{{locId}}"] = loc_path_ops

        else:
            get_op = {
                "summary": f"query {coll.id} by {qt}",
                "description": desc,
                "operationId": _operation_id("query", qt, coll.id),
                "tags": [tag],
                "parameters": params,
                "responses": cov_resp,
            }
            path_ops = {"get": get_op}
            if include_post:
                path_ops["post"] = _post_operation(get_op, qt, coll.id, cov_resp)
            paths[f"{base}/{qt}"] = path_ops

    return paths


def _core_paths(profile: ServiceProfile) -> dict:
    landing_response = _landing_page_schema(
        profile.req_uri,
        title=profile.title,
        description=profile.description or "",
        keywords=profile.keywords or None,
    )
    
    # Conformance response with required conformance classes
    conformance_response = _R200_CONFORMANCE.copy()
    if profile.required_conformance_classes:
        conformance_response["content"]["application/json"]["schema"]["properties"]["conformsTo"]["contains"] = {
            "enum": profile.required_conformance_classes
        }
    
    return {
        "/": {"get": {
            "summary": "Landing page",
            "description": "Landing page",
            "operationId": "getLandingPage",
            "tags": ["server"],
            "parameters": [_F, _LANG],
            "responses": {"200": landing_response, "400": _ERR_400, "500": _ERR_500},
        }},
        "/conformance": {"get": {
            "summary": "API conformance definition",
            "description": "API conformance definition",
            "operationId": "getConformanceDeclaration",
            "tags": ["server"],
            "parameters": [_F, _LANG],
            "responses": {"200": conformance_response, "400": _ERR_400, "500": _ERR_500},
        }},
        "/collections": {"get": {
            "summary": "Collections",
            "description": "Collections",
            "operationId": "getCollections",
            "tags": ["server"],
            "parameters": [_F, _LANG],
            "responses": {"200": {"description": "Collections list", "content": {"application/json": {"schema": {"type": "object", "properties": {"links": _LINKS_ARRAY}}}}}, "400": _ERR_400, "500": _ERR_500},
        }},
        "/openapi": {"get": {
            "summary": "OpenAPI definition",
            "description": "Retrieve the OpenAPI definition document for this API.",
            "operationId": "getOpenAPI",
            "tags": ["server"],
            "parameters": [_F],
            "responses": {"200": {"description": "OpenAPI document"}, "default": _ERR_DEFAULT},
        }},
    }


def _processes_paths(profile: ServiceProfile) -> dict:
    if not profile.processes:
        return {}
    paths: dict = {
        "/processes": {"get": {
            "summary": "Processes",
            "description": "Processes",
            "operationId": "getProcesses",
            "tags": ["server"],
            "parameters": [_F],
            "responses": {
                "200": {"$ref": f"{_PROCESSES}/responses/ProcessList.yaml"},
                "default": _ERR_DEFAULT,
            },
        }},
        "/jobs": {"get": {
            "summary": "Retrieve jobs list",
            "description": "Retrieve a list of jobs",
            "operationId": "getJobs",
            "tags": ["jobs"],
            "responses": {
                "200": {"description": "List of jobs", "content": {"application/json": {"schema": {"type": "object"}}}},
                "404": _ERR_404,
                "default": _ERR_DEFAULT,
            },
        }},
        "/jobs/{jobId}": {
            "get": {
                "summary": "Retrieve job details",
                "description": "Retrieve job details",
                "operationId": "getJob",
                "tags": ["jobs"],
                "parameters": [{"name": "jobId", "in": "path", "required": True, "description": "job identifier", "schema": {"type": "string"}}, _F],
                "responses": {
                    "200": {"description": "Job details", "content": {"application/json": {"schema": {"type": "object"}}}},
                    "404": _ERR_404,
                    "default": _ERR_DEFAULT,
                },
            },
            "delete": {
                "summary": "Cancel / delete job",
                "description": "Cancel / delete job",
                "operationId": "deleteJob",
                "tags": ["jobs"],
                "parameters": [{"name": "jobId", "in": "path", "required": True, "description": "job identifier", "schema": {"type": "string"}}],
                "responses": {
                    "204": {"description": "Job deleted successfully"},
                    "404": _ERR_404,
                    "default": _ERR_DEFAULT,
                },
            },
        },
        "/jobs/{jobId}/results": {"get": {
            "summary": "Retrieve job results",
            "description": "Retrieve job results",
            "operationId": "getJobResults",
            "tags": ["jobs"],
            "parameters": [{"name": "jobId", "in": "path", "required": True, "description": "job identifier", "schema": {"type": "string"}}, _F],
            "responses": {
                "200": {"description": "Job results", "content": {"application/json": {"schema": {"type": "object"}}}},
                "404": _ERR_404,
                "default": _ERR_DEFAULT,
            },
        }},
    }
    for proc in profile.processes:
        pid = proc["id"]
        pdesc = proc.get("description", pid)
        ptitle = proc.get("title", pid)
        output_content = proc.get("output_content", {"application/json": {"schema": {"type": "object"}}})
        paths[f"/processes/{pid}"] = {"get": {
            "summary": "Get process metadata",
            "description": pdesc,
            "operationId": _operation_id("describe", pid, "Process"),
            "tags": [pid],
            "parameters": [_F],
            "responses": {
                "200": {"description": f"{ptitle} process metadata", "content": {"application/json": {"schema": {"type": "object"}}}},
                "default": _ERR_DEFAULT,
            },
        }}
        paths[f"/processes/{pid}/execution"] = {"post": {
            "summary": f"Process {ptitle} execution",
            "description": pdesc,
            "operationId": _operation_id("execute", pid, "Job"),
            "tags": [pid],
            "parameters": [{
                "name": "Prefer",
                "in": "header",
                "required": False,
                "description": "Indicates client preferences, including whether the client is capable of asynchronous processing.",
                "schema": {"type": "string", "enum": ["respond-async"]},
            }],
            "requestBody": {
                "required": True,
                "description": "Mandatory execute request JSON",
                "content": {"application/json": {"schema": {"$ref": f"{_PROCESSES}/schemas/execute.yaml"}}},
            },
            "responses": {
                "200": {"description": "Process output schema", "content": output_content},
                "201": {"$ref": f"{_PROCESSES}/responses/ExecuteAsync.yaml"},
                "404": _ERR_404,
                "500": _ERR_500,
                "default": _ERR_DEFAULT,
            },
        }}
    return paths


# ---------------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------------

def build_openapi(profile: ServiceProfile) -> dict:
    paths: dict = _core_paths(profile)
    for coll in profile.collections:
        paths.update(_collection_paths(coll, profile.collection_examples.get(coll.id), profile))
    paths.update(_processes_paths(profile))

    tags = [{"name": "server", "description": profile.title}]
    for coll in profile.collections:
        tags.append({"name": coll.id, "description": getattr(coll, "description", None) or coll.id})
    if profile.processes:
        tags += [{"name": p["id"]} for p in profile.processes]
        tags += [{"name": "jobs"}]

    # Build f parameter enum from profile output formats + standard formats
    f_enum = _f_enum(profile)

    # Build the info.contact block. A profile-level `provider` takes precedence;
    # otherwise fall back to document_metadata editors/orgs.
    m = profile.document_metadata
    contact: dict = {}
    if profile.provider:
        p = profile.provider
        contact["name"] = p.name
        if p.url:
            contact["url"] = p.url
        if p.contact:
            c = p.contact
            if c.email:
                contact["email"] = c.email
            # OpenAPI contact only models name/url/email — carry the rest as x- extensions.
            for key in ("phone", "hours", "instructions", "address", "postalcode", "city", "country"):
                val = getattr(c, key, None)
                if val:
                    contact[f"x-{key}"] = val
    if "name" not in contact and m and m.editors:
        contact["name"] = m.editors[0]
    if "x-organization" not in contact and m and m.submitting_orgs:
        contact["x-organization"] = m.submitting_orgs[0]
    # Fall back to a generic contact if nothing is specified
    if not contact:
        contact["name"] = profile.title

    # Assemble the info block, adding optional x- metadata extensions.
    info: dict = {
        "title": profile.title,
        "version": profile.version,
        "description": profile.description or f"OGC API - EDR Part 3 Service Profile: {profile.title}",
        "x-ogc-profile": profile.req_uri,
        "x-keywords": profile.keywords if profile.keywords else [],
        "contact": contact,
    }
    if profile.classification:
        info["x-classification"] = {
            k: v for k, v in (
                ("level", profile.classification.level),
                ("system", profile.classification.system),
            ) if v
        }
    if profile.metadata_date:
        info["x-metadata-date"] = profile.metadata_date
    if profile.resource_service_publish_date:
        info["x-resource-publish-date"] = profile.resource_service_publish_date
    if profile.resource_default_locale:
        info["x-default-locale"] = profile.resource_default_locale

    return {
        "openapi": "3.1.0",
        "info": info,
        # Per OGC API - EDR Part 3 REQ_publishing: this profile is implementation-independent.
        # The placeholder server URL "/" is required by OpenAPI validators but implementations
        # SHALL substitute their own server URL when deploying this profile.
        "servers": [
            {
                "url": "/",
                "description": (
                    "Placeholder server URL. Per OGC API - EDR Part 3 REQ_publishing, "
                    "this profile document is implementation-independent. "
                    "Implementations SHALL substitute their own server URL."
                ),
            }
        ],
        "tags": tags,
        "paths": paths,
        "components": {
            "parameters": {
                "f": {
                    "name": "f", "in": "query", "required": False,
                    "description": "The optional f parameter indicates the output format which the server shall provide as part of the response document.",
                    "schema": {"type": "string", "enum": f_enum},
                    "style": "form", "explode": False,
                },
                "lang": {
                    "name": "lang", "in": "query", "required": False,
                    "description": "The optional lang parameter instructs the server return a response in a certain language, if supported.",
                    "schema": {"type": "string", "default": "en-US", "enum": ["en-US"]},
                },
            },
            "responses": {
                "default": {"description": "Unexpected error", "content": {"application/json": {"schema": {"type": "object"}}}},
            },
        },
    }


# ---------------------------------------------------------------------------
# AsyncAPI
# ---------------------------------------------------------------------------

def build_asyncapi(profile: ServiceProfile) -> dict:
    if not profile.pubsub:
        raise ValueError("profile has no pubsub configuration")

    pub = profile.pubsub
    channels: dict = {}
    operations: dict = {}
    messages: dict = {}

    pubsub_collections = pub.collections if pub.collections else [c.id for c in profile.collections]

    for coll in profile.collections:
        if coll.id not in pubsub_collections:
            continue

        ch_key = f"{coll.id}_notifications"
        msg_key = f"{coll.id}Observation"

        # Use per-collection filters if available, otherwise fall back to global
        coll_filters = pub.collection_filters.get(coll.id)
        filters = coll_filters.filters if coll_filters else pub.filters

        channels[ch_key] = {
            "address": f"collections/{coll.id}/items/#",
            "description": f"Real-time notifications for {coll.id}",
            "messages": {msg_key: {"$ref": f"#/components/messages/{msg_key}"}},
            **({"x-ogc-subscription": {
                "filters": [
                    {"name": f.name, "description": f.description, "schema": {"type": f.type.value}}
                    for f in filters
                ]
            }} if filters else {}),
        }

        operations[f"receive_{coll.id}_update"] = {
            "action": "receive",
            "channel": {"$ref": f"#/channels/{ch_key}"},
            "messages": [{"$ref": f"#/channels/{ch_key}/messages/{msg_key}"}],
        }

        messages[msg_key] = {
            "payload": {
                "type": "object",
                "required": ["type", "properties"],
                "properties": {
                    "type": {"type": "string", "const": "Feature"},
                    "properties": {
                        "type": "object",
                        "required": ["id", "timestamp"],
                        "properties": {
                            "id": {"type": "string"},
                            "timestamp": {"type": "string", "format": "date-time"},
                        },
                    },
                },
            }
        }

    # Build servers: default production + additional servers
    servers = {
        "production": {
            "host": f"{pub.broker_host}:{pub.broker_port}",
            "protocol": pub.protocol,
        }
    }
    for srv in pub.servers:
        server_def = {
            "description": srv.description,
            "host": f"{srv.host}:{srv.port}" if srv.port else srv.host,
            "protocol": srv.protocol,
            "security": [],
        }
        if srv.port:
            server_def["variables"] = {"port": {"default": str(srv.port), "enum": [str(srv.port)]}}
        if srv.pathname:
            server_def["pathname"] = srv.pathname
        servers[srv.name] = server_def

    return {
        "asyncapi": "3.0.0",
        "info": {"title": f"{profile.title} AsyncAPI", "version": profile.version},
        "servers": servers,
        "channels": channels,
        "operations": operations,
        "components": {"messages": messages},
    }


# ---------------------------------------------------------------------------
# AsciiDoc / Metanorma
# ---------------------------------------------------------------------------

def _req_adoc(profile: ServiceProfile) -> str:
    lines = [
        f"[[req_class_{profile.name}]]",
        "[requirements_class]",
        "====",
        "[%metadata]",
        f"identifier:: {profile.req_uri}",
        f"target-type:: {profile.title} Profile Standard",
    ]
    for req in profile.requirements:
        lines.append(f"requirement:: /req/{profile.name}/{req.id}")
    lines.append("====")
    return "\n".join(lines) + "\n"


def _conf_adoc(profile: ServiceProfile) -> str:
    lines = [
        f"[[ats_class_{profile.name}]]",
        "[conformance_class]",
        "====",
        "[%metadata]",
        f"identifier:: {profile.conf_uri}",
        f"target:: {profile.req_uri}",
    ]
    for test in profile.abstract_tests:
        lines.append(f"abstract-test:: /conf/{profile.name}/{test.id}")
    lines.append("====")
    return "\n".join(lines) + "\n"


def _individual_req_adoc(profile: ServiceProfile, req_id: str) -> str:
    req = next(r for r in profile.requirements if r.id == req_id)
    anchor = f"req_{profile.name}_{req.id}".replace("/", "_").replace("-", "_")
    lines = [
        f"[[{anchor}]]",
        "[requirement]",
        "====",
        "[%metadata]",
        f"identifier:: /req/{profile.name}/{req.id}",
        f"statement:: {req.statement}",
    ]
    for part in req.parts:
        lines.append(f"part:: {part}")
    lines.append("====")
    return "\n".join(lines) + "\n"


def _individual_test_adoc(profile: ServiceProfile, test_id: str) -> str:
    test = next(t for t in profile.abstract_tests if t.id == test_id)
    anchor = f"ats_{profile.name}_{test.id}".replace("/", "_").replace("-", "_")
    lines = [
        f"[[{anchor}]]",
        "[abstract_test]",
        "====",
        "[%metadata]",
        f"identifier:: /conf/{profile.name}/{test.id}",
        f"target:: /req/{profile.name}/{test.requirement_id}",
        f"test-purpose:: Validate that {test.id.replace('-', ' ')} is correctly implemented.",
        "test-method::",
    ]
    for step in test.steps:
        lines.append(f"step:: {step}")
    lines.append("====")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Metanorma root document
# ---------------------------------------------------------------------------

_PDF_OVERRIDE_FILENAME = "pdf_override.xsl"

# Individual template overrides for the OGC Metanorma flavor's PDF XSL. Each is
# keyed to a real template name in metanorma-ogc's ogc.standard.xsl and merged
# in via :pdf-stylesheet-override:. These are coupled to the OGC flavor.
_OVERRIDE_SUPPRESS_LOGO = """
  <!-- Suppress the OGC flavor logo on cover/preface (rebranding). -->
  <xsl:template name="insertLogoPreface"/>
  <xsl:template name="insertLogo"/>
"""

_OVERRIDE_SUPPRESS_CROSSING_LINES = """
  <!-- Remove the 'crossing lines' design element by making it invisible. -->
  <xsl:template name="insertCrossingLines">
    <fo:block-container absolute-position="fixed" width="0mm" height="0mm" font-size="0">
      <fo:block/>
    </fo:block-container>
  </xsl:template>
"""

_OVERRIDE_SUPPRESS_TITLE_UNDERLINES = """
  <!-- Remove the horizontal rule drawn beneath section titles. -->
  <xsl:template name="insertShortHorizontalLine">
    <fo:block/>
  </xsl:template>
  <xsl:template name="insertBigHorizontalLine">
    <fo:block/>
  </xsl:template>
"""

# Render the section-divider number as plain text instead of a coloured circle.
# Mirrors the flavor's own number computation so annexes still number correctly.
# The colour is injected so the number stays readable against whatever divider
# background is in effect (white text on the flavor's navy, or a dark DGIWG
# colour on a rebranded light page).
def _plain_section_numbers_override(color: str) -> str:
    return f"""
  <!-- Section-divider number as plain text (no OGC circle), coloured {color}. -->
  <xsl:template name="insertSectionNumInCircle">
    <xsl:variable name="sectionNum_"><xsl:call-template name="getSection"/></xsl:variable>
    <xsl:variable name="sectionNum">
      <xsl:choose>
        <xsl:when test="normalize-space($sectionNum_) = '' and self::mn:annex">
          <xsl:number format="A" count="mn:annex[not(@continue = 'true')]" level="any" lang="en"/>
        </xsl:when>
        <xsl:otherwise><xsl:value-of select="$sectionNum_"/></xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <fo:block font-size="24pt" font-weight="bold" color="{color}"><xsl:value-of select="$sectionNum"/></fo:block>
  </xsl:template>
"""


# Force the big section-divider title colour. The flavor's divider page-sequence
# sets the text colour to white (readable on its navy background); when the
# divider page is rebranded to a light background that white title becomes
# invisible, so we set an explicit (dark) colour here.
def _section_title_color_override(color: str) -> str:
    return f"""
  <!-- Section-divider title colour (readable on a rebranded light page). -->
  <xsl:template name="insertSectionTitleBig">
    <xsl:param name="title"/>
    <fo:block font-size="33pt" margin-bottom="6pt" color="{color}">
      <xsl:apply-templates select="xalan:nodeset($title)" mode="titlebig"/>
    </fo:block>
    <xsl:call-template name="insertBigHorizontalLine"/>
  </xsl:template>
"""


# Every-page watermark (e.g. "DRAFT"). The OGC flavor's region-body flow is
# painted on top of the header region, so a watermark placed in the header sits
# behind opaque tables. The footer region is painted after the body, so we
# reproduce the flavor's footer and prepend a page-fixed, rotated, semi-
# transparent SVG text mark inside the footer static-content — this overlays
# every page, including over tables.
def _page_watermark_override(text: str, color: str = "rgb(200,200,200)") -> str:
    esc = _xml_escape(text)
    watermark = f"""
      <fo:block-container absolute-position="fixed" left="0mm" top="0mm" font-size="0">
        <fo:block>
          <fo:instream-foreign-object content-height="{{$pageHeight}}mm" content-width="{{$pageWidth}}mm" fox:alt-text="Watermark">
            <svg xmlns="http://www.w3.org/2000/svg" width="{{$pageWidth}}mm" height="{{$pageHeight}}mm" viewBox="0 0 210 297">
              <text x="105" y="150" text-anchor="middle" transform="rotate(-45 105 150)" font-size="38" font-family="Lato" fill="{color}" fill-opacity="0.55">{esc}</text>
            </svg>
          </fo:instream-foreign-object>
        </fo:block>
      </fo:block-container>"""
    return f"""
  <!-- Every-page diagonal watermark, prepended to the footer region (painted
       over the body, so it also overlays tables). Reproduces the OGC footer. -->
  <xsl:template name="insertFooter">
    <xsl:param name="num"/>
    <xsl:param name="color"/>
    <fo:static-content flow-name="footer" role="artifact">
{watermark}
      <fo:block-container font-size="8pt" color="{{$color}}" padding-top="6mm">
        <xsl:if test="normalize-space($color) = ''">
          <xsl:variable name="color_text_title">
            <xsl:call-template name="getVariable"><xsl:with-param name="variable">color_text_title</xsl:with-param></xsl:call-template>
          </xsl:variable>
          <xsl:attribute name="color"><xsl:value-of select="$color_text_title"/></xsl:attribute>
        </xsl:if>
        <fo:table table-layout="fixed" width="100%">
          <fo:table-column column-width="90%"/>
          <fo:table-column column-width="10%"/>
          <fo:table-body>
            <fo:table-row>
              <fo:table-cell>
                <fo:block>
                  <fo:inline font-weight="bold">
                    <xsl:call-template name="addLetterSpacing">
                      <xsl:with-param name="text" select="concat($variables/mnx:doc[@num = $num]/copyright-owner, ' ')"/>
                      <xsl:with-param name="letter-spacing" select="0.2"/>
                    </xsl:call-template>
                  </fo:inline>
                  <xsl:call-template name="addLetterSpacing">
                    <xsl:with-param name="text" select="$variables/mnx:doc[@num = $num]/docnumber"/>
                    <xsl:with-param name="letter-spacing" select="0.2"/>
                  </xsl:call-template>
                </fo:block>
              </fo:table-cell>
              <fo:table-cell text-align="right">
                <fo:block font-weight="bold">
                  <fo:page-number/>
                </fo:block>
              </fo:table-cell>
            </fo:table-row>
          </fo:table-body>
        </fo:table>
      </fo:block-container>
    </fo:static-content>
  </xsl:template>
"""


def _effective_pdf_config(m) -> dict:
    """Resolve effective PDF-styling flags and divider colours from metadata.

    ``suppress_design_elements`` is the consolidated "debrand" switch: it turns
    on crossing-line suppression, plain section numbers and title-underline
    suppression together, and rebrands the section-divider pages to a light
    (default white) background with dark, readable numbers/titles so they no
    longer carry the OGC navy house style.
    """
    debrand = bool(getattr(m, "suppress_design_elements", False))
    crossing = debrand or bool(getattr(m, "suppress_crossing_lines", False))
    underlines = debrand or bool(getattr(m, "suppress_title_underlines", False))
    plain_nums = debrand or bool(getattr(m, "plain_section_numbers", False))

    colors = getattr(m, "colors", None)
    page_bg = getattr(colors, "page_background", None) if colors else None
    title_c = getattr(colors, "title", None) if colors else None
    cover_c = getattr(colors, "cover_text", None) if colors else None

    # Divider background + foreground colours.
    if debrand:
        # Rebrand: light divider pages (white unless overridden) + dark text.
        divider_bg = page_bg or "#FFFFFF"
        divider_fg = title_c or cover_c or "#1F3864"
    elif page_bg:
        # Explicit custom background: assume it is light, use a dark foreground.
        divider_bg = page_bg
        divider_fg = title_c or cover_c or "#1F3864"
    else:
        # Flavor default: navy divider pages, white number/title.
        divider_bg = None
        divider_fg = "white"

    return {
        "logo": bool(getattr(m, "suppress_flavor_logo", False)),
        "crossing": crossing,
        "underlines": underlines,
        "plain_nums": plain_nums,
        "body_font": getattr(m, "body_font", None),
        "watermark": getattr(m, "page_watermark", None),
        "divider_bg": divider_bg,
        "divider_fg": divider_fg,
    }


def _pdf_override_flags(m) -> list[str]:
    """Return the override snippets enabled by document_metadata, in order."""
    if not m:
        return []
    cfg = _effective_pdf_config(m)
    parts: list[str] = []
    if cfg["logo"]:
        parts.append(_OVERRIDE_SUPPRESS_LOGO)
    if cfg["crossing"]:
        parts.append(_OVERRIDE_SUPPRESS_CROSSING_LINES)
    if cfg["underlines"]:
        parts.append(_OVERRIDE_SUPPRESS_TITLE_UNDERLINES)
    if cfg["plain_nums"]:
        parts.append(_plain_section_numbers_override(cfg["divider_fg"]))
    # When the divider background is rebranded (light), force the big title
    # colour too — the flavor inherits white text, invisible on a light page.
    if cfg["divider_bg"] is not None:
        parts.append(_section_title_color_override(cfg["divider_fg"]))
    if cfg["watermark"]:
        parts.append(_page_watermark_override(cfg["watermark"]))
    # Body font override — the OGC flavor hardcodes Lato in the root-style
    # attribute-set, so :body-font: alone doesn't work; we need an XSL override.
    body = cfg["body_font"]
    if body:
        noto = '<xsl:value-of select="$font_noto_sans"/>'
        parts.append(
            f'\n  <!-- Override body font family (OGC default is Lato). -->\n'
            f'  <xsl:attribute-set name="root-style">\n'
            f'    <xsl:attribute name="font-family">{body}, STIX Two Math, {noto}</xsl:attribute>\n'
            f'    <xsl:attribute name="font-family-generic">Sans</xsl:attribute>\n'
            f'    <xsl:attribute name="font-size">11pt</xsl:attribute>\n'
            f'  </xsl:attribute-set>\n'
        )
    return parts


def _build_pdf_override_xsl(m) -> str | None:
    """Assemble the consolidated PDF stylesheet override, or None when unused.

    :pdf-stylesheet-override: accepts a single file, so all requested template
    overrides (logo suppression, crossing lines, section-number circles, title
    underlines, divider rebranding and the every-page watermark) are merged into
    one stylesheet. mn2pdf splices these named-template bodies over the flavor's
    at equal import precedence, so they take effect.
    """
    parts = _pdf_override_flags(m)
    if not parts:
        return None
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"\n'
        '                xmlns:fo="http://www.w3.org/1999/XSL/Format"\n'
        '                xmlns:mn="https://www.metanorma.org/ns/standoc"\n'
        '                xmlns:fox="http://xmlgraphics.apache.org/fop/extensions"\n'
        '                xmlns:xalan="http://xml.apache.org/xalan"\n'
        '                xmlns:java="http://xml.apache.org/xalan/java"\n'
        '                xmlns:mnx="https://www.metanorma.org/ns/xslt"\n'
        '                version="1.0">\n'
        + "".join(parts)
        + "</xsl:stylesheet>\n"
    )


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _build_boilerplate_xml(profile: ServiceProfile) -> str | None:
    """Build a Metanorma boilerplate XML overriding the flavor's legal text.

    Returns the XML string, or None when no boilerplate is configured. Any
    statement not supplied is synthesised from copyright_holder so no flavor
    default (e.g. OGC copyright) leaks through.
    """
    m = profile.document_metadata
    bp = m.boilerplate if m else None
    if not bp:
        return None

    holder = (m.copyright_holder if m and m.copyright_holder else None) or (
        m.submitting_orgs[0] if m and m.submitting_orgs else "the copyright holder"
    )
    year = m.copyright_year if m else 2026

    copyright_txt = bp.copyright or f"Copyright © {year} {holder}. All rights reserved."
    license_txt = bp.license or f"Use of this document is subject to the terms and conditions of {holder}."
    legal_txt = bp.legal or (
        "Attention is drawn to the possibility that some of the elements of this "
        f"document may be the subject of patent rights. {holder} shall not be held "
        "responsible for identifying any or all such patent rights."
    )
    feedback_txt = bp.feedback or f"Comments on this document should be directed to {holder}."

    return (
        "<boilerplate>\n"
        "  <copyright-statement>\n"
        "    <clause>\n"
        "      <title>Copyright notice</title>\n"
        f"      <p id=\"bp-copyright\">{_xml_escape(copyright_txt)}</p>\n"
        "    </clause>\n"
        "  </copyright-statement>\n"
        "  <license-statement>\n"
        "    <clause>\n"
        "      <title>License Agreement</title>\n"
        f"      <p id=\"bp-license\">{_xml_escape(license_txt)}</p>\n"
        "    </clause>\n"
        "  </license-statement>\n"
        "  <legal-statement>\n"
        "    <clause>\n"
        "      <title>Note</title>\n"
        f"      <p id=\"bp-legal\">{_xml_escape(legal_txt)}</p>\n"
        "    </clause>\n"
        "  </legal-statement>\n"
        "  <feedback-statement>\n"
        "    <clause>\n"
        f"      <p id=\"bp-feedback\">{_xml_escape(feedback_txt)}</p>\n"
        "    </clause>\n"
        "  </feedback-statement>\n"
        "</boilerplate>\n"
    )


def _build_document_adoc(profile: ServiceProfile) -> str:
    m = profile.document_metadata
    year = m.copyright_year if m else 2026
    default_date = f"{year}-01-01"
    # doctype: configurable; draft-standard is the default for in-progress profiles
    doctype = (m.doc_type if m and m.doc_type else "draft-standard")
    # docsubtype: 'profile' is the natural subtype for a service profile, but when
    # doctype is draft-standard/standard OGC expects implementation/profile etc.
    docsubtype = m.doc_subtype if m else "implementation"
    lines = [
        f"= {profile.title}",
        f":doctype: {doctype}",
        f":docsubtype: {docsubtype}",
        f":edition: {profile.version}",
        ":language: en",
        ":committee: technical",
        f":docnumber: {m.doc_number if m else profile.name}",
        f":copyright-year: {year}",
        f":published-date: {(m.publication_date if m and m.publication_date else default_date)}",
        f":issued-date: {(m.approval_date if m and m.approval_date else default_date)}",
        f":received-date: {(m.submission_date if m and m.submission_date else default_date)}",
    ]
    if m and m.status:
        lines.append(f":status: {m.status}")
    if m and m.external_id:
        lines.append(f":external-id: {m.external_id}")
    if m and m.editors:
        for i, editor in enumerate(m.editors):
            suffix = f"_{i + 1}" if i > 0 else ""
            lines.append(f":fullname{suffix}: {editor}")
            lines.append(f":role{suffix}: editor")
    if m and m.keywords:
        lines.append(f":keywords: {', '.join(m.keywords)}")
    if m and m.submitting_orgs:
        lines.append(f":submitting-organizations: {'; '.join(m.submitting_orgs)}")
    # PDF colour-scheme overrides (mapped to Metanorma attributes).
    if m and m.colors:
        for attr, value in m.colors.to_metanorma_attributes().items():
            lines.append(f":{attr}: {value}")
    # When debranding (suppress_design_elements) rebrands the section-divider
    # pages to a light background, emit the background-page colour unless the
    # profile already set one explicitly via colors.page_background.
    if m:
        cfg = _effective_pdf_config(m)
        explicit_bg = bool(m.colors and m.colors.page_background)
        if cfg["divider_bg"] is not None and not explicit_bg:
            lines.append(
                f":presentation-metadata-color-background-page: {cfg['divider_bg']}"
            )
        # The preface/contents pages draw the OGC 'crossing lines with dot'
        # motif inline (using the secondary-shade-2 / color_design_light colour),
        # not via a named template, so an XSL override can't remove them. When
        # crossing lines are being suppressed we white them out via the colour
        # instead, unless the profile already set colors.cover_lines explicitly.
        explicit_lines = bool(m.colors and m.colors.cover_lines)
        if cfg["crossing"] and not explicit_lines:
            lines.append(":presentation-metadata-color-secondary-shade-2: #FFFFFF")
    # PDF font overrides (body/header/monospace).
    if m and m.fonts:
        for attr, value in m.fonts.to_metanorma_attributes().items():
            lines.append(f":{attr}: {value}")
    # Custom cover page: replace the built-in OGC cover with our generated image.
    # The image file (cover.png) is written by generate(); this just references it.
    if m and m.cover and m.cover.logo:
        lines.append(":coverpage-image: cover.png")
        lines.append(":presentation-metadata-full-coverpage-replacement: true")
    # Copyright holder → also sets the PDF footer org name (replaces OGC default).
    if m and m.copyright_holder:
        lines.append(f":copyright-holder: {m.copyright_holder}")
    # PDF font family overrides (e.g. DGIWG house font 'Source Sans Pro').
    if m and m.body_font:
        lines.append(f":body-font: {m.body_font}")
    if m and m.header_font:
        lines.append(f":header-font: {m.header_font}")
    if m and m.monospace_font:
        lines.append(f":monospace-font: {m.monospace_font}")
    # Custom legal boilerplate (page ii). The XML file is written by generate().
    if m and m.boilerplate:
        lines.append(":boilerplate-authority: boilerplate.xml")
    # Consolidated PDF stylesheet override: logo suppression, crossing lines,
    # section-number circles, title underlines. The file is written by generate().
    if _pdf_override_flags(m):
        lines.append(f":pdf-stylesheet-override: {_PDF_OVERRIDE_FILENAME}")
    lines += [
        ":mn-document-class: ogc",
        ":mn-output-extensions: xml,html,pdf",
        ":local-cache-only:",
        "",
        "include::sections/00-abstract.adoc[]",
        "",
        "include::sections/01-preface.adoc[]",
        "",
        "include::sections/02-scope.adoc[]",
        "",
        "include::sections/03-conformance.adoc[]",
        "",
        "include::sections/04-references.adoc[]",
        "",
        "include::sections/05-terms.adoc[]",
        "",
        "include::sections/06-requirements.adoc[]",
        "",
        "include::sections/07-abstract-tests.adoc[]",
    ]
    return "\n".join(lines) + "\n"


def _terms_adoc(profile: ServiceProfile) -> str:
    """Render profile-supplied terms as Metanorma term clauses, or empty string."""
    m = profile.document_metadata
    terms = getattr(m, "terms", None) if m else None
    if not terms:
        return ""
    out = ["\n"]
    for t in terms:
        out.append(f"=== {t.term}\n\n{t.definition}\n")
        if t.source:
            out.append(f"\n_{t.source}_\n")
        out.append("\n")
    return "".join(out)


def _build_sections(profile: ServiceProfile) -> dict[str, str]:
    """Return the minimal boilerplate sections required by Metanorma OGC."""
    m = profile.document_metadata
    conf_uris = [profile.conf_uri]
    req_includes = "\n".join(
        f"include::../requirements/core/REQ_{r.id}.adoc[]" for r in profile.requirements
    )
    ats_includes = "\n".join(
        f"include::../abstract_tests/core/ATS_{t.id}.adoc[]" for t in profile.abstract_tests
    )

    # --- Submitters table rows (page iv) ---
    # Prefer the structured `submitters` list (each with its own affiliation).
    # Fall back to pairing editors with the first submitting org.
    if m and m.submitters:
        submitter_rows = "\n".join(
            f"| {s.name}{f' _({s.role})_' if s.role else ''} |{s.affiliation or ''}"
            for s in m.submitters
        )
    else:
        fallback_org = (m.submitting_orgs[0] if m and m.submitting_orgs else "")
        submitter_rows = "\n".join(
            f"| {editor} _(editor)_ |{fallback_org}"
            for editor in (m.editors if m and m.editors else ["Unknown"])
        )

    # --- Notice paragraph (front matter) ---
    notice_block = ""
    if m and m.notice:
        notice_block = (
            "\n[NOTE]\n"
            "====\n"
            f"{m.notice}\n"
            "====\n"
        )

    # --- References: base OGC refs + any profile-supplied normative references ---
    reference_lines = [
        "* [[[OGC-EDR-1,OGC 19-086r6]]], OGC API - Environmental Data Retrieval Standard",
        "* [[[OGC-EDR-3,nofetch(OGC ogcapi-edr-3)]]], OGC API - EDR Part 3: Service Profiles (draft)",
    ]
    if m and m.normative_references:
        for ref in m.normative_references:
            reference_lines.append(f"* [[[{ref.anchor},{ref.citation}]]], {ref.title}")

    # --- Classification banner (e.g. NATO RESTRICTED) ---
    classification_banner = ""
    if profile.classification:
        cl = profile.classification
        label = cl.level + (f" ({cl.system})" if cl.system else "")
        classification_banner = f"*SECURITY CLASSIFICATION: {label}*\n\n"

    # --- Point of contact paragraph (from provider) ---
    contact_block = ""
    if profile.provider:
        pv = profile.provider
        parts_ = [f"This service is provided by {pv.name}"]
        if pv.url:
            parts_.append(f" ({pv.url})")
        parts_.append(".")
        if pv.contact:
            c = pv.contact
            details = []
            if c.email:
                details.append(f"Email: {c.email}")
            if c.phone:
                details.append(f"Phone: {c.phone}")
            addr = ", ".join(
                x for x in (c.address, c.postalcode, c.city, c.country) if x
            )
            if addr:
                details.append(f"Address: {addr}")
            if c.hours:
                details.append(f"Hours: {c.hours}")
            if c.instructions:
                details.append(f"Contact instructions: {c.instructions}")
            if details:
                parts_.append(" " + " +\n".join(details))
        contact_block = (
            "\n[.preface]\n== Point of Contact\n\n"
            + "".join(parts_) + "\n"
        )

    return {
        "sections/00-abstract.adoc": (
            "[abstract]\n== Abstract\n\n"
            + classification_banner
            + f"This document defines the {profile.title}, "
            "an OGC API - Environmental Data Retrieval (EDR) Part 3 Service Profile. "
            "It specifies normative requirements and conformance tests for server implementations "
            f"conforming to this profile.\n"
            "\n"
            "[.preface]\n== Submitters\n\n"
            "All questions regarding this document should be directed to the editor or the submitters:\n\n"
            "[%unnumbered]\n"
            ".Submitters\n"
            "|===\n"
            "h|Name h|Affiliation\n\n"
            + submitter_rows
            + "\n|===\n"
        ),
        "sections/01-preface.adoc": (
            "[.preface]\n== Preface\n\n"
            f"This document was prepared by {', '.join(m.submitting_orgs) if m and m.submitting_orgs else 'the submitting organizations'}.\n"
            + notice_block
            + contact_block
        ),
        "sections/02-scope.adoc": (
            "== Scope\n\n"
            f"This standard defines the {profile.title}. "
            "It specifies requirements and conformance tests for implementations of this profile.\n"
        ),
        "sections/03-conformance.adoc": (
            "== Conformance\n\n"
            "Conformance with this standard shall be checked using the Abstract Test Suite in Annex A.\n\n"
            "The following conformance classes are defined:\n\n"
            + "\n".join(f"* {u}" for u in conf_uris) + "\n"
        ),
        "sections/04-references.adoc": (
            "[bibliography]\n== References\n\n"
            + "\n".join(reference_lines) + "\n"
        ),
        "sections/05-terms.adoc": (
            "== Terms, Definitions and Abbreviated Terms\n\n"
            "This document uses the terms defined in https://portal.ogc.org/public_ogc/directives/directives.php[OGC Policy Directive 49], "
            "which is based on the ISO/IEC Directives, Part 2, Rules for the structure and drafting of International Standards. "
            "In particular, the word \"shall\" (not \"must\") is the verb form used to indicate a requirement to be strictly followed to conform to this standard.\n\n"
            "This document also uses terms defined in OGC API - EDR Part 1: Core.\n"
            + _terms_adoc(profile)
        ),
        "sections/06-requirements.adoc": (
            "== Requirements\n\n"
            "include::../requirements/requirements_class_core.adoc[]\n\n"
            + req_includes + "\n"
        ),
        "sections/07-abstract-tests.adoc": (
            "[appendix,obligation=normative]\n== Abstract Test Suite\n\n"
            "include::../abstract_tests/ATS_class_core.adoc[]\n\n"
            + ats_includes + "\n"
        ),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def generate(profile: ServiceProfile, output_dir: Path) -> None:
    """Write all profile artifacts to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve output_dir to an absolute path to prevent traversal
    output_dir = output_dir.resolve()

    def safe_write(relative: str, content: str) -> None:
        target = (output_dir / relative).resolve()
        if not str(target).startswith(str(output_dir)):
            raise ValueError(f"Refusing to write outside output directory: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    # OpenAPI — use Dumper with anchor suppression so the output is plain YAML
    # without &id002 / *id002 aliases that confuse some OpenAPI tooling.
    safe_write("openapi.yaml", yaml.dump(
        build_openapi(profile),
        sort_keys=False,
        allow_unicode=True,
        Dumper=_NoAliasDumper,
    ))

    # AsyncAPI (optional)
    if profile.pubsub:
        safe_write("asyncapi.yaml", yaml.dump(build_asyncapi(profile), sort_keys=False, allow_unicode=True))

    # Requirements class
    safe_write("requirements/requirements_class_core.adoc", _req_adoc(profile))

    # Individual requirements
    for req in profile.requirements:
        safe_write(f"requirements/core/REQ_{req.id}.adoc", _individual_req_adoc(profile, req.id))

    # Conformance class
    safe_write("abstract_tests/ATS_class_core.adoc", _conf_adoc(profile))

    # Individual abstract tests
    for test in profile.abstract_tests:
        safe_write(f"abstract_tests/core/ATS_{test.id}.adoc", _individual_test_adoc(profile, test.id))

    # Profile config (round-trip)
    safe_write(
        "profile_config.json",
        profile.model_dump_json(indent=2),
    )

    # Metanorma document (always written — needed for --pdf)
    safe_write("document.adoc", _build_document_adoc(profile))
    for path, content in _build_sections(profile).items():
        safe_write(path, content)

    # Custom cover-page image (only when document_metadata.cover.logo is set).
    m = profile.document_metadata
    if m and m.cover and m.cover.logo:
        from oapi_profile_builder.cover import build_cover_image
        cover_file = build_cover_image(profile, output_dir)
        if cover_file:
            print(f"Custom cover page written to {output_dir / cover_file}")

    # Custom legal boilerplate (page ii), replacing the flavor's built-in text.
    boilerplate_xml = _build_boilerplate_xml(profile)
    if boilerplate_xml:
        safe_write("boilerplate.xml", boilerplate_xml)

    # Consolidated PDF stylesheet override (logo, crossing lines, section-number
    # circles, title underlines) — written when any override flag is set.
    pdf_override_xsl = _build_pdf_override_xsl(m)
    if pdf_override_xsl:
        safe_write(_PDF_OVERRIDE_FILENAME, pdf_override_xsl)

    print(f"Profile '{profile.name}' written to {output_dir}")
