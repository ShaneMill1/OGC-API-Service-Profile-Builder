# =================================================================
#
# Authors: Shane Mill <shane.mill@noaa.gov>
#
# Copyright (c) 2026 Shane Mill
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the \"Software\"), to deal in the Software without
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
OGC CITE testing via local Docker build of ets-ogcapi-edr10.
Automatically clones, builds, and caches the ETS image.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

_IMAGE_NAME = "ogccite/ets-ogcapi-edr10:local"
_REPO_URL = "https://github.com/opengeospatial/ets-ogcapi-edr10.git"
_POLL_INTERVAL = 3
_STARTUP_TIMEOUT = 60
_TEST_TIMEOUT = 600


def _find_free_port() -> int:
    """Find an available port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def _check_dependencies() -> None:
    """Ensure docker and mvn are available."""
    if shutil.which("docker") is None:
        print("Error: docker not found. Install Docker to use cite-test.", file=sys.stderr)
        sys.exit(1)
    if shutil.which("mvn") is None:
        print("Error: mvn (Maven) not found. Install Maven to use cite-test.", file=sys.stderr)
        sys.exit(1)


def _image_exists() -> bool:
    """Check if the ETS Docker image is already built."""
    result = subprocess.run(
        ["docker", "images", "-q", _IMAGE_NAME],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _build_image() -> None:
    """Clone the ETS repo, build with Maven, and create Docker image."""
    print(f"Building {_IMAGE_NAME} (this may take 5-10 minutes on first run)...\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "ets-ogcapi-edr10"
        
        # Clone
        print("Cloning ets-ogcapi-edr10...")
        subprocess.run(
            ["git", "clone", "--depth", "1", _REPO_URL, str(repo_dir)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        # Maven build
        print("Building with Maven (mvn clean install site -DskipTests -Pintegration-tests,docker)...")
        result = subprocess.run(
            ["mvn", "clean", "install", "site", "-DskipTests", "-Pintegration-tests,docker"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print("\nMaven build failed.\n", file=sys.stderr)
            print("STDOUT:", file=sys.stderr)
            print(result.stdout[-10000:], file=sys.stderr)
            print("\nSTDERR:", file=sys.stderr)
            print(result.stderr[-10000:], file=sys.stderr)
            sys.exit(1)
        
        # Docker build
        docker_dir = repo_dir / "target" / "docker" / "ogccite" / "ets-ogcapi-edr10" / "build"
        if not docker_dir.exists():
            print(f"Error: Docker build directory not found at {docker_dir}", file=sys.stderr)
            sys.exit(1)
        
        print(f"Building Docker image {_IMAGE_NAME}...")
        subprocess.run(
            ["docker", "build", "-t", _IMAGE_NAME, "."],
            cwd=docker_dir,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    
    print(f"✓ Image {_IMAGE_NAME} built successfully.\n")


def _start_container(container_name: str, port: int, iut_url: str) -> subprocess.Popen:
    """Start the TEAM Engine container in detached mode."""
    cmd = [
        "docker", "run", "-d", "--rm",
        "--name", container_name,
    ]
    
    # If testing localhost, use host network mode
    if "localhost" in iut_url or "127.0.0.1" in iut_url:
        cmd.extend(["--network", "host"])
    else:
        cmd.extend(["-p", f"{port}:8080"])
    
    cmd.append(_IMAGE_NAME)
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed to start container: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return None  # Container is running in background


def _wait_ready(container_name: str, port: int, use_host_network: bool = False) -> bool:
    """Wait for TEAM Engine to be ready."""
    # In host network mode, container uses port 8080 directly
    check_port = 8080 if use_host_network else port
    base = f"http://localhost:{check_port}"
    deadline = time.time() + _STARTUP_TIMEOUT
    
    while time.time() < deadline:
        try:
            resp = requests.get(f"{base}/teamengine", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        
        # Check if container exited
        result = subprocess.run(
            ["docker", "ps", "-q", "-f", f"name={container_name}"],
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            return False
        
        time.sleep(2)
    
    return False


def _run_tests(container_name: str, server_url: str) -> dict:
    """Run tests directly via TestNG CLI inside the container."""
    import uuid
    
    session_id = uuid.uuid4().hex[:16]
    output_dir = f"/tmp/cite-{session_id}"
    
    # Create custom testng.xml with IUT parameter at BOTH suite and test level
    # apiDefinition should point to the OpenAPI spec
    testng_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE suite SYSTEM "http://testng.org/testng-1.0.dtd">
<suite name="ogcapi-edr10" verbose="0" configfailurepolicy="continue">
  <parameter name="iut" value="{server_url}"/>
  <parameter name="apiDefinition" value="{server_url}/openapi"/>
  <parameter name="ics" value=""/>

  <listeners>
    <listener class-name="org.opengis.cite.ogcapiedr10.TestRunListener" />
    <listener class-name="org.opengis.cite.ogcapiedr10.TestFailureListener" />
  </listeners>

  <test name="Preconditions">
    <parameter name="iut" value="{server_url}"/>
    <classes>
      <class name="org.opengis.cite.ogcapiedr10.SuitePreconditions" />
    </classes>
  </test>

  <test name="Core">
    <parameter name="iut" value="{server_url}"/>
    <packages>
      <package name="org.opengis.cite.ogcapiedr10.landingpage" />
      <package name="org.opengis.cite.ogcapiedr10.conformance" />
      <package name="org.opengis.cite.ogcapiedr10.corecollections" />   
    </packages>
  </test>
  
  <test name="Collections">
    <parameter name="iut" value="{server_url}"/>
    <packages>
      <package name="org.opengis.cite.ogcapiedr10.collections" />
      <package name="org.opengis.cite.ogcapiedr10.queries" />       
    </packages>
  </test>
  
  <test name="JSON">
    <parameter name="iut" value="{server_url}"/>
    <packages>
      <package name="org.opengis.cite.ogcapiedr10.encodings.json" />      
    </packages>
  </test>  
  
  <test name="GeoJSON">
    <parameter name="iut" value="{server_url}"/>
    <packages>
      <package name="org.opengis.cite.ogcapiedr10.encodings.geojson" />      
    </packages>
  </test>  
  
  <test name="EDRGeoJSON">
    <parameter name="iut" value="{server_url}"/>
    <packages>
      <package name="org.opengis.cite.ogcapiedr10.encodings.edrgeojson" />      
    </packages>
  </test>  
</suite>
"""
    
    # Write testng.xml to container
    subprocess.run(
        ["docker", "exec", "-i", container_name, "sh", "-c", f"cat > /tmp/testng-{session_id}.xml"],
        input=testng_xml.encode(),
        check=True,
    )
    
    # Run TestNG with custom suite
    cmd = [
        "docker", "exec", container_name,
        "java",
        "-cp",
        "/usr/local/tomcat/webapps/teamengine/WEB-INF/lib/*:/usr/local/tomcat/lib/*",
        "org.testng.TestNG",
        "-d", output_dir,
        f"/tmp/testng-{session_id}.xml",
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=_TEST_TIMEOUT)
    
    if result.returncode != 0:
        print(f"\nTestNG execution failed (exit {result.returncode})", file=sys.stderr)
        print(f"STDOUT:\n{result.stdout[-3000:]}", file=sys.stderr)
        print(f"\nSTDERR:\n{result.stderr[-3000:]}", file=sys.stderr)
    
    # Copy results out of container
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            ["docker", "cp", f"{container_name}:{output_dir}", tmpdir],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        # Parse TestNG XML results
        results_file = Path(tmpdir) / Path(output_dir).name / "testng-results.xml"
        if results_file.exists():
            return _parse_testng_results(results_file)
    
    # Fallback: parse from stdout
    print("\nWarning: Could not find testng-results.xml, parsing stdout", file=sys.stderr)
    return _parse_testng_stdout(result.stdout)


