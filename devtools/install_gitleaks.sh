#!/usr/bin/env bash
set -euo pipefail

# Ubuntu CI and Linux x86_64 developer environments. Verify the archive against
# the official release checksum fixed here, rather than a downloaded checksum.
destination="${1:?Usage: bash devtools/install_gitleaks.sh INSTALL_DIRECTORY}"
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo 'This installer requires Linux x86_64; see SECURITY.md for other platforms.' >&2
  exit 1
fi
archive_dir="$(mktemp -d)"
trap 'rm -rf -- "$archive_dir"' EXIT
curl --fail --silent --show-error --location \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
  --output "$archive_dir/gitleaks.tar.gz"
printf '%s  %s\n' \
  551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb \
  "$archive_dir/gitleaks.tar.gz" | sha256sum --check --strict
mkdir -p "$destination"
tar -xzf "$archive_dir/gitleaks.tar.gz" -C "$destination" gitleaks
[[ "$("$destination/gitleaks" version)" == 8.30.1 ]]
echo 'Installed Gitleaks 8.30.1.'
