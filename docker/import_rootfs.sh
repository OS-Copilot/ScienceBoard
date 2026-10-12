#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
archive="${1:-$project_dir/.artifacts/scienceboard-rootfs.tar.gz}"
base_image="${SCIENCEBOARD_BASE_IMAGE:-scienceboard-rootfs:0.1}"
layered_image="${SCIENCEBOARD_LAYERED_IMAGE:-scienceboard-layered:0.1}"
runtime_image="${SCIENCEBOARD_DOCKER_IMAGE:-scienceboard:0.1}"

if [[ ! -f "$archive" ]]; then
    echo "Root filesystem archive does not exist: $archive" >&2
    exit 2
fi

echo "Importing reference filesystem as $base_image ..."
docker import \
    --platform linux/amd64 \
    --change 'CMD ["/bin/bash"]' \
    "$archive" "$base_image"

echo "Building sanitizing runtime overlay as $layered_image ..."
docker build \
    --build-arg "BASE_IMAGE=$base_image" \
    --tag "$layered_image" \
    --file "$project_dir/docker/Dockerfile" \
    "$project_dir"

"$project_dir/docker/flatten_image.sh" "$layered_image" "$runtime_image"

docker image inspect \
    --format 'image={{.RepoTags}} size={{.Size}} architecture={{.Architecture}} distribution={{index .Config.Labels "org.scienceboard.distribution"}}' \
    "$runtime_image"
