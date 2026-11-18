#
# Authors: Shane Mill <shane.mill@noaa.gov>
#
# Copyright (c) 2026 Shane Mill
#
# Licensed under the Apache License, Version 2.0 (see LICENSE).
#
# =================================================================
"""
Per-query OpenAPI building blocks driven by the profile YAML.

Everything a client sees for one EDR query (its parameters, the `f` choices,
the response media types and shapes, the HTTP status codes and the POST body)
is derived here from what the collection and query actually declare, so each
endpoint reflects its own configuration rather than profile-wide defaults.
"""

from __future__ import annotations

import copy

EDR = "https://schemas.opengis.net/ogcapi/edr/1.0/openapi"
FEATURES = "https://schemas.opengis.net/ogcapi/features/part1/1.0/openapi/ogcapi-features-1.yaml"
PROBLEM_MEDIA_TYPE = "application/problem+json"

# Media types used when a format is not declared in profile.output_formats.
DEFAULT_MEDIA_TYPES = {
    "GeoJSON": "application/geo+json",
    "CoverageJSON": "application/prs.coverage+json",
    "NetCDF": "application/netcdf",
    "GeoTIFF": "image/tiff; application=geotiff",
    "GRIB": "application/grib",
    "HTML": "text/html",
    "JSON": "application/json",
}
_BINARY = ("netcdf", "tiff", "grib", "octet-stream", "zip")

# Status codes documented when the profile does not configure http_responses.
DEFAULT_DATA_CODES = {
    "204": {"description": "No data available for the requested query (empty result inside the extent)"},
    "400": {"description": "Invalid or missing parameter"},
    "500": {"description": "Server error"},
}
DEFAULT_METADATA_CODES = {
    "400": {"description": "Invalid or missing parameter"},
    "404": {"description": "Not found"},
    "500": {"description": "Server error"},
}

PROBLEM_SCHEMA = {
    "type": "object",
    "description": "RFC 9457 problem details",
    "properties": {
        "type": {"type": "string", "format": "uri-reference", "default": "about:blank"},
        "title": {"type": "string"},
        "status": {"type": "integer"},
        "detail": {"type": "string"},
        "instance": {"type": "string", "format": "uri-reference"},
    },
}

# Fixed (required) parameters per query, always generated.
_REQUIRED = {
    "position": [{"$ref": f"{EDR}/parameters/positionCoords.yaml"}],
    "area": [{"$ref": f"{EDR}/parameters/areaCoords.yaml"}],
    "radius": [{"$ref": f"{EDR}/parameters/positionCoords.yaml"}, {"$ref": f"{EDR}/parameters/within.yaml"}],
    "cube": [{"$ref": f"{EDR}/parameters/bbox.yaml"}],
    "trajectory": [{"name": "coords", "in": "query", "required": True,
                    "description": "WKT LineString geometry", "schema": {"type": "string"}}],
    "corridor": [
        {"name": "coords", "in": "query", "required": True, "description": "WKT LineString geometry", "schema": {"type": "string"}},
        {"name": "corridor-width", "in": "query", "required": True, "description": "Width of the corridor", "schema": {"type": "number"}},
        {"name": "corridor-height", "in": "query", "description": "Height of the corridor", "schema": {"type": "number"}},
    ],
    "items": [],
    "locations": [],
}
# Default optional parameters (in order) when query_options.parameters is not set.
_DEFAULT_OPTIONAL = {
    "position": ["datetime", "parameter-name", "crs", "z"],
    "area": ["datetime", "parameter-name", "crs", "z"],
    "radius": ["datetime", "parameter-name", "crs", "z"],
    "cube": ["datetime", "parameter-name", "crs", "z"],
    "trajectory": ["datetime", "parameter-name", "crs", "z"],
    "corridor": ["datetime"],
    "items": ["bbox", "datetime", "parameter-name", "crs", "z"],
    "locations": ["bbox", "datetime"],
}
# Order parameters appear in, whatever order the YAML lists them.
_ORDER = ["bbox", "datetime", "parameter-name", "crs", "z", "resolution-x", "resolution-y", "resolution-z"]


