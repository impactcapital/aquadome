#!/usr/bin/env python3
"""
License policy enforcement — run in CI to block copyleft/non-commercial deps.
Usage: python scripts/check_licenses.py licenses.json
licenses.json produced by: pip-licenses --format=json --output-file=licenses.json

Blocked licenses (copyleft / non-commercial — incompatible with proprietary SaaS):
  AGPL-*          — triggers on network use (SaaS = distribution)
  GPL-2, GPL-3    — strong copyleft
  GNU General Public / GNU Affero — covers alternate license strings
  LGPL            — weak copyleft; safe only for dynamically linked unmodified libs,
                    but pip-licenses can't distinguish static vs dynamic — block by default
  SSPL            — Server Side Public License (MongoDB) — AGPL-like for SaaS
  CC-BY-NC-*      — non-commercial clause incompatible with commercial SaaS
  Rail-M          — AI Pubs Responsible AI License, usage-restricted

Allowed (permissive / commercial):
  Apache-2.0, MIT, BSD-*, PSF, ISC, MPL-2.0 (file-level), CC0-1.0, CC-BY-4.0
"""

import json
import sys

BLOCKED_PATTERNS = [
    "AGPL",
    "GPL-2",
    "GPL-3",
    "GNU General Public",
    "GNU Affero",
    "LGPL",
    "SSPL",
    "CC-BY-NC",
    "Rail-M",
]

ALLOWLISTED_PACKAGES: dict[str, str] = {
    # packages where pip-licenses mis-reports the license — manually verified OK
    # Example: "some-package": "Apache-2.0 (mis-reported as LGPL by pip-licenses)"
}


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "licenses.json"
    with open(path) as f:
        packages = json.load(f)

    violations: list[str] = []
    warnings: list[str] = []

    for pkg in packages:
        name = pkg.get("Name", "")
        license_str = pkg.get("License", "")

        if name in ALLOWLISTED_PACKAGES:
            continue

        blocked = False
        for pattern in BLOCKED_PATTERNS:
            if pattern.lower() in license_str.lower():
                violations.append(f"  {name} ({license_str})")
                blocked = True
                break

        if not blocked and license_str in ("UNKNOWN", "", "UNKNOWN;"):
            warnings.append(f"  WARNING  {name} ({license_str!r}) — review manually")

    if warnings:
        print("License warnings (unknown license — manual review required):")
        for w in warnings:
            print(w)
        print()

    if violations:
        print(f"LICENSE POLICY VIOLATION — {len(violations)} blocked package(s):\n")
        for v in violations:
            print(v)
        print("\nSee README §License policy. Do NOT add AGPL/GPL/copyleft deps to core.")
        print(
            "\nIf you need a blocked package, evaluate:\n"
            "  1. A permissively-licensed alternative (see ARCHITECTURE.md §A)\n"
            "  2. Running it as an isolated external service\n"
            "  3. A commercial license"
        )
        sys.exit(1)

    print(f"License check passed — {len(packages)} packages scanned, 0 violations.")


if __name__ == "__main__":
    main()
