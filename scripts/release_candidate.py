import argparse
import ast
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "docs/evidencias/producao/sprint-06-validacao/verify1"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cases(path):
    root = ET.parse(path).getroot()
    records = root.findall(".//testcase")
    if not records:
        raise ValueError("Empty JUnit refused")
    failed = [entry.attrib for entry in records if any(entry.find(tag) is not None for tag in ("failure", "error", "skipped"))]
    if failed:
        raise ValueError(f"JUnit contains failed/error/skipped cases: {failed}")
    identifiers = [(entry.get("classname"), entry.get("name")) for entry in records]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate test identifiers")
    for suite in root.iter("testsuite"):
        if any(int(suite.get(key, "0")) for key in ("failures", "errors", "skipped")):
            raise ValueError("Failed JUnit suite")
        if int(suite.get("tests", "0")) != len(suite.findall(".//testcase")):
            raise ValueError("JUnit count mismatch")
    return identifiers


def coverage(path):
    values = ET.parse(path).getroot().attrib
    covered = int(values["lines-covered"]) + int(values["branches-covered"])
    total = int(values["lines-valid"]) + int(values["branches-valid"])
    if total <= 0:
        raise ValueError("Empty coverage refused")
    return {key: values[key] for key in ("lines-covered", "lines-valid", "branches-covered", "branches-valid")} | {"combined_percent": 100 * covered / total}


def summarize(evidence, persist=True):
    baseline = set(cases(BASELINE / "junit.xml"))
    runs = []
    for name in ("regression", "retest"):
        directory = evidence / name
        current = set(cases(directory / "junit.xml"))
        missing = baseline - current
        if missing:
            raise ValueError(f"Previous tests missing: {sorted(missing)}")
        measured = coverage(directory / "coverage.xml")
        if measured["combined_percent"] < coverage(BASELINE / "coverage.xml")["combined_percent"]:
            raise ValueError("Combined coverage fell below Sprint 6 measured baseline")
        runs.append({"run": name, "tests": len(current), "previous_preserved": len(baseline),
                     "added": len(current - baseline), "failures": 0, "errors": 0, "skipped": 0,
                     "coverage": measured, "modules": dict(sorted(Counter(item[0] for item in current).items()))})
    if set(cases(evidence / "regression/junit.xml")) != set(cases(evidence / "retest/junit.xml")):
        raise ValueError("Complete retest differs from regression")
    for engine in ("chromium", "firefox", "webkit"):
        browser_cases = [identifier for identifier in current if identifier[0] == "tests.test_sprint07_browser" and f"[{engine}-" in identifier[1]]
        if not browser_cases:
            raise ValueError(f"Required release browser not exercised: {engine}")
    if persist:
        write_json(evidence / "regression-summary.json", runs)
    return runs


def curate(raw, destination):
    if destination.exists():
        raise ValueError("New evidence destination required")
    destination.mkdir(parents=True)
    retained, omitted = [], []
    screenshots = 0
    for path in sorted(raw.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(raw)
        selected = path.suffix in {".json", ".xml", ".txt"} and not any(part in {"snapshot", "tampered", "synthetic"} for part in relative.parts)
        selected = selected or (path.name == "manifest.json" and "snapshot" in relative.parts)
        screen_name = str(relative)
        representative = "test_catalog_client_sale_stock_financial_audit_journey" in screen_name
        representative = representative or ("-390]" in screen_name and any(name in screen_name for name in (
            "test_admin_role_employee_and_restricted_login_journey", "test_public_password_and_platform_provisioning_journey")))
        representative = representative or ("test_all_screens_navigation_accessibility_responsive" in screen_name and "-admin-320]" in screen_name)
        if path.suffix == ".png" and "sprint07" in screen_name and representative and screenshots < 15:
            selected = True
            screenshots += 1
        if selected:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.name == "axe.json":
                result = json.loads(path.read_text(encoding="utf-8-sig"))
                write_json(target, {"raw_sha256": digest(path), "testEngine": result.get("testEngine"),
                    "url": result.get("url"), "passed_rule_count": len(result.get("passes", [])),
                    "incomplete_rule_count": len(result.get("incomplete", [])),
                    "violations": [{"id": violation["id"], "impact": violation.get("impact"),
                        "targets": [node["target"] for node in violation.get("nodes", [])]}
                        for violation in result.get("violations", [])]})
            else:
                shutil.copyfile(path, target)
            retained.append(relative.as_posix())
        else:
            omitted.append({"path": relative.as_posix(), "size": path.stat().st_size, "sha256": digest(path)})
    write_json(destination / "retention.json", {"retained": retained, "omitted": omitted,
        "reason": "Raw diagnostic files remain in ignored .release-work; successful binary traces, HTML and synthetic dumps are not duplicated in Git."})


def traceability(evidence):
    passed = set(cases(evidence / "regression/junit.xml"))
    inventory = ROOT / "docs/04-modulos-e-funcionalidades/inventario-requisito-rota-servico-teste.csv"
    with inventory.open(encoding="utf-8", newline="") as stream:
        routes = list(csv.DictReader(stream))
    observed = json.loads((evidence / "regression/http-route-coverage.json").read_text(encoding="utf-8"))["observations"]
    with (evidence / "traceability.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["requirement", "methods", "route", "implementation_endpoint", "implementation_services", "executed_service_tests", "observed_http_tests_and_status", "evidence", "limit"])
        for route in routes:
            linked = []
            for candidate in route["testes_de_servico_indiretos"].split("|"):
                if "::" not in candidate:
                    continue
                filename, function = candidate.split("::", 1)
                module = filename.removesuffix(".py").replace("/", ".")
                linked.extend(f"{record[0]}::{record[1]}" for record in passed if record[0] == module and (record[1] == function or record[1].startswith(function + "[")))
            writer.writerow([route["requisito"], route["metodos"], route["rota"], route["endpoint"], route["servicos_diretos"],
                "|".join(sorted(linked)), "|".join(sorted(f"{entry['test']}:{entry['method']}:{entry['status']}" for entry in observed if entry["endpoint"] == route["endpoint"])),
                "regression/junit.xml|retest/junit.xml|regression/http-route-coverage.json|auditoria-modulos.md|auditoria-ui.md",
                "Static service linkage is not route-level HTTP coverage; see audit and browser evidence. " + route["observacao"]])
    components = []
    for directory in ("app", "migrations", "scripts", "tests", "docs"):
        for path in sorted((ROOT / directory).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or "evidencias" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            functions = []
            if path.suffix == ".py":
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                functions = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
            components.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path), "definitions": functions})
    write_json(evidence / "component-inventory.json", {"route_count": len(routes), "files": components,
        "method": "Complete file/AST inventory, not proof that each function or template is exercised."})


