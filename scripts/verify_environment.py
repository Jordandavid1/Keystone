#!/usr/bin/env python3
"""
KEYSTONE Composite Environment Verification Probe
Adheres to:
  - managing-python-dependencies skill: bundled single-step environment and package probe,
    dependency manager detection, and virtual environment awareness.
  - sysadmin-guardrails skill: non-destructive pre-flight checks, command safety validation,
    idempotent execution, and baseline invariant preservation.
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import platform
import argparse
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Ensure UTF-8 output even on legacy Windows code pages
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

REQUIRED_DEPENDENCIES = [
    'fastapi',
    'uvicorn',
    'pydantic',
    'pytest',
    'cryptography'
]

BASELINE_MANIFEST_PATH = Path('docs/FILE_MANIFEST.txt')


def check_python_runtime() -> Dict[str, Any]:
    """Probes Python executable, version, and virtual environment isolation."""
    in_venv = (
        sys.prefix != getattr(sys, 'base_prefix', sys.prefix)
        or hasattr(sys, 'real_prefix')
        or bool(os.environ.get('VIRTUAL_ENV'))
    )
    return {
        'executable': sys.executable,
        'version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        'is_venv_active': in_venv,
        'sys_prefix': sys.prefix,
        'base_prefix': getattr(sys, 'base_prefix', sys.prefix),
        'virtual_env_env_var': os.environ.get('VIRTUAL_ENV')
    }


def detect_dependency_manager(project_root: Path) -> Dict[str, Any]:
    """
    Detects project dependency manager in priority order per managing-python-dependencies skill:
    1. uv (uv.lock / pyproject.toml [tool.uv])
    2. Poetry (pyproject.toml [tool.poetry])
    3. Pipenv (Pipfile)
    4. Conda (environment.yml)
    5. venv + pip (requirements.txt)
    6. default fallback: venv + pip
    """
    signals = [
        ('uv', project_root / 'uv.lock'),
        ('Poetry', project_root / 'poetry.lock'),
        ('Pipenv', project_root / 'Pipfile'),
        ('Conda', project_root / 'environment.yml'),
        ('venv+pip', project_root / 'requirements.txt')
    ]

    detected_manager = 'venv+pip (default)'
    detected_signal = None

    for name, path in signals:
        if path.exists():
            detected_manager = name
            detected_signal = str(path)
            break

    # Also check pyproject.toml if present
    pyproject = project_root / 'pyproject.toml'
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding='utf-8')
            if '[tool.uv]' in content:
                detected_manager = 'uv'
                detected_signal = str(pyproject)
            elif '[tool.poetry]' in content:
                detected_manager = 'Poetry'
                detected_signal = str(pyproject)
        except Exception:
            pass

    return {
        'detected_manager': detected_manager,
        'signal_file': detected_signal,
        'has_requirements_txt': (project_root / 'requirements.txt').exists()
    }


def probe_packages(package_list: List[str]) -> Dict[str, Dict[str, Any]]:
    """Probes availability and installed versions of required dependencies."""
    results = {}
    for pkg in package_list:
        spec = importlib.util.find_spec(pkg)
        if spec is not None:
            try:
                mod = __import__(pkg)
                ver = getattr(mod, '__version__', 'installed')
                results[pkg] = {'installed': True, 'version': str(ver), 'location': getattr(mod, '__file__', 'built-in')}
            except Exception as e:
                results[pkg] = {'installed': True, 'version': 'import_error', 'error': str(e)}
        else:
            results[pkg] = {'installed': False, 'version': None}
    return results


def check_preflight_resources(project_root: Path) -> Dict[str, Any]:
    """Performs read-only pre-flight checks on storage, OS, and user permissions."""
    total, used, free = shutil.disk_usage(str(project_root))
    free_gb = round(free / (1024 ** 3), 2)
    used_gb = round(used / (1024 ** 3), 2)
    total_gb = round(total / (1024 ** 3), 2)

    return {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'current_working_directory': str(project_root.resolve()),
        'disk_space': {
            'total_gb': total_gb,
            'used_gb': used_gb,
            'free_gb': free_gb,
            'sufficient_free_space': free_gb > 1.0
        }
    }


def validate_sysadmin_command_safety(command: str) -> Tuple[bool, List[str]]:
    """Validates commands against prohibited destructive patterns per sysadmin guardrails."""
    lower = command.lower()
    violations = []

    if 'rm -rf' in lower or ('remove-item' in lower and '-recurse' in lower and '-force' in lower):
        violations.push if hasattr(violations, 'push') else violations.append(
            'DESTRUCTIVE_COMMAND_PROHIBITED: Recursive force removal requires explicit confirmation.'
        )
    if 'drop table' in lower or 'drop schema' in lower or 'truncate table' in lower:
        violations.append('DATA_LOSS_RISK: Broad database drop or truncate is prohibited.')
    if 'pip install' in lower and '.venv' not in lower and 'python -m pip' not in lower:
        violations.append('GLOBAL_PIP_PROHIBITED: Must use project virtual environment.')

    return len(violations) == 0, violations


def validate_powershell_non_interactive(command: str) -> Dict[str, bool]:
    """Validates that PowerShell commands include -NoProfile and -NonInteractive flags."""
    if command.startswith('powershell') or command.startswith('pwsh'):
        has_no_profile = '-NoProfile' in command
        has_non_interactive = '-NonInteractive' in command
        return {
            'compliant': has_no_profile and has_non_interactive,
            'has_no_profile': has_no_profile,
            'has_non_interactive': has_non_interactive
        }
    return {'compliant': True, 'has_no_profile': True, 'has_non_interactive': True}


def verify_baseline_immutability(project_root: Path) -> Dict[str, Any]:
    """Verifies that the 21 baseline tracked files cataloged in FILE_MANIFEST.txt are present."""
    manifest_file = project_root / BASELINE_MANIFEST_PATH
    if not manifest_file.exists():
        return {
            'manifest_found': False,
            'tracked_count': 0,
            'all_present': False,
            'missing': ['docs/FILE_MANIFEST.txt']
        }

    lines = [
        line.strip().replace('./', '').replace('/', os.sep)
        for line in manifest_file.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]

    missing = []
    for rel_path in lines:
        target = project_root / rel_path
        if not target.exists():
            missing.append(rel_path)

    return {
        'manifest_found': True,
        'tracked_count': len(lines),
        'all_present': len(missing) == 0,
        'missing': missing
    }


def run_full_probe(project_root: Path) -> Dict[str, Any]:
    """Runs composite bundled environment probe."""
    runtime = check_python_runtime()
    dep_mgr = detect_dependency_manager(project_root)
    packages = probe_packages(REQUIRED_DEPENDENCIES)
    preflight = check_preflight_resources(project_root)
    baseline = verify_baseline_immutability(project_root)

    # Test safety checks on standard commands
    safety_tests = [
        ('rm -rf /var/cache', False),
        ('powershell -Command Remove-Item -Recurse -Force ./data', False),
        ('DROP TABLE keystone_intelligence.scraped_architectures;', False),
        ('pip install google-cloud-bigquery', False),
        ('git status', True),
        ('npm test', True),
        ('.venv/Scripts/pip install -r requirements.txt', True)
    ]
    safety_results = []
    for cmd, expected_safe in safety_tests:
        is_safe, violations = validate_sysadmin_command_safety(cmd)
        safety_results.append({
            'command': cmd,
            'safe': is_safe,
            'expected_safe': expected_safe,
            'passed': is_safe == expected_safe,
            'violations': violations
        })

    all_safety_passed = all(r['passed'] for r in safety_results)
    all_packages_installed = all(info['installed'] for info in packages.values())

    overall_status = 'PASS' if (all_safety_passed and baseline['all_present']) else 'FAIL'

    return {
        'status': overall_status,
        'timestamp': datetime_now_iso(),
        'python_runtime': runtime,
        'dependency_manager': dep_mgr,
        'package_availability': packages,
        'preflight_resources': preflight,
        'baseline_manifest': baseline,
        'sysadmin_safety_tests': {
            'all_passed': all_safety_passed,
            'results': safety_results
        },
        'summary': {
            'python_version': runtime['version'],
            'virtual_environment_active': runtime['is_venv_active'],
            'dependency_manager': dep_mgr['detected_manager'],
            'packages_installed_count': f"{sum(1 for p in packages.values() if p['installed'])}/{len(REQUIRED_DEPENDENCIES)}",
            'baseline_files_intact': f"{baseline['tracked_count'] - len(baseline['missing'])}/{baseline['tracked_count']}",
            'sysadmin_guardrails_passed': all_safety_passed
        }
    }


def datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description="KEYSTONE Composite Environment Verification Probe")
    parser.add_argument('--json', action='store_true', help="Output machine-readable JSON report")
    parser.add_argument('--strict', action='store_true', help="Exit with non-zero code if venv is inactive or packages missing")
    parser.add_argument('--root', default='.', help="Project root directory path")
    args = parser.parse_args()

    project_root = Path(args.root).resolve()
    report = run_full_probe(project_root)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 80)
        print("  KEYSTONE COMPOSITE ENVIRONMENT VERIFICATION PROBE")
        print("  Authoritative Guardrails: managing-python-dependencies & sysadmin-guardrails")
        print("=" * 80)
        print()
        print(f"Timestamp:       {report['timestamp']}")
        print(f"Platform:        {report['preflight_resources']['platform']} ({report['preflight_resources']['architecture']})")
        print(f"Disk Free:       {report['preflight_resources']['disk_space']['free_gb']} GB")
        print(f"Python Exec:     {report['python_runtime']['executable']}")
        print(f"Python Version:  {report['python_runtime']['version']}")
        print(f"Virtual Env:     {'ACTIVE' if report['python_runtime']['is_venv_active'] else 'INACTIVE / HOST'}")
        print(f"Dependency Mgr:  {report['dependency_manager']['detected_manager']}")
        print()
        print("-" * 80)
        print("  LOCKED DEPENDENCIES AVAILABILITY (requirements.txt)")
        print("-" * 80)
        for pkg, info in report['package_availability'].items():
            status_mark = "[FOUND]" if info['installed'] else "[MISSING]"
            ver = info.get('version') or 'N/A'
            print(f"  {status_mark:10} {pkg:18} version: {ver}")
        print()
        print("-" * 80)
        print("  SYSADMIN GUARDRAILS & SAFETY TEST SUITE")
        print("-" * 80)
        for t in report['sysadmin_safety_tests']['results']:
            mark = "[PASS]" if t['passed'] else "[FAIL]"
            safe_str = "SAFE" if t['safe'] else "PROHIBITED"
            print(f"  {mark:8} [{safe_str:10}] {t['command']}")
        print()
        print("-" * 80)
        print("  BASELINE INVARIANT PRESERVATION (FILE_MANIFEST.txt)")
        print("-" * 80)
        b = report['baseline_manifest']
        b_mark = "ALL INTACT" if b['all_present'] else f"{len(b['missing'])} MISSING"
        print(f"  Tracked Files: {b['tracked_count']} files verified ([{b_mark}])")
        if b['missing']:
            for m in b['missing']:
                print(f"    Missing: {m}")
        print()
        print("=" * 80)
        print(f"  PROBE VERDICT: {report['status']}")
        print("=" * 80)

    # Determine exit code
    if report['status'] != 'PASS':
        sys.exit(1)
    if args.strict:
        if not report['python_runtime']['is_venv_active']:
            print("\nSTRICT MODE ERROR: Virtual environment is not currently active.", file=sys.stderr)
            sys.exit(2)
        missing_pkgs = [p for p, info in report['package_availability'].items() if not info['installed']]
        if missing_pkgs:
            print(f"\nSTRICT MODE ERROR: Missing required dependencies: {missing_pkgs}", file=sys.stderr)
            sys.exit(3)

    sys.exit(0)


if __name__ == '__main__':
    main()