# ---------------------------------------------------------------------------
# Formats
# ---------------------------------------------------------------------------

def media_type(profile, name: str) -> str:
    for fmt in (profile.output_formats if profile else []):
        if fmt.name == name:
            return fmt.media_type
    return DEFAULT_MEDIA_TYPES.get(name, name)


def schema_ref(profile, name: str) -> str | None:
    for fmt in (profile.output_formats if profile else []):
        if fmt.name == name:
            return fmt.schema_ref
    return None


def query_formats(profile, coll, variables) -> list[str]:
    """The formats a query returns: query > collection > profile output formats."""
    fmts = list(getattr(variables, "output_formats", None) or [])
    if not fmts:
        fmts = list(coll.output_formats or [])
    if not fmts and profile:
        fmts = [f.name for f in profile.output_formats]
    return fmts or ["CoverageJSON"]


def default_format(variables, formats: list[str]) -> str | None:
    """Declared default_output_format, or the only format when there is just one."""
    val = getattr(variables, "default_output_format", None) if variables is not None else None
    if val is None and variables is not None:
        val = (getattr(variables, "model_extra", None) or {}).get("default_output_format")
    if val:
        return val
    return formats[0] if len(formats) == 1 else None


def f_param(formats: list[str], default: str | None = None, what: str = "data") -> dict:
    """Inline `f` parameter listing exactly these formats (EDR uses format names)."""
    schema = {"type": "string", "enum": list(dict.fromkeys(formats))}
    if default:
        schema["default"] = default
    desc = (
        "The optional f parameter indicates the output format which the server shall "
        f"provide as part of the response document. Formats for this {what}: "
        + ", ".join(schema["enum"]) + "."
    )
    if default:
        desc += f" Default: {default}."
    return {"name": "f", "in": "query", "required": False, "description": desc,
            "schema": schema, "style": "form", "explode": False}


def metadata_formats(coll) -> list[str]:
    """`f` values for a collection's metadata, from the media types of its links."""
    names = []
    for link in (coll.links or []):
        t = (link.type or "").split(";")[0].strip()
        if t == "application/json":
            names.append("json")
        elif t == "text/html":
            names.append("html")
    return list(dict.fromkeys(names)) or ["json", "html"]


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

def _supported_crs(profile, coll) -> list[str]:
    if coll.crs:
        return list(coll.crs)
    er = profile.extent_requirements if profile else None
    if er and er.supported_crs and er.supported_crs.allowed:
        return list(er.supported_crs.allowed)
    return []


def _param_names(coll) -> dict:
    return dict(coll.parameter_names.root) if coll.parameter_names else {}


def _unit_text(param) -> str:
    u = getattr(param, "unit", None)
    if not u:
        return ""
    label = _label(u.label)
    sym = getattr(u, "symbol", None)
    sym_val = getattr(sym, "value", None) if sym is not None and not isinstance(sym, str) else sym
    bits = [b for b in (label and f"unit {label}", sym_val and f"symbol {sym_val}") if b]
    return "; ".join(bits)


def crs_param(profile, coll) -> dict:
    crs = _supported_crs(profile, coll)
    p = {"name": "crs", "in": "query", "required": False,
         "description": "Identifier of the coordinate reference system for the response."
                        + (f" Supported for this collection: {', '.join(crs)}." if crs else ""),
         "schema": {"type": "string"}}
    if crs:
        p["schema"]["enum"] = crs
        p["schema"]["default"] = crs[0]
    return p


def parameter_name_param(coll) -> dict:
    names = _param_names(coll)
    lines = [f"- `{pid}`" + (f" ({_unit_text(p)})" if _unit_text(p) else "") for pid, p in names.items()]
    desc = "Comma-separated list of parameters to retrieve."
    if lines:
        desc += " Parameters of this collection:\n" + "\n".join(lines)
    items = {"type": "string"}
    if names:
        items["enum"] = list(names)
    return {"name": "parameter-name", "in": "query", "required": False, "description": desc,
            "style": "form", "explode": False, "schema": {"type": "array", "items": items}}


