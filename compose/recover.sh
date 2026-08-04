#!/usr/bin/env bash
#
# Resgate manual, para quando o automático não resolveu.
#
# Destrava qualquer execução presa do init.sh e roda o ciclo completo na marra:
# para o container, busca atualização, conserta o save e sobe — sem esperar
# jogadores saírem. É o plano B; no dia a dia quem manda é o init.sh.
#
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="/tmp/palworld-init.pid"

log() { printf '%s [recover] %s\n' "$(date '+%F %T')" "$*"; }

if [ -s "$PID_FILE" ]; then
  pid="$(head -1 "$PID_FILE" | tr -dc '0-9')"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    log "init.sh preso no PID $pid (provavelmente esperando jogadores) — encerrando."
    kill -TERM "$pid" 2>/dev/null || true

    for _ in $(seq 1 10); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    kill -KILL "$pid" 2>/dev/null || true
  fi
fi

log "Iniciando ciclo completo."
exec "$DIR/init.sh" --force
