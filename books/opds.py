#!/usr/bin/env python3
"""Generate static OPDS 1.2 catalog files for a local books directory.

Every immediate sub-directory of --dir becomes an OPDS navigation section
(a folder in the ksync mirror); files under it become acquisition entries.
Files directly in --dir are listed on the root feed.

Feeds use relative hrefs, so the tree works on any static web server. Add
the root feed URL in the ksync WAF:

    https://<host>/<path>/opds.xml

Usage:
    python3 books/opds.py --dir ~/books
    python3 books/opds.py --dir ~/books --convert
"""

from __future__ import annotations

import argparse
import datetime
import os
import shutil
import sys
import time
import urllib.parse
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

ATOM_NS = "http://www.w3.org/2005/Atom"
OPDS_ACQUISITION = "http://opds-spec.org/acquisition"
NAV_TYPE = "application/atom+xml;profile=opds-catalog"

MIME = {
    ".epub": "application/epub+zip",
    ".pdf": "application/pdf",
    ".mobi": "application/x-mobipocket-ebook",
    ".azw": "application/vnd.amazon.ebook",
    ".azw3": "application/vnd.amazon.mobi8-ebook",
    ".txt": "text/plain",
    ".cbz": "application/x-cbz",
    ".cbr": "application/x-cbr",
    ".fb2": "application/x-fictionbook+xml",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".rtf": "application/rtf",
    ".html": "text/html",
    ".htm": "text/html",
    ".djvu": "image/vnd.djvu",
    ".zip": "application/zip",
}
SKIP = {".ds_store", "thumbs.db"}
FEED_NAME = "opds.xml"


def iso(ts: float) -> str:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mime_of(path: Path) -> str:
    return MIME.get(path.suffix.lower(), "application/octet-stream")


def title_of(path: Path) -> str:
    return path.stem


def _skip_dir(path: Path, skip_roots: set[Path]) -> bool:
    resolved = path.resolve()
    return any(resolved == s or s in resolved.parents for s in skip_roots)


def sections(root: Path, skip_roots: set[Path] | None = None) -> list[Path]:
    skip_roots = skip_roots or set()
    out = []
    with os.scandir(root) as it:
        for e in it:
            if e.name.startswith(".") or e.name.lower() in SKIP:
                continue
            if e.name.lower() == FEED_NAME:
                continue
            p = Path(e.path)
            if _skip_dir(p, skip_roots):
                continue
            if e.is_dir(follow_symlinks=True):
                out.append(p)
    out.sort(key=lambda p: p.name.lower())
    return out


def files_under(root: Path, skip_roots: set[Path] | None = None) -> list[Path]:
    skip_roots = skip_roots or set()
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d.lower() not in SKIP
            and not _skip_dir(Path(dirpath) / d, skip_roots)
        ]
        for fn in filenames:
            if fn.startswith(".") or fn.lower() in SKIP:
                continue
            if fn.lower() == FEED_NAME:
                continue
            out.append(Path(dirpath) / fn)
    out.sort(key=lambda p: p.name.lower())
    return out


def quote_rel(rel: Path) -> str:
    return "/".join(urllib.parse.quote(part) for part in rel.parts)


def entry_xml(title: str, entry_id: str, updated: str, links: list[tuple[str, str, str]],
              content: str | None = None) -> str:
    parts = [
        "  <entry>",
        f"    <title>{escape(title)}</title>",
        f"    <id>{escape(entry_id)}</id>",
        f"    <updated>{updated}</updated>",
    ]
    for href, rel, type_ in links:
        parts.append(f'    <link href={quoteattr(href)} rel={quoteattr(rel)} type={quoteattr(type_)}/>')
    if content is not None:
        parts.append(f'    <content type="text">{escape(content)}</content>')
    parts.append("  </entry>")
    return "\n".join(parts)


def feed_xml(title: str, self_href: str, updated: str, entries: list[str]) -> str:
    head = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<feed xmlns="{ATOM_NS}">\n'
        f"  <title>{escape(title)}</title>\n"
        f"  <id>{escape(self_href)}</id>\n"
        f"  <updated>{updated}</updated>\n"
        f'  <link href={quoteattr(self_href)} rel="self" type="{NAV_TYPE}"/>\n'
        f'  <link href={quoteattr(self_href)} rel="start" type="{NAV_TYPE}"/>\n'
    )
    return head + "\n".join(entries) + "\n</feed>\n"


