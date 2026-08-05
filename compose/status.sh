#!/usr/bin/env bash
#
# Mostra o estado do servidor: quem esta online, saude do container, save e
# disco. Somente leitura — nao para, nao reinicia, nao altera nada.
#
set -euo pipefail

COMPOSE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAVED_DIR="$COMPOSE_DIR/Saved"
WORLD_ID="$(ls "$SAVED_DIR/SaveGames/0" 2>/dev/null | head -1 || true)"
SAVE_DIR="$SAVED_DIR/SaveGames/0/$WORLD_ID"
BACKUP_DIR="$SAVE_DIR/backup/world"
CONTAINER="palworld-server"
API_PORT=8212

# Mostra o IP dos jogadores (dado pessoal; util so para moderacao/ban).
SHOW_IP=0
[ "${1:-}" = "--ip" ] && SHOW_IP=1

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
dim()  { printf '\033[2m%s\033[0m\n' "$*"; }

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  bold "SERVIDOR FORA DO AR"
  echo "  O container nao existe. Para levantar:"
  echo "    $COMPOSE_DIR/init.sh --watchdog"
  exit 1
fi

running="$(docker inspect -f '{{.State.Running}}' "$CONTAINER")"
restarts="$(docker inspect -f '{{.RestartCount}}' "$CONTAINER")"
image="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER")"
since="$(docker inspect -f '{{.State.StartedAt}}' "$CONTAINER")"
uptime_h="$(docker ps --filter "name=$CONTAINER" --format '{{.Status}}')"

bold "CONTAINER"
if [ "$running" = "true" ]; then
  echo "  estado ....... no ar ($uptime_h)"
else
  echo "  estado ....... PARADO"
fi
echo "  versao ....... ${image##*:}"
echo "  reinicios .... $restarts"
echo "  desde ........ $(date -d "$since" '+%d/%m %H:%M:%S' 2>/dev/null || echo "$since")"
echo

ip="$([ "$(docker inspect -f "{{.HostConfig.NetworkMode}}" "$CONTAINER" 2>/dev/null)" = host ] && echo 127.0.0.1 || docker inspect -f "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" "$CONTAINER" 2>/dev/null || true)"
pw="$(docker run --rm --network none -v "$SAVED_DIR:/data" alpine \
  sh -c 'sed -n "s/.*AdminPassword=\"\([^\"]*\)\".*/\1/p" /data/Config/LinuxServer/PalWorldSettings.ini' 2>/dev/null | tr -d '\r\n' || true)"

api() { curl -fsS --max-time 10 -u "admin:$pw" "http://$ip:$API_PORT$1" 2>/dev/null; }

if [ -n "$ip" ] && [ -n "$pw" ] && info="$(api /v1/api/info)"; then
  metrics="$(api /v1/api/metrics)"
  players="$(api /v1/api/players)"

  bold "SERVIDOR"
  echo "  nome ......... $(jq -r '.servername' <<<"$info")"
  echo "  fps .......... $(jq -r '.serverfps' <<<"$metrics") (media $(jq -r '.serverfpsaverage|floor' <<<"$metrics"))"
  echo "  dia no jogo .. $(jq -r '.days' <<<"$metrics")"
  echo "  bases ........ $(jq -r '.basecampnum' <<<"$metrics")"
  echo

  n="$(jq -r '.players|length' <<<"$players")"
  max="$(jq -r '.maxplayernum' <<<"$metrics")"
  bold "JOGADORES ($n/$max)"
  if [ "$n" -eq 0 ]; then
    dim "  ninguem online"
  elif [ "$SHOW_IP" -eq 1 ]; then
    jq -r '.players[] | "  \(.name)  nivel \(.level)  ping \(.ping|round)ms  \(.iP)"' <<<"$players"
  else
    jq -r '.players[] | "  \(.name)  nivel \(.level)  ping \(.ping|round)ms"' <<<"$players"
    dim "  (use --ip para ver os enderecos, necessario para ban)"
  fi
else
  bold "SERVIDOR"
  echo "  REST API nao respondeu — pode estar ainda subindo."
fi
echo

bold "SAVE"
if [ -n "$WORLD_ID" ] && [ -s "$SAVE_DIR/Level.sav" ]; then
  echo "  mundo ........ $(stat -c '%s bytes, gravado %y' "$SAVE_DIR/Level.sav" | cut -d. -f1)"
  newest=""
  for d in $(ls -1 "$BACKUP_DIR" 2>/dev/null | sort -r); do
    if [ -s "$BACKUP_DIR/$d/Level.sav" ]; then newest="$d"; break; fi
  done
  echo "  ult. backup .. ${newest:-nenhum}"
  echo "  backups ...... $(ls -1 "$BACKUP_DIR" 2>/dev/null | wc -l) do jogo, $(ls -1 "$SAVED_DIR/snapshots" 2>/dev/null | wc -l) snapshots"
else
  echo "  ATENCAO: Level.sav ausente ou vazio"
fi
echo

# Saves e imagens costumam estar em particoes diferentes; a que aperta durante
# uma atualizacao e a do Docker, nao a dos saves.
bold "DISCO"
df -h "$COMPOSE_DIR" | awk 'NR==2 {printf "  saves ........ %s livres de %s (%s usado)\n", $4, $2, $5}'
docker_root="$(docker info -f '{{.DockerRootDir}}' 2>/dev/null || echo /var/lib/docker)"
df -h "$docker_root" | awk 'NR==2 {printf "  imagens ...... %s livres de %s (%s usado)\n", $4, $2, $5}'
echo "  palserver .... $(docker images --format '{{.Size}}' ghcr.io/pocketpairjp/palserver | tr '\n' ' ')por imagem"

# Uma atualizacao mantem a imagem antiga no disco ate o servidor voltar.
avail_gb="$(df -BG --output=avail "$docker_root" | tail -1 | tr -dc '0-9')"
if [ "${avail_gb:-99}" -lt 20 ]; then
  printf '\033[1;33m  atencao: menos de 20GB livres; uma atualizacao precisa de ~13GB\033[0m\n'
fi
echo

bold "AGENDAMENTOS"
crontab -l 2>/dev/null | grep -E "init\.sh" | sed 's/>>.*//' | sed 's|/home[^ ]*/||' | sed 's/^/  /' || echo "  nenhum"
