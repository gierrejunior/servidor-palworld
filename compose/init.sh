#!/usr/bin/env bash
#
# Mantém o servidor Palworld no ar, atualizado e com o save íntegro.
#
#   init.sh            checa e só age se houver update ou se o servidor caiu
#   init.sh --force    recria o container mesmo estando tudo certo
#
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$COMPOSE_DIR/compose.yaml"
SAVED_DIR="$COMPOSE_DIR/Saved"
WORLD_ID="$(ls "$SAVED_DIR/SaveGames/0" 2>/dev/null | head -1 || true)"
SAVE_DIR="$SAVED_DIR/SaveGames/0/$WORLD_ID"
BACKUP_DIR="$SAVE_DIR/backup/world"
CONTAINER="palworld-server"
REGISTRY_REPO="pocketpairjp/palserver"
ROOT_IMAGE="alpine"
API_PORT=8212

PULL_ATTEMPTS=3
MAX_RESTORE_ATTEMPTS=5
STARTUP_TIMEOUT=180
PLAYER_POLL_INTERVAL=300
PLAYER_WAIT_MAX=21600
KEEP_SNAPSHOTS=10

LOCK_FILE="/tmp/palworld-init.lock"
LOG_FILE="$COMPOSE_DIR/init.log"
LOG_MAX_BYTES=5242880

# watchdog = só levanta se caiu (nunca atualiza)  |  daily = checa update
# force    = ciclo completo agora, sem esperar jogadores
MODE="daily"
case "${1:-}" in
  --watchdog) MODE="watchdog" ;;
  --force)    MODE="force" ;;
  "")         ;;
  *) printf 'uso: %s [--watchdog|--force]\n' "$0" >&2; exit 2 ;;
esac

UPDATE_TAG=""
ADMIN_PW=""

log()  { printf '%s [%s] %s\n'  "$(date '+%F %T')" "$MODE" "$*"; }
warn() { printf '%s [aviso] %s\n' "$(date '+%F %T')" "$*"; }
err()  { printf '%s [erro] %s\n'  "$(date '+%F %T')" "$*" >&2; }

# Impede que uma execução atropele outra — o ciclo diário pode ficar horas
# esperando jogadores saírem, e o watchdog roda a cada 5 min nesse meio-tempo.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  [ "$MODE" = "watchdog" ] && exit 0
  err "Outra execução do init.sh está em andamento; abortando."
  exit 1
fi
printf '%s\n' "$$" >&9

# O watchdog roda a cada 5 min; sem isso o init.log cresce para sempre.
# Trunca no lugar para não invalidar o descritor que o cron mantém aberto.
rotate_log() {
  local size
  [ -f "$LOG_FILE" ] || return 0
  size="$(stat -c %s "$LOG_FILE" 2>/dev/null || echo 0)"
  [ "$size" -gt "$LOG_MAX_BYTES" ] || return 0
  tail -n 2000 "$LOG_FILE" >"$LOG_FILE.tmp" 2>/dev/null || return 0
  cat "$LOG_FILE.tmp" >"$LOG_FILE"
  rm -f "$LOG_FILE.tmp"
}
rotate_log

# Saved/ pertence ao uid 999 do container; sem sudo, escrevemos via container root.
as_root() {
  docker run --rm -v "$SAVED_DIR:/data" "$ROOT_IMAGE" sh -euc "$1"
}

# ---------------------------------------------------------------- versão ----

current_tag() {
  sed -n 's|^[[:space:]]*image:[[:space:]]*[^[:space:]]*palserver:\(.*\)$|\1|p' "$COMPOSE_FILE"
}

latest_tag() {
  local token tags
  token="$(curl -fsS --max-time 30 \
    "https://ghcr.io/token?scope=repository:${REGISTRY_REPO}:pull&service=ghcr.io" \
    | grep -o '"token":"[^"]*' | cut -d'"' -f4)" || return 1
  tags="$(curl -fsS --max-time 30 -H "Authorization: Bearer $token" \
    "https://ghcr.io/v2/${REGISTRY_REPO}/tags/list")" || return 1
  printf '%s' "$tags" \
    | tr ',' '\n' | grep -o '"v[0-9][^"]*"' | tr -d '"' \
    | sed 's/^v//' | sort -V | tail -1 | sed 's/^/v/'
}

detect_update() {
  local cur new
  cur="$(current_tag)"
  log "Versão instalada: $cur"

  if ! new="$(latest_tag)" || [ -z "$new" ]; then
    warn "Registry inacessível; seguindo com $cur"
    return 0
  fi

  if [ "$new" = "$cur" ]; then
    log "Já está na versão mais recente."
  else
    log "Nova versão disponível: $new"
    UPDATE_TAG="$new"
  fi
}

