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
LOCK_FILE="/tmp/palworld-stats.lock"

log() { printf '%s [stats] %s\n' "$(date '+%F %T')" "$*"; }

exec 9>"$LOCK_FILE"
flock -n 9 || { log "outra publicacao em andamento; saindo."; exit 0; }

mkdir -p "$DOCS"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

log "lendo o save..."
if ! "$COMPOSE_DIR/pal-stats.sh" --json > "$tmp/dados.json" 2>/dev/null; then
  log "falha ao ler o save; nada publicado."
  exit 1
fi
[ -s "$tmp/dados.json" ] || { log "JSON vazio; nada publicado."; exit 1; }

# Compara ignorando o carimbo de hora.
if [ -f "$DOCS/dados.json" ] \
   && diff -q <(jq -S 'del(.gerado_em)' "$DOCS/dados.json" 2>/dev/null) \
              <(jq -S 'del(.gerado_em)' "$tmp/dados.json") >/dev/null 2>&1; then
  log "nada mudou desde a ultima publicacao."
  exit 0
fi

log "dados mudaram; gerando dashboard..."
cp "$tmp/dados.json" "$DOCS/dados.json"
python3 "$COMPOSE_DIR/palstats/gerar-dashboard.py" "$DOCS/dados.json" "$DOCS/index.html" >/dev/null

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
