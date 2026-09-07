import argparse
import base64
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


PYTHON_IMAGE = "python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
NODE_IMAGE = "node:22.19.0-bookworm-slim@sha256:4a4884e8a44826194dff92ba316264f392056cbe243dcc9fd3551e71cea02b90"
GITLEAKS_IMAGE = "ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f"
INPUTS = ("requirements.in", "requirements.txt", "requirements-dev.in", "requirements-dev.txt", "package.json", "package-lock.json")
TOOL_PINS = ("pip==26.2.1", "pip-tools==7.6.1", "pip-audit==2.10.1", "cyclonedx-bom==7.3.1")
BASE_COMMIT = "7b0c97f87ec8cf1a9584c389717383c457bc764f"
REVIEWED_FIXTURE_LINES = {
    "compose.test.yml": {"69c52e9225d75f2cc437a74cd7f740e1cf616372526516621f847417af48064b"},
    "scripts/validate_image.sh": {"032e9d84b8c3e36e0eae74062e367f31151297f64bbd03d4b28c40443b967208"},
    "scripts/validate_sprint03_adversarial.ps1": {"e853d77674231abea6024445f39a56e2699853a5b5459ec172556098b431e3a7"},
    "scripts/validate_sprint04.ps1": {"e853d77674231abea6024445f39a56e2699853a5b5459ec172556098b431e3a7"},
    "scripts/validate_release_candidate.ps1": {"0354965d5cda266bdcfd118f55680011acf9bc4e06ae2f4fc1ee04fcb0fe020b"},
    "scripts/validate_operational_proof.ps1": {"274ab8a49377291b395a3414c058a2b0d976ebbad9872ab49337932ff40be506", "4e13c9ad4265d546abbed6abc59312653e171d2d88e99a7f094fba63af744ae5"},
    "scripts/validate_sprint05_adversarial.ps1": {"0ea3b4aeeb43c074caf9f713b6b96ee3995dbbce6d1cf51ee8fe6227f804d781"},
    "tests/test_sprint02_adversarial.py": {"015054dddc9063ee02835ccc13f9d7b241b2132f20d45b424114f22676edc8e0"},
    "tests/test_startup.py": {"b908c0bb30861caac7d76aff09dc0b57b15a0270dc0061ffcec4158524bffca8"},
}


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def digest_inputs(root):
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in INPUTS}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"files": hashes, "digest": digest, "algorithm": "sha256(sorted compact JSON filename-to-raw-file-sha256 map)"}


def candidate_paths(root):
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root, capture_output=True, check=True)
    return sorted(set(name for name in result.stdout.decode("utf-8").split("\0") if name))


def source_hashes(root, output=None):
    hashes = {}
    for name in candidate_paths(root):
        if name.startswith(("docs/", ".release-work/")):
            continue
        source = root / name
        if output is not None and source.resolve().is_relative_to(output):
            continue
        if source.is_file():
            hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    return hashes


def stage_candidate(root, destination, output):
    staged = []
    excluded = []
    for name in candidate_paths(root):
        source = root / name
        if source.resolve().is_relative_to(output) or name.startswith(".release-work/"):
            excluded.append(name)
            continue
        if not source.exists():
            continue
        if not source.resolve().is_relative_to(root):
            raise RuntimeError(f"Candidate path resolves outside checkout: {name}")
        if not source.is_file():
            continue
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        staged.append(name)
    return {"selection": "git ls-files --cached --others --exclude-standard", "file_count": len(staged), "historical_evidence_files": sum(name.startswith("docs/evidencias/") for name in staged), "path_list_sha256": hashlib.sha256("\n".join(staged).encode()).hexdigest(), "excluded_output_files": len(excluded), "limitations": "Working checkout candidate, including tracked historical evidence, excludes ignored ephemeral tools, raw reports, dist archives, traces and dumps. Not a full filesystem or Git-history scan. Ignored packaged release artifacts need separate manifest verification."}


def execute(command, records, allowed=(0,), cwd=None):
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True)
    records.append({"command": [str(part) for part in command], "started_at": started, "exit_code": result.returncode})
    if result.returncode not in allowed:
        raise RuntimeError(f"Command failed (exit {result.returncode}): {command[0]}")
    return result


