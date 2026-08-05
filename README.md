# Servidor Palworld com manutenção automática

Fork do [repositório oficial da Pocketpair](https://github.com/pocketpairjp/palworld-dedicated-server-docker)
com scripts que mantêm o servidor de pé sozinho: vigiam quedas, aplicam
atualizações e — principalmente — **recuperam o mundo quando o save corrompe**.

Também lê o `Level.sav` e publica um **dashboard público** com as estatísticas
do mundo, atualizado sozinho duas vezes por dia:

### 📊 [gierrejunior.github.io/servidor-palworld](https://gierrejunior.github.io/servidor-palworld/)

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
./status.sh            # quem está online, saúde do container, save e disco
./pal-stats.sh         # estatísticas do mundo lidas do Level.sav
./publish-stats.sh     # regenera o dashboard e publica se algo mudou
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

# Reinício diário às 5:00 (limpeza de memória), aplicando update se houver.
0 5 * * * /caminho/servidor-palworld/compose/init.sh >> /caminho/servidor-palworld/compose/init.log 2>&1

# Dashboard: duas vezes por dia, publica se os números mudaram.
0 8,20 * * * /caminho/servidor-palworld/compose/publish-stats.sh >> /caminho/servidor-palworld/compose/stats.log 2>&1
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

## Dashboard de estatísticas

O `pal-stats.sh` lê o `Level.sav` e extrai jogadores, pals, IVs, raridades e
datas de captura. No terminal:

```bash
./pal-stats.sh          # relatório colorido
./pal-stats.sh --json   # mesmos dados em JSON
```

O `publish-stats.sh` gera o dashboard e publica no GitHub Pages, **comitando só
quando os números mudam** — o carimbo de hora sozinho não justifica um commit.

### O obstáculo: Palworld v1.0 mudou o formato do save

A partir da v0.6, incluindo a v1.0, os saves passaram a ser comprimidos com
**Oodle** (magic `PlM`) em vez de zlib (`PlZ`). O
[palworld-save-tools](https://github.com/cheahjs/palworld-save-tools), principal
ferramenta da comunidade, está parado desde outubro de 2024 e só entende `PlZ` —
ele falha com `not a compressed Palworld save, found b'PlM' instead of b'PlZ'`.

A imagem em `palstats/` resolve isso compilando o
[ooz](https://github.com/powzix/ooz), reimplementação aberta do decodificador
Oodle, e ligando os dois por `ctypes`. O repositório do ooz é Windows-only, então
o `Dockerfile` troca o `stdafx.h` por equivalentes do GCC e corta o trecho final
do `kraken.cpp`, que carrega a DLL oficial da Oodle.

Foram necessários mais dois ajustes para a v1.0:

| Sintoma | Causa | Solução |
|---|---|---|
| `Warning: EOF not reached` | Personagens ganharam bytes no fim | Ler as propriedades e ignorar o resto |
| `Unknown type: SetProperty` | Tipo novo, desconhecido pela lib | Consumir os bytes e descartar |

Só o decodificador de personagens é registrado. Construções, vegetação e
containers ficam como bytes crus: evita outras incompatibilidades da v1.0 e
derruba a leitura de 32 MB para **menos de 3 segundos**.

> **Guildas ainda não funcionam.** A estrutura mudou mais do que os outros
> campos — o `base_ids` parece ter sumido e o restante não alinha. As 3 bases
> são lidas corretamente, mas nome da guilda e lista de membros, não.

### Isolamento

A análise nunca toca o save real:

- roda em container descartável, com `--network none`
- opera sobre uma **cópia** do `Level.sav`, montada como somente-leitura
- nada é instalado na máquina hospedeira

O JSON publicado leva apenas apelidos do jogo. Identificadores internos, Steam ID
e IP ficam de fora — só aparece o que já é visível para quem entra no servidor.
Ainda assim, avise seus jogadores antes de tornar a página pública.

### O que o dashboard mostra

| Seção | O que traz | Interação |
|---|---|---|
| **Faixa ao vivo** | Quem está online agora, nível e ping | Clique no nome abre o perfil |
| **Troféus** | 12 títulos calculados na hora a partir da coleção | Clique abre o perfil do ganhador |
| **Ranking** | Nível, experiência, pals, alphas, lucky, melhor pal | Clique abre o perfil e filtra a lista |
| **Comparar** | Dois jogadores lado a lado em 10 métricas | Destaca quem ganha cada uma |
| **Capturas por dia** | Barras empilhadas por jogador | Clique num dia lista os pals daquele dia |
| **Quando cada um joga** | Distribuição por hora do dia | Tooltip com a divisão por jogador |
| **Corrida da coleção** | Pals acumulados ao longo do tempo | Clique numa linha isola o jogador |
| **Espécies exclusivas** | O que cada um tem que ninguém mais tem | — |
| **Hall da fama** | Os 8 melhores IVs do servidor | — |
| **Explorador** | Todos os pals, com rolagem infinita | Busca, 4 filtros e 4 ordenações |

Clicar num jogador na legenda **isola ele nos três gráficos ao mesmo tempo** e
filtra a lista de pals junto — o resto desbota em vez de sumir, para a comparação
continuar visível. Os períodos (7 dias / 30 dias / tudo) redesenham tudo no
navegador, sem nova publicação.

Os troféus saem de combinações dos dados brutos: **Coruja** conta capturas entre
0h e 6h, **Maratonista** procura o melhor dia isolado, **Perfeccionista** exige no
mínimo 20 pals para não premiar quem tem três com sorte, **Geneticista** conta
pals com IV médio acima de 85.

**Tempo de jogo não existe no save** — o Palworld não registra. O que dá para
reconstruir é a atividade a partir do horário de captura de cada pal, que o
`OwnedTime` guarda com hora cheia.

### Duas velocidades: por que o dado ao vivo não vai no repositório

O GitHub Pages tem um limite documentado de **10 builds por hora**. Commitar de
minuto em minuto para mostrar quem está online deixaria o site *mais* desatualizado
— a maioria dos builds entraria em fila — além de inflar o histórico do
repositório sem necessidade.

A saída foi separar pelo ritmo de cada dado:

| Dado | Tamanho | Onde vive | Frequência |
|---|---|---|---|
| Coleção, IVs, troféus, gráficos | ~100 KB | GitHub Pages | 2× por dia |
| Quem está online, ping, visto por último | ~1 KB | Gist | a cada 2 min |

O Gist não dispara build nenhum, então escapa do limite. O coletor
(`live-update.sh`) consulta apenas a REST API — não lê o save nem sobe container,
e roda em menos de um segundo.

A leitura usa `api.github.com` e não a URL `raw`. Medindo os dois: o CDN do `raw`
serve conteúdo de até 5 minutos atrás e **ignora cache-buster**, enquanto a API
devolve o dado fresco. Em troca, ela limita 60 requisições por hora por IP — daí o
intervalo de 90 segundos no navegador. Como o cache dela é de 60s, consultar mais
rápido não traria nada.

O resultado honesto é **1 a 2 minutos de frescor**, não segundos. Para tempo real
de verdade o caminho seria Cloudflare Workers + KV, que é trocar uma URL.

### Estrutura dos arquivos

```
compose/palstats/
├── Dockerfile          imagem com o ooz compilado + palworld-save-tools
├── report.py           lê o Level.sav e emite o relatório (ou --json)
├── gerar-dashboard.py  monta o site em docs/
└── web/
    ├── index.html      estrutura, só os containers vazios
    ├── estilo.css
    ├── app.js          tudo o que desenha, a partir de dados.json
    └── favicon.svg
```

A primeira versão montava HTML, CSS e JavaScript dentro de f-strings do Python.
Funcionava, mas cada chave precisava virar `{{ }}` e o editor não ajudava — dois
bugs passaram despercebidos assim: aspas duplas aninhadas que truncavam um atributo
e engoliam metade de um tooltip, e um `let` lido antes da declaração que deixava a
página em branco **sem erro no console**. Em arquivos de verdade, ambos seriam
óbvios em segundos.

Hoje o `gerar-dashboard.py` não gera HTML: copia `web/` e grava o `dados.json`.
Todo o conteúdo é desenhado no navegador, o que também deixa CSS e JS cacheáveis
entre visitas.

### Adaptando para o seu servidor

O nome do servidor está no `web/index.html` e as cores dos jogadores em
`web/app.js` (`PALETA`). O resto sai do save. Para publicar no seu GitHub Pages:

```bash
gh api -X POST repos/USUARIO/REPO/pages -f "source[branch]=main" -f "source[path]=/docs"
```

O Gist é criado sozinho na primeira execução do `live-update.sh`, que grava o id em
`compose/gist-id`.

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
