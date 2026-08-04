#!/usr/bin/env python3
"""Gera um dashboard HTML estatico e interativo a partir do JSON do report.py.

Sem dependencias externas e sem recursos remotos: os dados vao embutidos na
propria pagina, entao o arquivo funciona sozinho no GitHub Pages.
"""
import html
import json
import sys
from datetime import date, datetime

dados = json.load(open(sys.argv[1], encoding="utf-8"))
destino = sys.argv[2]

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
for d in tempo:
    total = sum(d["j"].values())
    # Maior primeiro: a base da pilha fica visualmente estavel entre os dias.
    partes = sorted(d["j"].items(), key=lambda kv: -kv[1])
    segmentos = "".join(
        f'<i style="height:{barra(n, max_cap)}%;background:{cor_de.get(nome, "#6b7684")}"></i>'
        for nome, n in partes
    )
    detalhe = " · ".join(f"{E(nome)}: {n}" for nome, n in partes)
    colunas.append(
        f'<div class="dia" title="{date.fromisoformat(d["d"]):%d/%m} — {total} capturas ({detalhe})">'
        f'<div class="pilha">{segmentos}</div>'
        f'<span>{date.fromisoformat(d["d"]):%d/%m}</span></div>'
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

HTML = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SonicCurupiraBeer — estatísticas</title>
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
  .pilha {{ width:100%; display:flex; flex-direction:column-reverse;
    justify-content:flex-start; flex:1; min-height:0; }}
  .pilha i {{ width:100%; min-height:2px; display:block; }}
  .pilha i:last-child {{ border-radius:3px 3px 0 0; }}
  .dia span {{ font-size:.6rem; color:var(--dim); white-space:nowrap;
    transform:rotate(-45deg); }}
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
    const det = donos.filter(n => porHora[n][h]).map(n => `${{esc(n)}}: ${{porHora[n][h]}}`).join(' · ');
    const segs = donos.filter(n => porHora[n][h]).map(n =>
      `<i style="height:${{porHora[n][h] / pico * 100}}%;background:${{corDe(n)}}"></i>`).join('');
    return `<div class="hora" title="${{String(h).padStart(2,'0')}}h — ${{totalHora(h)}} capturas${{det ? ' (' + det + ')' : ''}}">
      <div class="pilha">${{segs}}</div>
      <span>${{h % 3 === 0 ? String(h).padStart(2,'0') : ''}}</span></div>`;
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
      points="${{serie[n].map((v, i) => `${{x(i).toFixed(1)}},${{y(v).toFixed(1)}}`).join(' ')}}">
      <title>${{esc(n)}}: ${{serie[n][dias.length - 1]}} pals</title></polyline>`).join('');

  $('corrida').innerHTML = `
    <svg viewBox="0 -6 ${{W}} ${{H + 12}}" preserveAspectRatio="none"
         style="width:100%;height:170px" role="img"
         aria-label="Pals acumulados por jogador ao longo do tempo">${{linhas}}</svg>
    <div class="legenda">${{donos.map(n =>
      `<span class="leg"><i style="background:${{corDe(n)}}"></i>${{esc(n)}}
       <b style="color:var(--tx)">${{serie[n][dias.length - 1]}}</b></span>`).join('')}}</div>
    <div class="dim" style="margin-top:4px">${{dias[0].split('-').reverse().slice(0,2).join('/')}}
      até ${{dias[dias.length-1].split('-').reverse().slice(0,2).join('/')}}</div>`;
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

  $('painel').innerHTML = `
    <button class="voltar" aria-label="Voltar para a visão geral">← Voltar</button>
    <h3>${{esc(j.nome)}}</h3>
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
</script>
</body>
</html>
"""

open(destino, "w", encoding="utf-8").write(HTML)
print(f"dashboard escrito em {destino} ({len(HTML):,} bytes)")