def _parse_testng_results(xml_file: Path) -> dict:
    """Parse TestNG XML results."""
    import xml.etree.ElementTree as ET
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    passed = 0
    failed = 0
    skipped = 0
    failures = []
    
    for test in root.findall(".//test-method"):
        status = test.attrib.get("status", "UNKNOWN")
        if status == "PASS":
            passed += 1
        elif status == "FAIL":
            failed += 1
            name = test.attrib.get("name", "unknown")
            exception = test.find(".//exception")
            message = exception.find(".//message") if exception is not None else None
            msg_text = message.text if message is not None else "No details"
            failures.append({"name": name, "message": msg_text})
        elif status == "SKIP":
            skipped += 1
    
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    }


def _parse_testng_stdout(stdout: str) -> dict:
    """Parse TestNG console output as fallback."""
    # Simple regex parsing of TestNG output
    import re
    
    passed = failed = skipped = 0
    
    # Look for summary line like "Total tests run: 50, Passes: 45, Failures: 5, Skips: 0"
    match = re.search(r'Total tests run: (\d+), (?:Passes|Passed): (\d+), Failures: (\d+), Skips: (\d+)', stdout)
    if match:
        passed = int(match.group(2))
        failed = int(match.group(3))
        skipped = int(match.group(4))
    
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": [],
    }