bump_compose_tag() {
  sed -i "s|^\([[:space:]]*image:[[:space:]]*[^[:space:]]*palserver:\).*|\1${UPDATE_TAG}|" "$COMPOSE_FILE"
  log "compose.yaml atualizado para $UPDATE_TAG"
}

# ------------------------------------------------------------- REST API ----

container_ip() {
  docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER" 2>/dev/null || true
}

admin_pw() {
  if [ -z "$ADMIN_PW" ]; then
    ADMIN_PW="$(as_root 'sed -n "s/.*AdminPassword=\"\([^\"]*\)\".*/\1/p" /data/Config/LinuxServer/PalWorldSettings.ini' 2>/dev/null | tr -d '\r\n')" || return 1
  fi
  [ -n "$ADMIN_PW" ] || return 1
  printf '%s' "$ADMIN_PW"
}

api_get() {
  local path="$1" ip pw
  ip="$(container_ip)"; [ -n "$ip" ] || return 1
  pw="$(admin_pw)" || return 1
  curl -fsS --max-time 15 -u "admin:$pw" "http://$ip:$API_PORT$path"
}

api_post() {
  local path="$1" data="${2:-}" ip pw
  ip="$(container_ip)"; [ -n "$ip" ] || return 1
  pw="$(admin_pw)" || return 1
  curl -fsS --max-time 90 -X POST -u "admin:$pw" \
    -H 'Content-Type: application/json' -d "$data" \
    "http://$ip:$API_PORT$path" >/dev/null
}

players_online() {
  local body
  body="$(api_get /v1/api/players)" || return 1
  jq -er '.players | length' <<<"$body" 2>/dev/null || return 1
}

# Espera o servidor esvaziar antes de derrubar. Se a API não responder, segue —
# ficar preso para sempre seria pior do que desconectar alguém às 5h.
wait_for_empty() {
  local waited=0 n
  while :; do
    if ! n="$(players_online)"; then
      warn "Não consegui consultar os jogadores; prosseguindo com a manutenção."
      return 0
    fi

    if [ "$n" -eq 0 ]; then
      log "Nenhum jogador online — liberado para reiniciar."
      return 0
    fi

    if [ "$waited" -ge "$PLAYER_WAIT_MAX" ]; then
      warn "Esperei $((PLAYER_WAIT_MAX / 3600))h e ainda há $n jogador(es); prosseguindo."
      return 0
    fi

    log "$n jogador(es) online — nova checagem em $((PLAYER_POLL_INTERVAL / 60)) min."
    sleep "$PLAYER_POLL_INTERVAL"
    waited=$((waited + PLAYER_POLL_INTERVAL))
  done
}

# O servidor ignora SIGTERM: `docker stop` sempre termina em SIGKILL, e um
# SIGKILL no meio da gravação é o que corrompeu o save. O caminho limpo é
# mandar salvar e desligar pela API, e só então derrubar o container.
graceful_stop() {
  local n i

  if n="$(players_online)" && [ "$n" -gt 0 ]; then
    api_post /v1/api/announce '{"message":"Manutencao: o servidor reinicia em 30 segundos."}' || true
    sleep 30
  fi

  if api_post /v1/api/save; then
    log "Mundo salvo via REST API."
  else
    warn "Não consegui salvar via API; contando com o autosave."
  fi

  # Sem isso o Docker reergue o servidor entre o shutdown e o down.
  docker update --restart=no "$CONTAINER" >/dev/null 2>&1 || true

  if api_post /v1/api/shutdown '{"waittime":1,"message":"Manutencao"}'; then
    log "Shutdown solicitado; aguardando o servidor encerrar sozinho..."
    for i in $(seq 1 45); do
      if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" != "true" ]; then
        log "Encerrou limpo em ~$((i * 2))s (exit $(docker inspect -f '{{.State.ExitCode}}' "$CONTAINER" 2>/dev/null))."
        break
      fi
      sleep 2
    done
  else
    warn "API de shutdown indisponível; caindo para o stop do Docker."
  fi

  log "Removendo o container..."
  docker compose -f "$COMPOSE_FILE" down -t 30 --remove-orphans
}

# ----------------------------------------------------------------- disco ----

avail_gb() {
  local dir
  dir="$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)"
  df -BG --output=avail "$dir" 2>/dev/null | tail -1 | tr -dc '0-9'
}

# Só remove imagens que nenhum container referencia. O palserver em uso está
# protegido porque o pull acontece com o servidor ainda de pé.
free_disk_space() {
  local before after
  before="$(avail_gb)"
  warn "Liberando espaço (${before}GB livres): imagens órfãs e cache de build."
  docker image prune -af >/dev/null 2>&1 || true
  docker builder prune -af >/dev/null 2>&1 || true
  after="$(avail_gb)"
  log "Espaço livre: ${before}GB -> ${after}GB"
}

