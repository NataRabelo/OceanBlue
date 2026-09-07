# Sprint 7 — supply-chain audit

Base: `7b0c97f87ec8cf1a9584c389717383c457bc764f`. No commit, application change, business provider, business environment, database connection or full regression belongs to this audit. Release assembly and full regression belong to the parent runner; `Dockerfile.test` belongs to the browser agent.

**Final frozen-source scan:** the parent reran the complete script after all UI corrections, including decimal focus, Nova Role readiness and transient-toast observation, from `2026-09-07T16:09:10-03:00` to `16:13:02-03:00`. `summary.json` reports `passed_with_historical_review`; `gitleaks-review.json` binds all 339 candidate files outside `docs/` and the scan artifacts. All ten current-source detections match individually reviewed synthetic fixture lines; 19,698 historical-evidence detections remain explicitly review-required, not certified secret-free. Python production/development and npm advisory gates passed, together with hashed installs and the SBOM checks. The final complete regression began only afterward; assembly also requires its complete independent retest. Earlier source corrections caused verify-only to reject stale scans, recorded in `../failed-candidate/stale-scan-rejected.json`, `../visual-rejected-candidate/stale-scan-rejected.json`, `../pdv-rejected-candidate/stale-scan-rejected.txt`, `../decimal-focus-rejected-candidate/stale-scan-rejected.txt` and `../role-readiness-rejected-candidate/stale-scan-rejected.txt`. Earlier concurrent edits correctly caused incomplete scans rather than stale approval; `gitleaks-initial-triage.json` and `runner-checks.json` preserve the preparation/negative controls. Assembly repeats verify-only against the unchanged candidate.

## Confirmed dependency defects and fixes

Actual `pip-audit` against the original locks reported 5 vulnerability records in production and 13 in development. The development response repeats `PYSEC-2026-196`; this is 12 unique advisory IDs, not 13 distinct vulnerabilities. Findings establish vulnerable package versions, not successful exploitation of OceanBlue.

| Dependency | Before | After | Scope and reason |
| --- | --- | --- | --- |
| Flask | 3.0.3 | 3.1.3 | Both; CVE-2026-27205, session access / cache variation |
| gunicorn | 21.2.0 | 23.0.0 | Both; CVE-2024-1135 and CVE-2024-6827, HTTP request smuggling |
| marshmallow | 3.19.0 | 3.26.2 | Both; CVE-2025-68480, collection deserialization denial of service; stays on major 3 |
| python-dotenv | 1.0.1 | 1.2.2 | Both; CVE-2026-28684, symlink-sensitive environment-file rewriting |
| pip | 25.0.1 in dev and bundled base | 26.2.1 | Upgraded in dev; newly pinned in production to replace bundled pip during the hashed production install |
| pytest | 8.3.5 | 9.0.3 | Dev; CVE-2025-71176, temporary-directory handling on Unix |
| pip-tools | 7.4.1 | 7.6.1 | Dev; compiler compatibility with the fixed pip; no scanner vulnerability claimed for pip-tools |
| Pygments | absent | 2.21.0 | New dev transitive dependency of pytest |

Pip advisory aliases: CVE-2026-8643, CVE-2025-8869, CVE-2026-1703, CVE-2026-3219, CVE-2026-6357 and CVE-2026-13346. The fallback-tar extraction advisory explicitly depends on Python versions without PEP 706; the pinned Python 3.12 environment already provides that mitigation. Pip was nevertheless upgraded for the other actionable advisories. Exact scanner IDs, fixes and dependency deltas are retained in `dependency-deltas.json` and the baseline scan JSONs.

Final inventories contain **28 production and 41 development packages**, compared with 27 and 40 at base. Playwright remains 1.55.0. No npm pins change. Both final Python lock scans report zero known vulnerabilities; `npm audit` reports zero. The production and development inventories, audit targets and CycloneDX components are checked for exact name/version equality to their respective locks.

## Reproduction and runner contract

Run with host Python 3.12+ and an available Docker daemon. The host script uses only Python's standard library. Registry access is needed for public tool/package downloads and vulnerability databases; Gitleaks itself runs with `--network none`.

