#!/usr/bin/env bash
set -euo pipefail

# Ubuntu CI and Linux x86_64 developer environments. The checksum is fixed here,
# rather than trusting a checksum file downloaded alongside the binary.
destination="${1:?Usage: bash devtools/install_actionlint.sh INSTALL_DIRECTORY}"
archive_dir="$(mktemp -d)"
trap 'rm -rf -- "$archive_dir"' EXIT
curl --fail --silent --show-error --location \
  https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz \
  --output "$archive_dir/actionlint.tar.gz"
printf '%s  %s\n' \
  8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8 \
  "$archive_dir/actionlint.tar.gz" | sha256sum --check --strict
mkdir -p "$destination"
tar -xzf "$archive_dir/actionlint.tar.gz" -C "$destination" actionlint
"$destination/actionlint" -version
