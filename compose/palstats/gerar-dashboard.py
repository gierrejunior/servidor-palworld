#!/usr/bin/env python3
"""Gera um dashboard HTML estatico e interativo a partir do JSON do report.py.

Sem dependencias externas e sem recursos remotos: os dados vao embutidos na
propria pagina, entao o arquivo funciona sozinho no GitHub Pages.
"""
import html
import json
import sys
from datetime import date, datetime
from urllib.parse import quote

dados = json.load(open(sys.argv[1], encoding="utf-8"))
destino = sys.argv[2]
# Id do Gist com o estado ao vivo. Sem ele a pagina fica so com o retrato.
GIST_ID = sys.argv[3] if len(sys.argv) > 3 else ""

E = html.escape  # nomes de jogador sao texto arbitrario: sempre escapar


def barra(valor, maximo, largura=100):
    return round(valor / maximo * largura, 1) if maximo else 0


m = dados["mundo"]
jogadores = dados["jogadores"]
gerado = datetime.fromisoformat(dados["gerado_em"])

cards = "".join(
    f'<div class="stat"><span class="num">{v:,}</span><span class="lbl">{r}</span></div>'
    for r, v in (
        ("jogadores", m["jogadores"]),
        ("pals", m["pals"]),
        ("espécies", m["especies"]),
        ("alphas", m["alphas"]),
        ("lucky", m["lucky"]),
        ("rank 4+", m["rank4"]),
    )
)

max_exp = max((j["exp"] for j in jogadores), default=1)
linhas = []
for i, j in enumerate(jogadores, 1):
    mp = j["melhor_pal"]
    melhor = f'{E(mp["especie"])} <span class="dim">· IV {mp["media_ivs"]}</span>' if mp else "—"
    linhas.append(
        f"""<tr data-jogador="{E(j["nome"])}" tabindex="0" role="button"
        aria-label="Ver detalhes de {E(j["nome"])}">
      <td class="pos">{i}</td>
      <td class="nome">{E(j["nome"])}</td>
      <td class="nivel">{j["nivel"]}</td>
      <td class="barra-cel">
        <div class="mini"><i style="width:{barra(j["exp"], max_exp)}%"></i></div>
        <span class="dim">{j["exp"]:,}</span>
      </td>
      <td>{j["pals"]}</td>
      <td>{j["alphas"]}</td>
      <td>{j["lucky"]}</td>
      <td class="melhor">{melhor}</td>
    </tr>"""
    )

# Uma cor por jogador, na ordem do ranking; sobra o cinza para pals selvagens.
PALETA = ["#4ea1ff", "#ffc857", "#ff7ab8", "#5ddba0", "#b18cff", "#ff9d5c", "#4dd4d4"]
cor_de = {j["nome"]: PALETA[i % len(PALETA)] for i, j in enumerate(jogadores)}
cor_de["selvagem"] = "#6b7684"

tempo = dados["linha_tempo"][-30:]
max_cap = max((sum(d["j"].values()) for d in tempo), default=1)

colunas = []
for i, d in enumerate(tempo):
    total = sum(d["j"].values())
    # Maior primeiro: a base da pilha fica visualmente estavel entre os dias.
    partes = sorted(d["j"].items(), key=lambda kv: -kv[1])
    segmentos = "".join(
        f'<i style="height:{barra(n, max_cap)}%;background:{cor_de.get(nome, "#6b7684")}"></i>'
        for nome, n in partes
    )
    # Aspas simples de proposito: este HTML vai dentro de um atributo
    # delimitado por aspas duplas, e aspas duplas aqui truncariam o atributo.
    detalhe = "<br>".join(
        "<span style='color:{}'>■</span> {}: <b>{}</b>".format(
            cor_de.get(nome, "#6b7684"), E(nome), n
        )
        for nome, n in partes
    )
    rotulo = f'{date.fromisoformat(d["d"]):%d/%m}'
    # Rotulo so nas pontas e a cada 5 dias: eixo legivel sem virar poluicao.
    mostra = i == 0 or i == len(tempo) - 1 or i % 5 == 0
    colunas.append(
        f'<div class="dia" tabindex="0" role="img"'
        f' aria-label="{rotulo}: {total} capturas"'
        f' data-tip="<b>{rotulo}</b> — {total} capturas<br>{detalhe}">'
        f'<div class="pilha">{segmentos}</div>'
        f'<span>{rotulo if mostra else ""}</span></div>'
    )
barras_tempo = "".join(colunas)

legenda = "".join(
    f'<span class="leg"><i style="background:{c}"></i>{E(n)}</span>'
    for n, c in cor_de.items()
    if any(n in d["j"] for d in tempo)
)

max_esp = dados["especies_comuns"][0][1] if dados["especies_comuns"] else 1
especies = "".join(
    f'<div class="linha"><span class="rot">{E(e)}</span>'
    f'<div class="mini"><i style="width:{barra(n, max_esp)}%"></i></div>'
    f'<span class="val">{n}</span></div>'
    for e, n in dados["especies_comuns"]
)

passivas = "".join(
    f'<li><span>{E(s)}</span><span class="dim">{n}</span></li>'
    for s, n in dados["passivas"][:8]
)

DADOS_JS = json.dumps(
    {"pals": dados.get("pals", []), "jogadores": jogadores},
    ensure_ascii=False,
    separators=(",", ":"),
)
CORES_JS = json.dumps(cor_de, ensure_ascii=False)