```text
python scripts/release_supply_chain.py --output-dir docs/evidencias/producao/sprint-07-execucao/supply-chain
python scripts/release_supply_chain.py --output-dir docs/evidencias/producao/sprint-07-execucao/supply-chain --verify-only
python scripts/release_supply_chain.py --output-dir docs/evidencias/producao/sprint-07-execucao/supply-chain --npm-sbom-only
```

The first command performs fresh scans and automatically reviews exact known fixture lines. Run it in the full runner **after source freeze and before tests**; a new evidence directory requires this full command. Assemble calls the second command. `--verify-only` performs integrity checks only and cannot create or refresh a scan. `--root PATH` supports another checkout. `--expected-lock-digest SHA256` rejects an unexpected input/lock state before downloads.

The third command performs only offline npm SBOM/inventory generation and exact lock/integrity checks; it does not rerun pip-audit, npm audit, Gitleaks or regression, and cannot refresh/approve the overall summary. The full runner includes this same npm step automatically and hashes all three npm inventory/SBOM artifacts. Verify-only rejects summaries missing those artifacts.

The combined digest covers raw bytes of both `.in` files, both Python locks, `package.json`, and `package-lock.json`: SHA256 of the compact, key-sorted JSON map from filename to raw-file SHA256. This audit's digest is `3e67c5a607f4ea66ee53fd74911cea2b9528e64a4657e2870b60366adb4ef5e2`.

- Exit **0**: dependency and current-source gates passed; `passed_with_historical_review` can still require historical evidence review. This does not mean zero secrets overall.
- Exit **1**: a dependency vulnerability or an unclassified current-source secret finding remains.
- Exit **2**: scanner failure, incomplete collection, installation/SBOM mismatch, changed source, or digest/integrity error.

Tools are isolated from the application: Python 3.12.12 on the repository's digest-pinned Debian bookworm image; pip 26.2.1; pip-tools 7.6.1; pip-audit 2.10.1; cyclonedx-bom 7.3.1; Node 22.19.0 / npm 10.9.3; Gitleaks 8.30.1. Image digests, complete installed Python tool versions, timestamps and actual command exit codes are in `summary.json` and `python-verification.json`.

Locks were regenerated in that Python image with pip 26.2.1 / pip-tools 7.6.1, preserving unaffected existing pins:

```text
pip-compile --quiet --generate-hashes --allow-unsafe --strip-extras --resolver=backtracking --index-url=https://pypi.org/simple --output-file=requirements.txt requirements.in
pip-compile --quiet --generate-hashes --allow-unsafe --strip-extras --resolver=backtracking --index-url=https://pypi.org/simple --output-file=requirements-dev.txt requirements-dev.in
```

Fresh isolated virtual environments install each lock with `--require-hashes --only-binary=:all:`, followed by `pip check`. `installed-artifacts-*.json` retains the downloaded wheel URLs and verified hashes. This validates Linux amd64 / CPython 3.12; other operating systems, marker branches and architectures were not installation-tested. Application compatibility and pytest-major-version regression remain the parent/browser gates.

## Secret scanner scope and review

Gitleaks scans a temporary independent-copy snapshot selected by `git ls-files --cached --others --exclude-standard`. This includes tracked historical evidence and current nonignored untracked candidate files. Git-ignored `.release-work`, generated `dist` archives, tools, dumps and traces are excluded, as is the active output directory. Ignored packaged artifacts require the parent's separate manifest verification. This is a working-checkout audit, **not a full filesystem or Git-history scan**. Archive and decode depth are both limited to 2, and default scanner rules/allowlists still apply.

All scanner findings are redacted at 100%. Raw scanner output stays in ignored `.release-work/supply-chain/`; committed candidates contain scope/rule aggregates, unique-path/fingerprint counts and a few representatives with literal `REDACTED`, plus every current-source finding individually. No credential values are retained in compact reports.

The initial archive-inclusive scan returned 19,674 records, including 10 source findings in isolated Compose, startup/smoke validation scripts and mocked tests. These 10 were reviewed as synthetic fixtures. Their precise per-file **line SHA256** and rule are declared in `REVIEWED_FIXTURE_LINES` in the script; shifted lines remain recognizable, changed content does not. No entire test/script path is accepted automatically. Current run counts and all individual decisions are in `gitleaks-redacted.json`.

