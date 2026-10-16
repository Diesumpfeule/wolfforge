#!/usr/bin/env bash
# wolfforge – LibreWolf overhaul. Installs the app to ~/.local/share/wolfforge/app
# and the `wolfforge` command to ~/.local/bin.
#
#   ./install.sh            install / update, then open the app
#   ./install.sh --apply    install / update and apply without opening the app
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HOME/.local/share/wolfforge/app"
BIN="$HOME/.local/bin/wolfforge"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

need=()
python3 -c 'import textual' 2>/dev/null || need+=(python3-textual)
python3 -c 'import jinja2' 2>/dev/null || need+=(python3-jinja2)
command -v librewolf >/dev/null 2>&1 || flatpak info io.gitlab.librewolf-community >/dev/null 2>&1 || {
  say "LibreWolf isn't installed – adding its official repo …"
  curl -fsSL https://repo.librewolf.net/librewolf.repo | sudo tee /etc/yum.repos.d/librewolf.repo >/dev/null
  need+=(librewolf)
}
if [ ${#need[@]} -gt 0 ]; then
  say "Installing: ${need[*]}"
  sudo dnf install -y "${need[@]}"
fi

say "Copying wolfforge to $APP …"
mkdir -p "$APP" "$(dirname "$BIN")"
if [ "$HERE" != "$APP" ]; then
  rm -rf "$APP/wolfforge"
  cp -r "$HERE/wolfforge" "$APP/"
  cp "$HERE/README.md" "$HERE/install.sh" "$APP/" 2>/dev/null || true
fi
cat > "$BIN" <<EOF
#!/bin/sh
export PYTHONPATH="$APP\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m wolfforge "\$@"
EOF
chmod +x "$BIN"
export PATH="$HOME/.local/bin:$PATH"

# LibreWolf creates its profile on first start
if ! "$BIN" status 2>/dev/null | grep -q "^LibreWolf .*/"; then
  say "Letting LibreWolf create its profile (headless, a few seconds) …"
  if command -v librewolf >/dev/null; then
    timeout 12 librewolf --headless about:blank >/dev/null 2>&1 || true
  else
    timeout 15 flatpak run io.gitlab.librewolf-community --headless about:blank >/dev/null 2>&1 || true
  fi
fi

if [ "${1:-}" = "--apply" ]; then
  "$BIN" apply
else
  "$BIN"
fi