# Favicon como data URI: mantem a pagina autossuficiente, sem arquivo extra.
# O quote() e obrigatorio porque "#" das cores abriria um fragmento na URL.
_FAVICON_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
    "<circle cx='16' cy='16' r='15' fill='#eef2f6'/>"
    "<path d='M1 16a15 15 0 0 1 30 0z' fill='#4ea1ff'/>"
    "<rect x='1' y='13.6' width='30' height='4.8' fill='#12161b'/>"
    "<circle cx='16' cy='16' r='5.6' fill='#eef2f6' stroke='#12161b' stroke-width='2.6'/>"
    "</svg>"
)
FAVICON = "data:image/svg+xml," + quote(_FAVICON_SVG)

HTML = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SonicCurupiraBeer — estatísticas</title>
<link rel="icon" href="{FAVICON}">
<link rel="apple-touch-icon" href="{FAVICON}">
<meta name="theme-color" content="#0f1216">
<meta name="description" content="Estatísticas do servidor Palworld SonicCurupiraBeer: ranking, coleções, troféus e capturas.">
<meta property="og:title" content="SonicCurupiraBeer — estatísticas">
<meta property="og:description" content="Ranking, troféus e a coleção de pals de cada jogador.">
<meta property="og:type" content="website">
<style>
  :root {{
    --bg:#0f1216; --card:#171c22; --line:#232b34; --tx:#e6edf3; --dim:#8b98a5;
    --ac:#4ea1ff; --gold:#ffc857; --pink:#ff7ab8;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{ --bg:#f6f8fa; --card:#fff; --line:#d8dee4; --tx:#1f2328; --dim:#656d76; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--tx);
    font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:28px 18px 60px; }}
  h1 {{ font-size:1.7rem; margin:0 0 4px; }}
  h2 {{ font-size:1.05rem; margin:34px 0 12px; }}
  .sub {{ color:var(--dim); font-size:.9rem; margin-bottom:22px; }}
  .card {{ background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:16px; }}
  .stats {{ display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:14px 16px; display:flex; flex-direction:column; gap:2px; }}
  .num {{ font-size:1.7rem; font-weight:650; }}
  .lbl {{ color:var(--dim); font-size:.8rem; text-transform:uppercase; letter-spacing:.06em; }}
  .scroll {{ overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; min-width:640px; }}
  th {{ text-align:left; font-size:.75rem; text-transform:uppercase; letter-spacing:.06em;
    color:var(--dim); font-weight:600; padding:0 10px 8px; }}
  td {{ padding:10px; border-top:1px solid var(--line); }}
  tbody tr {{ cursor:pointer; }}
  tbody tr:hover, tbody tr:focus {{ background:rgba(78,161,255,.09); outline:none; }}
  .pos {{ color:var(--dim); width:28px; }}
  .nome {{ font-weight:620; }}
  .nivel {{ font-weight:650; color:var(--ac); }}
  .barra-cel {{ min-width:170px; }}
  .mini {{ background:var(--line); border-radius:99px; height:6px; overflow:hidden; margin-bottom:3px; }}
  .mini i {{ display:block; height:100%; background:var(--ac); border-radius:99px; }}
  .dim {{ color:var(--dim); font-size:.85rem; }}
  .melhor {{ font-size:.9rem; }}
  .tempo {{ display:flex; align-items:flex-end; gap:3px; height:170px; }}
  .dia {{ flex:1; display:flex; flex-direction:column; justify-content:flex-end;
    align-items:center; gap:6px; height:100%; min-width:0; }}
  /* tooltip proprio: o title nativo demora ~1s e nao aceita formatacao */
  .tip {{ position:fixed; z-index:50; pointer-events:none; opacity:0;
    transition:opacity .12s; background:var(--card); color:var(--tx);
    border:1px solid var(--line); border-radius:9px; padding:8px 11px;
    font-size:.82rem; line-height:1.5; box-shadow:0 6px 24px rgba(0,0,0,.35);
    max-width:260px; }}
  .tip.on {{ opacity:1; }}
  .dia:focus, .hora:focus {{ outline:2px solid var(--ac); outline-offset:2px;
    border-radius:4px; }}
  .dia:hover .pilha, .hora:hover .pilha {{ filter:brightness(1.25); }}

  .pilha {{ width:100%; display:flex; flex-direction:column-reverse;
    justify-content:flex-start; flex:1; min-height:0; }}
  .pilha i {{ width:100%; min-height:2px; display:block; }}
  .pilha i:last-child {{ border-radius:3px 3px 0 0; }}
  .dia span {{ font-size:.6rem; color:var(--dim); white-space:nowrap;
    transform:rotate(-45deg); }}
  .eixo {{ display:flex; justify-content:space-between; margin-top:6px;
    font-size:.7rem; color:var(--dim); }}
  .legenda {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:26px;
    font-size:.82rem; color:var(--dim); }}
  .leg {{ display:inline-flex; align-items:center; gap:6px; }}
  .leg i {{ width:11px; height:11px; border-radius:3px; display:inline-block; }}
  .linha {{ display:grid; grid-template-columns:150px 1fr 40px; gap:10px;
    align-items:center; margin-bottom:7px; }}
  .rot {{ font-size:.88rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .val {{ text-align:right; color:var(--dim); font-size:.85rem; }}
  ul {{ list-style:none; margin:0; padding:0; }}
  li {{ display:flex; justify-content:space-between; padding:7px 0;
    border-top:1px solid var(--line); font-size:.9rem; }}
  li:first-child {{ border-top:0; }}
  .dois {{ display:grid; gap:16px; grid-template-columns:1fr; }}
  @media (min-width:760px) {{ .dois {{ grid-template-columns:1fr 1fr; }} }}
  footer {{ margin-top:40px; color:var(--dim); font-size:.8rem; text-align:center; }}

  /* explorador */
  .ferramentas {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; }}
  input, select {{ background:var(--card); color:var(--tx); border:1px solid var(--line);
    border-radius:8px; padding:8px 11px; font:inherit; font-size:.9rem; }}
  input:focus, select:focus {{ outline:2px solid var(--ac); outline-offset:-1px; }}
  input {{ flex:1; min-width:150px; }}
  .tag {{ font-size:.62rem; padding:2px 6px; border-radius:99px; letter-spacing:.05em; }}
  .tag.lucky {{ background:var(--gold); color:#000; }}
  .tag.alpha {{ background:var(--pink); color:#000; }}
  .iv-forte {{ color:var(--gold); font-weight:650; }}
  #contagem {{ color:var(--dim); font-size:.85rem; padding:8px 2px; }}
  #lista td {{ font-size:.9rem; }}
  /* A rolagem infinita acontece dentro desta caixa, nao na pagina inteira. */
  .explorador {{ max-height:min(68vh,620px); overflow:auto; }}
  .explorador thead th {{ position:sticky; top:0; z-index:1;
    background:var(--card); padding-top:14px; }}
  #lista tr {{ cursor:default; }}
  #lista tr:hover {{ background:rgba(78,161,255,.06); }}
  .f-esp, .f-dono {{ cursor:pointer; border-bottom:1px dotted transparent; }}
  .f-esp:hover, .f-dono:hover {{ color:var(--ac); border-bottom-color:var(--ac); }}
  .vazio {{ padding:26px; text-align:center; color:var(--dim); }}
  .painel {{ border:1px solid var(--ac); border-radius:12px; padding:16px;
    background:var(--card); margin-bottom:14px; display:none; }}
  .painel.on {{ display:block; }}
  .painel h3 {{ margin:0 0 10px; font-size:1.15rem; }}
  .painel .grade {{ display:grid; gap:10px;
    grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); margin-bottom:12px; }}
  .painel .g {{ background:var(--bg); border-radius:8px; padding:9px 11px; }}
  .painel .g b {{ display:block; font-size:1.25rem; }}
  .voltar {{ float:right; background:var(--bg); border:1px solid var(--line);
    color:var(--tx); border-radius:8px; padding:6px 13px; cursor:pointer;
    font:inherit; font-size:.85rem; }}
  .voltar:hover {{ border-color:var(--ac); color:var(--ac); }}

  /* faixa ao vivo */
  .live {{ display:none; background:var(--card); border:1px solid var(--line);
    border-radius:12px; padding:12px 16px; margin-bottom:20px;
    align-items:center; gap:14px; flex-wrap:wrap; }}
  .live.on {{ display:flex; }}
  .live .bolha {{ width:9px; height:9px; border-radius:99px; flex:none; }}
  .live .bolha.verde {{ background:#3fb950; box-shadow:0 0 0 0 rgba(63,185,80,.7);
    animation:pulso 2.4s infinite; }}
  .live .bolha.cinza {{ background:var(--dim); }}
  .live .bolha.vermelha {{ background:#f85149; }}
  @keyframes pulso {{ 70% {{ box-shadow:0 0 0 9px rgba(63,185,80,0); }}
    100% {{ box-shadow:0 0 0 0 rgba(63,185,80,0); }} }}
  @media (prefers-reduced-motion:reduce) {{ .live .bolha.verde {{ animation:none; }} }}
  .live .quem {{ display:flex; gap:8px; flex-wrap:wrap; }}
  .live .jog {{ background:var(--bg); border-radius:99px; padding:4px 11px;
    font-size:.85rem; cursor:pointer; border:1px solid var(--line); }}
  .live .jog:hover {{ border-color:var(--ac); }}
  .live .quando {{ margin-left:auto; color:var(--dim); font-size:.78rem; }}
  .ponto-on {{ color:#3fb950; }}

  /* trofeus */
  .trofeus {{ display:grid; gap:10px;
    grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); }}
  .trofeu {{ background:var(--card); border:1px solid var(--line); border-radius:12px;
    padding:13px 15px; cursor:pointer; transition:border-color .12s, transform .12s;
    display:flex; gap:12px; align-items:center; text-align:left; font:inherit;
    color:inherit; width:100%; }}
  .trofeu:hover, .trofeu:focus {{ border-color:var(--ac); transform:translateY(-2px);
    outline:none; }}
  .trofeu .emoji {{ font-size:1.7rem; line-height:1; }}
  .trofeu b {{ display:block; font-size:.95rem; }}
  .trofeu .quem {{ color:var(--ac); font-weight:600; font-size:.9rem; }}
  .trofeu .det {{ color:var(--dim); font-size:.78rem; }}

  /* atividade por hora */
  .horas {{ display:flex; align-items:flex-end; gap:3px; height:150px; }}
  .hora {{ flex:1; display:flex; flex-direction:column; justify-content:flex-end;
    align-items:center; gap:5px; height:100%; min-width:0; }}
  .hora span {{ font-size:.6rem; color:var(--dim); height:.8em; }}

  /* especies exclusivas */
  .excl {{ padding:10px 0; border-top:1px solid var(--line); }}
  .excl:first-child {{ border-top:0; padding-top:0; }}
  .excl-nome {{ display:flex; align-items:center; gap:7px; font-weight:600;
    margin-bottom:3px; }}
  .excl-nome i {{ width:11px; height:11px; border-radius:3px; display:inline-block; }}
  .excl-lista {{ font-size:.85rem; line-height:1.7; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>SonicCurupiraBeer</h1>
  <div class="sub">Estatísticas do mundo · atualizado em {gerado:%d/%m/%Y às %H:%M}</div>

  <div id="live" class="live" aria-live="polite"></div>

  <div class="stats">{cards}</div>

  <h2>Troféus <span class="dim">— clique para ver o dono</span></h2>
  <div class="trofeus" id="trofeus"></div>

  <h2>Ranking de jogadores <span class="dim">— clique para ver os detalhes</span></h2>
  <div id="painel" class="painel" role="region" aria-live="polite"></div>
  <div class="card scroll">
    <table>
      <thead><tr>
        <th></th><th>jogador</th><th>nível</th><th>experiência</th>
        <th>pals</th><th>alphas</th><th>lucky</th><th>melhor pal</th>
      </tr></thead>
      <tbody id="ranking">{"".join(linhas)}</tbody>
    </table>
  </div>

  <h2>Capturas por dia <span class="dim">— por jogador</span></h2>
  <div class="card">
    <div class="tempo">{barras_tempo}</div>
    <div class="legenda">{legenda}</div>
  </div>

  <div class="dois">
    <div>
      <h2>Espécies mais comuns</h2>
      <div class="card">{especies}</div>
    </div>
    <div>
      <h2>Passivas mais frequentes</h2>
      <div class="card"><ul>{passivas}</ul></div>
    </div>
  </div>

  <div class="dois">
    <div>
      <h2>Quando cada um joga <span class="dim">— hora da captura</span></h2>
      <div class="card"><div id="horas" class="horas"></div>
        <div class="legenda" id="leg-horas"></div></div>
    </div>
    <div>
      <h2>Corrida da coleção <span class="dim">— pals acumulados</span></h2>
      <div class="card"><div id="corrida"></div></div>
    </div>
  </div>

  <h2>Espécies exclusivas <span class="dim">— quem tem o que ninguém mais tem</span></h2>
  <div class="card" id="exclusivas"></div>

  <h2>Explorar todos os pals</h2>
  <div class="ferramentas">
    <input id="busca" type="search" placeholder="Buscar espécie..." aria-label="Buscar espécie">
    <select id="dono" aria-label="Filtrar por dono"><option value="">Todos os donos</option></select>
    <select id="tipo" aria-label="Filtrar por tipo">
      <option value="">Todos os tipos</option>
      <option value="l">Só Lucky</option>
      <option value="a">Só Alpha</option>
      <option value="r">Rank 4+</option>
    </select>
    <select id="ordem" aria-label="Ordenar">
      <option value="iv">Melhores IVs</option>
      <option value="n">Maior nível</option>
      <option value="f">Mais amizade</option>
      <option value="c">Captura recente</option>
    </select>
  </div>
  <div id="contagem" aria-live="polite"></div>
  <div class="card" style="padding:0">
    <div id="explorador" class="explorador">
      <table>
        <thead><tr>
          <th style="padding-left:16px">espécie</th><th>nível</th><th>IV médio</th>
          <th>HP / ATK / DEF</th><th>dono</th><th>capturado</th>
        </tr></thead>
        <tbody id="lista"></tbody>
      </table>
      <div id="sentinela" style="height:1px"></div>
    </div>
  </div>

  <footer>
    Gerado automaticamente a partir do save do servidor · {m["doentes"]} pals doentes nas bases
  </footer>
</div>

<script>
const D = {DADOS_JS};
const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));

const $ = id => document.getElementById(id);
const busca = $('busca'), fDono = $('dono'), fTipo = $('tipo'), fOrdem = $('ordem');

[...new Set(D.pals.map(p => p.d).filter(Boolean))].sort().forEach(n => {{
  const o = document.createElement('option');
  o.value = n; o.textContent = n; fDono.appendChild(o);
}});

const mediaIv = p => (p.iv[0] + p.iv[1] + p.iv[2]) / 3;
const CORES = {CORES_JS};
const corDe = n => CORES[n] || '#6b7684';

// ---- tooltip dos graficos ----
// Um unico elemento reaproveitado por todas as barras: delegacao de evento em
// vez de um listener por coluna. Segue o mouse e tambem responde ao teclado.
const tip = Object.assign(document.createElement('div'), {{ className: 'tip' }});
document.body.appendChild(tip);

function mostrarTip(alvo, x, y) {{
  tip.innerHTML = alvo.dataset.tip;
  tip.classList.add('on');
  const r = tip.getBoundingClientRect();
  // Vira o lado quando encostaria na borda da janela.
  const px = Math.min(Math.max(8, x + 14), innerWidth - r.width - 8);
  const py = y - r.height - 14 < 8 ? y + 20 : y - r.height - 14;
  tip.style.left = px + 'px';
  tip.style.top = py + 'px';
}}
const esconderTip = () => tip.classList.remove('on');

document.addEventListener('mousemove', e => {{
  const alvo = e.target.closest('[data-tip]');
  if (alvo) mostrarTip(alvo, e.clientX, e.clientY); else esconderTip();
}});
document.addEventListener('focusin', e => {{
  const alvo = e.target.closest('[data-tip]');
  if (!alvo) return esconderTip();
  const r = alvo.getBoundingClientRect();
  mostrarTip(alvo, r.left + r.width / 2, r.top);
}});
document.addEventListener('focusout', esconderTip);
addEventListener('scroll', esconderTip, {{ passive: true }});

// ---- explorador com rolagem infinita ----
// Os filtros sempre percorrem D.pals inteiro; a rolagem so controla quanto ja
// foi desenhado. Nada de polling: um IntersectionObserver avisa quando chegar
// ao fim, e as linhas sao anexadas em lote, sem redesenhar o que ja esta la.
const LOTE = 80;
let filtrados = [], desenhados = 0;

const linhaHtml = p => {{
  const mi = mediaIv(p);
  return `<tr>
    <td style="padding-left:16px"><b class="f-esp" data-e="${{esc(p.e)}}"
        title="Ver todos os ${{esc(p.e)}}">${{esc(p.e)}}</b>
      ${{p.l ? '<span class="tag lucky">LUCKY</span>' : ''}}
      ${{p.a ? '<span class="tag alpha">ALPHA</span>' : ''}}
      ${{p.r >= 4 ? '<span class="dim">★' + p.r + '</span>' : ''}}</td>
    <td>${{p.n}}</td>
    <td class="${{mi >= 80 ? 'iv-forte' : ''}}">${{mi.toFixed(1)}}</td>
    <td class="dim">${{p.iv.join(' / ')}}</td>
    <td>${{p.d ? `<span class="f-dono" data-d="${{esc(p.d)}}" title="Ver ${{esc(p.d)}}">${{esc(p.d)}}</span>`
             : '<span class="dim">selvagem</span>'}}</td>
    <td class="dim">${{p.c ? p.c.split('-').reverse().slice(0, 2).join('/') : '—'}}</td>
  </tr>`;
}};

function desenharLote() {{
  if (desenhados >= filtrados.length) return;
  const ate = Math.min(desenhados + LOTE, filtrados.length);
  $('lista').insertAdjacentHTML('beforeend',
    filtrados.slice(desenhados, ate).map(linhaHtml).join(''));
  desenhados = ate;
  $('contagem').textContent = filtrados.length === D.pals.length
    ? `${{D.pals.length}} pals · mostrando ${{desenhados}}`
    : `${{filtrados.length}} de ${{D.pals.length}} pals · mostrando ${{desenhados}}`;
}}

function filtrar() {{
  const q = busca.value.trim().toLowerCase();
  const dono = fDono.value, tipo = fTipo.value, ordem = fOrdem.value;

  filtrados = D.pals.filter(p =>
    (!q || p.e.toLowerCase().includes(q)) &&
    (!dono || p.d === dono) &&
    (!tipo || (tipo === 'l' && p.l) || (tipo === 'a' && p.a) || (tipo === 'r' && p.r >= 4))
  );

  const chaves = {{ iv: p => -mediaIv(p), n: p => -p.n, f: p => -p.f, c: p => p.c ? -Date.parse(p.c) : 1 }};
  filtrados.sort((a, b) => chaves[ordem](a) - chaves[ordem](b));

  desenhados = 0;
  $('lista').innerHTML = '';
  if (filtrados.length === 0) {{
    $('lista').innerHTML = '<tr><td colspan="6" class="vazio">Nenhum pal encontrado com esses filtros.</td></tr>';
    $('contagem').textContent = `0 de ${{D.pals.length}} pals`;
    return;
  }}
  desenharLote();
  // Se o primeiro lote nao encheu a tela, a sentinela segue visivel e o
  // observer dispara de novo sozinho.
}}

// Digitar redesenha a lista inteira; esperar o usuario parar evita o piscar.
let timer;
const agendarFiltro = () => {{ clearTimeout(timer); timer = setTimeout(filtrar, 160); }};
busca.addEventListener('input', agendarFiltro);
[fDono, fTipo, fOrdem].forEach(el => el.addEventListener('change', filtrar));

// root = a propria caixa, para a rolagem infinita nao depender da pagina.
new IntersectionObserver(e => {{ if (e[0].isIntersecting) desenharLote(); }},
  {{ root: $('explorador'), rootMargin: '400px' }}).observe($('sentinela'));

filtrar();

// ---- perfil de atividade por hora ----
(() => {{
  const donos = [...new Set(D.pals.map(p => p.d).filter(Boolean))];
  const porHora = {{}};
  donos.forEach(n => porHora[n] = new Array(24).fill(0));
  D.pals.forEach(p => {{ if (p.d && p.h >= 0) porHora[p.d][p.h]++; }});

  const totalHora = h => donos.reduce((s, n) => s + porHora[n][h], 0);
  const pico = Math.max(...Array.from({{length: 24}}, (_, h) => totalHora(h)), 1);

  $('horas').innerHTML = Array.from({{length: 24}}, (_, h) => {{
    const ativos = donos.filter(n => porHora[n][h]).sort((a, b) => porHora[b][h] - porHora[a][h]);
    const det = ativos.map(n =>
      `<span style='color:${{corDe(n)}}'>■</span> ${{esc(n)}}: <b>${{porHora[n][h]}}</b>`).join('<br>');
    const segs = ativos.map(n =>
      `<i style="height:${{porHora[n][h] / pico * 100}}%;background:${{corDe(n)}}"></i>`).join('');
    const hh = String(h).padStart(2, '0');
    return `<div class="hora" tabindex="0" role="img"
        aria-label="${{hh}} horas: ${{totalHora(h)}} capturas"
        data-tip="<b>${{hh}}h às ${{String((h+1)%24).padStart(2,'0')}}h</b> — ${{totalHora(h)}} capturas${{det ? '<br>' + det : ''}}">
      <div class="pilha">${{segs}}</div>
      <span>${{h % 6 === 0 ? hh + 'h' : ''}}</span></div>`;
  }}).join('');

  $('leg-horas').innerHTML = donos.map(n =>
    `<span class="leg"><i style="background:${{corDe(n)}}"></i>${{esc(n)}}</span>`).join('');
}})();

// ---- corrida da colecao (acumulado) ----
(() => {{
  const donos = [...new Set(D.pals.map(p => p.d).filter(Boolean))];
  const dias = [...new Set(D.pals.filter(p => p.c).map(p => p.c))].sort();
  if (!dias.length) return;

  const serie = {{}};
  donos.forEach(n => {{
    let acc = 0;
    serie[n] = dias.map(d => acc += D.pals.filter(p => p.d === n && p.c === d).length);
  }});
  const teto = Math.max(...donos.map(n => serie[n][dias.length - 1]), 1);

  const W = 300, H = 150;
  const x = i => (i / Math.max(dias.length - 1, 1)) * W;
  const y = v => H - (v / teto) * H;

  const linhas = donos.map(n =>
    `<polyline fill="none" stroke="${{corDe(n)}}" stroke-width="2.5"
      stroke-linejoin="round" stroke-linecap="round"
      points="${{serie[n].map((v, i) => `${{x(i).toFixed(1)}},${{y(v).toFixed(1)}}`).join(' ')}}"/>`).join('');

  // Faixas invisiveis por dia: dao um alvo de mouse largo o suficiente, que a
  // linha sozinha (2.5px) nao daria.
  const fatias = dias.map((d, i) => {{
    const larg = W / dias.length;
    const det = donos.map(n => ({{ n, v: serie[n][i] }}))
      .sort((a, b) => b.v - a.v)
      .map(o => `<span style='color:${{corDe(o.n)}}'>■</span> ${{esc(o.n)}}: <b>${{o.v}}</b>`)
      .join('<br>');
    return `<rect x="${{(i * larg).toFixed(1)}}" y="-6" width="${{larg.toFixed(1)}}" height="${{H + 12}}"
      fill="transparent" data-tip="<b>${{d.split('-').reverse().slice(0,2).join('/')}}</b><br>${{det}}"/>`;
  }}).join('');

  const meio = dias[Math.floor(dias.length / 2)];
  const rotulo = s => s.split('-').reverse().slice(0, 2).join('/');

  $('corrida').innerHTML = `
    <svg viewBox="0 -6 ${{W}} ${{H + 12}}" preserveAspectRatio="none"
         style="width:100%;height:170px" role="img"
         aria-label="Pals acumulados por jogador ao longo do tempo">${{linhas}}${{fatias}}</svg>
    <div class="eixo"><span>${{rotulo(dias[0])}}</span><span>${{rotulo(meio)}}</span>
      <span>${{rotulo(dias[dias.length - 1])}}</span></div>
    <div class="legenda">${{donos.map(n =>
      `<span class="leg"><i style="background:${{corDe(n)}}"></i>${{esc(n)}}
       <b style="color:var(--tx)">${{serie[n][dias.length - 1]}}</b></span>`).join('')}}</div>`;
}})();

// ---- trofeus ----
// Titulos calculados na hora a partir da colecao de cada um. So entra quem
// tem alguma coisa: categoria sem vencedor nao vira card vazio.
(() => {{
  const donos = [...new Set(D.pals.map(p => p.d).filter(Boolean))];
  const meus = n => D.pals.filter(p => p.d === n);

  const vencedor = (fn) => {{
    let melhor = null;
    donos.forEach(n => {{
      const v = fn(meus(n), n);
      if (v && v.valor > 0 && (!melhor || v.valor > melhor.valor)) melhor = {{ ...v, nome: n }};
    }});
    return melhor;
  }};

  const contarHoras = (ps, de, ate) =>
    ps.filter(p => p.h >= de && p.h <= ate).length;

  const categorias = [
    ['🏆', 'Maior nível', () => {{
      const j = D.jogadores[0];
      return j && {{ valor: j.nivel, det: `nível ${{j.nivel}}`, nome: j.nome }};
    }}, true],
    ['📚', 'Colecionador', ps => {{
      const n = new Set(ps.map(p => p.e)).size;
      return {{ valor: n, det: `${{n}} espécies diferentes` }};
    }}],
    ['👑', 'Caçador de Alphas', ps => {{
      const n = ps.filter(p => p.a).length;
      return {{ valor: n, det: `${{n}} alphas capturados` }};
    }}],
    ['🍀', 'Sortudo', ps => {{
      const n = ps.filter(p => p.l).length;
      return {{ valor: n, det: `${{n}} lucky pals` }};
    }}],
    ['💎', 'Perfeccionista', ps => {{
      if (ps.length < 20) return null;
      const m = ps.reduce((s, p) => s + mediaIv(p), 0) / ps.length;
      return {{ valor: m, det: `IV médio ${{m.toFixed(1)}} na coleção` }};
    }}],
    ['⭐', 'Criador', ps => {{
      const n = ps.filter(p => p.r >= 4).length;
      return {{ valor: n, det: `${{n}} pals rank 4+` }};
    }}],
    ['🌙', 'Coruja', ps => {{
      const n = contarHoras(ps, 0, 5);
      return {{ valor: n, det: `${{n}} capturas entre 0h e 6h` }};
    }}],
    ['🌅', 'Madrugador', ps => {{
      const n = contarHoras(ps, 6, 11);
      return {{ valor: n, det: `${{n}} capturas de manhã` }};
    }}],
    ['⚡', 'Maratonista', ps => {{
      const dias = {{}};
      ps.forEach(p => {{ if (p.c) dias[p.c] = (dias[p.c] || 0) + 1; }});
      const [dia, n] = Object.entries(dias).sort((a, b) => b[1] - a[1])[0] || [];
      return n ? {{ valor: n, det: `${{n}} capturas em ${{dia.split('-').reverse().slice(0,2).join('/')}}` }} : null;
    }}],
    ['❤️', 'Melhor amigo', ps => {{
      const p = ps.sort((a, b) => b.f - a.f)[0];
      return p && p.f > 0 ? {{ valor: p.f, det: `${{p.e}} — amizade ${{p.f.toLocaleString('pt-BR')}}` }} : null;
    }}],
  ];

  $('trofeus').innerHTML = categorias.map(([emoji, titulo, fn, direto]) => {{
    const v = direto ? fn() : vencedor(fn);
    if (!v) return '';
    return `<button class="trofeu" data-jogador="${{esc(v.nome)}}">
      <span class="emoji">${{emoji}}</span>
      <span><b>${{titulo}}</b>
        <span class="quem">${{esc(v.nome)}}</span>
        <span class="det">${{esc(v.det)}}</span></span>
    </button>`;
  }}).join('');

  $('trofeus').addEventListener('click', e => {{
    const b = e.target.closest('.trofeu');
    if (b) abrir(b.dataset.jogador);
  }});
}})();

// ---- atalhos na tabela: clicar em especie filtra, clicar no dono abre ----
$('lista').addEventListener('click', e => {{
  const esp = e.target.closest('.f-esp');
  if (esp) {{ busca.value = esp.dataset.e; fDono.value = ''; filtrar();
    $('explorador').scrollTop = 0; return; }}
  const dn = e.target.closest('.f-dono');
  if (dn) abrir(dn.dataset.d);
}});

// ---- especies exclusivas ----
(() => {{
  const porEspecie = {{}};
  D.pals.forEach(p => {{
    if (!p.d) return;
    (porEspecie[p.e] ||= new Set()).add(p.d);
  }});

  const exclusivas = {{}};
  Object.entries(porEspecie).forEach(([esp, donos]) => {{
    if (donos.size === 1) {{
      const dono = [...donos][0];
      (exclusivas[dono] ||= []).push(esp);
    }}
  }});

  const ordenado = Object.entries(exclusivas).sort((a, b) => b[1].length - a[1].length);
  $('exclusivas').innerHTML = ordenado.length === 0
    ? '<div class="dim">Todo mundo divide as mesmas espécies.</div>'
    : ordenado.map(([dono, esps]) => `
        <div class="excl">
          <div class="excl-nome"><i style="background:${{corDe(dono)}}"></i>
            ${{esc(dono)}} <span class="dim">${{esps.length}} exclusivas</span></div>
          <div class="dim excl-lista">${{esps.sort().map(esc).join(', ')}}</div>
        </div>`).join('');
}})();

// ---- painel por jogador ----
function abrir(nome) {{
  const j = D.jogadores.find(x => x.nome === nome);
  if (!j) return;
  const meus = D.pals.filter(p => p.d === nome);
  const top = [...meus].sort((a, b) => mediaIv(b) - mediaIv(a)).slice(0, 5);
  const especies = new Set(meus.map(p => p.e)).size;
  const r4 = meus.filter(p => p.r >= 4).length;

  const online = VIVO && (VIVO.online || []).some(o => o.n === nome);
  const visto = VIVO && VIVO.visto && VIVO.visto[nome];
  const presenca = online
    ? '<span class="ponto-on">● online agora</span>'
    : visto ? `<span class="dim">visto ${{haQuanto(visto)}}</span>` : '';

  $('painel').innerHTML = `
    <button class="voltar" aria-label="Voltar para a visão geral">← Voltar</button>
    <h3>${{esc(j.nome)}} <span style="font-size:.8rem;font-weight:400">${{presenca}}</span></h3>
    <div class="grade">
      <div class="g"><b>${{j.nivel}}</b><span class="dim">nível</span></div>
      <div class="g"><b>${{j.pals}}</b><span class="dim">pals</span></div>
      <div class="g"><b>${{especies}}</b><span class="dim">espécies</span></div>
      <div class="g"><b>${{j.alphas}}</b><span class="dim">alphas</span></div>
      <div class="g"><b>${{j.lucky}}</b><span class="dim">lucky</span></div>
      <div class="g"><b>${{r4}}</b><span class="dim">rank 4+</span></div>
      <div class="g"><b>${{j.nivel_medio_pals}}</b><span class="dim">nível médio</span></div>
    </div>
    <div class="dim" style="margin-bottom:6px">Melhores pals</div>
    <ul>${{top.map(p => `<li><span>${{esc(p.e)}}
      ${{p.l ? '<span class="tag lucky">LUCKY</span>' : ''}}
      ${{p.a ? '<span class="tag alpha">ALPHA</span>' : ''}}</span>
      <span class="dim">IV ${{mediaIv(p).toFixed(1)}} · nv ${{p.n}}</span></li>`).join('')}}</ul>`;

  $('painel').classList.add('on');
  $('painel').querySelector('.voltar').onclick = voltar;
  // Abrir um jogador tambem foca a lista nele; voltar precisa desfazer os dois.
  fDono.value = nome;
  filtrar();
  $('painel').scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
}}

function voltar() {{
  $('painel').classList.remove('on');
  fDono.value = '';
  filtrar();
  window.scrollTo({{ top: 0, behavior: 'smooth' }});
}}

$('ranking').addEventListener('click', e => {{
  const tr = e.target.closest('tr[data-jogador]');
  if (tr) abrir(tr.dataset.jogador);
}});
$('ranking').addEventListener('keydown', e => {{
  if (e.key === 'Enter' || e.key === ' ') {{
    const tr = e.target.closest('tr[data-jogador]');
    if (tr) {{ e.preventDefault(); abrir(tr.dataset.jogador); }}
  }}
}});
document.addEventListener('keydown', e => {{
  if (e.key === 'Escape' && $('painel').classList.contains('on')) voltar();
}});

// ---- estado ao vivo ----
// Vem de um Gist, nao do repositorio: commit a cada minuto estouraria o limite
// de 10 builds/hora do Pages. Usamos a API em vez da URL raw porque o CDN do
// raw segura o conteudo por 5 minutos e ignora cache-buster. A API tem teto de
// 60 requisicoes/hora por IP, dai o intervalo de 90s - e o proprio cache dela
// e de 60s, entao consultar mais rapido nao adiantaria nada.
const GIST = '{GIST_ID}';
let VIVO = null;

const haQuanto = iso => {{
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 90) return 'agora mesmo';
  if (s < 5400) return `há ${{Math.round(s / 60)}} min`;
  if (s < 172800) return `há ${{Math.round(s / 3600)}} h`;
  return `há ${{Math.round(s / 86400)}} dias`;
}};

function pintarVivo() {{
  const el = $('live');
  if (!VIVO) return;
  el.classList.add('on');

  const online = VIVO.online || [];
  let bolha, texto;
  if (!VIVO.no_ar) {{
    bolha = 'vermelha'; texto = '<b>Servidor fora do ar</b>';
  }} else if (online.length === 0) {{
    bolha = 'cinza'; texto = '<b>Ninguém online</b>';
  }} else {{
    bolha = 'verde';
    texto = `<b>${{online.length}} online agora</b>`;
  }}

  el.innerHTML = `<span class="bolha ${{bolha}}"></span>${{texto}}
    <span class="quem">${{online.map(o =>
      `<span class="jog" data-jogador="${{esc(o.n)}}">${{esc(o.n)}}
        <span class="dim">nv ${{o.nv}} · ${{o.p}}ms</span></span>`).join('')}}</span>
    <span class="quando">atualizado ${{haQuanto(VIVO.ts)}}</span>`;

  el.querySelectorAll('.jog').forEach(j =>
    j.onclick = () => abrir(j.dataset.jogador));

  // Marca quem esta online no ranking.
  const nomes = new Set(online.map(o => o.n));
  document.querySelectorAll('#ranking tr[data-jogador]').forEach(tr => {{
    const td = tr.querySelector('.nome');
    const ja = td.querySelector('.ponto-on');
    if (nomes.has(tr.dataset.jogador)) {{
      if (!ja) td.insertAdjacentHTML('afterbegin', '<span class="ponto-on" title="online agora">● </span>');
    }} else if (ja) ja.remove();
  }});
}}

async function buscarVivo() {{
  if (!GIST) return;
  try {{
    const r = await fetch(`https://api.github.com/gists/${{GIST}}`, {{
      headers: {{ 'Accept': 'application/vnd.github+json' }}
    }});
    if (!r.ok) return;                       // 403 = teto de requisicoes; mantem o ultimo
    const g = await r.json();
    const arq = g.files && g.files['live.json'];
    if (arq && arq.content) {{ VIVO = JSON.parse(arq.content); pintarVivo(); }}
  }} catch (e) {{ /* offline ou bloqueado: a pagina segue util sem isso */ }}
}}

if (GIST) {{
  buscarVivo();
  setInterval(buscarVivo, 90000);
  // Reconsulta ao voltar para a aba, mas so se ja passou do intervalo.
  document.addEventListener('visibilitychange', () => {{
    if (!document.hidden && VIVO && Date.now() - Date.parse(VIVO.ts) > 90000) buscarVivo();
  }});
}}
</script>
</body>
</html>
"""

open(destino, "w", encoding="utf-8").write(HTML)
print(f"dashboard escrito em {destino} ({len(HTML):,} bytes)")
