#!/bin/sh
# Installiert ClaudeGravity als eigenständiges Programm (ohne Python) unter macOS und Linux:
#
#   curl -fsSL https://github.com/gb-web-de/claudegravity-loop/releases/latest/download/claudegravity-install.sh | sh
#
# Lädt das passende Archiv vom GitHub-Release, prüft die SHA-256-Summe und startet `claudegravity install`:
# Programm nach ~/.local/bin, MCP-Server und Skill in alle gefundenen Clients. Argumente gehen an den Installer:
#
#   curl -fsSL …/claudegravity-install.sh | sh -s -- --project ~/projekte/shop --no-path
#
# CLAUDEGRAVITY_VERSION=v1.6.0 nimmt eine bestimmte Version, CLAUDEGRAVITY_ARCHIVE=<datei> ein lokales Archiv.
set -eu

REPO="gb-web-de/claudegravity-loop"

fail() {
  echo "[!] $*" >&2
  exit 1
}

case "$(uname -s)" in
  Linux) os=linux ;;
  Darwin) os=macos ;;
  *) fail "System $(uname -s) wird nicht unterstützt. Unter Windows: claudegravity-install.ps1" ;;
esac
case "$(uname -m)" in
  x86_64 | amd64) arch=x86_64 ;;
  arm64 | aarch64) arch=arm64 ;;
  *) fail "Prozessor $(uname -m) wird nicht unterstützt. Mit Python 3.10+: pipx install git+https://github.com/$REPO" ;;
esac
asset="claudegravity-$os-$arch.tar.gz"

# Der Release-Workflow trägt hier die Version des Releases ein; aus dem Repository geht es zur neuesten
release_tag="__RELEASE_TAG__"
case "$release_tag" in __*) release_tag="" ;; esac
version="${CLAUDEGRAVITY_VERSION:-$release_tag}"
if [ -n "$version" ]; then
  base="https://github.com/$REPO/releases/download/$version"
else
  base="https://github.com/$REPO/releases/latest/download"
fi

fetch() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 3 -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else
    fail "curl oder wget wird gebraucht."
  fi
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d ' ' -f 1
  else
    shasum -a 256 "$1" | cut -d ' ' -f 1
  fi
}

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT INT TERM

if [ -n "${CLAUDEGRAVITY_ARCHIVE:-}" ]; then
  cp "$CLAUDEGRAVITY_ARCHIVE" "$tmp/$asset"
else
  echo "[*] Lade $base/$asset"
  fetch "$base/$asset" "$tmp/$asset" || fail "Download fehlgeschlagen. Gibt es $asset in diesem Release?"
  fetch "$base/SHA256SUMS" "$tmp/SHA256SUMS" || fail "SHA256SUMS fehlt im Release."
  expected=$(awk -v name="$asset" '$2 == name || $2 == "*" name { print $1 }' "$tmp/SHA256SUMS")
  [ -n "$expected" ] || fail "$asset steht nicht in SHA256SUMS."
  [ "$(sha256 "$tmp/$asset")" = "$expected" ] || fail "Prüfsumme von $asset stimmt nicht."
fi

tar -xzf "$tmp/$asset" -C "$tmp"
"$tmp/claudegravity/claudegravity" install "$@"
