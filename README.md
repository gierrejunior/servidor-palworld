# Servidor Palworld com manutenção automática

Fork do [repositório oficial da Pocketpair](https://github.com/pocketpairjp/palworld-dedicated-server-docker)
com scripts que mantêm o servidor de pé sozinho: vigiam quedas, aplicam
atualizações e — principalmente — **recuperam o mundo quando o save corrompe**.

A imagem Docker continua sendo a oficial (`ghcr.io/pocketpairjp/palserver`).
O que este repositório acrescenta é a camada de operação em volta dela.

> Documentação original (inglês/japonês): [README do upstream](https://github.com/pocketpairjp/palworld-dedicated-server-docker#readme)
> · [Palworld Server Guide](https://tech.palworldgame.com/)

## O problema que isso resolve

Se você já viu o container em `Restarting` sem fim e este erro no log:

```
Error: Save data is corrupted. Please restore from a backup. 0/<WORLD_ID>/Level
LowLevelFatalError [File:.../PalSaveGameManager.cpp] [Line: 2053]
Segmentation fault (core dumped)
```

...o servidor não vai voltar sozinho. O `restart: unless-stopped` do Docker
apenas repete o crash para sempre.

**A causa mais comum é o desligamento.** O servidor dedicado **ignora SIGTERM**:
todo `docker stop` espera o `stop_grace_period` inteiro e termina em SIGKILL
(`Exited (137)`). Se esse SIGKILL cair durante uma gravação do `Level.sav`, o
arquivo fica truncado — às vezes com 0 bytes — e o mundo não abre mais.

O jogo guarda backups automáticos em `Saved/SaveGames/0/<WORLD_ID>/backup/world/`,
mas restaurá-los é manual, e o servidor fica fora do ar até alguém perceber.

## O que os scripts fazem

### Desligamento limpo

Em vez de deixar o Docker matar o processo, o `init.sh` desliga pela REST API:

1. Avisa quem está jogando (`/v1/api/announce`) e dá 30 s
2. Força a gravação do mundo (`/v1/api/save`)
3. Desativa a política de restart, para o Docker não reerguer o servidor no meio
4. Pede o encerramento (`/v1/api/shutdown`) — o servidor sai sozinho, com exit 0
5. Só então remove o container

O `stop_grace_period` do `compose.yaml` vira apenas rede de segurança.

### Recuperação do save

Em camadas, da mais barata para a mais drástica:

| Quando | O que acontece |
|---|---|
| Antes de qualquer mexida | Snapshot em `Saved/snapshots/` (mantém os 10 últimos) |
| `Level.sav` vazio ou ausente | Restaura o backup mais recente antes mesmo de tentar subir |
| Servidor recusa o save ao subir | Arquiva o quebrado e tenta o backup anterior — até 5 vezes |

Nada em `Saved/` é apagado: o save quebrado vai para `Saved/corrupted-save-<data>/`
em vez de ser sobrescrito. A limpeza automática mexe **só** em imagens Docker.

### Reinício diário e atualização

O servidor dedicado acumula memória ao longo do dia, então o ciclo diário
reinicia **sempre**, tenha ou não versão nova. Havendo atualização, ela é
aplicada na mesma parada — uma interrupção por dia, não duas.

Com o servidor **vazio**, reinicia na hora: são ~7 segundos fora do ar e não há
a quem avisar.

Com **gente online**, o reinício é adiado. A cada 5 min ele checa de novo e
reinicia assim que o último jogador sair. Existe um prazo (6 h por padrão): se
esgotar, avisa no chat e reinicia mesmo assim.

A contagem regressiva só aparece quando o reinício vai acontecer com gente
conectada:

| Momento | Mensagem no chat |
|---|---|
| 10 min antes | Explica que é rotina diária de limpeza de memória |
| 5 min antes | Pede para procurar lugar seguro |
| 4, 3, 2, 1 min | Aviso curto |
| Último minuto | A cada 5 segundos |
| Na hora | "Reiniciando o servidor agora" |

Na atualização, a imagem é baixada **antes** de o container parar — o download
não conta como tempo fora do ar, e a imagem em uso fica protegida da limpeza de
espaço. Só depois de o servidor voltar e ser confirmado nos logs é que a imagem
antiga é removida (cada versão do palserver ocupa ~13 GB).

Se o download falhar por falta de espaço, o script remove imagens que nenhum
container usa e tenta de novo, até 3 vezes. Não dando certo, **permanece na
versão atual** — mas o reinício de limpeza acontece do mesmo jeito.

## Requisitos

- Docker e Docker Compose
- `curl`, `jq`, `flock` (presentes na maioria das distros)
- Usuário no grupo `docker` (os scripts não usam `sudo`)
- `RESTAPIEnabled=True` e um `AdminPassword` em
  `Saved/Config/LinuxServer/PalWorldSettings.ini`

A senha de admin é lida do `.ini` em tempo de execução — não fica escrita em
lugar nenhum do repositório.

## Uso

```bash
git clone https://github.com/gierrejunior/servidor-palworld.git
cd servidor-palworld/compose
docker compose up -d
```

Depois de o servidor gerar o `Saved/` na primeira execução, ative a REST API no
`Saved/Config/LinuxServer/PalWorldSettings.ini` e reinicie.

### Os dois scripts

```bash
./init.sh --watchdog   # levanta o servidor se caiu; nunca atualiza nem reinicia
./init.sh              # ciclo diário: reinicia (e atualiza, se houver versão nova)
./init.sh --force      # ciclo completo agora, sem esperar jogadores
./init.sh --stop       # desliga com segurança (use antes de reiniciar a máquina)
./recover.sh           # plano B: destrava um init.sh preso e força o ciclo
```

O `recover.sh` existe para quando o automático não resolve — por exemplo, um
`init.sh` parado há horas esperando o último jogador sair. Ele encerra a execução
travada e roda o ciclo inteiro na marra.

Um `flock` garante que só um deles rode por vez; o watchdog sai quieto se o ciclo
diário estiver em andamento.

### Automação

```bash
crontab -e
```

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Vigia: a cada 5 min, levanta o servidor se ele caiu. Nunca atualiza.
*/5 * * * * /caminho/servidor-palworld/compose/init.sh --watchdog >> /caminho/servidor-palworld/compose/init.log 2>&1

# No boot da máquina (espera o Docker subir antes de checar).
@reboot sleep 60; /caminho/servidor-palworld/compose/init.sh --watchdog >> /caminho/servidor-palworld/compose/init.log 2>&1

# Atualização diária às 5:00 — espera o servidor esvaziar antes de reiniciar.
0 5 * * * /caminho/servidor-palworld/compose/init.sh >> /caminho/servidor-palworld/compose/init.log 2>&1
```

Separar as duas coisas é proposital: o watchdog roda o tempo todo e **nunca**
atualiza, então uma versão nova não derruba ninguém no meio da tarde. A
atualização acontece só no horário escolhido.

O `init.log` se auto-limita em 5 MB.

## Desligar ou reiniciar a máquina

Este é o ponto mais fácil de errar. Desligar a máquina manda SIGTERM ao
container; o servidor **ignora** e leva SIGKILL — o mesmo caminho que corrompe o
save. Então, antes de reiniciar:

```bash
./init.sh --stop
```

Ele salva pela API, encerra o servidor limpo e remove o container. No próximo
boot, o `restart: unless-stopped` e o `@reboot` do cron trazem tudo de volta.

Para não depender de lembrar disso, há uma unit que faz o desligamento seguro
automaticamente no shutdown:

```bash
sudo cp compose/systemd/palworld-graceful-stop.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now palworld-graceful-stop.service
```

Ajuste `User=` e o caminho do `ExecStop=` dentro do arquivo antes de instalar.

## Como saber se está funcionando

```bash
tail -f compose/init.log
```

Uma execução sem novidade é curta assim:

```
2026-08-04 14:10:11 [watchdog] Servidor no ar e sem pendências — nada a fazer.
2026-08-04 14:10:11 [watchdog] Save: 2244841 bytes | backup mais recente: 2026.08.04-17.09.57
```

E uma recuperação de save corrompido:

```
[aviso] Servidor fora do ar — iniciando recuperação.
[watchdog] Snapshot do save em Saved/snapshots/20260804-140456
[watchdog] Subindo o container...
[aviso] Servidor recusou o save (corrompido).
[watchdog] Restaurando backup 2026.08.04-17.04.02 (save atual arquivado em Saved/corrupted-save-20260804-140506)
[watchdog] Subindo o container...
[watchdog] Servidor no ar em :8211 (versão v1.0.2.101103)
```

## Restauração manual

Se preferir escolher o backup na mão:

```bash
cd compose
ls Saved/SaveGames/0/<WORLD_ID>/backup/world/     # backups do jogo
ls Saved/snapshots/                               # snapshots do init.sh
```

`Saved/` pertence ao usuário interno do container, então copiar exige root. Sem
`sudo`, dá para usar um container descartável:

```bash
docker run --rm -v "$PWD/Saved:/data" alpine sh -c '
  SAVE=/data/SaveGames/0/<WORLD_ID>
  SRC=$SAVE/backup/world/<CARIMBO>
  cp -a $SRC/Level.sav $SRC/LevelMeta.sav $SAVE/
  rm -rf $SAVE/Players && cp -a $SRC/Players $SAVE/Players
'
```

## Limitações conhecidas

- O caminho de **falta de espaço em disco** está implementado, mas não foi
  testado num disco de fato cheio.
- Se a REST API não responder, o script segue com a manutenção em vez de esperar
  para sempre — o que pode desconectar quem estiver online.
- A espera por jogadores tem teto de 6 h; passado isso, ele reinicia mesmo com
  gente conectada (com a contagem regressiva no chat).
- O reinício diário **não** é uma janela fixa: com gente online ele pode
  acontecer horas depois do horário agendado.
- Não há backup fora da máquina. Os snapshots e os backups do jogo moram no
  mesmo disco — um problema de hardware leva tudo junto.
- Testado em Linux. Docker Desktop no Windows/macOS não é recomendado para
  servidor dedicado (leitura/escrita em disco limitadas).

## Créditos

Imagem e documentação originais: [Pocketpair](https://github.com/pocketpairjp/palworld-dedicated-server-docker).
Este fork acrescenta apenas os scripts de operação em `compose/`.
