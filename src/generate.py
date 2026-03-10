"""
Serialization layer: ServiceProfile → files on disk.

All output is derived from the validated Pydantic model. No raw user input
reaches the filesystem — the model acts as the sanitization boundary.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from edr_pydantic.collections import Collection
from models import ServiceProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Keyed by the DataQueries field name (== EDR query type name)
_QUERY_PARAMS: dict[str, list[dict]] = {
    "items": [
        {"name": "bbox", "in": "query", "schema": {"type": "string"}},
        {"name": "datetime", "in": "query", "schema": {"type": "string"}},
    ],
    "position": [
        {"name": "coords", "in": "query", "required": True, "schema": {"type": "string"}},
        {"name": "datetime", "in": "query", "schema": {"type": "string"}},
    ],
    "area": [
        {"name": "coords", "in": "query", "required": True, "schema": {"type": "string"}},
        {"name": "datetime", "in": "query", "schema": {"type": "string"}},
    ],
    "radius": [
        {"name": "coords", "in": "query", "required": True, "schema": {"type": "string"}},
        {"name": "within", "in": "query", "required": True, "schema": {"type": "number"}},
        {"name": "within-units", "in": "query", "required": True, "schema": {"type": "string"}},
    ],
    "cube": [
        {"name": "bbox", "in": "query", "required": True, "schema": {"type": "string"}},
        {"name": "datetime", "in": "query", "schema": {"type": "string"}},
        {"name": "z", "in": "query", "schema": {"type": "string"}},
    ],
    "trajectory": [
        {"name": "coords", "in": "query", "required": True, "schema": {"type": "string"}},
        {"name": "datetime", "in": "query", "schema": {"type": "string"}},
    ],
    "corridor": [
        {"name": "coords", "in": "query", "required": True, "schema": {"type": "string"}},
        {"name": "corridor-width", "in": "query", "required": True, "schema": {"type": "number"}},
        {"name": "corridor-height", "in": "query", "schema": {"type": "number"}},
    ],
    "locations": [
        {"name": "datetime", "in": "query", "schema": {"type": "string"}},
    ],
    "instances": [],
}


def _collection_paths(coll: Collection) -> dict:
    paths: dict = {}
    base = f"/collections/{coll.id}"

    paths[base] = {"get": {
        "summary": f"Get {coll.id} collection metadata",
        "operationId": f"get_{coll.id}_collection",
        "responses": {"200": {"description": "Collection metadata"}},
    }}

    if not coll.data_queries:
        return paths

    # Derive active query types from the edr-pydantic DataQueries model fields
    active = {name for name, val in coll.data_queries if val is not None}

    for qt in active:
        params = _QUERY_PARAMS.get(qt, [])
        if qt == "items":
            paths[f"{base}/items"] = {"get": {
                "summary": f"Query {coll.id} items",
                "operationId": f"get_{coll.id}_items",
                "parameters": params,
                "responses": {"200": {"description": "GeoJSON FeatureCollection"}},
            }}
            paths[f"{base}/items/{{featureId}}"] = {"get": {
                "summary": f"Get {coll.id} item by ID",
                "operationId": f"get_{coll.id}_item",
                "parameters": [{"name": "featureId", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {"200": {"description": "GeoJSON Feature"}},
            }}
        elif qt == "locations":
            paths[f"{base}/locations"] = {"get": {
                "summary": f"List available locations for {coll.id}",
                "operationId": f"get_{coll.id}_locations",
                "responses": {"200": {"description": "GeoJSON FeatureCollection of locations"}},
            }}
            paths[f"{base}/locations/{{locationId}}"] = {"get": {
                "summary": f"Query {coll.id} by location",
                "operationId": f"get_{coll.id}_location",
                "parameters": [
                    {"name": "locationId", "in": "path", "required": True, "schema": {"type": "string"}},
                    *params,
                ],
                "responses": {"200": {"description": "Query results"}},
            }}
        else:
            paths[f"{base}/{qt}"] = {"get": {
                "summary": f"Query {coll.id} by {qt}",
                "operationId": f"get_{coll.id}_{qt}",
                "parameters": params,
                "responses": {"200": {"description": "Query results"}},
            }}

    return paths


# ---------------------------------------------------------------------------
# OpenAPI
# ---------------------------------------------------------------------------

def build_openapi(profile: ServiceProfile) -> dict:
    paths: dict = {}
    for coll in profile.collections:
        paths.update(_collection_paths(coll))

    return {
        "openapi": "3.0.3",
        "info": {
            "title": f"{profile.title} API",
            "version": profile.version,
            "description": f"OGC API - EDR Part 3 Service Profile: {profile.title}",
            "x-ogc-profile": profile.req_uri,
        },
        "paths": paths,
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
