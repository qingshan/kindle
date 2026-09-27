# Qingshan's Kindle apps

A [kpm](https://github.com/KindleModding/KPM) repository for a jailbroken Kindle,
published at **https://kindle.qingshan.dev/repo/**, plus host-side OPDS catalog
tools.

Built and tested on a **Kindle Oasis 10th gen** (`kindlehf`, firmware 5.16.x
“juno”) with KPM 0.2.x.

Kindle app packages (`ksync`, `kpod`, `kmux`, `tailscale`) live in their own
repositories. This tree holds the published kpm catalog and the host tools
those apps talk to.

## Installing apps on the Kindle

Each app now owns its own release package. Build it in that app's repository
with `just package`, then install the resulting `.kpkg` with KPM. The app
READMEs cover their on-device setup:

- ksync (`~/code/ksync`) — OPDS catalogs and Kindle collections.
- kpod (`~/code/kpod`) — OPML feeds and Bluetooth playback.
- kmux (`~/code/kmux`) — remote tmux sessions.
- tailscale (`~/code/tailscale`) — tailnet connectivity and SSH.

The public KPM catalog remains at
`https://kindle.qingshan.dev/repo/manifest.v2.json`. Adding it in KPM does
not install an app by itself. An app is installable from the catalog only
after its artifact URL is recorded in `repo/manifest.v2.json`.

## Host tools

For anyone running the server-side pieces these apps talk to. Nothing here
is installed on the Kindle.

- **[books](books/)** — static OPDS catalogs of AZW3s for ksync.
  `just books-opds --dir ~/books` turns a local directory into a catalog
  (optional `--convert`). `just books-readeck` turns unread
  [Readeck](https://readeck.org/) articles into AZW3s (needs `READECK_TOKEN`).

## Develop

The published KPM catalog is [`repo/`](repo/), following
[kpm-repository-template](https://github.com/KindleModding/kpm-repository-template).

The catalog is metadata only. Each `url` in `repo/manifest.v2.json` is the
address KPM downloads, and this repository does not store `.kpkg` files.
Push to `main` deploys GitHub Pages (custom domain `kindle.qingshan.dev`).

```sh
just books-opds --dir ~/books  # local dir → OPDS (optional --convert)
just books-readeck             # unread Readeck → AZW3s + OPDS (needs READECK_TOKEN)
just build                     # regenerate repo/index.html locally
just verify                    # published manifest is reachable JSON
```

Pages/DNS notes are in [`repo/README.md`](repo/README.md).

## License

MIT licensed. See [LICENSE](LICENSE).
