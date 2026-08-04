#!/usr/bin/env bash
#
# Publica o estado ao vivo do servidor num Gist, que o dashboard le.
#
# Roda a cada poucos minutos e consulta apenas a REST API - nao le o save, nao
# usa container, leva menos de um segundo. Nada disso passa pelo repositorio:
# commit a cada minuto estouraria o limite de 10 builds/hora do GitHub Pages.
#
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAVED_DIR="$COMPOSE_DIR/Saved"
ESTADO="$COMPOSE_DIR/live-state.json"
GIST_ID_FILE="$COMPOSE_DIR/gist-id"
CONTAINER="palworld-server"
API_PORT=8212
LOCK_FILE="/tmp/palworld-live.lock"

log() { printf '%s [live] %s\n' "$(date '+%F %T')" "$*"; }

exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

agora="$(date '+%Y-%m-%dT%H:%M:%S%:z')"

ip="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER" 2>/dev/null || true)"
pw=""
[ -n "$ip" ] && pw="$(docker run --rm -v "$SAVED_DIR:/data" alpine \
  sh -c 'sed -n "s/.*AdminPassword=\"\([^\"]*\)\".*/\1/p" /data/Config/LinuxServer/PalWorldSettings.ini' \
  2>/dev/null | tr -d '\r\n' || true)"

api() { curl -fsS --max-time 8 -u "admin:$pw" "http://$ip:$API_PORT$1" 2>/dev/null; }

if [ -n "$ip" ] && [ -n "$pw" ] && players="$(api /v1/api/players)" && metrics="$(api /v1/api/metrics)"; then
  no_ar=true
else
  no_ar=false
  players='{"players":[]}'
  metrics='{}'
fi

# O mapa de "visto por ultimo" mora aqui e nao no Gist: evita uma leitura de
# rede a cada execucao e sobrevive a qualquer problema de publicacao.
[ -f "$ESTADO" ] || echo '{}' > "$ESTADO"

jq -n \
  --argjson anterior "$(cat "$ESTADO")" \
  --argjson players "$players" \
  --arg agora "$agora" '
  $anterior + ([$players.players[]? | {(.name): $agora}] | add // {})
' > "$tmp/estado.json"
mv "$tmp/estado.json" "$ESTADO"

# Apenas apelido, nivel e ping. IP e Steam ID ficam de fora de proposito.
jq -n \
  --arg ts "$agora" \
  --argjson no_ar "$no_ar" \
  --argjson players "$players" \
  --argjson metrics "$metrics" \
  --argjson visto "$(cat "$ESTADO")" '
  {
    ts: $ts,
    no_ar: $no_ar,
    online: [$players.players[]? | {n: .name, nv: .level, p: (.ping | round)}],
    servidor: {
      fps: ($metrics.serverfps // null),
      dia: ($metrics.days // null),
      max: ($metrics.maxplayernum // null),
      uptime: ($metrics.uptime // null)
    },
    visto: $visto
  }
' > "$tmp/live.json"

if [ ! -s "$GIST_ID_FILE" ]; then
  log "criando o Gist..."
  url="$(gh gist create "$tmp/live.json" --public \
    --desc "Estado ao vivo do servidor Palworld SonicCurupiraBeer")"
  printf '%s\n' "${url##*/}" > "$GIST_ID_FILE"
  log "Gist criado: $url"
else
  gh gist edit "$(cat "$GIST_ID_FILE")" -f live.json "$tmp/live.json" >/dev/null
fi

log "$(jq -r '"\(.online | length) online · fps \(.servidor.fps // "?")"' "$tmp/live.json")"