def _print_results(results: dict) -> bool:
    passed = results["passed"]
    failed = results["failed"]
    skipped = results["skipped"]
    total = passed + failed + skipped

    print(f"\nOGC API - EDR CITE Results")
    print(f"  Passed:  {passed}/{total}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")

    if failed:
        print("\nFailed tests:")
        for failure in results["failures"][:10]:  # Limit to first 10
            print(f"  - {failure['name']}")
            print(f"    {failure['message'][:200]}")  # Truncate long messages
        if len(results["failures"]) > 10:
            print(f"\n  ... and {len(results['failures']) - 10} more failures")

    if failed == 0:
        print("\n✓ All CITE tests passed.")
    else:
        print(f"\n✗ {failed} test(s) failed.")
    
    return failed == 0


def run_cite(server_url: str, report_dir: Path | None = None) -> bool:
    """
    Run OGC API - EDR CITE tests against a live server.
    Automatically builds the ETS Docker image if not cached.
    
    Returns True if all tests pass.
    """
    import uuid
    
    _check_dependencies()
    
    # Build image if needed
    if not _image_exists():
        print(f"Image {_IMAGE_NAME} not found locally.")
        _build_image()
    else:
        print(f"Using cached image {_IMAGE_NAME}\n")
    
    container_name = f"ets-ogcapi-edr10-{uuid.uuid4().hex[:8]}"
    port = _find_free_port()
    
    print(f"Starting TEAM Engine container on port {port}...")
    _start_container(container_name, port, server_url)
    
    # Transform localhost URLs for container access
    test_url = server_url
    use_host_network = "localhost" in server_url or "127.0.0.1" in server_url
    if use_host_network:
        test_url = server_url.replace("localhost", "localhost").replace("127.0.0.1", "localhost")
    
    try:
        if not _wait_ready(container_name, port, use_host_network):
            print("Error: TEAM Engine failed to start.", file=sys.stderr)
            # Get container logs
            logs = subprocess.run(
                ["docker", "logs", container_name],
                capture_output=True,
                text=True,
            )
            print("\nContainer logs:", file=sys.stderr)
            print(logs.stdout[-2000:], file=sys.stderr)
            print(logs.stderr[-2000:], file=sys.stderr)
            return False
        
        print(f"Running OGC API - EDR tests against {test_url}...\n")
        results = _run_tests(container_name, test_url)
        print("Tests complete.\n")
        
        if report_dir:
            report_dir.mkdir(parents=True, exist_ok=True)
            report_file = report_dir / "cite_results.json"
            import json
            report_file.write_text(json.dumps(results, indent=2))
            print(f"Full report written to {report_file}\n")
        
        return _print_results(results)
    
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return False
    
    finally:
        print("\nStopping container...")
        subprocess.run(
            ["docker", "stop", container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