def source_files():
    files = set()
    for directory in ("app", "tests", "scripts", "migrations", "infra/production", ".github"):
        files.update(path for path in (ROOT / directory).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"})
    for pattern in ("requirements*", "Dockerfile*", "compose.*.yml", "package*.json", "*.ini", "VERSION", "CHANGELOG.md", "README.md", ".coveragerc", ".dockerignore", ".gitattributes", "docker-entrypoint.sh", "wsgi.py", ".env.example"):
        files.update(path for path in ROOT.glob(pattern) if path.is_file())
    for directory in ("02-instalacao-e-ambiente", "04-modulos-e-funcionalidades", "10-planejamento-sprints"):
        files.update(path for path in (ROOT / "docs" / directory).rglob("*") if path.is_file())
    return sorted(files)


def package(evidence, output):
    output.mkdir(parents=True, exist_ok=True)
    version = (ROOT / "VERSION").read_text().strip()
    filename = output / f"oceanblue-{version}.tar.gz"
    files = source_files()
    if evidence.resolve().is_relative_to(ROOT):
        files.extend(path.resolve() for path in evidence.rglob("*") if path.is_file() and path.name not in {"release-manifest.json", "evidence-sha256.json"})
        for path in (BASELINE / "junit.xml", BASELINE / "coverage.xml",
                     ROOT / "docs/evidencias/producao/sprint-06-validacao.md",
                     ROOT / "docs/evidencias/producao/sprint-07-execucao.md"):
            if path.is_file():
                files.append(path)
    files = sorted(set(files))
    hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in files}
    with filename.open("wb") as target, gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as compressed, tarfile.open(fileobj=compressed, mode="w") as archive:
        for path in files:
            data = path.read_bytes()
            entry = tarfile.TarInfo(path.relative_to(ROOT).as_posix())
            entry.size = len(data)
            entry.mode = 0o755 if path.suffix == ".sh" else 0o644
            entry.mtime = 0
            archive.addfile(entry, io.BytesIO(data))
    write_json(evidence / "release-manifest.json", {"version": version,
        "base_commit": "7b0c97f87ec8cf1a9584c389717383c457bc764f", "migration_head": "a0d1e2f3a4b5",
        "package": {"name": filename.name, "size": filename.stat().st_size, "sha256": digest(filename)},
        "sources": hashes, "flags": {"FEATURE_BOLETO": False, "FEATURE_FISCAL": False, "FEATURE_EXTERNAL_PROVIDERS": False},
        "reproducibility": "Deterministic source archive; image identity recorded separately. OS package repository and build metadata prevent claiming bit-identical Docker rebuilds.",
        "deploy_authorized": False})
    return filename


def verify(evidence, package_directory):
    manifest = json.loads((evidence / "release-manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["sources"].items():
        path = (ROOT / relative).resolve()
        if not path.is_relative_to(ROOT) or digest(path) != expected:
            raise ValueError(f"Source mismatch: {relative}")
    package_path = package_directory / manifest["package"]["name"]
    if digest(package_path) != manifest["package"]["sha256"]:
        raise ValueError("Package digest mismatch")
    with tarfile.open(package_path) as archive:
        members = archive.getmembers()
        if len(members) != len(manifest["sources"]) or {entry.name for entry in members} != set(manifest["sources"]):
            raise ValueError("Archive inventory mismatch")
        for member in members:
            if not member.isfile() or hashlib.sha256(archive.extractfile(member).read()).hexdigest() != manifest["sources"][member.name]:
                raise ValueError("Archive member mismatch")
    evidence_hashes = json.loads((evidence / "evidence-sha256.json").read_text(encoding="utf-8"))
    actual = {path.relative_to(evidence).as_posix(): digest(path) for path in evidence.rglob("*")
              if path.is_file() and path.name != "evidence-sha256.json"}
    if actual != evidence_hashes:
        raise ValueError("Evidence inventory/hash mismatch")
    summarize(evidence, persist=False)
    print(f"RELEASE VERIFIED: {len(manifest['sources'])} sources, {len(actual)} evidence files")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("curate", "summarize", "traceability", "package", "hash", "verify"))
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    if args.command == "curate":
        curate(args.raw, args.evidence)
    elif args.command == "summarize":
        summarize(args.evidence)
    elif args.command == "traceability":
        traceability(args.evidence)
    elif args.command == "package":
        print(package(args.evidence, args.output))
    elif args.command == "hash":
        write_json(args.evidence / "evidence-sha256.json", {path.relative_to(args.evidence).as_posix(): digest(path)
            for path in sorted(args.evidence.rglob("*")) if path.is_file() and path.name != "evidence-sha256.json"})
    elif args.command == "verify":
        verify(args.evidence, args.output)


if __name__ == "__main__":
    main()
