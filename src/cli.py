"""
CLI entry point.

Usage:
    python cli.py --config water_gauge.yaml --output ./water_gauge_profile
    python cli.py --config water_gauge.json --output ./water_gauge_profile
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from generate import generate
from models import ServiceProfile


def load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="OGC API - EDR Part 3 Service Profile Generator")
    parser.add_argument("--config", required=True, type=Path, help="Path to profile YAML or JSON config")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    args = parser.parse_args()

    if not args.config.exists():
        print(f"Error: config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    raw = load_config(args.config)

    try:
        profile = ServiceProfile.model_validate(raw)
    except ValidationError as exc:
        print("Profile validation failed:\n", exc, file=sys.stderr)
        sys.exit(1)

    generate(profile, args.output)


if __name__ == "__main__":
    main()
