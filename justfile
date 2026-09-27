# Host-side OPDS tools and the published kpm repo in ./repo
#
# Publish: GitHub Pages, on every push to main
#   (.github/workflows/publish.yml → https://kindle.qingshan.dev/repo/).
#
# Requires: just, python3.11+ (tomllib, for a local repo/index.html).

set shell := ["bash", "-euo", "pipefail", "-c"]

repo_dir := "repo"
venv := ".venv"
domain := "kindle.qingshan.dev"

# List available recipes
default:
    @just --list

# Create/refresh the local venv used to build repo/index.html (needs Python 3.11+ for tomllib)
venv:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -x "{{venv}}/bin/python" ]; then
        pybin=""
        for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
            if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
                pybin="$candidate"
                break
            fi
        done
        if [ -z "$pybin" ]; then
            echo "error: need a Python 3.11+ interpreter (tomllib) to build the index; none found" >&2
            exit 1
        fi
        echo "Creating venv with $pybin..."
        "$pybin" -m venv "{{venv}}"
    fi
    "{{venv}}/bin/pip" install -q -r "{{repo_dir}}/index_builder/requirements.txt"

# Regenerate repo/index.html
build: venv
    "{{venv}}/bin/python" "{{repo_dir}}/index_builder/build_index.py"
    @echo "Built {{repo_dir}}/index.html"

# Confirm the published repo is reachable and manifest.v2.json is valid JSON
verify:
    curl -fsSI "https://{{domain}}/repo/manifest.v2.json" | head -1
    curl -fsS "https://{{domain}}/repo/manifest.v2.json" | python3 -c "import json, sys; json.load(sys.stdin); print('manifest.v2.json is valid JSON')"

readeck_base_url := "https://readeck.qingshan.dev"

# Local directory → optional AZW3 convert → static OPDS (ksync catalog)
# e.g. just books-opds --dir ~/books --convert
books-opds *args:
    python3 books/opds.py {{args}}

# Unread Readeck articles → one AZW3 each under books/out/Readeck → OPDS
# Requires READECK_TOKEN. Extra args after `--`, e.g. just books-readeck -- --limit 10
books-readeck *args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "${READECK_TOKEN:-}" ]; then
        echo "error: READECK_TOKEN env var is required (Profile -> API Tokens in Readeck)" >&2
        exit 1
    fi
    python3 books/readeck.py \
        --base-url "{{readeck_base_url}}" \
        --archive-after-sync \
        {{args}}

# Remove local build artifacts
clean:
    rm -rf "{{venv}}" "{{repo_dir}}/index.html"
