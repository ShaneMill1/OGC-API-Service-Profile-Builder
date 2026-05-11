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
def _landing_page_schema(profile_uri: str) -> dict:
    return {
        "description": "Landing page",
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "required": ["links"],
                    "properties": {
                        "links": {
                            "type": "array",
                            "items": _LINK_SCHEMA,
                            "contains": {
                                "type": "object",
                                "required": ["href", "rel"],
                                "properties": {
                                    "rel": {"const": "profile"},
                                    "href": {"const": profile_uri}
                                }
                            }
                        }
                    }
                }
            }
        }
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
    crs_schema: dict = {"type": "string"}
    trs_schema: dict = {"type": "string"}
    vrs_schema: dict = {"type": "string"}

    if profile and profile.extent_requirements:
        er = profile.extent_requirements
        if er.allowed_crs:
            crs_schema["enum"] = er.allowed_crs
        elif er.crs_pattern:
            crs_schema["pattern"] = er.crs_pattern
        if er.allowed_trs:
            trs_schema["enum"] = er.allowed_trs
        elif er.trs_pattern:
            trs_schema["pattern"] = er.trs_pattern
        if er.allowed_vrs:
            vrs_schema["enum"] = er.allowed_vrs
        elif er.vrs_pattern:
            vrs_schema["pattern"] = er.vrs_pattern

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

    # Build crs array schema — use collection-level crs list if present
    crs_array_schema: dict = {"type": "array", "items": crs_schema}
    if coll.crs:
        # Collection declares its supported CRS list explicitly
        crs_array_schema["items"] = {"type": "string", "enum": list(coll.crs)}

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
                                    "items": {"type": "string", "format": "date-time"},
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
                                        "crs_details": {
                                            "type": "array",
                                            "description": "CRS values supported by this data query",
                                            "items": {
                                                "type": "object",
                                                "required": ["crs"],
                                                "properties": {
                                                    "crs": crs_schema,
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


def _collection_paths(coll: Collection, examples: dict | None = None,
                      profile: ServiceProfile | None = None) -> dict:
    paths: dict = {}
    base = f"/collections/{coll.id}"
    tag = coll.id
    desc = getattr(coll, "description", None) or coll.id

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

    active = {name for name, val in coll.data_queries if val is not None}

    for qt in active:
        params = _QUERY_PARAMS.get(qt, [])

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
            # instance-level query sub-paths
            for sub_qt in (active - {"instances"}):
                sub_params = _QUERY_PARAMS.get(sub_qt, [])
                paths[f"{base}/instances/{{instanceId}}/{sub_qt}"] = {"get": {
                    "summary": f"query {coll.id} instance by {sub_qt}",
                    "description": desc,
                    "operationId": _operation_id("query", sub_qt, "Instance", coll.id),
                    "tags": [tag],
                    "parameters": [instance_id_param, *sub_params],
                    "responses": cov_resp,
                }}

        elif qt == "items":
            paths[f"{base}/items"] = {"get": {
                "summary": f"query {coll.id} by items",
                "description": desc,
                "operationId": _operation_id("queryItems", coll.id),
                "tags": [tag],
                "parameters": params,
                "responses": cov_resp,
            }}

        elif qt == "locations":
            paths[f"{base}/locations"] = {"get": {
                "summary": f"Get pre-defined locations of {coll.id}",
                "description": desc,
                "operationId": _operation_id("getLocations", coll.id),
                "tags": [tag],
                "parameters": params,
                "responses": {
                    "200": _R200_FEATURES,
                    "400": _ERR_400, "500": _ERR_500,
                },
            }}
            paths[f"{base}/locations/{{locId}}"] = {"get": {
                "summary": f"query {coll.id} by location",
                "description": desc,
                "operationId": _operation_id("getLocation", coll.id),
                "tags": [tag],
                "parameters": [
                    {"$ref": f"{_EDR}/parameters/locationId.yaml"},
                    _DATETIME, _PARAM_NAME, _F,
                ],
                "responses": cov_resp,
            }}

        else:
            paths[f"{base}/{qt}"] = {"get": {
                "summary": f"query {coll.id} by {qt}",
                "description": desc,
                "operationId": _operation_id("query", qt, coll.id),
                "tags": [tag],
                "parameters": params,
                "responses": cov_resp,
            }}

    return paths


def _core_paths(profile: ServiceProfile) -> dict:
    landing_response = _landing_page_schema(profile.req_uri)
    
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
    f_enum = ["json", "html"]
    for fmt in profile.output_formats:
        if fmt.media_type not in f_enum:
            f_enum.append(fmt.media_type)

    # Build contact from document_metadata if available
    m = profile.document_metadata
    contact: dict = {}
    if m and m.editors:
        contact["name"] = m.editors[0]
    if m and m.submitting_orgs:
        contact["x-organization"] = m.submitting_orgs[0]
    # Fall back to a generic contact if nothing is specified
    if not contact:
        contact["name"] = profile.title

    return {
        "openapi": "3.1.0",
        "info": {
            "title": profile.title,
            "version": profile.version,
            "description": f"OGC API - EDR Part 3 Service Profile: {profile.title}",
            "x-ogc-profile": profile.req_uri,
            "contact": contact,
        },
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

def _build_document_adoc(profile: ServiceProfile) -> str:
    m = profile.document_metadata
    year = m.copyright_year if m else 2026
    # draft-standard is the correct OGC doctype for in-progress profiles
    doctype = "draft-standard"
    # profile is not a valid OGC subtype; implementation is the closest for a service profile
    docsubtype = "implementation" if not m or m.doc_subtype == "profile" else m.doc_subtype
    lines = [
        f"= {profile.title}",
        f":doctype: {doctype}",
        f":docsubtype: {docsubtype}",
        f":edition: {profile.version}",
        ":language: en",
        ":committee: technical",
        f":docnumber: {m.doc_number if m else profile.name}",
        f":copyright-year: {year}",
        f":published-date: {year}-01-01",
        f":issued-date: {year}-01-01",
        f":received-date: {year}-01-01",
    ]
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


def _build_sections(profile: ServiceProfile) -> dict[str, str]:
    """Return the minimal boilerplate sections required by Metanorma OGC."""
    m = profile.document_metadata
    conf_uris = [f"http://www.opengis.net/spec/ogcapi-edr-3/1.0/conf/{profile.name}"]
    submitters = m.submitting_orgs if m and m.submitting_orgs else ["Unknown"]
    req_includes = "\n".join(
        f"include::../requirements/core/REQ_{r.id}.adoc[]" for r in profile.requirements
    )
    ats_includes = "\n".join(
        f"include::../abstract_tests/core/ATS_{t.id}.adoc[]" for t in profile.abstract_tests
    )
    return {
        "sections/00-abstract.adoc": (
            "[abstract]\n== Abstract\n\n"
            f"This document defines the {profile.title}, "
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
            + "\n".join(
                f"| {editor} _(editor)_ |{submitters[0] if submitters else ''}"
                for editor in (m.editors if m and m.editors else ["Unknown"])
            )
            + "\n|===\n"
        ),
        "sections/01-preface.adoc": (
            "[.preface]\n== Preface\n\n"
            f"This document was prepared by {', '.join(m.submitting_orgs) if m and m.submitting_orgs else 'the submitting organizations'}.\n"
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
            "* [[[OGC-EDR-1,OGC 19-086r6]]], OGC API - Environmental Data Retrieval Standard\n"
            "* [[[OGC-EDR-3,nofetch(OGC ogcapi-edr-3)]]], OGC API - EDR Part 3: Service Profiles (draft)\n"
        ),
        "sections/05-terms.adoc": (
            "== Terms, Definitions and Abbreviated Terms\n\n"
            "This document uses the terms defined in https://portal.ogc.org/public_ogc/directives/directives.php[OGC Policy Directive 49], "
            "which is based on the ISO/IEC Directives, Part 2, Rules for the structure and drafting of International Standards. "
            "In particular, the word \"shall\" (not \"must\") is the verb form used to indicate a requirement to be strictly followed to conform to this standard.\n\n"
            "This document also uses terms defined in OGC API - EDR Part 1: Core.\n"
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

    print(f"Profile '{profile.name}' written to {output_dir}")