def within_units_param(variables) -> dict:
    units = list(getattr(variables, "within_units", None) or [])
    if not units and variables is not None:
        units = list((getattr(variables, "model_extra", None) or {}).get("within_units") or [])
    schema = {"type": "string"}
    if units:
        schema["enum"] = units
        schema["default"] = units[0]
    return {"name": "within-units", "in": "query", "required": True,
            "description": "Units of the within distance" + (f": {', '.join(units)}." if units else " (e.g. km)."),
            "schema": schema}


def items_bbox_param() -> dict:
    return {"name": "bbox", "in": "query", "required": False, "style": "form", "explode": False,
            "description": "Only features that intersect the bounding box are selected: "
                           "minLon,minLat,maxLon,maxLat (optionally with min/max height).",
            "schema": {"type": "array", "minItems": 4, "maxItems": 6, "items": {"type": "number"}}}


def resolution_param(axis: str) -> dict:
    return {"name": f"resolution-{axis}", "in": "query", "required": False,
            "description": f"Number of positions to return along the {axis} axis of the cube "
                           "(the server interpolates to that resolution).",
            "schema": {"type": "integer", "minimum": 1}}


def optional_parameter_names(qt: str, coll, opts) -> list[str]:
    if opts is not None and opts.parameters is not None:
        chosen = list(opts.parameters)
    else:
        has_vertical = bool(coll.extent and coll.extent.vertical)
        chosen = [p for p in _DEFAULT_OPTIONAL.get(qt, []) if p != "z" or has_vertical]
    return sorted(dict.fromkeys(chosen), key=lambda p: _ORDER.index(p) if p in _ORDER else 99)


def query_parameters(qt: str, profile, coll, variables, opts, formats, default_fmt) -> list[dict]:
    """GET parameters for one query: required, then the chosen optional ones, then f."""
    params = copy.deepcopy(_REQUIRED.get(qt, []))
    if qt == "radius":
        params.append(within_units_param(variables))
    for name in optional_parameter_names(qt, coll, opts):
        if name == "datetime":
            params.append({"$ref": f"{FEATURES}#/components/parameters/datetime"})
        elif name == "parameter-name":
            params.append(parameter_name_param(coll))
        elif name == "crs":
            params.append(crs_param(profile, coll))
        elif name == "z":
            params.append({"$ref": f"{EDR}/parameters/z.yaml"})
        elif name == "bbox":
            params.append(items_bbox_param() if qt == "items" else {"$ref": f"{EDR}/parameters/bbox.yaml"})
        elif name.startswith("resolution-"):
            params.append(resolution_param(name.split("-")[1]))
    params.append(f_param(formats, default_fmt, "query"))
    return params


# ---------------------------------------------------------------------------
# HTTP status codes
# ---------------------------------------------------------------------------

def status_responses(profile, opts, data: bool) -> dict:
    """Non-200 responses: query override > profile http_responses > built-in defaults."""
    configured = (opts.http_responses if opts is not None and opts.http_responses else None) \
        or (profile.http_responses if profile and profile.http_responses else None)
    if configured is None:
        base = DEFAULT_DATA_CODES if data else DEFAULT_METADATA_CODES
        specs = {code: {"description": d["description"], "title": d["description"], "detail": None,
                        "type": "about:blank"} for code, d in base.items()}
    else:
        specs = {code: s.model_dump() for code, s in configured.items()}
    out = {}
    for code in sorted(specs, key=int):
        if code == "200" or (code == "204" and not data):
            continue
        s = specs[code]
        resp = {"description": s["description"]}
        if int(code) >= 400:
            example = {"type": s.get("type") or "about:blank", "title": s.get("title") or s["description"],
                       "status": int(code)}
            if s.get("detail"):
                example["detail"] = s["detail"]
            resp["content"] = {PROBLEM_MEDIA_TYPE: {"schema": PROBLEM_SCHEMA, "example": example}}
        out[code] = resp
    return out