def inventory():
    packages = []
    for distribution in importlib.metadata.distributions():
        metadata = distribution.metadata
        license_value = metadata.get("License")
        if license_value and len(license_value) > 200:
            license_value = "license text in distribution; see license_files"
        packages.append({
            "name": metadata["Name"], "version": distribution.version,
            "license_expression": metadata.get("License-Expression"), "license": license_value,
            "license_classifiers": [value for value in metadata.get_all("Classifier", []) if value.startswith("License ::")],
            "license_files": metadata.get_all("License-File", []),
        })
    return sorted(packages, key=lambda package: package["name"].lower())


def npm_sbom(work, output):
    output.mkdir(parents=True, exist_ok=True)
    records = []
    project = read_json(work / "package.json")
    lock = read_json(work / "package-lock.json")
    locked = {path: package for path, package in lock["packages"].items() if path}
    inputs = {name: hashlib.sha256((work / name).read_bytes()).hexdigest() for name in ("package.json", "package-lock.json")}
    stage = work / "npm-sbom"
    stage.mkdir()
    synthetic_version = not project.get("version")
    staged_project = dict(project)
    staged_lock = json.loads(json.dumps(lock))
    if synthetic_version:
        staged_project["version"] = "0.0.0"
        staged_lock["version"] = "0.0.0"
        staged_lock["packages"][""]["version"] = "0.0.0"
    if {path: package for path, package in staged_lock["packages"].items() if path} != locked:
        raise RuntimeError("Temporary npm metadata adaptation changed locked dependencies")
    write_json(stage / "package.json", staged_project)
    write_json(stage / "package-lock.json", staged_lock)
    node = execute(["docker", "run", "--rm", "--network", "none", NODE_IMAGE, "node", "--version"], records).stdout.strip()
    npm = execute(["docker", "run", "--rm", "--network", "none", NODE_IMAGE, "npm", "--version"], records).stdout.strip()
    result = execute(["docker", "run", "--rm", "--network", "none", "--mount", f"type=bind,source={stage},target=/work,readonly", "--workdir", "/work", NODE_IMAGE, "npm", "sbom", "--sbom-format", "cyclonedx", "--package-lock-only", "--offline", "--ignore-scripts", "--include=dev", "--include=optional", "--include=peer"], records)
    sbom = json.loads(result.stdout)
    if sbom.get("bomFormat") != "CycloneDX" or not sbom.get("components"):
        raise RuntimeError("npm did not generate a CycloneDX component inventory")
    observed = {}
    packages = []
    for component in sbom["components"]:
        properties = {item["name"]: item["value"] for item in component.get("properties", [])}
        path = properties.get("cdx:npm:package:path")
        if path not in locked or path in observed:
            raise RuntimeError("Unexpected or duplicate npm SBOM package path")
        package = locked[path]
        name = package.get("name", path.rsplit("node_modules/", 1)[-1])
        if (component["name"], component["version"]) != (name, package["version"]):
            raise RuntimeError(f"npm SBOM name/version mismatch: {path}")
        expected_hashes = {(integrity.split("-", 1)[0], base64.b64decode(integrity.split("-", 1)[1]).hex()) for integrity in package.get("integrity", "").split()}
        actual_hashes = {(item["alg"].replace("-", "").lower(), item["content"]) for item in component.get("hashes", [])}
        if not expected_hashes or expected_hashes != actual_hashes:
            raise RuntimeError(f"npm SBOM integrity mismatch or absent lock integrity: {path}")
        observed[path] = (name, package["version"])
        packages.append({"path": path, "name": name, "version": package["version"], "dev": package.get("dev", False), "optional": package.get("optional", False), "resolved": package.get("resolved"), "integrity": package["integrity"], "license": package.get("license"), "sbom_licenses": component.get("licenses", [])})
    if set(observed) != set(locked):
        raise RuntimeError("npm SBOM omitted locked component paths")
    root_component = sbom["metadata"]["component"]
    root_component["name"] = project["name"]
    if synthetic_version:
        old_reference = root_component["bom-ref"]
        new_reference = "urn:oceanblue:npm:unversioned-root"
        root_component["bom-ref"] = new_reference
        root_component.pop("version", None)
        root_component.pop("purl", None)
        root_component.setdefault("properties", []).append({"name": "oceanblue:root-version-adaptation", "value": "Unversioned private project: temporary 0.0.0 was required by npm 10.9.3; placeholder version and purl removed from delivered SBOM."})
        for dependency in sbom.get("dependencies", []):
            if dependency["ref"] == old_reference:
                dependency["ref"] = new_reference
            dependency["dependsOn"] = [new_reference if reference == old_reference else reference for reference in dependency.get("dependsOn", [])]
    references = {root_component["bom-ref"], *(component["bom-ref"] for component in sbom["components"])}
    if any(dependency["ref"] not in references or not set(dependency.get("dependsOn", [])).issubset(references) for dependency in sbom.get("dependencies", [])):
        raise RuntimeError("npm SBOM contains dangling dependency references")
    write_json(output / "sbom-npm.cdx.json", sbom)
    write_json(output / "npm-inventory-licenses.json", {"source": "Exact package-lock.json package locations, including dev/optional/peer dependencies", "packages": sorted(packages, key=lambda package: package["path"]), "missing_license_metadata": [package["path"] for package in packages if not package["license"]], "license_counts": dict(Counter(str(package["license"]) for package in packages)), "limitations": "Lockfile and SBOM license metadata only; no tarball contents, installed node_modules or vendored browser assets were inspected. Not legal approval."})
    report = {"status": "passed", "image": NODE_IMAGE, "node": node, "npm": npm, "inputs_sha256": inputs, "locked_package_locations": len(locked), "sbom_components": len(observed), "exact_paths_names_versions_match": True, "all_integrity_hashes_match": True, "dependency_references_valid": True, "cyclonedx_version": sbom["specVersion"], "schema_validation": "Not independently schema-validated; native npm output with structural, reference and exact lock/integrity checks.", "network": "none", "root_version_adaptation": synthetic_version, "commands": records, "artifact_sha256": {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in ("sbom-npm.cdx.json", "npm-inventory-licenses.json")}}
    write_json(output / "npm-sbom-verification.json", report)
    return report