pull_update() {
  local ref="ghcr.io/${REGISTRY_REPO}:${UPDATE_TAG}" out attempt
  for attempt in $(seq 1 "$PULL_ATTEMPTS"); do
    log "Baixando $ref (tentativa $attempt/$PULL_ATTEMPTS, $(avail_gb)GB livres)..."
    if out="$(docker pull "$ref" 2>&1)"; then
      log "Imagem $UPDATE_TAG pronta."
      return 0
    fi

    printf '%s\n' "$out" | tail -3
    if grep -qiE 'no space left|not enough space|disk full' <<<"$out"; then
      free_disk_space
    else
      warn "Falha no download; nova tentativa em 30s."
      sleep 30
    fi
  done

  warn "Não consegui baixar $UPDATE_TAG após $PULL_ATTEMPTS tentativas; permaneço em $(current_tag)."
  return 1
}

# ------------------------------------------------------------------ save ----

good_backups() {
  [ -d "$BACKUP_DIR" ] || return 0
  local d
  for d in $(ls -1 "$BACKUP_DIR" 2>/dev/null | sort -r); do
    if [ -s "$BACKUP_DIR/$d/Level.sav" ]; then
      printf '%s\n' "$d"
    fi
  done
}

# Sem pipe para o `head`: fechar o pipe cedo mata good_backups com SIGPIPE.
newest_backup() {
  [ -d "$BACKUP_DIR" ] || return 0
  local d
  for d in $(ls -1 "$BACKUP_DIR" 2>/dev/null | sort -r); do
    if [ -s "$BACKUP_DIR/$d/Level.sav" ]; then
      printf '%s\n' "$d"
      return 0
    fi
  done
}

# Cópia extra antes de mexer no container — os backups do jogo são de hora em
# hora, isso aqui guarda o estado exato de agora.
snapshot_save() {
  [ -n "$WORLD_ID" ] || return 0
  [ -s "$SAVE_DIR/Level.sav" ] || return 0

  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  log "Snapshot do save em Saved/snapshots/$stamp"
  as_root "
    SAVE=/data/SaveGames/0/$WORLD_ID
    DST=/data/snapshots/$stamp
    mkdir -p \$DST
    cp -a \$SAVE/Level.sav \$SAVE/LevelMeta.sav \$SAVE/Players \$DST/
  " || warn "Falha ao criar o snapshot."
}

prune_snapshots() {
  as_root "
    cd /data/snapshots 2>/dev/null || exit 0
    ls -1 | sort -r | tail -n +$((KEEP_SNAPSHOTS + 1)) | while read -r d; do rm -rf \"\$d\"; done
  " || true
}

restore_backup() {
  local stamp="$1"
  local archive="corrupted-save-$(date +%Y%m%d-%H%M%S)"
  log "Restaurando backup $stamp (save atual arquivado em Saved/$archive)"
  as_root "
    SAVE=/data/SaveGames/0/$WORLD_ID
    SRC=\$SAVE/backup/world/$stamp
    mkdir -p /data/$archive
    cp -a \$SAVE/Level.sav \$SAVE/LevelMeta.sav \$SAVE/Players /data/$archive/ 2>/dev/null || true
    cp -a \$SRC/Level.sav \$SAVE/Level.sav
    cp -a \$SRC/LevelMeta.sav \$SAVE/LevelMeta.sav
    rm -rf \$SAVE/Players
    cp -a \$SRC/Players \$SAVE/Players
  "
}

preflight_save() {
  if [ -z "$WORLD_ID" ]; then
    log "Nenhum mundo salvo encontrado — o servidor criará um novo."
    return 0
  fi

  log "Mundo: $WORLD_ID"

  if [ -s "$SAVE_DIR/Level.sav" ]; then
    log "Level.sav OK ($(stat -c %s "$SAVE_DIR/Level.sav") bytes)"
    return 0
  fi

  warn "Level.sav ausente ou vazio — save corrompido."
  local first
  first="$(newest_backup)"
  if [ -z "$first" ]; then
    err "Nenhum backup utilizável em $BACKUP_DIR"
    return 1
  fi
  restore_backup "$first"
}

report_save() {
  [ -n "$WORLD_ID" ] || return 0
  local size newest
  size="$(stat -c %s "$SAVE_DIR/Level.sav" 2>/dev/null || echo 0)"
  newest="$(newest_backup)"
  log "Save: ${size} bytes | backup mais recente: ${newest:-nenhum}"
}

# ----------------------------------------------------------------- ciclo ----

