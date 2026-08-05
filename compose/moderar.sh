#!/usr/bin/env bash
#
# Moderacao do servidor: expulsar, suspender por tempo, banir e perdoar.
#
#   moderar.sh online                    quem esta online (com o id)
#   moderar.sh expulsar <nome> [motivo]  derruba agora; pode voltar
#   moderar.sh suspender <nome> <tempo> [motivo]
#   moderar.sh banir <nome> [motivo]     permanente
#   moderar.sh perdoar <nome>            remove o banimento
#   moderar.sh lista                     suspensoes em vigor
#
# Tempo: 30m, 6h, 7d.
#
# A API do Palworld nao tem suspensao temporaria - o ban dura ate alguem
# desbanir. A suspensao aqui e um ban somado a um agendamento: o `--tick`,
# chamado pelo cron, perdoa quem ja cumpriu o prazo.
#
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAVED_DIR="$COMPOSE_DIR/Saved"
IDENTIDADES="$COMPOSE_DIR/jogadores.json"
SUSPENSOES="$COMPOSE_DIR/suspensoes.json"
CONTAINER="palworld-server"
API_PORT=8212

log()  { printf '%s\n' "$*"; }
erro() { printf '\033[1;31m%s\033[0m\n' "$*" >&2; }

ip="$([ "$(docker inspect -f "{{.HostConfig.NetworkMode}}" "$CONTAINER" 2>/dev/null)" = host ] && echo 127.0.0.1 || docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" "$CONTAINER" 2>/dev/null || true)"
[ -n "$ip" ] || { erro "servidor fora do ar"; exit 1; }

pw="$(docker run --rm --network none -v "$SAVED_DIR:/data" alpine \
  sh -c 'sed -n "s/.*AdminPassword=\"\([^\"]*\)\".*/\1/p" /data/Config/LinuxServer/PalWorldSettings.ini' \
  2>/dev/null | tr -d '\r\n')"
[ -n "$pw" ] || { erro "nao consegui ler a senha de admin"; exit 1; }

api_get()  { curl -fsS --max-time 10 -u "admin:$pw" "http://$ip:$API_PORT$1"; }
api_post() {
  curl -fsS --max-time 20 -X POST -u "admin:$pw" -H 'Content-Type: application/json' \
    -d "$2" "http://$ip:$API_PORT$1" >/dev/null
}

[ -f "$SUSPENSOES" ]  || echo '{}' > "$SUSPENSOES"
[ -f "$IDENTIDADES" ] || echo '{}' > "$IDENTIDADES"

# Procura o id primeiro entre os online, depois no historico local.
resolver() {
  local nome="$1" id
  id="$(api_get /v1/api/players 2>/dev/null \
    | jq -r --arg n "$nome" '.players[]? | select(.name == $n) | .userId' | head -1)"
  [ -n "$id" ] && { printf '%s' "$id"; return 0; }

  id="$(jq -r --arg n "$nome" '.[$n].userid // empty' "$IDENTIDADES")"
  [ -n "$id" ] && { printf '%s' "$id"; return 0; }
  return 1
}

segundos() {
  local t="$1" n="${1%[mhd]}"
  case "$t" in
    *m) echo $((n * 60)) ;;
    *h) echo $((n * 3600)) ;;
    *d) echo $((n * 86400)) ;;
    *)  return 1 ;;
  esac
}

confirmar() {
  printf '%s [s/N] ' "$1"
  read -r r </dev/tty
  [[ "$r" =~ ^[sSyY]$ ]]
}

