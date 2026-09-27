# books

Host-side tools that build a **static OPDS catalog of AZW3s** for the
standalone ksync Kindle app. Not Kindle packages.

Requires Python 3.9+ and, for conversion, Calibre's `ebook-convert` on PATH.

## Local directory

Each subdirectory of `--dir` becomes an OPDS section; files become
acquisition entries. Relative hrefs, so the tree can sit on any static
web server.

```sh
just books-opds --dir ~/books
just books-opds --dir ~/books --convert   # epub, html, and other ebooks → sibling .azw3 first
```

Then publish the directory and add `https://<host>/<path>/opds.xml` in the
ksync WAF.

## Readeck

Unread bookmarks → one AZW3 per article under `books/out/Readeck/` → OPDS
at `books/out/opds.xml`. Already-synced IDs are remembered in
`books/out/.readeck-state.json`.

```sh
export READECK_TOKEN=…          # Profile → API Tokens (read/write if archiving)
just books-readeck              # fetch, convert, write OPDS, archive in Readeck
just books-readeck -- --limit 10 --dry-run
```

`books/out/` is gitignored. Publish that tree the same way as a local
catalog, then point ksync at its `opds.xml`.