The retained initial aggregate covers 399 unique paths and 13,257 unique fingerprints: 6,779 generic-key and 12,895 JWT records. The other 19,664 historical records retain review-required status. The initial triage is explicitly not an accepted final-state review; a successful frozen replay creates `gitleaks-redacted.json` and its bound review.

`gitleaks-review.json` binds the review to the compact scanner artifact, raw redacted report digest, and full non-document source hashes from the **staged bytes**. Staged hashes must match the checkout before scanning, and both staged and checkout hashes must remain unchanged afterward. Verify-only checks the artifact hashes, review bindings, current source hashes, dependency gate and absence of unclassified source findings. Unknown findings fail until individually investigated; replay does not blanket-accept new credentials.

Historical browser traces contain locally issued test JWTs; source manifests also produce generic-key/hash false positives. Historical records are grouped as `historical_evidence_requires_review`, not exhaustively certified synthetic and not automatically approved for publication. No real application credential was confirmed in reviewed current-source findings. No provider was contacted to test credential validity. Historical findings are deliberately not turned into a claim of an overall zero-secret checkout.

## SBOM, licenses and remaining coverage

`sbom-prod.cdx.json` and `sbom-dev.cdx.json` are CycloneDX 1.6 JSON generated by `cyclonedx-py environment --validate`. Their component inventories are checked against the exact hash-installed locks. They represent Python distributions, including the pinned pip, and are not complete container/OS/browser/native-library SBOMs.

`licenses-*.json` records installed distribution license expressions, legacy license values/classifiers and declared license files; `license-review.json` reports missing metadata and copyleft metadata needing notice review. `psycopg2-binary` declares **LGPL with exceptions**. Other declarations include MIT/MIT-0, BSD variants, Apache-2.0 and PSF-2.0, with dual expressions for cryptography and packaging. Metadata review is not legal approval or an exhaustive check of bundled libpq, OpenSSL, pip-vendored libraries, or notice redistribution.

The npm/UI dependency inventory is also included: **76 locked package locations and 76 matching CycloneDX 1.5 components** in `sbom-npm.cdx.json`, with metadata in `npm-inventory-licenses.json`. Licenses are MIT (64), ISC (8), Apache-2.0 (2), BSD-3-Clause (1) and MPL-2.0 (1); none lack lockfile license metadata. This covers all lockfile development, optional and peer dependencies, not installed `node_modules` or the contents of generated browser assets. `npm-sbom-verification.json` records the original manifest/lock SHA256, pinned image/tool versions, exact command, successful exit, artifact hashes and checks for every package path/name/version, every lock integrity hash and all dependency references.

Generation actually succeeded without networking, using the digest-pinned Node 22.19.0 / npm 10.9.3 image and `npm sbom --sbom-format cyclonedx --package-lock-only --offline --ignore-scripts --include=dev --include=optional --include=peer`. npm initially rejected the unversioned private root with `EINVALIDPURLTYPE`. The script therefore supplies `0.0.0` only in temporary copies of the two root metadata records, proves every locked dependency entry is unchanged, and removes that placeholder version/PURL from the delivered root component. It restores the real project name and rewrites root dependency references to a stable unversioned identifier; repository manifests and dependency digests remain unchanged. The npm SBOM receives structural/reference/inventory checks, **not an independent CycloneDX schema validation claim**. The final full frozen-source scan repeated this generation and validation.

**OS CVEs: not scanned.** The parent actually tried Docker Scout **1.24.0** against the public local Python base; Scout refused without authentication. No CVE report was generated and no account was changed. The exact probe is in `../image-scan-limit.json` and copied into the summary when available. There is no claim of zero Debian, CPython, embedded-library or browser CVEs. No alternate OS scanner was pursued while final gates were pending.

Scanner methodology: [pip-audit](https://github.com/pypa/pip-audit), [pip-tools](https://pypi.org/project/pip-tools/), [Gitleaks](https://github.com/gitleaks/gitleaks). Advisory results are point-in-time database observations, not malware detection or proof of absence of unknown vulnerabilities.
