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
from ogc_edr_profile.models import ServiceProfile


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

_R200_LANDING = {"description": "Landing page / conformance / collections list", "content": {"application/json": {"schema": {"type": "object", "properties": {"links": _LINKS_ARRAY}}}}}
_R200_COLLECTION = {"description": "Collection metadata", "content": {"application/json": {"schema": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "description": {"type": "string"}, "links": _LINKS_ARRAY}}}}}
_R200_FEATURES = {"description": "Feature collection", "content": {"application/json": {"schema": {"type": "object", "properties": {"instances": {"type": "array", "items": {"type": "object"}}, "features": {"type": "array", "items": {"type": "object"}}}}}}}

_COVERAGE_RESPONSE = {
    "200": {
        "description": "Coverage response",
        "content": {
            "application/prs.coverage+json": {
                "schema": {"$ref": f"{_EDR}/schemas/coverageJSON.yaml"}
            }
        },
    }
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


def _collection_paths(coll: Collection, examples: dict | None = None) -> dict:
    paths: dict = {}
    base = f"/collections/{coll.id}"
    tag = coll.id
    desc = getattr(coll, "description", None) or coll.id

    paths[base] = {"get": {
        "summary": f"Get {coll.title or coll.id} metadata",
        "description": desc,
        "operationId": f"describe{coll.id.title().replace('_', '')}Collection",
        "tags": [tag],
        "parameters": [_F, _LANG],
        "responses": {
            "200": _R200_COLLECTION,
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
                "operationId": f"getInstances{coll.id.title().replace('_', '')}",
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
                "operationId": f"getInstance{coll.id.title().replace('_', '')}",
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
                    "operationId": f"query{sub_qt.title()}Instance{coll.id.title().replace('_', '')}",
                    "tags": [tag],
                    "parameters": [instance_id_param, *sub_params],
                    "responses": _COVERAGE_RESPONSE,
                }}

        elif qt == "items":
            paths[f"{base}/items"] = {"get": {
                "summary": f"query {coll.id} by items",
                "description": desc,
                "operationId": f"queryItems{coll.id.title().replace('_', '')}",
                "tags": [tag],
                "parameters": params,
                "responses": _COVERAGE_RESPONSE,
            }}

        elif qt == "locations":
            paths[f"{base}/locations"] = {"get": {
                "summary": f"Get pre-defined locations of {coll.id}",
                "description": desc,
                "operationId": f"getLocations{coll.id.title().replace('_', '')}",
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
                "operationId": f"getLocation{coll.id.title().replace('_', '')}",
                "tags": [tag],
                "parameters": [
                    {"$ref": f"{_EDR}/parameters/locationId.yaml"},
                    _DATETIME, _PARAM_NAME, _F,
                ],
                "responses": _COVERAGE_RESPONSE,
            }}

        else:
            paths[f"{base}/{qt}"] = {"get": {
                "summary": f"query {coll.id} by {qt}",
                "description": desc,
                "operationId": f"query{qt.title()}{coll.id.title().replace('_', '')}",
                "tags": [tag],
                "parameters": params,
                "responses": _COVERAGE_RESPONSE,
            }}

    return paths


def _core_paths() -> dict:
    return {
        "/": {"get": {
            "summary": "Landing page",
            "description": "Landing page",
            "operationId": "getLandingPage",
            "tags": ["server"],
            "parameters": [_F, _LANG],
            "responses": {"200": _R200_LANDING, "400": _ERR_400, "500": _ERR_500},
        }},
        "/conformance": {"get": {
            "summary": "API conformance definition",
            "description": "API conformance definition",
            "operationId": "getConformanceDeclaration",
            "tags": ["server"],
            "parameters": [_F, _LANG],
            "responses": {"200": _R200_LANDING, "400": _ERR_400, "500": _ERR_500},
        }},
        "/collections": {"get": {
            "summary": "Collections",
            "description": "Collections",
            "operationId": "getCollections",
            "tags": ["server"],
            "parameters": [_F, _LANG],
            "responses": {"200": _R200_LANDING, "400": _ERR_400, "500": _ERR_500},
        }},
        "/openapi": {"get": {
            "summary": "OpenAPI definition",
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
                "200": {"$ref": "#/components/responses/200"},
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
                    "200": {"$ref": "#/components/responses/200"},
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
                    "204": {"$ref": "#/components/responses/204"},
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
                "200": {"$ref": "#/components/responses/200"},
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
            "operationId": f"describe{pid.title().replace('-', '')}Process",
            "tags": [pid],
            "parameters": [_F],
            "responses": {
                "200": {"$ref": "#/components/responses/200"},
                "default": _ERR_DEFAULT,
            },
        }}
        paths[f"/processes/{pid}/execution"] = {"post": {
            "summary": f"Process {ptitle} execution",
            "description": pdesc,
            "operationId": f"execute{pid.title().replace('-', '')}Job",
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
    paths: dict = _core_paths()
    for coll in profile.collections:
        paths.update(_collection_paths(coll, profile.collection_examples.get(coll.id)))
    paths.update(_processes_paths(profile))

    tags = [{"name": "server", "description": profile.title}]
    for coll in profile.collections:
        tags.append({"name": coll.id, "description": getattr(coll, "description", None) or coll.id})
    if profile.processes:
        tags += [{"name": p["id"]} for p in profile.processes]
        tags += [{"name": "jobs"}]

    return {
        "openapi": "3.0.3",
        "info": {
            "title": profile.title,
            "version": profile.version,
            "description": f"OGC API - EDR Part 3 Service Profile: {profile.title}",
            "x-ogc-profile": profile.req_uri,
        },
        "servers": [{"url": profile.server_url, "description": profile.title}] if getattr(profile, "server_url", None) else [],
        "tags": tags,
        "paths": paths,
        "components": {
            "parameters": {
                "f": {
                    "name": "f", "in": "query", "required": False,
                    "description": "The optional f parameter indicates the output format which the server shall provide as part of the response document. The default format is GeoJSON.",
                    "schema": {"type": "string", "default": "json", "enum": ["json", "html", "jsonld"]},
                    "style": "form", "explode": False,
                },
                "lang": {
                    "name": "lang", "in": "query", "required": False,
                    "description": "The optional lang parameter instructs the server return a response in a certain language, if supported.",
                    "schema": {"type": "string", "default": "en-US", "enum": ["en-US"]},
                },
            },
            "responses": {
                "200": {"description": "Successful operation", "content": {"application/json": {"schema": {"type": "object"}}}},
                "204": {"description": "No content"},
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

    for coll in profile.collections:
        ch_key = f"{coll.id}_notifications"
        msg_key = f"{coll.id}Observation"

        channels[ch_key] = {
            "address": f"collections/{coll.id}/items/#",
            "description": f"Real-time notifications for {coll.id}",
            "messages": {msg_key: {"$ref": f"#/components/messages/{msg_key}"}},
            **({"x-ogc-subscription": {
                "filters": [
                    {"name": f.name, "description": f.description, "schema": {"type": f.type.value}}
                    for f in pub.filters
                ]
            }} if pub.filters else {}),
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

    return {
        "asyncapi": "3.0.0",
        "info": {"title": f"{profile.title} AsyncAPI", "version": profile.version},
        "servers": {"production": {
            "host": f"{pub.broker_host}:{pub.broker_port}",
            "protocol": pub.protocol,
        }},
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

    # OpenAPI
    safe_write("openapi.yaml", yaml.dump(build_openapi(profile), sort_keys=False, allow_unicode=True))

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

    print(f"Profile '{profile.name}' written to {output_dir}")
