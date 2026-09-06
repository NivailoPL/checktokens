#!/bin/bash
set -euo pipefail
app_dir="$HOME/Library/Application Support/CheckTokens"
services_dir="$HOME/Library/Services"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --app-dir) app_dir="$2"; shift 2 ;;
    --services-dir) services_dir="$2"; shift 2 ;;
    *) echo "Usage: bash uninstall-macos.sh [--app-dir DIR] [--services-dir DIR]" >&2; exit 2 ;;
  esac
done
if [ -f "$services_dir/Check Tokens.workflow/Contents/checktokens-owned" ]; then
  rm -rf "$services_dir/Check Tokens.workflow"
fi
if [ -f "$app_dir/.checktokens-owned" ]; then
  rm -rf "$app_dir/CheckTokens.app"
  rm -f "$app_dir/.checktokens-owned" "$app_dir/uninstall-macos.sh"
  rmdir "$app_dir" 2>/dev/null || true
fi
/System/Library/CoreServices/pbs -flush >/dev/null 2>&1 || true
echo "CheckTokens uninstalled."
