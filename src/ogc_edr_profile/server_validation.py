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
Server validation: shell out to the schemathesis CLI against a live
server using a generated or pre-built OpenAPI spec.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

# Valid checks in schemathesis v4
VALID_CHECKS = {
    "not_a_server_error",
    "status_code_conformance",
    "content_type_conformance",
    "response_headers_conformance",
    "response_schema_conformance",
    "negative_data_rejection",
    "positive_data_acceptance",
    "missing_required_header",
    "unsupported_method",
    "use_after_free",
    "ensure_resource_availability",
    "ignored_auth",
    "all",
}


def validate_server(
    spec: dict,
    url: str,
    checks: list[str],
    max_examples: int,
    workers: int,
    exclude_pattern: re.Pattern | None,
    stateful: bool = False,
) -> bool:
    """
    Write spec to a temp file and run `schemathesis run` against `url`.
    Returns True if schemathesis exits 0 (all passed), False otherwise.
    """
    if shutil.which("schemathesis") is None:
        print(
            "schemathesis CLI not found. Run: pip install ogc-edr-profile[validate]",
            file=sys.stderr,
        )
        sys.exit(1)

    for check in checks:
        if check not in VALID_CHECKS:
            print(
                f"Unknown check '{check}'. Valid options: {', '.join(sorted(VALID_CHECKS))}",
                file=sys.stderr,
            )
            sys.exit(1)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as tmp:
        yaml.dump(spec, tmp, sort_keys=False, allow_unicode=True)
        tmp_path = Path(tmp.name)

    try:
        phases = "coverage,stateful" if stateful else "coverage"
        cmd = [
            "schemathesis", "run",
            str(tmp_path),
            "--url", url,
            "--checks", ",".join(checks),
            "--workers", str(workers),
            "--phases", phases,
        ]

        if exclude_pattern:
            cmd += ["--exclude-path-regex", exclude_pattern.pattern]

        # Exclude POST /execution and job resource paths unless stateful testing is enabled
        if not stateful:
            cmd += ["--exclude-path-regex", r"(/execution$|/jobs/[^/]+)"]
        else:
            cmd += ["--exclude-path-regex", r"/execution$"]

        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    finally:
        tmp_path.unlink(missing_ok=True)
