# Qingshan's Kindle Repo

Personal [kpm](https://github.com/KindleModding/KPM) package repository for
jailbroken Kindles, published to https://kindle.qingshan.dev/repo/.

Layout follows
[kpm-repository-template](https://github.com/KindleModding/kpm-repository-template)
(manifest v2, as used by current KPM and the official KMC repo).

Add this repo in kpm with:

```
;kpm add-repo https://kindle.qingshan.dev/repo/manifest.v2.json
```

then `;kpm install <package>`.

The catalog does not build or host app packages. `ksync`, `kpod`, `kmux`, and
`tailscale` are standalone projects. A package appears here when its absolute
artifact URL is added to `manifest.v2.json`.

`tools/kpm-helper.py repo add` still copies a local `.kpkg` into
`repo/packages/` and writes a relative URL. Those files are gitignored and
are not deployed. Record an absolute URL instead.

## Maintainers

Push to `main` builds the index and deploys GitHub Pages. The kpm files are
published under `/repo/` so the add-repo URL above does not change.

From the git root:

```sh
just build               # regenerate repo/index.html from manifest.v2.json
just verify              # https://kindle.qingshan.dev/repo/manifest.v2.json
```

Published files are `manifest.v2.json` and generated `index.html`. Kindle app
sources and release artifacts live in standalone repositories; this directory
neither builds nor vendors them.

### Custom domain

GitHub Actions Pages ignores a `CNAME` file. After the first successful
workflow run:

1. Repo **Settings → Pages → Custom domain**: `kindle.qingshan.dev`, Save.
   Do this **before** changing DNS.
2. At the DNS host (Google Cloud DNS nameservers on `qingshan.dev`), set:

   | Type | Name | Value |
   |---|---|---|
   | `CNAME` | `kindle` | `qingshan.github.io.` |

   Point at `qingshan.github.io`, not `qingshan.github.io/kindle`.
3. Wait for DNS and for GitHub to issue the certificate, then enable
   **Enforce HTTPS**.

Until step 2, the site is at `https://qingshan.github.io/kindle/repo/`.