def root_feed(root: Path, title: str, skip_roots: set[Path] | None = None) -> str:
    now = iso(time.time())
    entries: list[str] = []
    for s in sections(root, skip_roots):
        count = len(files_under(s, skip_roots))
        href = f"{quote_rel(Path(s.name))}/opds.xml"
        entries.append(entry_xml(
            s.name, href, now,
            [(href, "subsection", NAV_TYPE)],
            content=f"{count} book{'s' if count != 1 else ''}",
        ))
    for f in files_under(root, skip_roots):
        if f.parent != root:
            continue
        href = quote_rel(Path(f.name))
        entries.append(entry_xml(
            title_of(f), href, iso(f.stat().st_mtime),
            [(href, OPDS_ACQUISITION, mime_of(f))],
        ))
    return feed_xml(title, "opds.xml", now, entries)


def section_feed(root: Path, section: Path, skip_roots: set[Path] | None = None) -> str:
    sec_root = root / section
    now = iso(time.time())
    entries: list[str] = []
    for f in files_under(sec_root, skip_roots):
        href = quote_rel(f.relative_to(sec_root))
        entries.append(entry_xml(
            title_of(f), href, iso(f.stat().st_mtime),
            [(href, OPDS_ACQUISITION, mime_of(f))],
        ))
    return feed_xml(section.name, "opds.xml", now, entries)


def write_feeds(books: Path, out: Path, title: str) -> list[Path]:
    skip_roots: set[Path] = set()
    if out.resolve() != books.resolve():
        try:
            out.resolve().relative_to(books.resolve())
            skip_roots.add(out.resolve())
        except ValueError:
            pass
        out.mkdir(parents=True, exist_ok=True)
        for s in sections(books, skip_roots):
            for f in files_under(s, skip_roots):
                dst = out / f.relative_to(books)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
        for f in files_under(books, skip_roots):
            if f.parent == books:
                dst = out / f.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
        scan = out
    else:
        out.mkdir(parents=True, exist_ok=True)
        scan = books

    written = [out / "opds.xml"]
    (out / "opds.xml").write_text(root_feed(scan, title), encoding="utf-8")
    for s in sections(scan):
        rel = s.relative_to(scan)
        sec_out = out / rel
        sec_out.mkdir(parents=True, exist_ok=True)
        (sec_out / "opds.xml").write_text(section_feed(scan, rel), encoding="utf-8")
        written.append(sec_out / "opds.xml")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", "--books", dest="books", default=None,
                    help="books directory")
    ap.add_argument("--out", default=None,
                    help="output directory (default: the books dir, feeds in place)")
    ap.add_argument("--title", default="Books", help="root feed title")
    ap.add_argument("--convert", action="store_true",
                    help="convert non-native formats to AZW3 before writing feeds")
    ap.add_argument("--force", action="store_true", help="with --convert, overwrite existing AZW3s")
    args = ap.parse_args()

    books = Path(args.books).expanduser().resolve() if args.books else None
    if books is None:
        sys.exit("error: --dir is required")
    if not books.is_dir():
        sys.exit(f"error: books directory not found: {books}")

    if args.convert:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from convert import convert_tree
        n, skip = convert_tree(books, force=args.force)
        print(f"convert: {n} written, {skip} skipped")

    out = Path(args.out).expanduser().resolve() if args.out else books
    written = write_feeds(books, out, args.title)
    skip_roots: set[Path] = set()
    if out.resolve() != books.resolve():
        try:
            out.resolve().relative_to(books.resolve())
            skip_roots.add(out.resolve())
        except ValueError:
            pass
    n_sec = len(sections(books, skip_roots))
    n_files = len(files_under(books, skip_roots))
    print(f"Generated {len(written)} OPDS feed{'s' if len(written) != 1 else ''} under {out}")
    print(f"  {n_sec} section{'s' if n_sec != 1 else ''}, {n_files} book file{'s' if n_files != 1 else ''}")
    print("Publish this directory, then add this URL in the ksync WAF:")
    print("  https://<host>/<path>/opds.xml")


if __name__ == "__main__":
    main()
