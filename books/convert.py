#!/usr/bin/env python3
"""Convert ebooks to AZW3 with Calibre's ebook-convert.

Native Kindle formats (.azw, .azw3, .mobi, .pdf, .txt) are left as-is.
Other known ebook types are converted to a sibling .azw3 (skipped if it
already exists, unless --force). Unrelated files are left alone.

Usage:
    python3 books/convert.py --src article.epub
    python3 books/convert.py --dir ~/books
    python3 books/convert.py --src article.html --dst article.azw3 --title "…"
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

KINDLE_NATIVE_EXTS = {".azw", ".azw3", ".mobi", ".pdf", ".txt"}
# Formats Calibre can turn into AZW3. Anything else in the tree is not an ebook.
CONVERT_EXTS = {
    ".epub", ".html", ".htm", ".fb2", ".doc", ".docx", ".rtf", ".odt",
    ".djvu", ".cbz", ".cbr", ".lit", ".pdb", ".chm", ".lrf", ".prc",
}
SKIP_NAMES = {".ds_store", "thumbs.db", "opds.xml"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def ebook_convert() -> str:
    path = shutil.which("ebook-convert")
    if path is None:
        sys.exit(
            "error: ebook-convert not found in PATH.\n"
            "Install Calibre and make sure ebook-convert is on PATH."
        )
    return path


def convert_to_azw3(
    src: Path,
    dst: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    extra_args: list[str] | None = None,
) -> bool:
    """Convert src to dst (.azw3). Returns True if a file was written."""
    src = src.resolve()
    dst = dst.resolve()
    if dst.exists() and not force:
        log(f"skip {dst.name} (exists)")
        return False
    if src.suffix.lower() in KINDLE_NATIVE_EXTS:
        if src == dst:
            return False
        if dry_run:
            log(f"[dry-run] would copy {src} -> {dst}")
            return True
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log(f"copied {src.name} -> {dst.name}")
        return True
    if dry_run:
        log(f"[dry-run] would convert {src} -> {dst}")
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ebook_convert(), str(src), str(dst)]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(src.parent))
    if result.returncode != 0:
        raise RuntimeError(
            f"ebook-convert failed for {src}:\n{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    log(f"converted {src.name} -> {dst.name}")
    return True


def convert_tree(root: Path, *, force: bool = False, dry_run: bool = False) -> tuple[int, int]:
    """Convert every non-native ebook under root to a sibling .azw3."""
    converted = 0
    skipped = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith(".") or path.name.lower() in SKIP_NAMES:
            continue
        suffix = path.suffix.lower()
        if suffix in KINDLE_NATIVE_EXTS or suffix not in CONVERT_EXTS:
            skipped += 1
            continue
        dst = path.with_suffix(".azw3")
        if convert_to_azw3(path, dst, force=force, dry_run=dry_run):
            converted += 1
        else:
            skipped += 1
    return converted, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, help="source file to convert")
    ap.add_argument("--dst", type=Path, help="output .azw3 (default: --src with .azw3 suffix)")
    ap.add_argument("--dir", type=Path, help="convert every non-native file under this directory")
    ap.add_argument("--title", help="ebook title (passed to ebook-convert)")
    ap.add_argument("--authors", help="ebook authors (passed to ebook-convert)")
    ap.add_argument("--force", action="store_true", help="overwrite existing .azw3 files")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if bool(args.src) == bool(args.dir):
        sys.exit("error: pass exactly one of --src or --dir")

    extra: list[str] = []
    if args.title:
        extra.extend(["--title", args.title])
    if args.authors:
        extra.extend(["--authors", args.authors])

    if args.dir:
        root = args.dir.expanduser().resolve()
        if not root.is_dir():
            sys.exit(f"error: directory not found: {root}")
        n, skip = convert_tree(root, force=args.force, dry_run=args.dry_run)
        print(f"converted {n}, skipped {skip} under {root}")
        return

    src = args.src.expanduser().resolve()
    if not src.is_file():
        sys.exit(f"error: source file not found: {src}")
    dst = (args.dst.expanduser().resolve() if args.dst else src.with_suffix(".azw3"))
    convert_to_azw3(src, dst, force=args.force, dry_run=args.dry_run, extra_args=extra or None)


if __name__ == "__main__":
    main()
