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
CLI entry point.

Usage:
    ogc-edr-profile generate --config water_gauge.yaml --output ./my_profile
    ogc-edr-profile validate --config water_gauge.yaml
    ogc-edr-profile schema --output ./profile.schema.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from ogc_edr_profile.generate import generate, build_openapi
from ogc_edr_profile.models import ServiceProfile


def _parse_datetimes(obj, _in_examples: bool = False):
    """Recursively convert ISO 8601 datetime strings to datetime objects for edr-pydantic."""
    from datetime import datetime
    import re
    ISO_RE = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})$')
    if isinstance(obj, dict):
        return {
            k: _parse_datetimes(v, _in_examples=_in_examples or k == "collection_examples")
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_parse_datetimes(v, _in_examples=_in_examples) for v in obj]
    if not _in_examples and isinstance(obj, str) and ISO_RE.match(obj):
        return datetime.fromisoformat(obj.replace('Z', '+00:00'))
    return obj


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        return _parse_datetimes(yaml.safe_load(text))
    return _parse_datetimes(json.loads(text))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="OGC API - EDR Part 3 Service Profile Generator")
    sub = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = sub.add_parser("generate", help="Validate a profile config and generate all artifacts")
    gen.add_argument("--config", required=True, type=Path, help="Profile YAML or JSON config")
    gen.add_argument("--output", required=True, type=Path, help="Output directory")

    # validate
    val = sub.add_parser("validate", help="Validate a profile config without generating output")
    val.add_argument("--config", required=True, type=Path, help="Profile YAML or JSON config")

    # schema
    sch = sub.add_parser("schema", help="Export the ServiceProfile JSON Schema")
    sch.add_argument("--output", type=Path, default=None, help="Write schema to file (default: stdout)")

    # validate-server
    vs = sub.add_parser("validate-server", help="Validate a live server against the profile OpenAPI")
    vs_src = vs.add_mutually_exclusive_group(required=True)
    vs_src.add_argument("--config", type=Path, help="Profile YAML or JSON config (builds OpenAPI in-memory)")
    vs_src.add_argument("--openapi", type=Path, help="Pre-built OpenAPI YAML file")
    vs.add_argument("--url", required=True, help="Base URL of the live server")
    vs.add_argument("--checks", default="not_a_server_error",
                    help="Comma-separated checks: not_a_server_error, response_schema_conformance, "
                         "content_type_conformance, status_code_conformance (default: not_a_server_error)")
    vs.add_argument("--max-examples", type=int, default=10, dest="max_examples",
                    help="Schemathesis examples per endpoint (default: 10)")
    vs.add_argument("--workers", type=int, default=1, help="Parallel workers (default: 1)")
    vs.add_argument("--exclude-paths", default=None, dest="exclude_paths",
                    help="Regex pattern for paths to skip (e.g. 'instances/{instanceId}')")
    vs.add_argument("--stateful", action="store_true", default=False,
                    help="Enable stateful testing (POST /execution → GET /jobs/{jobId})")

    args = parser.parse_args()

    if args.command == "schema":
        schema = json.dumps(ServiceProfile.model_json_schema(), indent=2)
        if args.output:
            args.output.write_text(schema, encoding="utf-8")
            print(f"Schema written to {args.output}")
        else:
            print(schema)
        return

    if args.command == "validate-server":
        _run_validate_server(args)
        return

    if not args.config.exists():
        print(f"Error: config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    raw = load_config(args.config)

    try:
        profile = ServiceProfile.model_validate(raw)
    except ValidationError as exc:
        print("Profile validation failed:\n", exc, file=sys.stderr)
        sys.exit(1)

    if args.command == "validate":
        print(f"Profile '{profile.name}' is valid.")
        return

    generate(profile, args.output)


def _run_validate_server(args) -> None:
    import re
    from ogc_edr_profile.server_validation import validate_server

    if args.openapi:
        import yaml
        spec = yaml.safe_load(args.openapi.read_text(encoding="utf-8"))
    else:
        if not args.config.exists():
            print(f"Error: config file not found: {args.config}", file=sys.stderr)
            sys.exit(1)
        raw = load_config(args.config)
        try:
            profile = ServiceProfile.model_validate(raw)
        except Exception as exc:
            print(f"Profile validation failed:\n{exc}", file=sys.stderr)
            sys.exit(1)
        spec = build_openapi(profile)

    exclude_pattern = re.compile(args.exclude_paths) if args.exclude_paths else None
    checks = [c.strip() for c in args.checks.split(",")]

    print(f"Validating server: {args.url}")
    print(f"Checks: {', '.join(checks)}")
    print(f"Max examples: {args.max_examples}  Workers: {args.workers}\n")

    ok = validate_server(
        spec=spec,
        url=args.url,
        checks=checks,
        max_examples=args.max_examples,
        workers=args.workers,
        exclude_pattern=exclude_pattern,
        stateful=args.stateful,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
