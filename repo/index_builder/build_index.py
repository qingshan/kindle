#!/usr/bin/env python3
"""Write repo/index.html from manifest.v2.json."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

KPM_MANIFEST_VERSION = 2
ROOT = Path(__file__).resolve().parent.parent
BUILDER = Path(__file__).resolve().parent


def valid_package_id(package_id: str) -> bool:
    return bool(package_id) and all(
        ch.islower() and (ch.isalnum() or ch in "-_") for ch in package_id
    )


def main() -> None:
    config = tomllib.loads((BUILDER / "config.toml").read_text())
    manifest = json.loads((ROOT / "manifest.v2.json").read_text())

    version = manifest.get("manifest_version")
    if version != KPM_MANIFEST_VERSION:
        sys.exit(f"error: expected manifest version {KPM_MANIFEST_VERSION}, got {version}")

    repo_id = manifest.get("id", "")
    if " " in repo_id or not repo_id.isalnum():
        sys.exit(f"error: repository id must be alphanumeric with no spaces: {repo_id!r}")

    packages = manifest.get("packages")
    if not isinstance(packages, dict):
        sys.exit("error: manifest packages must be an object")
    for package_id in packages:
        if not valid_package_id(package_id):
            sys.exit(f"error: package id must be lowercase [a-z0-9_-]: {package_id!r}")

    env = Environment(
        loader=FileSystemLoader(BUILDER / "templates"),
        autoescape=select_autoescape(),
    )
    html = env.get_template("index.html").render(
        {
            "manifest": manifest,
            "show_url": config["show_url"],
            "url": config["url"],
            "package_ids": sorted(packages),
            "is_empty": len(packages) == 0,
        }
    )
    if not html.endswith("\n"):
        html += "\n"
    (ROOT / "index.html").write_text(html)


if __name__ == "__main__":
    main()
