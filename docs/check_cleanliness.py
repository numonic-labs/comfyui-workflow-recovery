#!/usr/bin/env python3
"""Fast heuristic pre-scan for the OSS-cleanliness gate (checks 1, 3, 6, 7).

NOT a replacement for the mandatory human `ip-disclosure-review` (gate check 5).
Exits non-zero if any heuristic check fails, so it can wire into CI.

Run from the repo root:  python docs/check_cleanliness.py
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files/dirs that ship in the package (what actually reaches installers).
SKIP_DIRS = {".git", ".github", "tests", "docs", "__pycache__", ".venv", "assets"}

# Internal identifiers that must NEVER ship. The PUBLIC product name "Numonic",
# the public api.numonic.ai host, and app.numonic.ai are explicitly allowed.
INTERNAL_PATTERNS = [
    (r"\bPlatform-Cap-\d+", "capability code"),
    (r"\btenant_id\b", "tenant id reference"),
    (r"3f1b0a13-64b8-4d4e", "CRM tenant UUID"),
    (r"gitlab\.com/numonic-labs", "internal GitLab path"),
    (r"/workspaces/codebase", "monorepo path"),
    (r"packages/extractors", "monorepo internal path"),
    (r"\bdv\.[a-z_]+_(hub|link|sat)\b", "Data Vault schema name"),
    (r"supabase\.co", "internal Supabase host"),
]

# Literal secret assignments (allow the word in comments/docstrings; flag only
# assignment to a non-empty literal or a Bearer literal).
SECRET_PATTERNS = [
    (r"(?i)(api_key|access_token|secret|password)\s*=\s*['\"][A-Za-z0-9_\-]{12,}['\"]", "hardcoded secret literal"),
    (r"Bearer\s+[A-Za-z0-9_\-]{16,}", "hardcoded bearer token"),
]

failures = []


def iter_shipped_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith((".pyc",)):
                continue
            yield os.path.join(dirpath, name)


def check_content():
    for path in iter_shipped_files():
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except (UnicodeDecodeError, OSError):
            continue
        rel = os.path.relpath(path, ROOT)
        for pattern, label in INTERNAL_PATTERNS:
            if re.search(pattern, text):
                failures.append(f"[internal-id] {rel}: {label} ({pattern})")
        for pattern, label in SECRET_PATTERNS:
            if re.search(pattern, text):
                failures.append(f"[secret] {rel}: {label}")


def check_license():
    lic = os.path.join(ROOT, "LICENSE")
    if not os.path.exists(lic):
        failures.append("[license] LICENSE file missing")
        return
    with open(lic, encoding="utf-8") as fh:
        text = fh.read()
    if "MIT License" not in text or "Numonic Labs" not in text:
        failures.append("[license] LICENSE is not MIT / Numonic Labs")


def check_readme_diff_section():
    readme = os.path.join(ROOT, "README.md")
    if not os.path.exists(readme):
        failures.append("[readme] README.md missing")
        return
    with open(readme, encoding="utf-8") as fh:
        text = fh.read().lower()
    if "how this differs" not in text:
        failures.append("[readme] missing 'How this differs' section")


def main():
    check_content()
    check_license()
    check_readme_diff_section()
    if failures:
        print("OSS-cleanliness pre-scan FAILED:")
        for f in failures:
            print("  -", f)
        print("\n(Reminder: this does not replace the mandatory ip-disclosure-review.)")
        return 1
    print("OSS-cleanliness pre-scan passed (heuristic checks 1, 3, 6, 7).")
    print("Still required before publish: human ip-disclosure-review (check 5).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