def npm_sbom_only(args):
    root = args.root.resolve()
    output = args.output_dir.resolve()
    before = digest_inputs(root)
    if args.expected_lock_digest and before["digest"] != args.expected_lock_digest:
        raise RuntimeError("Input/lock digest does not match --expected-lock-digest")
    with tempfile.TemporaryDirectory(prefix="oceanblue-npm-sbom-") as temporary:
        work = Path(temporary)
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(root / name, work / name)
        report = npm_sbom(work, output)
    if before != digest_inputs(root):
        raise RuntimeError("Input/lock files changed during npm SBOM generation")
    print(json.dumps({"status": report["status"], "npm_components": report["sbom_components"], "lock_digest": before["digest"]}))
    return 0


def python_worker(output):
    output.mkdir(parents=True, exist_ok=True)
    records = []
    execute([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--index-url=https://pypi.org/simple", *TOOL_PINS], records)
    tooling = inventory()
    scopes = {}
    deltas = {}
    for scope, lock in (("prod", "requirements.txt"), ("dev", "requirements-dev.txt")):
        environment = Path(tempfile.mkdtemp(prefix=f"supply-{scope}-"))
        execute([sys.executable, "-m", "venv", str(environment)], records)
        interpreter = str(environment / "bin/python")
        install_report = environment / "install.json"
        execute([interpreter, "-m", "pip", "install", "--disable-pip-version-check", "--index-url=https://pypi.org/simple", "--only-binary=:all:", "--require-hashes", "--report", str(install_report), "-r", lock], records)
        installed = read_json(install_report)
        artifacts = [{"name": item["metadata"]["name"], "version": item["metadata"]["version"], "url": item["download_info"]["url"], "hashes": item["download_info"]["archive_info"]["hashes"]} for item in installed["install"]]
        write_json(output / f"installed-artifacts-{scope}.json", artifacts)
        check = execute([interpreter, "-m", "pip", "check"], records)
        metadata = execute([interpreter, str(Path(__file__).resolve()), "--metadata-worker"], records)
        packages = json.loads(metadata.stdout)
        write_json(output / f"licenses-{scope}.json", packages)
        audit_path = output / f"pip-audit-{scope}.json"
        audit = execute(["pip-audit", "-r", lock, "--disable-pip", "--strict", "--progress-spinner=off", "--format=json", "--output", str(audit_path)], records, allowed=(0, 1))
        findings = read_json(audit_path)
        baseline_path = output / f"pip-audit-before-{scope}.json"
        execute(["pip-audit", "-r", f"baseline-{lock}", "--disable-pip", "--strict", "--progress-spinner=off", "--format=json", "--output", str(baseline_path)], records, allowed=(0, 1))
        baseline = read_json(baseline_path)
        before_versions = {item["name"]: item["version"] for item in baseline["dependencies"]}
        after_versions = {item["name"]: item["version"] for item in findings["dependencies"]}
        deltas[scope] = {"changes": [{"name": name, "before": before_versions.get(name), "after": after_versions.get(name)} for name in sorted(before_versions.keys() | after_versions.keys()) if before_versions.get(name) != after_versions.get(name)], "before_vulnerability_records": sum(len(item.get("vulns", [])) for item in baseline["dependencies"]), "before_unique_advisories": len({vulnerability["id"] for item in baseline["dependencies"] for vulnerability in item.get("vulns", [])}), "confirmed_vulnerable_pins": [{"name": item["name"], "version": item["version"], "advisories": [{"id": vulnerability["id"], "aliases": vulnerability.get("aliases", []), "fix_versions": vulnerability.get("fix_versions", [])} for vulnerability in item["vulns"]]} for item in baseline["dependencies"] if item.get("vulns")]}
        write_json(baseline_path, baseline)
        pins = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", Path(lock).read_text(), re.MULTILINE))
        normalize = lambda name: re.sub(r"[-_.]+", "-", name).lower()
        expected = {normalize(name): version for name, version in pins.items()}
        actual = {normalize(item["name"]): item["version"] for item in packages}
        audited = {normalize(item["name"]): item.get("version") for item in findings["dependencies"]}
        if actual != expected or audited != expected or any("skip_reason" in item for item in findings["dependencies"]):
            raise RuntimeError(f"Installed/audited package set differs from {lock}")
        sbom_path = output / f"sbom-{scope}.cdx.json"
        execute(["cyclonedx-py", "environment", interpreter, "--sv=1.6", "--output-reproducible", "--validate", "--of=JSON", "-o", str(sbom_path)], records)
        sbom = read_json(sbom_path)
        sbom_packages = {normalize(item["name"]): item["version"] for item in sbom["components"]}
        if sbom_packages != expected:
            raise RuntimeError(f"SBOM component set differs from {lock}")
        write_json(sbom_path, sbom)
        write_json(audit_path, findings)
        scopes[scope] = {"lock": lock, "packages": len(expected), "pip_check": check.stdout.strip(), "audit_exit_code": audit.returncode, "vulnerability_records": sum(len(item.get("vulns", [])) for item in findings["dependencies"]), "sbom_components": len(sbom_packages), "hash_install": "passed", "inventory_matches_lock": True, "sbom_validated": True}
    write_json(output / "python-verification.json", {"python": platform.python_version(), "platform": platform.platform(), "tool_pins": TOOL_PINS, "tool_environment": tooling, "scopes": scopes, "commands": records})
    write_json(output / "dependency-deltas.json", {"base_commit": BASE_COMMIT, "scopes": deltas})
    license_review = {}
    for scope in scopes:
        packages = read_json(output / f"licenses-{scope}.json")
        license_review[scope] = {"package_count": len(packages), "missing_license_metadata": [item["name"] for item in packages if not any(item[key] for key in ("license_expression", "license", "license_classifiers"))], "copyleft_metadata_requires_notice_review": [item["name"] for item in packages if "GPL" in json.dumps(item)], "status": "metadata_reviewed_not_legal_approval"}
    write_json(output / "license-review.json", license_review)


def compact_gitleaks(raw_path, root, output):
    findings = read_json(raw_path)
    groups = defaultdict(list)
    source_records = []
    source_lines = {}
    for finding in findings:
        filename = finding["File"].removeprefix("/src/")
        if filename.startswith("docs/evidencias/"):
            category = "historical_evidence_requires_review"
            scope = "/".join(filename.split("/")[:4])
        else:
            category = "unclassified_source"
            scope = "current_source"
            if filename not in source_lines:
                source = root / filename
                source_lines[filename] = source.read_text(encoding="utf-8", errors="replace").splitlines() if source.is_file() else []
            lines = source_lines[filename]
            line = lines[finding["StartLine"] - 1] if 0 < finding["StartLine"] <= len(lines) else ""
            line_hash = hashlib.sha256(line.encode()).hexdigest()
            if finding["RuleID"] == "generic-api-key" and line_hash in REVIEWED_FIXTURE_LINES.get(filename, set()):
                category = "reviewed_synthetic_fixture"
            source_records.append({"file": filename, "line": finding["StartLine"], "rule": finding["RuleID"], "category": category, "line_sha256": line_hash, "match": "REDACTED", "basis": "Exact reviewed test/smoke fixture line; isolated Compose, offline startup validation or mocked test input." if category == "reviewed_synthetic_fixture" else "Requires individual review; not suppressed by filename."})
        groups[(category, scope, finding["RuleID"])].append(finding)
    compact = []
    for (category, scope, rule), entries in sorted(groups.items()):
        compact.append({"category": category, "scope": scope, "rule": rule, "count": len(entries), "unique_paths": len({entry["File"] for entry in entries}), "unique_fingerprints": len({entry.get("Fingerprint", f'{entry["File"]}:{rule}:{entry["StartLine"]}') for entry in entries}), "representatives": [{"file": entry["File"].removeprefix("/src/"), "line": entry["StartLine"], "match": "REDACTED"} for entry in entries[:2]]})
    counts = Counter()
    for entry in compact:
        counts[entry["category"]] += entry["count"]
    report = {"status": "unclassified_source" if counts["unclassified_source"] else "historical_review_required" if counts["historical_evidence_requires_review"] else "passed", "runtime_gate": "failed" if counts["unclassified_source"] else "passed", "total_findings": len(findings), "counts_by_category": dict(counts), "unique_paths": len({entry["File"] for entry in findings}), "unique_fingerprints": len({entry.get("Fingerprint", f'{entry["File"]}:{entry["RuleID"]}:{entry["StartLine"]}') for entry in findings}), "classification": "Only exact reviewed source fixture lines are accepted. Historical evidence is retained for review, not automatically declared safe or a confirmed production credential leak. No external credential validation is performed.", "redaction": "Gitleaks --redact=100; retained examples contain only paths, lines and literal REDACTED. Full redacted scanner output stays in ignored .release-work.", "groups": compact, "source_findings": source_records}
    write_json(output / "gitleaks-redacted.json", report)
    return {key: value for key, value in report.items() if key not in ("groups", "source_findings")}


def host_audit(args):
    root = args.root.resolve()
    output = args.output_dir.resolve()
    current = digest_inputs(root)
    if args.expected_lock_digest and current["digest"] != args.expected_lock_digest:
        raise RuntimeError("Input/lock digest does not match --expected-lock-digest")
    if args.verify_only:
        saved = read_json(output / "summary.json")
        if saved["inputs"] != current or not saved.get("inputs_unchanged"):
            raise RuntimeError("Saved scan does not match current input/lock digests")
        if not {"sbom-npm.cdx.json", "npm-inventory-licenses.json", "npm-sbom-verification.json"}.issubset(saved["artifact_sha256"]):
            raise RuntimeError("Saved scan lacks the required npm inventory/SBOM evidence")
        for name, digest in saved["artifact_sha256"].items():
            if hashlib.sha256((output / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"Evidence digest mismatch: {name}")
        review = read_json(output / "gitleaks-review.json")
        report = read_json(output / "gitleaks-redacted.json")
        if saved["status"] not in ("passed", "passed_with_historical_review") or report["runtime_gate"] != "passed" or review["runtime_gate"] != "passed":
            raise RuntimeError("Scan/review has vulnerabilities or unclassified source findings")
        if review["scanner_report_sha256"] != saved["artifact_sha256"]["gitleaks-redacted.json"] or review["raw_scanner_report_sha256"] != saved["gitleaks"]["raw_sha256"]:
            raise RuntimeError("Reviewed scanner artifact binding does not match")
        if review["source_sha256"] != source_hashes(root, output):
            raise RuntimeError("Runtime/source files changed after the reviewed scan; run fresh scans")
        if any(finding["category"] != "reviewed_synthetic_fixture" for finding in report["source_findings"]):
            raise RuntimeError("Unknown source finding cannot be accepted by verify-only")
        print(json.dumps({"status": "digests_verified", "lock_digest": current["digest"], "scan_status": saved["status"]}))
        return 0
    output.mkdir(parents=True, exist_ok=True)
    records = []
    summary = {"started_at": datetime.now(timezone.utc).isoformat(), "inputs": current, "status": "incomplete", "images": {"python": PYTHON_IMAGE, "node": NODE_IMAGE, "gitleaks": GITLEAKS_IMAGE}, "os_cve_scan": {"status": "not_scanned", "reason": "No OS vulnerability scanner/database was run. Python, npm and Gitleaks results do not cover Debian packages, CPython, embedded native libraries or installed browsers."}, "limitations": ["No business environment, provider, application or database is started.", "Python installs and SBOM cover CPython 3.12 Linux amd64; other platform markers are not verified.", "Advisory results are point-in-time registry results, not proof of absence of vulnerabilities or malicious packages.", "License metadata is reported, not legal approval; embedded library licenses require separate review.", "Gitleaks scans staged Git candidate files and archives/decode depth 2, excluding ignored ephemeral artifacts and the active report directory. Not a full filesystem or Git-history scan."]}
    try:
        docker_version = execute(["docker", "version", "--format", "{{.Client.Version}} {{.Server.Version}}"], records).stdout.strip()
        summary["docker_version"] = docker_version
        os_probe = root / "docs/evidencias/producao/sprint-07-execucao/image-scan-limit.json"
        if os_probe.is_file():
            summary["os_cve_scan"]["parent_probe"] = read_json(os_probe)
        with tempfile.TemporaryDirectory(prefix="oceanblue-supply-") as temporary:
            work = Path(temporary)
            for name in INPUTS:
                shutil.copyfile(root / name, work / name)
            for lock in ("requirements.txt", "requirements-dev.txt"):
                baseline = execute(["git", "show", f"{BASE_COMMIT}:{lock}"], records, cwd=root)
                (work / f"baseline-{lock}").write_text(baseline.stdout, encoding="utf-8")
            shutil.copyfile(Path(__file__).resolve(), work / "release_supply_chain.py")
            mount = f"type=bind,source={work},target=/work"
            execute(["docker", "run", "--rm", "--mount", mount, "--workdir", "/work", PYTHON_IMAGE, "python", "release_supply_chain.py", "--python-worker", "--output-dir", "/work/out"], records)
            for artifact in (work / "out").iterdir():
                shutil.copyfile(artifact, output / artifact.name)
            node = execute(["docker", "run", "--rm", "--network", "none", NODE_IMAGE, "node", "--version"], records).stdout.strip()
            npm = execute(["docker", "run", "--rm", "--network", "none", NODE_IMAGE, "npm", "--version"], records).stdout.strip()
            npm_audit = execute(["docker", "run", "--rm", "--mount", mount, "--workdir", "/work", NODE_IMAGE, "npm", "audit", "--package-lock-only", "--ignore-scripts", "--registry=https://registry.npmjs.org", "--json"], records, allowed=(0, 1))
            npm_report = json.loads(npm_audit.stdout)
            if "error" in npm_report or "vulnerabilities" not in npm_report:
                raise RuntimeError("npm audit did not return a valid vulnerability report")
            write_json(output / "npm-audit.json", npm_report)
            summary["node"] = {"node": node, "npm": npm, "audit_exit_code": npm_audit.returncode}
            npm_verification = npm_sbom(work, output)
            summary["node"]["sbom_components"] = npm_verification["sbom_components"]
            summary["node"]["exact_lock_and_integrity_match"] = True
            records.extend(npm_verification["commands"])
            summary["gitleaks_version"] = execute(["docker", "run", "--rm", "--network", "none", GITLEAKS_IMAGE, "version"], records).stdout.strip()
            (work / "gitleaks.toml").write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
            before_sources = source_hashes(root, output)
            staged_source = work / "source"
            summary["candidate_scope"] = stage_candidate(root, staged_source, output)
            staged_hashes = {name: hashlib.sha256((staged_source / name).read_bytes()).hexdigest() for name in before_sources if (staged_source / name).is_file()}
            if staged_hashes != before_sources:
                raise RuntimeError("Staged source bytes differ from pre-scan checkout hashes")
            scan = execute(["docker", "run", "--rm", "--network", "none", "--mount", f"type=bind,source={staged_source},target=/src,readonly", "--mount", mount, GITLEAKS_IMAGE, "dir", "/src", "--config=/work/gitleaks.toml", "--redact=100", "--no-banner", "--ignore-gitleaks-allow", "--max-archive-depth=2", "--max-decode-depth=2", "--report-format=json", "--report-path=/work/gitleaks.json", "--log-level=warn"], records, allowed=(0, 1))
            after_sources = source_hashes(root, output)
            final_staged_hashes = {name: hashlib.sha256((staged_source / name).read_bytes()).hexdigest() for name in staged_hashes}
            if before_sources != after_sources or final_staged_hashes != staged_hashes:
                raise RuntimeError("Runtime/source files changed during Gitleaks scan; run fresh scans")
            raw_directory = root / ".release-work/supply-chain"
            raw_directory.mkdir(parents=True, exist_ok=True)
            raw_report = raw_directory / "gitleaks-current.redacted.json"
            shutil.copyfile(work / "gitleaks.json", raw_report)
            summary["gitleaks"] = compact_gitleaks(work / "gitleaks.json", staged_source, output)
            summary["gitleaks"]["exit_code"] = scan.returncode
            summary["gitleaks"]["raw_report"] = ".release-work/supply-chain/gitleaks-current.redacted.json"
            summary["gitleaks"]["raw_sha256"] = hashlib.sha256(raw_report.read_bytes()).hexdigest()
            summary["gitleaks"]["excluded_paths"] = ["Git-ignored artifacts", str(output)]
            compact_report = read_json(output / "gitleaks-redacted.json")
            review = {"reviewed_at": datetime.now(timezone.utc).isoformat(), "runtime_gate": compact_report["runtime_gate"], "scanner_report_sha256": hashlib.sha256((output / "gitleaks-redacted.json").read_bytes()).hexdigest(), "raw_scanner_report_sha256": summary["gitleaks"]["raw_sha256"], "source_sha256": staged_hashes, "source_binding": "Independent staged copies; staged bytes matched checkout before scan and both staged and checkout hashes remained unchanged after scan.", "source_findings": compact_report["source_findings"], "review_method": "Exact per-file reviewed fixture line SHA256, generic-api-key rule only. Every other source detection fails the gate. Full staged source hashes bind this review to scanned bytes. Replay re-runs scans and exact fixture checks autonomously.", "historical_evidence": {"status": "review_required", "count": compact_report["counts_by_category"].get("historical_evidence_requires_review", 0), "basis": "Prior local validation evidence includes synthetic JWTs and source-manifest hash false positives. Individual historical credentials were not validated against providers or exhaustively proved synthetic. This review does not assert zero secrets or approve historical artifact publication."}}
            write_json(output / "gitleaks-review.json", review)
        verification = read_json(output / "python-verification.json")
        summary["python"] = verification["scopes"]
        summary["inputs_unchanged"] = current == digest_inputs(root)
        if not summary["inputs_unchanged"]:
            raise RuntimeError("Input/lock files changed while scans were running")
        findings = any(scope["audit_exit_code"] for scope in verification["scopes"].values()) or npm_audit.returncode or summary["gitleaks"]["runtime_gate"] == "failed"
        summary["status"] = "failed" if findings else "passed_with_historical_review" if summary["gitleaks"]["status"] == "historical_review_required" else "passed"
        summary["artifact_sha256"] = {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in ("pip-audit-prod.json", "pip-audit-dev.json", "pip-audit-before-prod.json", "pip-audit-before-dev.json", "dependency-deltas.json", "installed-artifacts-prod.json", "installed-artifacts-dev.json", "licenses-prod.json", "licenses-dev.json", "license-review.json", "sbom-prod.cdx.json", "sbom-dev.cdx.json", "python-verification.json", "npm-audit.json", "sbom-npm.cdx.json", "npm-inventory-licenses.json", "npm-sbom-verification.json", "gitleaks-redacted.json", "gitleaks-review.json")}
        return 1 if findings else 0
    finally:
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        summary["commands"] = records
        write_json(output / "summary.json", summary)


def main():
    parser = argparse.ArgumentParser(description="Isolated supply-chain scans; exit 0 dependency/source gate passed (historical review may remain), 1 vulnerabilities/unclassified source, 2 execution/digest error.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/evidencias/producao/sprint-07-execucao/supply-chain"))
    parser.add_argument("--expected-lock-digest")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--npm-sbom-only", action="store_true", help="Generate only the offline npm SBOM/inventory; does not refresh or approve the full scan summary.")
    parser.add_argument("--python-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--metadata-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.npm_sbom_only:
            if args.verify_only:
                raise RuntimeError("--npm-sbom-only and --verify-only cannot be combined")
            return npm_sbom_only(args)
        if args.metadata_worker:
            print(json.dumps(inventory()))
            return 0
        if args.python_worker:
            python_worker(args.output_dir)
            return 0
        return host_audit(args)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"Supply-chain scan failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
