#!/bin/bash

set -e
set -o pipefail

# Logging aktivieren
LOGFILE="setup.log"
exec > >(tee -a "$LOGFILE") 2>&1

# .env einlesen
if [ ! -f .env ]; then
  echo "❌ .env-Datei nicht gefunden!"
  exit 1
fi
source .env

VERSION=${LOGANALYZER_VERSION:-4.1.13}
TARGET_DIR="./resources/loganalyzer-${VERSION}"
DOWNLOAD_URL="https://download.adiscon.com/loganalyzer/loganalyzer-${VERSION}.tar.gz"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

echo "🔧 Starte Setup für Loganalyzer v$VERSION"

# Prüfe, ob Loganalyzer bereits entpackt wurde
if [ -d "$TARGET_DIR/src" ]; then
  echo "ℹ️ Loganalyzer bereits vorhanden unter $TARGET_DIR/src – überspringe Download."
else
  echo "📥 Lade Loganalyzer von $DOWNLOAD_URL ..."
  wget -q "$DOWNLOAD_URL" -O "$TMP_DIR/loganalyzer.tar.gz" || {
    echo "❌ Download fehlgeschlagen. Prüfe Version oder URL."
    exit 1
  }

  echo "📦 Entpacke Archiv nach $TARGET_DIR/src ..."
  mkdir -p "$TARGET_DIR/src"
  tar -xzf "$TMP_DIR/loganalyzer.tar.gz" -C "$TMP_DIR"
  cp -r "$TMP_DIR/loganalyzer-${VERSION}/src/"* "$TARGET_DIR/src/"
  rm -rf "$TMP_DIR"
  echo "✅ Loganalyzer bereitgestellt."
fi

# Docker-Image bauen
# echo "🐳 Baue Docker-Image loganalyzer:${VERSION} ..."
# docker build \
#   --build-arg LOGANALYZER_VERSION="$VERSION" \
#   -t "loganalyzer:${VERSION}" \
#   .

# Container bauen und starten
echo "🚀 Starte Container mit docker-compose ..."
docker compose --env-file .env up -d --build 

# Abschlussinfo
echo ""
echo "🎉 Setup abgeschlossen."
echo ""
echo "🔎 Loganalyzer ist erreichbar unter: http://localhost:${LOGANALYZER_PORT}"
echo "📨 Syslog-NG ist erreichbar auf den folgenden Ports:"
echo "   - UDP: ${SYSLOG_UDP_PORT}"
echo "   - TCP: ${SYSLOG_TCP_PORT}"
echo ""