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
PDF compilation: shell out to the Metanorma Docker image.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def compile_pdf(output_dir: Path, profile=None) -> bool:
    """
    Run `docker run metanorma/metanorma compile` against document.adoc
    in output_dir. Returns True on success.

    If *profile* is provided, custom fonts declared in document_metadata will be
    pre-installed into the fontist cache so Metanorma can embed them.
    """
    if shutil.which("docker") is None:
        print("docker not found. Install Docker to use --pdf.", file=sys.stderr)
        sys.exit(1)

    doc = output_dir / "document.adoc"
    if not doc.exists():
        print(f"document.adoc not found in {output_dir}", file=sys.stderr)
        sys.exit(1)

    fonts_dir = Path.home() / ".fontist" / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    # Pre-install any custom fonts requested by the profile so fontist inside
    # the container recognizes them during PDF generation.
    extra_fonts: list[str] = []
    if profile is not None:
        m = getattr(profile, "document_metadata", None)
        if m:
            for attr in ("body_font", "header_font", "monospace_font"):
                val = getattr(m, attr, None)
                if val:
                    extra_fonts.append(val)

    # De-duplicate while preserving order.
    if extra_fonts:
        seen: set[str] = set()
        extra_fonts = [f for f in extra_fonts if not (f in seen or seen.add(f))]  # type: ignore[func-returns-value]

    # Build the Docker command. When custom fonts are needed, we run fontist
    # install + metanorma compile in the *same* container so the fontist
    # database is available at compile time. We also monkey-patch the OGC
    # processor's fonts_manifest so mn2pdf receives the correct font paths.
    if extra_fonts:
        install_cmds = " && ".join(f"fontist install '{f}'" for f in extra_fonts)
        # Ruby snippet to inject extra fonts into the OGC processor's manifest
        # so mn2pdf's font-manifest YAML includes them.
        font_hash_entries = ", ".join(f'\\"{f}\\" => nil' for f in extra_fonts)
        # Write the Ruby patch via heredoc to avoid shell quoting issues.
        patch_rb_escaped = (
            'require \\"metanorma-ogc\\"; '
            "module Metanorma; module Ogc; class Processor; "
            "alias_method :_orig_fonts_manifest, :fonts_manifest; "
            f"def fonts_manifest; _orig_fonts_manifest.merge({{{font_hash_entries}}}); end; "
            "end; end; end"
        )
        shell_script = (
            f"{install_cmds} && "
            f'printf "%s" "{patch_rb_escaped}" > /tmp/_font_patch.rb && '
            "RUBYOPT='-r/tmp/_font_patch.rb' "
            "metanorma compile --agree-to-terms -t ogc -x pdf document.adoc"
        )
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{output_dir.resolve()}:/metanorma",
            "-v", f"{fonts_dir}:/config/fonts",
            "-w", "/metanorma",
            "metanorma/metanorma",
            "bash", "-c", shell_script,
        ]
        print(f"Installing custom fonts ({', '.join(extra_fonts)}) and compiling PDF...")
    else:
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{output_dir.resolve()}:/metanorma",
            "-v", f"{fonts_dir}:/config/fonts",
            "metanorma/metanorma",
            "metanorma", "compile",
            "--agree-to-terms",
            "-t", "ogc",
            "-x", "pdf",
            "document.adoc",
        ]
        print("Compiling PDF via Metanorma Docker...")
    result = subprocess.run(cmd, check=False)
    if result.returncode == 0:
        pdf = output_dir / "document.pdf"
        print(f"PDF written to {pdf}")
    return result.returncode == 0
