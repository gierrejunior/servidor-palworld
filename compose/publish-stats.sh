#!/usr/bin/env bash
#
# Regenera o dashboard a partir do save e publica no GitHub Pages.
#
# Comita apenas quando os numeros mudam de verdade: o carimbo de hora do
# relatorio muda a cada execucao e sozinho nao justifica um commit.
#
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$COMPOSE_DIR/.." && pwd)"
DOCS="$REPO_DIR/docs"
SAVED_DIR="$COMPOSE_DIR/Saved"
LOCK_FILE="/tmp/palworld-stats.lock"

log() { printf '%s [stats] %s\n' "$(date '+%F %T')" "$*"; }

exec 9>"$LOCK_FILE"
flock -n 9 || { log "outra publicacao em andamento; saindo."; exit 0; }

mkdir -p "$DOCS"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Ler o save custa ~3s de CPU e disputa com a simulacao. Se tem gente
# jogando, adia: o proximo horario pega o mesmo dado.
ip="$([ "$(docker inspect -f "{{.HostConfig.NetworkMode}}" palworld-server 2>/dev/null)" = host ] && echo 127.0.0.1 || docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" palworld-server 2>/dev/null || true)"
if [ -n "$ip" ]; then
  pw="$(docker run --rm --network none -v "$SAVED_DIR:/data" alpine \
    sh -c 'sed -n "s/.*AdminPassword=\\"\\([^\\"]*\\)\\".*/\\1/p" /data/Config/LinuxServer/PalWorldSettings.ini' 2>/dev/null | tr -d '\r\n' || true)"
  n="$(curl -fsS --max-time 8 -u "admin:$pw" "http://$ip:8212/v1/api/players" 2>/dev/null | jq -r '.players|length' 2>/dev/null || echo 0)"
  if [ "${n:-0}" -gt 0 ]; then
    log "$n jogador(es) online; adiando para nao competir por CPU."
    exit 0
  fi
fi

log "lendo o save..."
if ! "$COMPOSE_DIR/pal-stats.sh" --json > "$tmp/dados.json" 2>/dev/null; then
  log "falha ao ler o save; nada publicado."
  exit 1
fi
[ -s "$tmp/dados.json" ] || { log "JSON vazio; nada publicado."; exit 1; }

# Compara ignorando o carimbo de hora.
if [ -f "$DOCS/dados.json" ] \
   && diff -q <(jq -S 'del(.gerado_em, .gist)' "$DOCS/dados.json" 2>/dev/null) \
              <(jq -S 'del(.gerado_em, .gist)' "$tmp/dados.json") >/dev/null 2>&1; then
  log "nada mudou desde a ultima publicacao."
  exit 0
fi

log "dados mudaram; montando o site..."
python3 "$COMPOSE_DIR/palstats/gerar-dashboard.py" "$tmp/dados.json" "$DOCS" \
  "$(cat "$COMPOSE_DIR/gist-id" 2>/dev/null || true)" >/dev/null

cd "$REPO_DIR"
if git diff --quiet -- docs/; then
  log "sem diferenca no git; nada a commitar."
  exit 0
fi

resumo="$(jq -r '"\(.mundo.jogadores) jogadores, \(.mundo.pals) pals, \(.mundo.especies) especies"' "$DOCS/dados.json")"
git add docs/
git commit -q -m "chore: atualiza estatisticas do servidor

$resumo"

if git push -q origin main 2>/dev/null; then
  log "publicado: $resumo"
else
  log "commit feito, mas o push falhou (verifique a chave SSH no ambiente do cron)."
  exit 1
fi
