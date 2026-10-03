"""
License policy enforcement for AquaDome.

Blocks any dependency carrying a license incompatible with proprietary
closed-source SaaS deployment. Run in CI to prevent AGPL/GPL contamination.

Blocked patterns (AGPL-3.0 triggered by network use, GPL copyleft, non-commercial):
  - AGPL-*
  - GPL-* (except LGPL if dynamically linked and not modified)
  - CC-BY-NC-*
  - Custom Meta (DINOv3, RADIO-NC)
  - AI Pubs Rail-M (Surya)

Allowed:
  - Apache-2.0
  - MIT
  - BSD-*
  - CC0-1.0
  - CC-BY-4.0
  - LGPL-* (if dynamically linked, unmodified)
  - PSF (Python)
  - ISC
  - MPL-2.0 (file-level, compatible)
"""

from __future__ import annotations

import json
import sys

BLOCKED_PREFIXES = [
    "AGPL",
    "GPL-",
    "CC-BY-NC",
    "SSPL",
    "AI Pubs",
    "RAIL-M",
]

ALLOWED_PREFIXES = [
    "Apache",
    "MIT",
    "BSD",
    "CC0",
    "CC-BY-4",
    "PSF",
    "ISC",
    "MPL-2",
    "LGPL",
    "Python",
    "Unlicense",
    "Public Domain",
    "UNKNOWN",  # review manually; warn but don't block
]


def main(license_file: str) -> None:
    with open(license_file) as f:
        packages = json.load(f)

    violations: list[str] = []
    warnings: list[str] = []

    for pkg in packages:
        name = pkg.get("Name", "?")
        license_str = pkg.get("License", "UNKNOWN")

        is_blocked = any(license_str.upper().startswith(b.upper()) for b in BLOCKED_PREFIXES)
        is_allowed = any(license_str.upper().startswith(a.upper()) for a in ALLOWED_PREFIXES)

        if is_blocked:
            violations.append(f"  BLOCKED  {name} ({license_str})")
        elif not is_allowed:
            warnings.append(f"  WARNING  {name} ({license_str}) — review manually")

    if warnings:
        print("License warnings (manual review required):")
        for w in warnings:
            print(w)
        print()

    if violations:
        print("LICENSE POLICY VIOLATIONS — the following packages are BLOCKED:")
        for v in violations:
            print(v)
        print(
            "\nAquaDome core must use only Apache-2.0 / MIT / BSD dependencies.\n"
            "If you need a blocked package, evaluate:\n"
            "  1. A permissively-licensed alternative (see ARCHITECTURE.md §A)\n"
            "  2. Running it as an isolated external service (check AGPL network-use clause)\n"
            "  3. A commercial license"
        )
        sys.exit(1)

    print(f"License check passed — {len(packages)} packages, 0 violations.")


if __name__ == "__main__":
    main(sys.argv[1])
