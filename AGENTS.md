# Agent notes

Host tools and a [kpm](https://github.com/KindleModding/KPM) catalog for a
jailbroken Kindle Oasis 10th gen (`kindlehf`, firmware 5.16.x “juno”).
User docs: [README.md](README.md).

Kindle app packages are standalone projects — do not re-add them here:

| App | Path |
| --- | --- |
| ksync | `~/code/ksync` |
| kpod | `~/code/kpod` |
| kmux | `~/code/kmux` |
| tailscale | `~/code/tailscale` |

## Commands

```sh
just books-opds --dir ~/books  # local dir → OPDS (optional --convert)
just books-readeck             # unread Readeck → AZW3s + OPDS (needs READECK_TOKEN)
just build                     # regenerate repo/index.html locally
just verify                    # published manifest is reachable JSON
```

Push to `main` deploys GitHub Pages (`kindle.qingshan.dev/repo/`).
Package artifacts are hosted by the standalone app repositories' GitHub
Releases; this catalog stores their URLs in `repo/manifest.v2.json`.

## Layout

- [`books/`](books/) — host-side static OPDS catalogs of AZW3s for ksync.
- [`repo/`](repo/) — published kpm repository (manifest v2). Do not commit
  `.kpkg` files; `repo/packages/` is gitignored and Pages does not serve it.
- [`tools/kpm-helper.py`](tools/kpm-helper.py) — upstream KPM manifest helper.
  `repo add` copies a package into `repo/packages/` and writes a relative
  URL. That output is not the publish path.

Install scripts in the app repos are POSIX `sh` (Kindle ash).

## Style

- Commit subject: imperative, what changed.
- Comments: short and factual; no changelog narration.
- Do not expand scope into the extracted app repositories unless asked.