# Duas amostras: um container em crash-loop pode ser flagrado "Running" entre
# reinícios, mas o RestartCount se move.
server_healthy() {
  local run1 run2 count1 count2
  run1="$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" || return 1
  [ "$run1" = "true" ] || return 1
  count1="$(docker inspect -f '{{.RestartCount}}' "$CONTAINER")"

  sleep 10

  run2="$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" || return 1
  count2="$(docker inspect -f '{{.RestartCount}}' "$CONTAINER")"

  [ "$run2" = "true" ] && [ "$count1" = "$count2" ]
}

# 0 = subiu, 1 = save corrompido, 2 = falhou por outro motivo
wait_for_server() {
  local deadline=$((SECONDS + STARTUP_TIMEOUT)) logs
  while [ $SECONDS -lt $deadline ]; do
    logs="$(docker compose -f "$COMPOSE_FILE" logs --no-color 2>/dev/null || true)"

    if grep -q "Save data is corrupted" <<<"$logs"; then
      return 1
    fi
    if grep -q "Running Palworld dedicated server on" <<<"$logs"; then
      return 0
    fi
    if [ "$(docker inspect -f '{{.State.Restarting}}' "$CONTAINER" 2>/dev/null)" = "true" ]; then
      return 2
    fi
    sleep 3
  done
  return 2
}

start_server() {
  local attempt=0 status
  local -a backups
  mapfile -t backups < <(good_backups)

  while :; do
    log "Subindo o container..."
    docker compose -f "$COMPOSE_FILE" up -d

    set +e
    wait_for_server
    status=$?
    set -e

    case $status in
      0)
        log "Servidor no ar em :8211 (versão $(current_tag))"
        return 0
        ;;
      1)
        warn "Servidor recusou o save (corrompido)."
        docker compose -f "$COMPOSE_FILE" down

        if [ "$attempt" -ge "$MAX_RESTORE_ATTEMPTS" ] || [ "$attempt" -ge "${#backups[@]}" ]; then
          err "Backups esgotados após $attempt tentativa(s). Restaure manualmente."
          return 1
        fi

        restore_backup "${backups[$attempt]}"
        attempt=$((attempt + 1))
        ;;
      *)
        err "Servidor não subiu dentro de ${STARTUP_TIMEOUT}s. Últimas linhas:"
        docker compose -f "$COMPOSE_FILE" logs --no-color --tail 30
        return 1
        ;;
    esac
  done
}

# Cada imagem do palserver ocupa ~13GB. Nunca toca em Saved/.
cleanup_old_images() {
  local keep="ghcr.io/${REGISTRY_REPO}:$(current_tag)"
  local id ref target removed=0

  while read -r id ref; do
    [ -z "$id" ] && continue
    [ "$ref" = "$keep" ] && continue

    target="$ref"
    [ "${ref##*:}" = "<none>" ] && target="$id"

    if docker rmi "$target" >/dev/null 2>&1; then
      log "Imagem antiga removida: $ref"
      removed=$((removed + 1))
    else
      warn "Não foi possível remover $ref (em uso por outro container?)"
    fi
  done < <(docker images --format '{{.ID}} {{.Repository}}:{{.Tag}}' "ghcr.io/${REGISTRY_REPO}")

  # Camadas soltas de downloads interrompidos.
  docker image prune -f >/dev/null 2>&1 || true

  [ "$removed" -eq 0 ] && log "Nenhuma imagem antiga para limpar."
  return 0
}

# ------------------------------------------------------------------ main ----

main() {
  cd "$COMPOSE_DIR"

  # O watchdog nunca atualiza: ele só existe para levantar o que caiu.
  [ "$MODE" != "watchdog" ] && detect_update

  local healthy=0
  server_healthy && healthy=1 || true

  if [ -z "$UPDATE_TAG" ] && [ "$healthy" -eq 1 ] && [ "$MODE" != "force" ]; then
    log "Servidor no ar e sem pendências — nada a fazer."
    report_save
    return 0
  fi

  # Baixa antes de parar: o servidor segue no ar durante o download e a imagem
  # em uso fica protegida de qualquer limpeza de espaço.
  if [ -n "$UPDATE_TAG" ]; then
    pull_update || UPDATE_TAG=""

    if [ -z "$UPDATE_TAG" ] && [ "$healthy" -eq 1 ]; then
      warn "Update indisponível e servidor de pé — deixo como está."
      report_save
      return 0
    fi
  fi

  if [ "$healthy" -eq 1 ]; then
    [ "$MODE" != "force" ] && wait_for_empty
    snapshot_save
    graceful_stop
  else
    warn "Servidor fora do ar — iniciando recuperação."
    snapshot_save
    docker compose -f "$COMPOSE_FILE" down --remove-orphans >/dev/null 2>&1 || true
  fi

  [ -n "$UPDATE_TAG" ] && bump_compose_tag

  preflight_save
  start_server
  cleanup_old_images
  prune_snapshots
  report_save
}

main "$@"
