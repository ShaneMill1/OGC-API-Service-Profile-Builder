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
from urllib.parse import urljoin, urlsplit

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


def _discover_service_desc_path(base_url: str) -> str | None:
    """
    Fetch the landing page and resolve where the live server actually serves
    its OpenAPI document.

    OGC API standards do not fix the OpenAPI document path. It is discoverable
    via the landing page link with rel="service-desc" (machine-readable). This
    returns the path relative to ``base_url`` (e.g. "/openapi.json") suitable
    for use as an OpenAPI path template, or None if it cannot be resolved to a
    path on the same host as ``base_url``.
    """
    try:
        import requests
    except ImportError:
        return None

    # Normalise to a base that urljoin treats as a directory.
    base = base_url if base_url.endswith("/") else base_url + "/"

    try:
        resp = requests.get(
            base,
            headers={"Accept": "application/json"},
            timeout=10,
        )
        resp.raise_for_status()
        landing = resp.json()
    except Exception:
        return None

    if not isinstance(landing, dict):
        return None

    links = landing.get("links")
    if not isinstance(links, list):
        return None

    href = None
    for link in links:
        if isinstance(link, dict) and link.get("rel") == "service-desc" and link.get("href"):
            href = link["href"]
            break
    if not href:
        return None

    # Resolve relative hrefs against the landing page URL.
    absolute = urljoin(base, href)

    base_parts = urlsplit(base)
    href_parts = urlsplit(absolute)

    # schemathesis appends the OpenAPI path template to --url, so the spec can
    # only describe resources on the same origin as the validated base URL.
    if (href_parts.scheme, href_parts.netloc) != (base_parts.scheme, base_parts.netloc):
        return None

    # Return the href path relative to the base URL's path.
    base_path = base_parts.path  # ends with "/"
    href_path = href_parts.path or "/"
    if href_path.startswith(base_path):
        rel = href_path[len(base_path):]
    else:
        rel = href_path.lstrip("/")
    return "/" + rel


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

    # The OpenAPI document path is discoverable, not fixed by OGC API. The spec
    # ships a placeholder "/openapi" path; remap it to wherever the live server
    # actually advertises its service-desc link, or drop it if we cannot resolve
    # a same-origin path (testing a path the standard never mandated would be a
    # false failure).
    drop_openapi_path = False
    paths = spec.get("paths")
    if isinstance(paths, dict) and "/openapi" in paths:
        discovered = _discover_service_desc_path(url)
        if discovered and discovered != "/openapi":
            if discovered in paths:
                # Server serves its spec at a path the profile already describes.
                paths.pop("/openapi")
            else:
                paths[discovered] = paths.pop("/openapi")
            print(f"Discovered service-desc document at: {discovered}")
        elif not discovered:
            drop_openapi_path = True
            print("Could not resolve service-desc from landing page; "
                  "excluding /openapi from validation.")

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

        if drop_openapi_path:
            cmd += ["--exclude-path-regex", r"^/openapi$"]

        # Exclude POST /execution and job resource paths unless stateful testing is enabled
        if not stateful:
            cmd += ["--exclude-path-regex", r"(/execution$|/jobs/[^/]+)"]
        else:
            cmd += ["--exclude-path-regex", r"/execution$"]

        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    finally:
        tmp_path.unlink(missing_ok=True)
