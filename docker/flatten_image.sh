#!/usr/bin/env bash
set -Eeuo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_image="${1:-scienceboard-layered:0.1}"
target_image="${2:-scienceboard:0.1}"
flat_image="${SCIENCEBOARD_FLAT_IMAGE:-scienceboard-flat-rootfs:0.1}"
container_id=""

cleanup() {
    if [[ -n "$container_id" ]]; then
        docker container rm --force "$container_id" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT INT TERM

docker image inspect "$source_image" >/dev/null
container_id="$(docker container create "$source_image")"

echo "Flattening sanitized filesystem from $source_image into $flat_image ..."
docker container export "$container_id" | docker image import \
    --platform linux/amd64 \
    --change 'CMD ["/bin/bash"]' \
    - "$flat_image"

docker container rm "$container_id" >/dev/null
container_id=""

echo "Restoring runtime metadata as $target_image ..."
docker build \
    --build-arg "BASE_IMAGE=$flat_image" \
    --tag "$target_image" \
    --file "$project_dir/docker/Portable.Dockerfile" \
    "$project_dir"

docker image inspect --format \
    'image={{.RepoTags}} size={{.Size}} architecture={{.Architecture}} distribution={{index .Config.Labels "org.scienceboard.distribution"}}' \
    "$target_image"
