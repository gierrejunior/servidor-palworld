#!/usr/bin/env bash
#
# Estatisticas do mundo a partir do Level.sav.
#
# Trabalha sobre uma COPIA do save, dentro de um container descartavel. O save
# real e montado em lugar nenhum e nada e instalado na maquina.
#
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAVED_DIR="$COMPOSE_DIR/Saved"
WORLD_ID="$(ls "$SAVED_DIR/SaveGames/0" 2>/dev/null | head -1 || true)"
SAVE="$SAVED_DIR/SaveGames/0/$WORLD_ID/Level.sav"
IMAGE="palworld-stats:local"

[ -n "$WORLD_ID" ] || { echo "nenhum mundo salvo encontrado" >&2; exit 1; }
[ -s "$SAVE" ] || { echo "Level.sav ausente ou vazio: $SAVE" >&2; exit 1; }

# A imagem carrega o ooz compilado; so reconstroi se o Dockerfile mudar.
if ! docker image inspect "$IMAGE" >/dev/null 2>&1 \
   || [ "$COMPOSE_DIR/palstats/Dockerfile" -nt "$(docker image inspect -f '{{.Metadata.LastTagTime}}' "$IMAGE" 2>/dev/null && echo /dev/null)" ] 2>/dev/null; then
  echo "construindo a imagem de analise (so na primeira vez)..." >&2
  docker build -q -t "$IMAGE" "$COMPOSE_DIR/palstats" >/dev/null
fi

# Copia para o container nunca enxergar o save real.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp "$SAVE" "$tmp/Level.sav"

# Sem o TZ o container roda em UTC e o relatorio sai com a hora errada.
TZ_HOST="$(cat /etc/timezone 2>/dev/null || readlink -f /etc/localtime | sed 's|.*/zoneinfo/||')"

docker run --rm --network none -e "TZ=${TZ_HOST:-UTC}" -v "$tmp:/work:ro" "$IMAGE" "$@" 2>/dev/null
