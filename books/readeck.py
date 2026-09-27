#!/usr/bin/env python3
"""Fetch unread Readeck bookmarks, convert each article to AZW3, emit OPDS.

Pipeline: Readeck REST API -> article HTML + images -> one AZW3 per article
under <out>/Readeck/ -> books/opds.py so ksync can pull the catalog.

Does not sideload to the Kindle. Publish <out> and add <out>/opds.xml in ksync.

Usage:
    python3 books/readeck.py --base-url https://readeck.qingshan.dev
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from convert import convert_to_azw3  # noqa: E402
from opds import write_feeds  # noqa: E402


def log(msg: str) -> None:
    print(f"[readeck] {msg}", file=sys.stderr, flush=True)


def api_request(base_url: str, token: str, path_or_url: str, method: str = "GET",
                 json_body: dict | None = None, accept: str | None = None):
    url = path_or_url if path_or_url.startswith("http") else base_url.rstrip("/") + path_or_url
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if accept:
        headers["Accept"] = accept
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})


def fetch_unread_bookmarks(base_url: str, token: str, limit: int) -> list[dict]:
    params = {
        "read_status": "unread",
        "is_loaded": "true",
        "has_errors": "false",
        "limit": limit,
        "sort": "-created",
    }
    query = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    status, body, _ = api_request(base_url, token, f"/api/bookmarks?{query}")
    if status != 200:
        raise RuntimeError(f"Failed to list bookmarks ({status}): {body[:500]!r}")
    return json.loads(body)


_LINK_RE = re.compile(r'<([^>]+)>\s*;\s*rel="?media"?', re.IGNORECASE)


def fetch_article_html(base_url: str, token: str, bookmark_id: str) -> tuple[str, dict[str, str]]:
    url = base_url.rstrip("/") + f"/api/bookmarks/{bookmark_id}/article"
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/html"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            body = resp.read()
            link_values = resp.headers.get_all("Link") or []
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read()
        link_values = e.headers.get_all("Link") if e.headers else []

    if status != 200:
        raise RuntimeError(f"Failed to fetch article HTML for {bookmark_id} ({status}): {body[:300]!r}")

    resource_map: dict[str, str] = {}
    for link_value in link_values:
        m = _LINK_RE.search(link_value)
        if m:
            resource_url = m.group(1)
            resource_map[os.path.basename(resource_url)] = resource_url

    return body.decode("utf-8", errors="replace"), resource_map


class ImgSrcCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.srcs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "img":
            for name, value in attrs:
                if name.lower() == "src" and value:
                    self.srcs.append(value)


_IMG_SIGS: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8\xff", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
    (b"BM", ".bmp"),
]


def _guess_image_ext(content_type: str, url: str, body: bytes) -> str:
    content_type = (content_type or "").split(";")[0].strip().lower()
    stripped = body.lstrip()[:200].lower()
    if b"<svg" in stripped or (b"<?xml" in stripped[:20] and b"svg" in body[:500].lower()):
        return ".svg"
    if content_type == "image/svg+xml":
        return ".svg"
    for sig, ext in _IMG_SIGS:
        if body.startswith(sig):
            if sig == b"RIFF":
                if body[8:12] == b"WEBP":
                    return ".webp"
                continue
            return ext
    if "png" in content_type:
        return ".png"
    if "gif" in content_type:
        return ".gif"
    if "webp" in content_type:
        return ".webp"
    if "bmp" in content_type:
        return ".bmp"
    ext_from_url = os.path.splitext(url.split("?")[0])[1].lower()
    if ext_from_url in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"):
        return ext_from_url
    return ".jpg"


def localize_images(article_html: str, resource_map: dict[str, str], base_url: str, token: str,
                     image_dir: Path, prefix: str) -> str:
    collector = ImgSrcCollector()
    collector.feed(article_html)
    updated_html = article_html
    for i, src in enumerate(dict.fromkeys(collector.srcs)):
        resolved = resource_map.get(os.path.basename(src), src)
        try:
            status, body, headers = api_request(base_url, token, resolved)
            if status != 200 or not body:
                log(f"    warning: failed to fetch image {src!r} ({status})")
                continue
            ext = _guess_image_ext(headers.get("Content-Type", ""), resolved, body)
            local_name = f"{prefix}_img{i}{ext}"
            (image_dir / local_name).write_bytes(body)
            updated_html = updated_html.replace(f'src="{src}"', f'src="images/{local_name}"')
            updated_html = updated_html.replace(f"src='{src}'", f'src="images/{local_name}"')
        except Exception as e:  # noqa: BLE001
            log(f"    warning: failed to fetch image {src}: {e}")
    return updated_html


def archive_bookmark(base_url: str, token: str, bookmark_id: str) -> None:
    status, body, _ = api_request(base_url, token, f"/api/bookmarks/{bookmark_id}", method="PATCH",
                                   json_body={"is_archived": True})
    if status != 200:
        raise RuntimeError(f"Failed to archive bookmark {bookmark_id} ({status}): {body[:300]!r}")


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^\w\- ]+", "", text).strip()
    return re.sub(r"\s+", "_", cleaned)[:80] or "article"


def article_html_document(bm: dict, article_html: str) -> str:
    title = html.escape(bm.get("title") or "Untitled")
    site = html.escape(bm.get("site_name") or bm.get("site") or "")
    authors = ", ".join(bm.get("authors") or [])
    url = html.escape(bm.get("url") or "")
    meta_bits = " &middot; ".join(x for x in [site, html.escape(authors)] if x)
    parts = [
        "<html><head><meta charset='utf-8'/>",
        f"<title>{title}</title></head><body>",
        f"<h1>{title}</h1>",
    ]
    if meta_bits:
        parts.append(f'<p style="color:#666"><em>{meta_bits}</em></p>')
    if url:
        parts.append(f'<p style="color:#888;font-size:0.8em">{url}</p>')
    parts.append(article_html)
    parts.append("</body></html>")
    return "\n".join(parts)


def load_state(state_file: Path) -> dict:
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except json.JSONDecodeError:
            log(f"Warning: could not parse state file {state_file}, starting fresh")
    return {"synced_ids": []}


def save_state(state_file: Path, state: dict) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="https://readeck.qingshan.dev",
                        help="Readeck base URL")
    parser.add_argument("--token", default=os.environ.get("READECK_TOKEN"),
                        help="Readeck API token (or set READECK_TOKEN)")
    parser.add_argument("--out", default=str(HERE / "out"),
                        help="catalog directory (default: books/out)")
    parser.add_argument("--section", default="Readeck",
                        help="OPDS section name under --out")
    parser.add_argument("--limit", type=int, default=30,
                        help="Max unread bookmarks to fetch")
    parser.add_argument("--state-file", default=None,
                        help="Synced bookmark IDs (default: <out>/.readeck-state.json)")
    parser.add_argument("--archive-after-sync", action="store_true",
                        help="Mark included bookmarks archived in Readeck after a successful convert")
    parser.add_argument("--force", action="store_true", help="reconvert even if the AZW3 exists")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-work-dir", action="store_true")
    args = parser.parse_args()

    if not args.token:
        sys.exit("error: --token or READECK_TOKEN env var is required")

    out = Path(args.out).expanduser().resolve()
    section_dir = out / args.section
    state_file = Path(args.state_file).expanduser() if args.state_file else out / ".readeck-state.json"
    state = load_state(state_file)
    synced_ids = set(state.get("synced_ids", []))

    log(f"Fetching up to {args.limit} unread bookmarks from {args.base_url}...")
    try:
        bookmarks = fetch_unread_bookmarks(args.base_url, args.token, args.limit)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"error: {e}")

    pending = [b for b in bookmarks if b["id"] not in synced_ids]
    if not pending:
        log("Nothing new.")
        out.mkdir(parents=True, exist_ok=True)
        write_feeds(out, out, "Books")
        print(f"OPDS catalog: {out / 'opds.xml'}")
        return

    log(f"{len(pending)} new bookmark(s).")
    section_dir.mkdir(parents=True, exist_ok=True)
    included_ids: list[str] = []
    work_dir = Path(tempfile.mkdtemp(prefix="readeck-"))
    try:
        for bm in pending:
            bookmark_id = bm["id"]
            title = bm.get("title") or "Untitled"
            slug = slugify(title)
            azw3_path = section_dir / f"{slug}.azw3"
            log(f"- [{bookmark_id}] {title}")
            if azw3_path.exists() and not args.force:
                log(f"  skip existing {azw3_path.name}")
                included_ids.append(bookmark_id)
                continue
            try:
                article_html, resource_map = fetch_article_html(args.base_url, args.token, bookmark_id)
                article_dir = work_dir / slug
                image_dir = article_dir / "images"
                image_dir.mkdir(parents=True, exist_ok=True)
                article_html = localize_images(
                    article_html, resource_map, args.base_url, args.token, image_dir, slug
                )
                html_path = article_dir / "article.html"
                html_path.write_text(article_html_document(bm, article_html), encoding="utf-8")
                authors = ", ".join(bm.get("authors") or []) or "Readeck"
                extra = ["--title", title, "--authors", authors]
                convert_to_azw3(
                    html_path, azw3_path, force=args.force, dry_run=args.dry_run, extra_args=extra
                )
                included_ids.append(bookmark_id)
            except Exception as e:  # noqa: BLE001
                log(f"  ERROR, skipping: {e}")
                continue

        write_feeds(out, out, "Books")
        print(f"OPDS catalog: {out / 'opds.xml'}")

        if not args.dry_run:
            if args.archive_after_sync:
                log("Archiving included bookmarks in Readeck...")
                for bookmark_id in included_ids:
                    try:
                        archive_bookmark(args.base_url, args.token, bookmark_id)
                    except Exception as e:  # noqa: BLE001
                        log(f"  warning: failed to archive {bookmark_id}: {e}")
            synced_ids.update(included_ids)
            state["synced_ids"] = sorted(synced_ids)
            save_state(state_file, state)
    finally:
        if args.keep_work_dir:
            log(f"Kept work dir: {work_dir}")
        else:
            shutil.rmtree(work_dir, ignore_errors=True)

    log("Done.")


if __name__ == "__main__":
    main()
