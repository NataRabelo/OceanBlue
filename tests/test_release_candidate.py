import json

import pytest

from scripts import release_candidate as release


def test_release_contains_runtime_entrypoint_and_locked_configuration():
    names = {path.relative_to(release.ROOT).as_posix() for path in release.source_files()}
    assert {"wsgi.py", "docker-entrypoint.sh", "Dockerfile", "requirements.txt", "VERSION", "compose.production.yml", "infra/production/nginx.conf"} <= names


def test_health_reports_packaged_release_version():
    from app import create_app

    client = create_app().test_client()
    for path in ("/api/health", "/health"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.json["version"] == (release.ROOT / "VERSION").read_text().strip()


@pytest.mark.parametrize("body", [
    '<testsuites><testsuite tests="0" /></testsuites>',
    '<testsuites><testsuite tests="1"><testcase classname="suite" name="case"><skipped /></testcase></testsuite></testsuites>',
    '<testsuites><testsuite tests="2"><testcase classname="suite" name="case"/><testcase classname="suite" name="case"/></testsuite></testsuites>',
    '<testsuites><testsuite tests="9"><testcase classname="suite" name="case"/></testsuite></testsuites>',
    '<testsuites><testsuite tests="1" errors="1"><testcase classname="suite" name="case"/></testsuite></testsuites>',
])
def test_release_rejects_incomplete_or_ambiguous_junit(tmp_path, body):
    path = tmp_path / "junit.xml"
    path.write_text(body)
    with pytest.raises(ValueError):
        release.cases(path)


def test_release_archive_is_reproducible_and_contains_only_expected_sources(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    version = root / "VERSION"
    version.write_text("2.1.0-rc.1\n")
    source = root / "example.py"
    source.write_text("release = True\n")
    monkeypatch.setattr(release, "ROOT", root)
    monkeypatch.setattr(release, "source_files", lambda: [version, source])
    evidence = tmp_path / "evidence"
    first = release.package(evidence, tmp_path / "first")
    second = release.package(evidence, tmp_path / "second")
    assert first.read_bytes() == second.read_bytes()
    manifest = json.loads((evidence / "release-manifest.json").read_text())
    assert set(manifest["sources"]) == {"VERSION", "example.py"}
    assert manifest["package"]["sha256"] == release.digest(first)


def test_release_retains_structured_evidence_without_success_trace_duplication(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "junit.xml").write_text("synthetic-junit")
    (raw / "trace.zip").write_bytes(b"synthetic-trace")
    (raw / "database.dump").write_bytes(b"synthetic-backup")
    destination = tmp_path / "evidence"
    release.curate(raw, destination)
    assert (destination / "junit.xml").read_text() == "synthetic-junit"
    assert not (destination / "trace.zip").exists()
    assert not (destination / "database.dump").exists()
    retention = json.loads((destination / "retention.json").read_text())
    assert {entry["path"] for entry in retention["omitted"]} == {"trace.zip", "database.dump"}
    assert (raw / "trace.zip").exists()
