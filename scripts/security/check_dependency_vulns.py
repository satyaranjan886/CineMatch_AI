#!/usr/bin/env python3
"""Dependency vulnerability gate for CI (Python + npm).

Fails on CRITICAL/HIGH findings unless they have a non-expired entry in
security/dependency-exceptions.yml. Moderate/low findings are printed but
do not fail the gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is in base requirements via django stack
    yaml = None


ROOT = Path(__file__).resolve().parents[2]
EXCEPTIONS_PATH = ROOT / "security" / "dependency-exceptions.yml"
REPORT_DIR = ROOT / "security" / "reports"


def _load_exceptions() -> dict:
    if yaml is None:
        raise SystemExit("PyYAML is required. Install project requirements or pyyaml.")
    if not EXCEPTIONS_PATH.is_file():
        raise SystemExit(f"Missing exceptions file: {EXCEPTIONS_PATH}")
    data = yaml.safe_load(EXCEPTIONS_PATH.read_text()) or {}
    return data


def _parse_expiry(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _active_exception_ids(entries: list[dict], *, today: date) -> set[str]:
    active: set[str] = set()
    expired: list[str] = []
    for entry in entries or []:
        vuln_id = str(entry.get("id", "")).strip()
        if not vuln_id:
            continue
        expires = _parse_expiry(entry.get("expires"))
        if expires is not None and expires < today:
            expired.append(f"{vuln_id} (expired {expires.isoformat()})")
            continue
        active.add(vuln_id)
    if expired:
        print("ERROR: dependency exceptions expired — renew or remediate:")
        for item in expired:
            print(f"  - {item}")
        raise SystemExit(2)
    return active


def _normalize_severity(value: str | None) -> str:
    return (value or "unknown").strip().lower()


def _write_report(name: str, payload: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / name
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def check_python(*, requirements: Path) -> int:
    exceptions = _load_exceptions()
    fail_severities = {
        _normalize_severity(s) for s in exceptions.get("policy", {}).get("fail_severities", ["critical", "high"])
    }
    allowed = _active_exception_ids(exceptions.get("python") or [], today=date.today())

    cmd = [
        sys.executable,
        "-m",
        "pip_audit",
        "-r",
        str(requirements),
        "--format",
        "json",
        "--progress-spinner",
        "off",
    ]
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    raw = proc.stdout.strip() or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print(proc.stdout)
        print(proc.stderr)
        print("ERROR: pip-audit did not return JSON")
        return 1

    report_path = _write_report("pip-audit.json", payload)
    print(f"Wrote {report_path.relative_to(ROOT)}")
    if proc.stderr.strip():
        # Cache warnings are noisy but harmless.
        for line in proc.stderr.splitlines():
            if "Failed to write to cache" in line:
                continue
            print(line)

    findings: list[dict] = []
    for dep in payload.get("dependencies") or []:
        for vuln in dep.get("vulns") or []:
            severity = _normalize_severity(vuln.get("severity") or "high")
            # pip-audit/OSV often omits severity; treat unknown advisory hits as high.
            if severity == "unknown":
                severity = "high"
            findings.append(
                {
                    "ecosystem": "python",
                    "package": dep.get("name"),
                    "version": dep.get("version"),
                    "id": vuln.get("id"),
                    "aliases": vuln.get("aliases") or [],
                    "fix_versions": vuln.get("fix_versions") or [],
                    "severity": severity,
                }
            )

    return _evaluate_findings(findings, allowed=allowed, fail_severities=fail_severities, label="Python")


def check_npm(*, frontend_dir: Path) -> int:
    exceptions = _load_exceptions()
    fail_severities = {
        _normalize_severity(s) for s in exceptions.get("policy", {}).get("fail_severities", ["critical", "high"])
    }
    allowed = _active_exception_ids(exceptions.get("npm") or [], today=date.today())

    cmd = ["npm", "audit", "--omit=dev", "--json"]
    print(f"$ {' '.join(cmd)}  (cwd={frontend_dir})")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=frontend_dir)
    raw = proc.stdout.strip() or "{}"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print(proc.stdout)
        print(proc.stderr)
        print("ERROR: npm audit did not return JSON")
        return 1

    report_path = _write_report("npm-audit.json", payload)
    print(f"Wrote {report_path.relative_to(ROOT)}")

    findings: list[dict] = []
    vulns = payload.get("vulnerabilities") or {}
    for package, info in vulns.items():
        for via in info.get("via") or []:
            if not isinstance(via, dict):
                continue
            advisory_url = str(via.get("url") or "")
            advisory_id = advisory_url.rstrip("/").split("/")[-1] if advisory_url else ""
            if not advisory_id.startswith("GHSA-"):
                # Fall back to numeric source id as string for visibility.
                advisory_id = str(via.get("source") or package)
            severity = _normalize_severity(via.get("severity") or info.get("severity"))
            findings.append(
                {
                    "ecosystem": "npm",
                    "package": via.get("name") or package,
                    "version": info.get("range"),
                    "id": advisory_id,
                    "title": via.get("title"),
                    "severity": severity,
                    "url": advisory_url,
                }
            )

    return _evaluate_findings(findings, allowed=allowed, fail_severities=fail_severities, label="npm")


def _evaluate_findings(
    findings: list[dict],
    *,
    allowed: set[str],
    fail_severities: set[str],
    label: str,
) -> int:
    if not findings:
        print(f"{label}: no known vulnerabilities reported.")
        return 0

    print(f"\n{label} findings ({len(findings)}):")
    print(f"{'Severity':<10} {'Package':<20} {'ID':<36} Status")
    print("-" * 90)

    blocking: list[dict] = []
    for finding in sorted(findings, key=lambda item: (item["severity"], item["package"], item["id"])):
        vuln_id = str(finding["id"])
        severity = finding["severity"]
        if severity in fail_severities and vuln_id not in allowed:
            status = "FAIL"
            blocking.append(finding)
        elif vuln_id in allowed:
            status = "EXCEPTION"
        else:
            status = "report-only"
        print(f"{severity:<10} {str(finding['package']):<20} {vuln_id:<36} {status}")

    if blocking:
        print(f"\n{label}: {len(blocking)} CRITICAL/HIGH finding(s) without an active exception.")
        print("Remediate the packages or add a dated exception in security/dependency-exceptions.yml")
        print("Update security/dependency-exceptions.yml if accepting residual risk.")
        return 1

    excepted = sum(1 for f in findings if str(f["id"]) in allowed)
    print(f"\n{label}: gate passed ({excepted} excepted, none blocking).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        choices=["python", "npm", "all"],
        help="Which ecosystem to scan",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=ROOT / "requirements" / "prod.txt",
        help="Python requirements file for pip-audit",
    )
    parser.add_argument(
        "--frontend-dir",
        type=Path,
        default=ROOT / "frontend",
        help="Frontend directory containing package-lock.json",
    )
    args = parser.parse_args(argv)

    codes: list[int] = []
    if args.target in {"python", "all"}:
        codes.append(check_python(requirements=args.requirements))
    if args.target in {"npm", "all"}:
        codes.append(check_npm(frontend_dir=args.frontend_dir))
    return 1 if any(codes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