cmd="${1:-}"
case "$cmd" in

  online)
    api_get /v1/api/players | jq -r '
      if (.players | length) == 0 then "ninguem online"
      else .players[] | "\(.name)\t\(.userId)\tnv \(.level)"
      end' | column -t -s$'\t'
    ;;

  expulsar|kick)
    nome="${2:?uso: moderar.sh expulsar <nome> [motivo]}"
    motivo="${3:-Expulso pela administracao}"
    id="$(resolver "$nome")" || { erro "nao encontrei o id de '$nome'"; exit 1; }
    api_post /v1/api/kick "$(jq -nc --arg u "$id" --arg m "$motivo" '{userid:$u,message:$m}')"
    log "$nome expulso. Pode reconectar."
    ;;

  suspender)
    nome="${2:?uso: moderar.sh suspender <nome> <tempo> [motivo]}"
    tempo="${3:?informe o tempo: 30m, 6h, 7d}"
    motivo="${4:-Suspenso temporariamente}"
    dur="$(segundos "$tempo")" || { erro "tempo invalido: use 30m, 6h ou 7d"; exit 1; }
    id="$(resolver "$nome")" || { erro "nao encontrei o id de '$nome'"; exit 1; }

    ate="$(date -d "+$dur seconds" '+%Y-%m-%dT%H:%M:%S%:z')"
    confirmar "Suspender $nome por $tempo (até $(date -d "$ate" '+%d/%m %H:%M'))?" || { log "cancelado"; exit 0; }

    api_post /v1/api/ban "$(jq -nc --arg u "$id" --arg m "$motivo" '{userid:$u,message:$m}')"
    jq --arg u "$id" --arg n "$nome" --arg a "$ate" --arg m "$motivo" \
      '.[$u] = {nome:$n, ate:$a, motivo:$m}' "$SUSPENSOES" > "$SUSPENSOES.tmp"
    mv "$SUSPENSOES.tmp" "$SUSPENSOES"
    log "$nome suspenso até $(date -d "$ate" '+%d/%m às %H:%M'). Volta sozinho."
    ;;

  banir|ban)
    nome="${2:?uso: moderar.sh banir <nome> [motivo]}"
    motivo="${3:-Banido pela administracao}"
    id="$(resolver "$nome")" || { erro "nao encontrei o id de '$nome'"; exit 1; }
    confirmar "Banir $nome PERMANENTEMENTE?" || { log "cancelado"; exit 0; }
    api_post /v1/api/ban "$(jq -nc --arg u "$id" --arg m "$motivo" '{userid:$u,message:$m}')"
    log "$nome banido. Para reverter: moderar.sh perdoar $nome"
    ;;

  perdoar|unban)
    nome="${2:?uso: moderar.sh perdoar <nome>}"
    id="$(resolver "$nome")" || { erro "nao encontrei o id de '$nome'"; exit 1; }
    api_post /v1/api/unban "$(jq -nc --arg u "$id" '{userid:$u}')"
    jq --arg u "$id" 'del(.[$u])' "$SUSPENSOES" > "$SUSPENSOES.tmp"
    mv "$SUSPENSOES.tmp" "$SUSPENSOES"
    log "$nome perdoado."
    ;;

  lista)
    if [ "$(jq 'length' "$SUSPENSOES")" -eq 0 ]; then
      log "nenhuma suspensao em vigor"
    else
      jq -r 'to_entries[] | "\(.value.nome)\tate \(.value.ate[0:16] | sub("T"; " "))\t\(.value.motivo)"' \
        "$SUSPENSOES" | column -t -s$'\t'
    fi
    ;;

  --tick)
    # Chamado pelo cron: perdoa quem ja cumpriu o prazo.
    agora="$(date '+%s')"
    for id in $(jq -r 'keys[]' "$SUSPENSOES"); do
      ate="$(jq -r --arg u "$id" '.[$u].ate' "$SUSPENSOES")"
      nome="$(jq -r --arg u "$id" '.[$u].nome' "$SUSPENSOES")"
      [ "$(date -d "$ate" '+%s')" -gt "$agora" ] && continue
      if api_post /v1/api/unban "$(jq -nc --arg u "$id" '{userid:$u}')"; then
        jq --arg u "$id" 'del(.[$u])' "$SUSPENSOES" > "$SUSPENSOES.tmp"
        mv "$SUSPENSOES.tmp" "$SUSPENSOES"
        printf '%s [moderar] suspensao de %s expirou; perdoado\n' "$(date '+%F %T')" "$nome"
      fi
    done
    ;;

  *)
    sed -n '3,17p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
