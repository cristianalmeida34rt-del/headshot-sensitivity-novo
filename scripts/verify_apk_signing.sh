#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
TARGET="${2:-}"
EXPECTED_FILE="$(dirname "$0")/apk_signing_sha1.txt"

if [[ -z "$MODE" || -z "$TARGET" || ! -f "$EXPECTED_FILE" ]]; then
  echo "Uso: $0 --apk <arquivo.apk> ou --keystore <arquivo.keystore>" >&2
  exit 2
fi

EXPECTED="$(tr -d ':[:space:]' < "$EXPECTED_FILE" | tr '[:lower:]' '[:upper:]')"
case "$MODE" in
  --apk)
    [[ -s "$TARGET" ]] || { echo "APK não encontrado: $TARGET" >&2; exit 2; }
    ACTUAL="$(LC_ALL=C keytool -printcert -jarfile "$TARGET" 2>&1 | awk -F': ' '/SHA1:/{print $2; exit}')"
    ;;
  --keystore)
    [[ -s "$TARGET" ]] || { echo "Keystore não encontrado: $TARGET" >&2; exit 2; }
    ACTUAL="$(LC_ALL=C keytool -list -v -keystore "$TARGET" -storepass android -alias androiddebugkey 2>&1 | awk -F': ' '/SHA1:/{print $2; exit}')"
    ;;
  *)
    echo "Modo inválido: $MODE" >&2
    exit 2
    ;;
esac
ACTUAL="$(printf '%s' "$ACTUAL" | tr -d ':[:space:]' | tr '[:lower:]' '[:upper:]')"
if [[ -z "$ACTUAL" || "$ACTUAL" != "$EXPECTED" ]]; then
  echo "::error::Assinatura incompatível; publicação bloqueada para proteger a atualização sobre instalações existentes." >&2
  echo "Esperado SHA-1: $(cat "$EXPECTED_FILE")" >&2
  echo "Encontrado SHA-1: ${ACTUAL:-indisponível}" >&2
  exit 1
fi
echo "Assinatura validada: o SHA-1 do APK/keystore corresponde ao certificado publicado anteriormente."