def ok_description(profile, opts, default: str) -> str:
    configured = (opts.http_responses if opts is not None and opts.http_responses else None) \
        or (profile.http_responses if profile and profile.http_responses else None)
    if configured and "200" in configured:
        return configured["200"].description
    return default


# ---------------------------------------------------------------------------
# Shaped response examples
# ---------------------------------------------------------------------------

def _label(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v
    root = getattr(v, "root", v)
    return root.get("en") if isinstance(root, dict) else str(root)


def _unit_obj(param) -> dict | None:
    u = getattr(param, "unit", None)
    if not u:
        return None
    out = {}
    if u.label is not None:
        out["label"] = _label(u.label)
    sym = getattr(u, "symbol", None)
    if sym is not None:
        out["symbol"] = sym if isinstance(sym, str) else {k: v for k, v in (("value", sym.value), ("type", sym.type)) if v}
    return out or None


def _bbox(coll) -> list | None:
    s = coll.extent.spatial if coll.extent and coll.extent.spatial else None
    return list(s.bbox[0]) if s and s.bbox else None


def _start_time(coll) -> str:
    t = coll.extent.temporal if coll.extent and coll.extent.temporal else None
    if t and t.interval and t.interval[0] and t.interval[0][0]:
        v = t.interval[0][0]
        return v.isoformat().replace("+00:00", "Z") if hasattr(v, "isoformat") else str(v)
    return "2026-01-01T00:00:00Z"


def _sample_point(coll) -> list:
    b = _bbox(coll)
    if b and len(b) >= 4:
        return [round((b[0] + b[2]) / 2, 4), round((b[1] + b[3]) / 2, 4)]
    return [0.0, 0.0]


_GEOM_COORDS = {
    "Point": lambda p: p,
    "MultiPoint": lambda p: [p],
    "LineString": lambda p: [p, [p[0] + 0.1, p[1] + 0.1]],
    "MultiLineString": lambda p: [[p, [p[0] + 0.1, p[1] + 0.1]]],
    "Polygon": lambda p: [[p, [p[0] + 0.1, p[1]], [p[0] + 0.1, p[1] + 0.1], p]],
    "MultiPolygon": lambda p: [[[p, [p[0] + 0.1, p[1]], [p[0] + 0.1, p[1] + 0.1], p]]],
}


def feature_schema(coll, geometry_types: list[str]) -> tuple[dict, dict]:
    """GeoJSON Feature schema + example built from the collection's parameters."""
    props_schema = {"datetime": {"type": "string", "format": "date-time",
                                 "description": "Observation time (RFC 3339)."}}
    props_example = {"datetime": _start_time(coll)}
    for pid, p in _param_names(coll).items():
        unit = _unit_obj(p)
        entry = {"type": "object", "description": _label(getattr(p, "description", None)) or pid,
                 "properties": {"value": {"type": "number"}}}
        ex = {"value": 0.0}
        if unit:
            entry["properties"]["unit"] = {"type": "object", "example": unit}
            ex["unit"] = unit
        props_schema[pid] = entry
        props_example[pid] = ex
    point = _sample_point(coll)
    geom_types = geometry_types or ["Point"]
    schema = {
        "type": "object", "required": ["type", "geometry", "properties"],
        "properties": {
            "type": {"type": "string", "enum": ["Feature"]},
            "id": {"type": "string"},
            "geometry": {"type": "object", "required": ["type", "coordinates"],
                         "properties": {"type": {"type": "string", "enum": geom_types},
                                        "coordinates": {"type": "array"}}},
            "properties": {"type": "object", "properties": props_schema},
        },
    }
    g = geom_types[0]
    example = {"type": "Feature", "id": "1",
               "geometry": {"type": g, "coordinates": _GEOM_COORDS[g](point)},
               "properties": props_example}
    if any(t != "Point" for t in geom_types):
        schema["properties"]["bbox"] = {"type": "array", "items": {"type": "number"}, "minItems": 4}
    return schema, example


def feature_collection_schema(coll, geometry_types, paging_props: dict | None = None) -> tuple[dict, dict]:
    f_schema, f_example = feature_schema(coll, geometry_types)
    props = {"type": {"type": "string", "enum": ["FeatureCollection"]},
             "features": {"type": "array", "items": f_schema},
             "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4}}
    props.update(paging_props or {})
    example = {"type": "FeatureCollection", "features": [f_example]}
    if _bbox(coll):
        example["bbox"] = _bbox(coll)
    return {"type": "object", "required": ["type", "features"], "properties": props}, example


_DOMAIN_TYPE = {"cube": "Grid", "area": "Grid", "position": "PointSeries"}


def coveragejson_schema(coll, qt: str) -> tuple[dict, dict]:
    """CoverageJSON schema + example whose parameters/ranges are the collection's parameters."""
    names = _param_names(coll)
    params_schema, params_ex, ranges_schema, ranges_ex = {}, {}, {}, {}
    for pid, p in names.items():
        unit = _unit_obj(p)
        obs = getattr(p, "observedProperty", None)
        pex = {"type": "Parameter"}
        if getattr(p, "description", None):
            pex["description"] = {"en": _label(p.description)}
        if obs is not None:
            pex["observedProperty"] = {k: v for k, v in (("id", getattr(obs, "id", None)),
                                                         ("label", {"en": _label(obs.label)})) if v}
        if unit:
            pex["unit"] = {"label": {"en": unit.get("label")}, **({"symbol": unit["symbol"]} if "symbol" in unit else {})}
        params_schema[pid] = {"type": "object", "example": pex}
        params_ex[pid] = pex
        ranges_schema[pid] = {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["NdArray"]}, "dataType": {"type": "string"},
            "axisNames": {"type": "array", "items": {"type": "string"}},
            "shape": {"type": "array", "items": {"type": "integer"}},
            "values": {"type": "array", "items": {"type": "number", "nullable": True}}}}
        ranges_ex[pid] = {"type": "NdArray", "dataType": "float", "axisNames": ["t", "y", "x"],
                          "shape": [1, 1, 1], "values": [0.0]}
    x, y = _sample_point(coll)
    domain_type = _DOMAIN_TYPE.get(qt, "Point")
    coverage_ex = {
        "type": "Coverage",
        "domain": {"type": "Domain", "domainType": domain_type,
                   "axes": {"x": {"values": [x]}, "y": {"values": [y]}, "t": {"values": [_start_time(coll)]}},
                   "referencing": [{"coordinates": ["x", "y"],
                                    "system": {"type": "GeographicCRS", "id": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"}}]},
        "parameters": params_ex, "ranges": ranges_ex,
    }
    coverage_schema = {"type": "object", "required": ["type", "domain", "ranges"], "properties": {
        "type": {"type": "string", "enum": ["Coverage"]},
        "domain": {"type": "object"},
        "parameters": {"type": "object", "properties": params_schema},
        "ranges": {"type": "object", "properties": ranges_schema}}}
    if qt in ("radius", "trajectory", "corridor", "locations", "items"):
        return ({"type": "object", "required": ["type", "coverages"], "properties": {
                    "type": {"type": "string", "enum": ["CoverageCollection"]},
                    "parameters": {"type": "object", "properties": params_schema},
                    "coverages": {"type": "array", "items": coverage_schema}}},
                {"type": "CoverageCollection", "parameters": params_ex,
                 "coverages": [{k: v for k, v in coverage_ex.items() if k != "parameters"}]})
    return coverage_schema, coverage_ex


def data_response(profile, coll, qt: str, formats: list[str], opts,
                  single_feature: bool = False, paging_props: dict | None = None) -> dict:
    """The 200 response: one media type per format of this query, shaped by the data."""
    content = {}
    geom = opts.geometry_types if opts is not None else ["Point"]
    for name in formats:
        mt = media_type(profile, name)
        ref = schema_ref(profile, name)
        if name == "GeoJSON" or mt == "application/geo+json":
            schema, example = (feature_schema(coll, geom) if single_feature
                               else feature_collection_schema(coll, geom, paging_props))
        elif name == "CoverageJSON" or "coverage" in mt:
            schema, example = coveragejson_schema(coll, qt)
        elif any(b in mt for b in _BINARY) or mt.startswith(("image/", "audio/", "video/")):
            schema, example = {"type": "string", "format": "binary"}, None
        elif ref and ref.endswith((".json", ".yaml", ".yml")) or (ref and "schema" in ref):
            schema, example = {"$ref": ref}, None
        else:
            # A schema_ref that is a web page (not a JSON schema) is linked, not $ref'd.
            schema, example = {"type": "object"}, None
        if ref and "$ref" not in schema:
            schema = {**schema, "externalDocs": {"description": f"{name} schema", "url": ref}}
        entry = {"schema": schema}
        if example is not None:
            entry["example"] = example
        content[mt] = entry
    noun = "feature" if single_feature else "data"
    label = " / ".join(f"{n} {noun} response" for n in formats)
    configured = ok_description(profile, opts, "")
    desc = f"{configured} ({label})" if configured else label
    return {"description": desc, "content": content}


# ---------------------------------------------------------------------------
# POST request body
# ---------------------------------------------------------------------------

def _param_to_property(p: dict) -> tuple[str, dict] | None:
    """Convert a GET parameter into a request-body property (same name, same schema)."""
    ref = p.get("$ref", "")
    if ref:
        name = {"positionCoords.yaml": "coords", "areaCoords.yaml": "coords", "within.yaml": "within",
                "bbox.yaml": "bbox", "z.yaml": "z"}.get(ref.rsplit("/", 1)[-1])
        if ref.endswith("/datetime"):
            name = "datetime"
        if not name:
            return None
        schema = {
            "coords": {"type": "string", "description": "WKT geometry, e.g. POINT(lon lat)"},
            "within": {"type": "number", "description": "Radius distance"},
            "bbox": {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 6,
                     "description": "Bounding box [minLon, minLat, maxLon, maxLat]"},
            "z": {"type": "string", "description": "Vertical level(s)"},
            "datetime": {"type": "string", "description": "RFC 3339 datetime or interval"},
        }[name]
        return name, schema
    schema = copy.deepcopy(p.get("schema", {"type": "string"}))
    if p.get("description"):
        schema["description"] = p["description"]
    return p["name"], schema


def post_body(params: list[dict], coll, profile, limit_param: dict | None = None) -> dict:
    """Request body mirroring the GET parameters, with a populated example."""
    props, required, example = {}, [], {}
    for p in params + ([limit_param] if limit_param else []):
        conv = _param_to_property(p)
        if not conv:
            continue
        name, schema = conv
        props[name] = schema
        if p.get("required") or (p.get("$ref", "").endswith(("Coords.yaml", "within.yaml"))) or \
                (name == "bbox" and p.get("$ref")):
            required.append(name)
        if "default" in schema:
            example[name] = schema["default"]
        elif name == "coords":
            x, y = _sample_point(coll)
            example[name] = f"POINT({x} {y})"
        elif name == "within":
            example[name] = 10
        elif name == "bbox" and _bbox(coll):
            example[name] = _bbox(coll)
        elif name == "parameter-name" and schema.get("items", {}).get("enum"):
            example[name] = schema["items"]["enum"][:1]
        elif name == "datetime":
            example[name] = f"{_start_time(coll)}/.."
    body = {"type": "object", "properties": props}
    if required:
        body["required"] = required
    return body, example
