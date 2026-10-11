#!/usr/bin/env bash
set -euo pipefail

# Ubuntu CI and Linux x86_64 developer environments. Checksums are fixed here,
# rather than trusting checksum files downloaded alongside the binaries.
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
curl --fail --silent --show-error --location \
  https://github.com/koalaman/shellcheck/releases/download/v0.11.0/shellcheck-v0.11.0.linux.x86_64.tar.gz \
  --output "$archive_dir/shellcheck.tar.gz"
printf '%s  %s\n' \
  b7af85e41cc99489dcc21d66c6d5f3685138f06d34651e6d34b42ec6d54fe6f6 \
  "$archive_dir/shellcheck.tar.gz" | sha256sum --check --strict
tar -xzf "$archive_dir/shellcheck.tar.gz" -C "$destination" \
  --strip-components=1 shellcheck-v0.11.0/shellcheck
"$destination/actionlint" -version
"$destination/shellcheck" --version
