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

tempo = dados["linha_tempo"]
max_cap = max((n for _, n in tempo), default=1)
barras_tempo = "".join(
    f'<div class="dia" title="{d}: {n} capturas">'
    f'<i style="height:{barra(n, max_cap)}%"></i>'
    f'<span>{date.fromisoformat(d).strftime("%d/%m")}</span></div>'
    for d, n in tempo[-30:]
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
  .dia i {{ width:100%; background:linear-gradient(180deg,var(--ac),#2b6cb0);
    border-radius:3px 3px 0 0; min-height:2px; }}
  .dia span {{ font-size:.6rem; color:var(--dim); white-space:nowrap;
    transform:rotate(-45deg); }}
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
  .vazio {{ padding:26px; text-align:center; color:var(--dim); }}
  .painel {{ border:1px solid var(--ac); border-radius:12px; padding:16px;
    background:var(--card); margin-bottom:14px; display:none; }}
  .painel.on {{ display:block; }}
  .painel h3 {{ margin:0 0 10px; font-size:1.15rem; }}
  .painel .grade {{ display:grid; gap:10px;
    grid-template-columns:repeat(auto-fit,minmax(110px,1fr)); margin-bottom:12px; }}
  .painel .g {{ background:var(--bg); border-radius:8px; padding:9px 11px; }}
  .painel .g b {{ display:block; font-size:1.25rem; }}
  .fechar {{ float:right; background:none; border:0; color:var(--dim);
    font-size:1.3rem; cursor:pointer; line-height:1; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>SonicCurupiraBeer</h1>
  <div class="sub">Estatísticas do mundo · atualizado em {gerado:%d/%m/%Y às %H:%M}</div>

  <div class="stats">{cards}</div>

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

  <h2>Capturas por dia</h2>
  <div class="card"><div class="tempo">{barras_tempo}</div></div>

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
  <div id="contagem"></div>
  <div class="card scroll" style="padding:0">
    <table>
      <thead><tr>
        <th style="padding-left:16px">espécie</th><th>nível</th><th>IV médio</th>
        <th>HP / ATK / DEF</th><th>dono</th><th>capturado</th>
      </tr></thead>
      <tbody id="lista"></tbody>
    </table>
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

function render() {{
  const q = busca.value.trim().toLowerCase();
  const dono = fDono.value, tipo = fTipo.value, ordem = fOrdem.value;

  let itens = D.pals.filter(p =>
    (!q || p.e.toLowerCase().includes(q)) &&
    (!dono || p.d === dono) &&
    (!tipo || (tipo === 'l' && p.l) || (tipo === 'a' && p.a) || (tipo === 'r' && p.r >= 4))
  );

  const chaves = {{ iv: p => -mediaIv(p), n: p => -p.n, f: p => -p.f, c: p => p.c ? -Date.parse(p.c) : 1 }};
  itens.sort((a, b) => chaves[ordem](a) - chaves[ordem](b));

  $('contagem').textContent =
    `${{itens.length}} de ${{D.pals.length}} pals` + (itens.length > 300 ? ' — exibindo os 300 primeiros' : '');

  $('lista').innerHTML = itens.length === 0
    ? '<tr><td colspan="6" class="vazio">Nenhum pal encontrado com esses filtros.</td></tr>'
    : itens.slice(0, 300).map(p => {{
        const mi = mediaIv(p);
        return `<tr>
          <td style="padding-left:16px"><b>${{esc(p.e)}}</b>
            ${{p.l ? '<span class="tag lucky">LUCKY</span>' : ''}}
            ${{p.a ? '<span class="tag alpha">ALPHA</span>' : ''}}
            ${{p.r >= 4 ? '<span class="dim">★' + p.r + '</span>' : ''}}</td>
          <td>${{p.n}}</td>
          <td class="${{mi >= 80 ? 'iv-forte' : ''}}">${{mi.toFixed(1)}}</td>
          <td class="dim">${{p.iv.join(' / ')}}</td>
          <td>${{esc(p.d) || '<span class="dim">selvagem</span>'}}</td>
          <td class="dim">${{p.c ? p.c.split('-').reverse().slice(0, 2).join('/') : '—'}}</td>
        </tr>`;
      }}).join('');
}}

[busca, fDono, fTipo, fOrdem].forEach(el => el.addEventListener('input', render));
render();

// ---- painel por jogador ----
function abrir(nome) {{
  const j = D.jogadores.find(x => x.nome === nome);
  if (!j) return;
  const meus = D.pals.filter(p => p.d === nome);
  const top = [...meus].sort((a, b) => mediaIv(b) - mediaIv(a)).slice(0, 5);
  const especies = new Set(meus.map(p => p.e)).size;
  const r4 = meus.filter(p => p.r >= 4).length;

  $('painel').innerHTML = `
    <button class="fechar" aria-label="Fechar">&times;</button>
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
  $('painel').querySelector('.fechar').onclick = () => $('painel').classList.remove('on');
  fDono.value = nome; render();
  $('painel').scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
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
</script>
</body>
</html>
"""

open(destino, "w", encoding="utf-8").write(HTML)
print(f"dashboard escrito em {destino} ({len(HTML):,} bytes)")
