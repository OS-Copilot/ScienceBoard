#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
image="${1:-scienceboard:0.1}"
archive="${2:-$project_dir/.artifacts/scienceboard-docker-0.1.tar.zst}"
checksum="$archive.sha256"

if [[ -e "$archive" || -e "$checksum" ]]; then
    echo "Refusing to overwrite an existing distribution artifact: $archive" >&2
    exit 2
fi
command -v zstd >/dev/null || {
    echo "zstd is required to package the image" >&2
    exit 2
}

"$project_dir/scripts/audit_distribution.py" --image "$image"
mkdir -p "$(dirname -- "$archive")"

docker save "$image" | zstd -T0 -10 -o "$archive"
(
    cd -- "$(dirname -- "$archive")"
    sha256sum "$(basename -- "$archive")" > "$(basename -- "$checksum")"
)

cat "$checksum"
docker image inspect --format \
    'image={{.RepoTags}} id={{.Id}} size={{.Size}} layers={{len .RootFS.Layers}}' \
    "$image"
