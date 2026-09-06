#!/bin/bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
app_dir="$HOME/Library/Application Support/CheckTokens"
services_dir="$HOME/Library/Services"
package=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --package) package="$2"; shift 2 ;;
    --app-dir) app_dir="$2"; shift 2 ;;
    --services-dir) services_dir="$2"; shift 2 ;;
    *) echo "Usage: bash install-macos.sh [--package ZIP] [--app-dir DIR] [--services-dir DIR]" >&2; exit 2 ;;
  esac
done
[ "$(uname -s)" = Darwin ] || { echo "macOS is required." >&2; exit 1; }
[ "$(sw_vers -productVersion | cut -d. -f1)" -ge 15 ] || { echo "macOS 15 or later is required." >&2; exit 1; }
case "$app_dir:$services_dir" in /*:/*) ;; *) echo "Installation paths must be absolute." >&2; exit 1 ;; esac
task_tmp="$(mktemp -d "${TMPDIR:-/tmp}/checktokens-install.XXXXXX")"
trap 'rm -rf "$task_tmp"' EXIT
arch="$(uname -m)"
case "$arch" in arm64|x86_64) ;; *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; esac

if [ -z "$package" ] && [ -d "$script_dir/CheckTokens.app" ]; then
  source_dir="$script_dir"
else
  if [ -z "$package" ]; then
    # Version-pinned: code from a tag installs that tag, not a moving latest release.
    release="https://github.com/NivailoPL/checktokens/releases/download/v0.2.0"
    package="$task_tmp/CheckTokens-macos-$arch.zip"
    curl --fail --location --proto '=https' --tlsv1.2 "$release/$(basename "$package")" -o "$package"
    curl --fail --location --proto '=https' --tlsv1.2 "$release/SHA256SUMS" -o "$task_tmp/SHA256SUMS"
  fi
  sums="$(dirname "$package")/SHA256SUMS"
  [ -f "$sums" ] || { echo "Missing SHA256SUMS next to the package." >&2; exit 1; }
  expected="$(awk -v name="$(basename "$package")" '$2 == name {print $1}' "$sums")"
  actual="$(shasum -a 256 "$package" | awk '{print $1}')"
  [ -n "$expected" ] && [ "$actual" = "$expected" ] || { echo "Package checksum mismatch." >&2; exit 1; }
  source_dir="$task_tmp/package"
  mkdir "$source_dir"
  ditto -x -k "$package" "$source_dir"
fi

binary="$source_dir/CheckTokens.app/Contents/MacOS/checktokens"
[ -f "$source_dir/MANIFEST.sha256" ] || { echo "Missing package manifest." >&2; exit 1; }
(cd "$source_dir" && shasum -a 256 -c MANIFEST.sha256 >/dev/null) || { echo "Package content verification failed." >&2; exit 1; }
[ -x "$binary" ] && [ -d "$source_dir/Check Tokens.workflow" ] || { echo "Incomplete package." >&2; exit 1; }
file "$binary" | grep -q "$arch" || { echo "The package does not match this Mac's architecture." >&2; exit 1; }
mkdir -p "$app_dir" "$services_dir"
staging="$(mktemp -d "$app_dir/.install.XXXXXX")"
trap 'rm -rf "$task_tmp" "$staging"' EXIT
ditto "$source_dir/CheckTokens.app" "$staging/CheckTokens.app"
ditto "$source_dir/Check Tokens.workflow" "$staging/Check Tokens.workflow"
# Keep arbitrary Unicode/quotes in the installation path out of shell source.
encoded_binary="$(printf '%s' "$app_dir/CheckTokens.app/Contents/MacOS/checktokens" | /usr/bin/base64 | tr -d '\n')"
printf -v workflow_command 'exec "$(printf %%s %s | /usr/bin/base64 -D)" --gui -- "$@"' "$encoded_binary"
plutil -replace actions.0.action.ActionParameters.COMMAND_STRING -string "$workflow_command" \
  "$staging/Check Tokens.workflow/Contents/document.wflow"
plutil -lint "$staging/Check Tokens.workflow/Contents/document.wflow" >/dev/null

# Only replace an installation we own; never overwrite an unrelated Finder action.
if [ -e "$services_dir/Check Tokens.workflow" ] && [ ! -f "$services_dir/Check Tokens.workflow/Contents/checktokens-owned" ]; then
  echo "A different Check Tokens workflow already exists. Nothing was replaced." >&2; exit 1
fi
if [ -e "$app_dir/CheckTokens.app" ] && [ ! -f "$app_dir/.checktokens-owned" ]; then
  echo "An unrecognized CheckTokens installation already exists. Nothing was replaced." >&2; exit 1
fi
touch "$staging/Check Tokens.workflow/Contents/checktokens-owned"
app_backup=0
workflow_backup=0
app_installed=0
workflow_installed=0
install_complete=0
cleanup() {
  task_exit=$?
  keep_staging=0
  if [ "$install_complete" -eq 0 ]; then
    if [ "$app_installed" -eq 1 ]; then rm -rf "$app_dir/CheckTokens.app"; fi
    if [ "$workflow_installed" -eq 1 ]; then rm -rf "$services_dir/Check Tokens.workflow"; fi
    if [ "$app_backup" -eq 1 ]; then mv "$staging/previous.app" "$app_dir/CheckTokens.app" || keep_staging=1; fi
    if [ "$workflow_backup" -eq 1 ]; then mv "$staging/previous.workflow" "$services_dir/Check Tokens.workflow" || keep_staging=1; fi
    echo "Installation failed; restored available previous files." >&2
  fi
  if [ "$keep_staging" -eq 0 ]; then rm -rf "$staging"; else echo "Recovery files preserved at $staging" >&2; fi
  rm -rf "$task_tmp"
  return "$task_exit"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
if [ -e "$app_dir/CheckTokens.app" ]; then
  mv "$app_dir/CheckTokens.app" "$staging/previous.app"
  app_backup=1
fi
if [ -e "$services_dir/Check Tokens.workflow" ]; then
  mv "$services_dir/Check Tokens.workflow" "$staging/previous.workflow"
  workflow_backup=1
fi
mv "$staging/CheckTokens.app" "$app_dir/CheckTokens.app"
app_installed=1
mv "$staging/Check Tokens.workflow" "$services_dir/Check Tokens.workflow"
workflow_installed=1
touch "$app_dir/.checktokens-owned"
cp "$script_dir/uninstall-macos.sh" "$app_dir/uninstall-macos.sh"
install_complete=1
/System/Library/CoreServices/pbs -flush >/dev/null 2>&1 || true
echo "Installed CheckTokens. Select files in Finder → right-click → Check Tokens (or Services → Check Tokens)."
echo "If blocked by macOS, open CheckTokens.app once and use System Settings → Privacy & Security → Open Anyway."
echo "App: $app_dir/CheckTokens.app"
