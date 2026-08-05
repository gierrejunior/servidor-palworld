/* Dashboard do servidor Palworld.
 *
 * Tudo e desenhado a partir de dados.json, gerado pelo report.py a partir do
 * Level.sav. O estado ao vivo (quem esta online) vem de um Gist, porque o
 * GitHub Pages so reconstroi 10 vezes por hora e um commit por minuto deixaria
 * a pagina mais atrasada do que esta.
 */
'use strict';

const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const PALETA = ['#4ea1ff', '#ffc857', '#ff7ab8', '#5ddba0', '#b18cff', '#ff9d5c', '#4dd4d4'];

// Estado global. Declarado no topo de proposito: o resto do arquivo o le em
// funcoes que rodam durante a inicializacao.
let D = null;          // dados.json
let CORES = {};        // jogador -> cor
let DONOS = [];
let PERIODO = 30;      // dias nos graficos; 0 = tudo
let FOCO = null;       // jogador isolado
let DIA_SEL = '';      // dia escolhido no grafico de capturas
let VIVO = null;       // estado ao vivo

const corDe = n => CORES[n] || '#6b7684';
const mediaIv = p => (p.iv[0] + p.iv[1] + p.iv[2]) / 3;
const fmtDia = d => d.split('-').reverse().slice(0, 2).join('/');
const barraPct = (v, max) => (max ? (v / max * 100).toFixed(1) : 0);
const nUM = v => v.toLocaleString('pt-BR');

const diasComCaptura = () => [...new Set(D.pals.filter(p => p.c).map(p => p.c))].sort();
const diasDoPeriodo = () => {
  const todos = diasComCaptura();
  return PERIODO ? todos.slice(-PERIODO) : todos;
};

/* ------------------------------------------------------------------ tooltip */
// Um unico elemento reaproveitado por todas as barras, via delegacao.
const tip = Object.assign(document.createElement('div'), { className: 'tip' });

function mostrarTip(alvo, x, y) {
  tip.innerHTML = alvo.dataset.tip;
  tip.classList.add('on');
  const r = tip.getBoundingClientRect();
  tip.style.left = Math.min(Math.max(8, x + 14), innerWidth - r.width - 8) + 'px';
  tip.style.top = (y - r.height - 14 < 8 ? y + 20 : y - r.height - 14) + 'px';
}
const esconderTip = () => tip.classList.remove('on');

/* ------------------------------------------------------------------- cabeca */
function desenharTopo() {
  const m = D.mundo;
  const gerado = new Date(D.gerado_em);
  $('sub').textContent = 'Estatísticas do mundo · atualizado em ' +
    gerado.toLocaleDateString('pt-BR') + ' às ' +
    gerado.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });

  $('cards').innerHTML = [
    ['jogadores', m.jogadores], ['pals', m.pals], ['espécies', m.especies],
    ['alphas', m.alphas], ['lucky', m.lucky], ['rank 4+', m.rank4],
  ].map(([r, v]) =>
    `<div class="stat"><span class="num">${nUM(v)}</span><span class="lbl">${r}</span></div>`
  ).join('');

  $('rodape').textContent =
    `Gerado automaticamente a partir do save do servidor · ${m.doentes} pals doentes nas bases`;
}

/* ------------------------------------------------------------------ ranking */
function desenharRanking() {
  const maxExp = Math.max(...D.jogadores.map(j => j.exp), 1);
  $('ranking').innerHTML = D.jogadores.map((j, i) => {
    const mp = j.melhor_pal;
    const melhor = mp
      ? `${esc(mp.especie)} <span class="dim">· IV ${mp.media_ivs}</span>` : '—';
    return `<tr data-jogador="${esc(j.nome)}" tabindex="0" role="button"
        aria-label="Ver detalhes de ${esc(j.nome)}">
      <td class="pos">${i + 1}</td>
      <td class="nome">${esc(j.nome)}</td>
      <td class="nivel">${j.nivel}</td>
      <td class="barra-cel">
        <div class="mini"><i style="width:${barraPct(j.exp, maxExp)}%"></i></div>
        <span class="dim">${nUM(j.exp)}</span>
      </td>
      <td>${j.pals}</td><td>${j.alphas}</td><td>${j.lucky}</td>
      <td class="melhor">${melhor}</td>
    </tr>`;
  }).join('');
}

/* -------------------------------------------------------------------- listas */
function desenharListas() {
  const maxEsp = D.especies_comuns[0] ? D.especies_comuns[0][1] : 1;
  $('especies').innerHTML = D.especies_comuns.map(([e, n]) =>
    `<div class="linha"><span class="rot">${esc(e)}</span>
      <div class="mini"><i style="width:${barraPct(n, maxEsp)}%"></i></div>
      <span class="val">${n}</span></div>`).join('');

  $('passivas').innerHTML = D.passivas.map(([s, n]) =>
    `<li><span>${esc(s)}</span><span class="dim">${n}</span></li>`).join('');

  $('hall').innerHTML = D.hall_ivs.slice(0, 8).map(p =>
    `<div class="pal ${p.lucky ? 'lucky' : ''}">
      <div><b>${esc(p.especie)}</b>
        ${p.lucky ? '<span class="tag lucky">LUCKY</span>' : ''}
        ${p.alpha ? '<span class="tag alpha">ALPHA</span>' : ''}</div>
      <div class="iv">${p.media_ivs}</div>
      <div class="dim">HP ${p.ivs[0]} · ATK ${p.ivs[1]} · DEF ${p.ivs[2]}</div>
      <div class="dim">nível ${p.nivel} · ${esc(p.dono)}</div>
    </div>`).join('');
}

/* ------------------------------------------------------------------ graficos */
function desenharCapturas() {
  const dias = diasDoPeriodo();
  const porDia = {};
  dias.forEach(d => porDia[d] = {});
  D.pals.forEach(p => {
    if (!p.c || !p.d || !(p.c in porDia)) return;
    porDia[p.c][p.d] = (porDia[p.c][p.d] || 0) + 1;
  });

  const totais = dias.map(d => Object.values(porDia[d]).reduce((a, b) => a + b, 0));
  const pico = Math.max(...totais, 1);

  $('eixo-tempo').innerHTML =
    [pico, Math.round(pico / 2), 0].map(v => `<span>${v}</span>`).join('');

  $('tempo').innerHTML = dias.map((d, i) => {
    const partes = Object.entries(porDia[d]).sort((a, b) => b[1] - a[1]);
    const segs = partes.map(([n, q]) =>
      `<i data-j="${esc(n)}" style="height:${barraPct(q, pico)}%;background:${corDe(n)}"></i>`).join('');
    // Aspas simples: este HTML vai dentro de um atributo de aspas duplas.
    const det = partes.map(([n, q]) =>
      `<span style='color:${corDe(n)}'>■</span> ${esc(n)}: <b>${q}</b>`).join('<br>');
    return `<div class="dia${DIA_SEL === d ? ' sel' : ''}" data-dia="${d}" tabindex="0" role="button"
        aria-label="${fmtDia(d)}: ${totais[i]} capturas"
        data-tip="<b>${fmtDia(d)}</b> — ${totais[i]} capturas${det ? '<br>' + det : ''}<br><span class='dim'>clique para ver os pals</span>">
      <div class="pilha">${segs}</div><span>${fmtDia(d)}</span></div>`;
  }).join('');

  const presentes = DONOS.filter(n => dias.some(d => porDia[d][n]));
  $('leg-tempo').innerHTML = presentes.map(n =>
    `<button class="leg" data-jogador="${esc(n)}" title="Clique para isolar ${esc(n)}">
      <i style="background:${corDe(n)}"></i>${esc(n)}</button>`).join('');
}

function desenharHoras() {
  const dias = new Set(diasDoPeriodo());
  const porHora = {};
  DONOS.forEach(n => porHora[n] = new Array(24).fill(0));
  D.pals.forEach(p => { if (p.d && p.h >= 0 && dias.has(p.c)) porHora[p.d][p.h]++; });

  const totalHora = h => DONOS.reduce((s, n) => s + porHora[n][h], 0);
  const pico = Math.max(...Array.from({ length: 24 }, (_, h) => totalHora(h)), 1);

  $('horas').innerHTML = Array.from({ length: 24 }, (_, h) => {
    const ativos = DONOS.filter(n => porHora[n][h]).sort((a, b) => porHora[b][h] - porHora[a][h]);
    const det = ativos.map(n =>
      `<span style='color:${corDe(n)}'>■</span> ${esc(n)}: <b>${porHora[n][h]}</b>`).join('<br>');
    const segs = ativos.map(n =>
      `<i data-j="${esc(n)}" style="height:${barraPct(porHora[n][h], pico)}%;background:${corDe(n)}"></i>`).join('');
    const hh = String(h).padStart(2, '0');
    return `<div class="hora" tabindex="0" role="img"
        aria-label="${hh} horas: ${totalHora(h)} capturas"
        data-tip="<b>${hh}h às ${String((h + 1) % 24).padStart(2, '0')}h</b> — ${totalHora(h)} capturas${det ? '<br>' + det : ''}">
      <div class="pilha">${segs}</div>
      <span>${h % 6 === 0 ? hh + 'h' : ''}</span></div>`;
  }).join('');

  $('eixo-horas').innerHTML =
    [pico, Math.round(pico / 2), 0].map(v => `<span>${v}</span>`).join('');

  $('leg-horas').innerHTML = DONOS.filter(n => porHora[n].some(v => v)).map(n =>
    `<button class="leg" data-jogador="${esc(n)}" title="Clique para isolar ${esc(n)}">
      <i style="background:${corDe(n)}"></i>${esc(n)}</button>`).join('');
}

function desenharCorrida() {
  const dias = diasDoPeriodo();
  if (!dias.length) return;

  // Comeca do que a pessoa ja tinha antes da janela, para a curva nao "zerar"
  // quando o periodo e curto.
  const inicio = dias[0];
  const serie = {};
  DONOS.forEach(n => {
    let acc = D.pals.filter(p => p.d === n && p.c && p.c < inicio).length;
    serie[n] = dias.map(d => acc += D.pals.filter(p => p.d === n && p.c === d).length);
  });
  const teto = Math.max(...DONOS.map(n => serie[n][dias.length - 1]), 1);

  const W = 300, H = 150;
  const x = i => (i / Math.max(dias.length - 1, 1)) * W;
  const y = v => H - (v / teto) * H;

  const linhas = DONOS.map(n =>
    `<polyline data-j="${esc(n)}" fill="none" stroke="${corDe(n)}" stroke-width="2.5"
      stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"
      points="${serie[n].map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')}"/>`).join('');

  const grade = [0, 0.5, 1].map(f =>
    `<line x1="0" x2="${W}" y1="${(H * f).toFixed(1)}" y2="${(H * f).toFixed(1)}"
      stroke="var(--line)" stroke-width="1" vector-effect="non-scaling-stroke" opacity=".6"/>`).join('');

  // Faixas invisiveis por dia: a linha de 2.5px e alvo de mouse pequeno demais.
  const larg = W / dias.length;
  const fatias = dias.map((d, i) => {
    const det = DONOS.map(n => ({ n, v: serie[n][i] })).sort((a, b) => b.v - a.v)
      .map(o => `<span style='color:${corDe(o.n)}'>■</span> ${esc(o.n)}: <b>${o.v}</b>`).join('<br>');
    return `<rect x="${(i * larg).toFixed(1)}" y="-6" width="${larg.toFixed(1)}" height="${H + 12}"
      fill="transparent" data-tip="<b>${fmtDia(d)}</b><br>${det}"/>`;
  }).join('');

  const meio = dias[Math.floor(dias.length / 2)];
  $('corrida').innerHTML = `
    <div class="grafico">
      <div class="eixo-y">${[teto, Math.round(teto / 2), 0].map(v => `<span>${v}</span>`).join('')}</div>
      <div class="area">
        <svg viewBox="0 -6 ${W} ${H + 12}" preserveAspectRatio="none"
             style="width:100%;height:150px;display:block" role="img"
             aria-label="Pals acumulados por jogador ao longo do tempo">
          ${grade}${linhas}${fatias}</svg>
        <div class="eixo"><span>${fmtDia(dias[0])}</span><span>${fmtDia(meio)}</span>
          <span>${fmtDia(dias[dias.length - 1])}</span></div>
      </div>
    </div>
    <div class="legenda">${DONOS.map(n =>
      `<button class="leg" data-jogador="${esc(n)}" title="Clique para isolar ${esc(n)}">
        <i style="background:${corDe(n)}"></i>${esc(n)}
        <b style="color:var(--tx)">${serie[n][dias.length - 1]}</b></button>`).join('')}</div>
    <div class="dica-foco">Clique num jogador da legenda para isolá-lo nos gráficos e na lista.</div>`;
}

const desenharGraficos = () => {
  desenharCapturas();
  desenharHoras();
  desenharCorrida();
  aplicarFoco();
};

/* ---------------------------------------------------------------------- foco */
function aplicarFoco() {
  document.querySelectorAll('[data-j]').forEach(el => {
    const meu = !FOCO || el.dataset.j === FOCO;
    el.style.opacity = meu ? '' : '.12';
    if (el.tagName === 'polyline') el.setAttribute('stroke-width', meu && FOCO ? '4' : '2.5');
  });
  document.querySelectorAll('.leg[data-jogador]').forEach(el => {
    el.classList.toggle('ativo', FOCO === el.dataset.jogador);
    el.classList.toggle('apagado', !!FOCO && FOCO !== el.dataset.jogador);
  });
}

function alternarFoco(nome) {
  FOCO = FOCO === nome ? null : nome;
  aplicarFoco();
  // O foco tambem manda na lista: sem isso a pagina diria duas coisas ao mesmo tempo.
  $('dono').value = FOCO || '';
  filtrar();
}

/* --------------------------------------------------------------- explorador */
// Filtros percorrem D.pals inteiro; a rolagem so controla quanto ja foi
// desenhado. Um IntersectionObserver avisa o fim - nada de polling.
const LOTE = 80;
let filtrados = [], desenhados = 0;

const linhaHtml = p => {
  const mi = mediaIv(p);
  return `<tr>
    <td style="padding-left:16px"><b class="f-esp" data-e="${esc(p.e)}"
        title="Ver todos os ${esc(p.e)}">${esc(p.e)}</b>
      ${p.l ? '<span class="tag lucky">LUCKY</span>' : ''}
      ${p.a ? '<span class="tag alpha">ALPHA</span>' : ''}
      ${p.r >= 4 ? '<span class="dim">★' + p.r + '</span>' : ''}</td>
    <td>${p.n}</td>
    <td class="${mi >= 80 ? 'iv-forte' : ''}">${mi.toFixed(1)}</td>
    <td class="dim">${p.iv.join(' / ')}</td>
    <td>${p.d ? `<span class="f-dono" data-d="${esc(p.d)}" title="Ver ${esc(p.d)}">${esc(p.d)}</span>`
              : '<span class="dim">selvagem</span>'}</td>
    <td class="dim">${p.c ? fmtDia(p.c) : '—'}</td>
  </tr>`;
};

function desenharLote() {
  if (desenhados >= filtrados.length) return;
  const ate = Math.min(desenhados + LOTE, filtrados.length);
  $('lista').insertAdjacentHTML('beforeend',
    filtrados.slice(desenhados, ate).map(linhaHtml).join(''));
  desenhados = ate;

  const contexto = DIA_SEL ? ` · capturados em ${fmtDia(DIA_SEL)}` : '';
  $('contagem').textContent = (filtrados.length === D.pals.length
    ? `${D.pals.length} pals · mostrando ${desenhados}`
    : `${filtrados.length} de ${D.pals.length} pals · mostrando ${desenhados}`) + contexto;
}

function filtrar() {
  const q = $('busca').value.trim().toLowerCase();
  const dono = $('dono').value, tipo = $('tipo').value, ordem = $('ordem').value;

  filtrados = D.pals.filter(p =>
    (!q || p.e.toLowerCase().includes(q)) &&
    (!dono || p.d === dono) &&
    (!DIA_SEL || p.c === DIA_SEL) &&
    (!tipo || (tipo === 'l' && p.l) || (tipo === 'a' && p.a) || (tipo === 'r' && p.r >= 4))
  );

  const chaves = {
    iv: p => -mediaIv(p), n: p => -p.n, f: p => -p.f,
    c: p => (p.c ? -Date.parse(p.c) : 1),
  };
  filtrados.sort((a, b) => chaves[ordem](a) - chaves[ordem](b));

  desenhados = 0;
  $('lista').innerHTML = '';
  if (!filtrados.length) {
    $('lista').innerHTML =
      '<tr><td colspan="6" class="vazio">Nenhum pal encontrado com esses filtros.</td></tr>';
    $('contagem').textContent = `0 de ${D.pals.length} pals`;
    return;
  }
  desenharLote();
}

/* ------------------------------------------------------------------- painel */
const haQuanto = iso => {
  const s = (Date.now() - Date.parse(iso)) / 1000;
  if (s < 90) return 'agora mesmo';
  if (s < 5400) return `há ${Math.round(s / 60)} min`;
  if (s < 172800) return `há ${Math.round(s / 3600)} h`;
  return `há ${Math.round(s / 86400)} dias`;
};

function abrir(nome) {
  const j = D.jogadores.find(x => x.nome === nome);
  if (!j) return;
  const meus = D.pals.filter(p => p.d === nome);
  const top = [...meus].sort((a, b) => mediaIv(b) - mediaIv(a)).slice(0, 5);

  const online = VIVO && (VIVO.online || []).some(o => o.n === nome);
  const visto = VIVO && VIVO.visto && VIVO.visto[nome];
  const presenca = online ? '<span class="ponto-on">● online agora</span>'
    : visto ? `<span class="dim">visto ${haQuanto(visto)}</span>` : '';

  $('painel').innerHTML = `
    <button class="voltar" aria-label="Voltar para a visão geral">← Voltar</button>
    <h3>${esc(j.nome)} <span style="font-size:.8rem;font-weight:400">${presenca}</span></h3>
    <div class="grade-p">
      <div class="g"><b>${j.nivel}</b><span class="dim">nível</span></div>
      <div class="g"><b>${j.pals}</b><span class="dim">pals</span></div>
      <div class="g"><b>${new Set(meus.map(p => p.e)).size}</b><span class="dim">espécies</span></div>
      <div class="g"><b>${j.alphas}</b><span class="dim">alphas</span></div>
      <div class="g"><b>${j.lucky}</b><span class="dim">lucky</span></div>
      <div class="g"><b>${meus.filter(p => p.r >= 4).length}</b><span class="dim">rank 4+</span></div>
      <div class="g"><b>${j.nivel_medio_pals}</b><span class="dim">nível médio</span></div>
    </div>
    <div class="dim" style="margin-bottom:6px">Melhores pals</div>
    <ul>${top.map(p => `<li><span>${esc(p.e)}
      ${p.l ? '<span class="tag lucky">LUCKY</span>' : ''}
      ${p.a ? '<span class="tag alpha">ALPHA</span>' : ''}</span>
      <span class="dim">IV ${mediaIv(p).toFixed(1)} · nv ${p.n}</span></li>`).join('')}</ul>`;

  $('painel').classList.add('on');
  $('painel').querySelector('.voltar').onclick = voltar;
  $('dono').value = nome;
  filtrar();
  $('painel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function voltar() {
  $('painel').classList.remove('on');
  $('dono').value = '';
  filtrar();
  scrollTo({ top: 0, behavior: 'smooth' });
}

/* --------------------------------------------------------------- comparacao */
const METRICAS = [
  ['nível', j => j.nivel],
  ['experiência', j => j.exp, nUM],
  ['pals', j => j.pals],
  ['espécies', (j, ps) => new Set(ps.map(p => p.e)).size],
  ['alphas', j => j.alphas],
  ['lucky', j => j.lucky],
  ['rank 4+', (j, ps) => ps.filter(p => p.r >= 4).length],
  ['nível médio dos pals', j => j.nivel_medio_pals],
  ['IV médio', (j, ps) => ps.length ? +(ps.reduce((s, p) => s + mediaIv(p), 0) / ps.length).toFixed(1) : 0],
  ['melhor IV', (j, ps) => ps.length ? +Math.max(...ps.map(mediaIv)).toFixed(1) : 0],
];

function comparar() {
  const a = D.jogadores.find(j => j.nome === $('cmpA').value);
  const b = D.jogadores.find(j => j.nome === $('cmpB').value);
  if (!a || !b) return;
  const pa = D.pals.filter(p => p.d === a.nome);
  const pb = D.pals.filter(p => p.d === b.nome);

  const linhas = METRICAS.map(([rot, fn, fmt]) => {
    const va = fn(a, pa), vb = fn(b, pb), f = fmt || (v => v);
    return `<div class="v dir ${va > vb ? 'venc' : ''}">${f(va)}</div>
            <div class="rot">${rot}</div>
            <div class="v ${vb > va ? 'venc' : ''}">${f(vb)}</div>`;
  }).join('');

  $('comparacao').innerHTML = `<div class="cmp">
    <div class="cmp-nome" style="justify-content:flex-end">
      ${esc(a.nome)}<i style="background:${corDe(a.nome)}"></i></div>
    <div></div>
    <div class="cmp-nome"><i style="background:${corDe(b.nome)}"></i>${esc(b.nome)}</div>
    ${linhas}</div>`;
}

/* ------------------------------------------------------------------ trofeus */
function desenharTrofeus() {
  const meus = n => D.pals.filter(p => p.d === n);
  const vencedor = fn => {
    let melhor = null;
    DONOS.forEach(n => {
      const v = fn(meus(n), n);
      if (v && v.valor > 0 && (!melhor || v.valor > melhor.valor)) melhor = { ...v, nome: n };
    });
    return melhor;
  };
  const nasHoras = (ps, de, ate) => ps.filter(p => p.h >= de && p.h <= ate).length;

  const categorias = [
    ['🏆', 'Maior nível', () => {
      const j = D.jogadores[0];
      return j && { valor: j.nivel, det: `nível ${j.nivel}`, nome: j.nome };
    }, true],
    ['📚', 'Colecionador', ps => {
      const n = new Set(ps.map(p => p.e)).size;
      return { valor: n, det: `${n} espécies diferentes` };
    }],
    ['👑', 'Caçador de Alphas', ps => {
      const n = ps.filter(p => p.a).length;
      return { valor: n, det: `${n} alphas capturados` };
    }],
    ['🍀', 'Sortudo', ps => {
      const n = ps.filter(p => p.l).length;
      return { valor: n, det: `${n} lucky pals` };
    }],
    ['💎', 'Perfeccionista', ps => {
      if (ps.length < 20) return null;
      const m = ps.reduce((s, p) => s + mediaIv(p), 0) / ps.length;
      return { valor: m, det: `IV médio ${m.toFixed(1)} na coleção` };
    }],
    ['⭐', 'Criador', ps => {
      const n = ps.filter(p => p.r >= 4).length;
      return { valor: n, det: `${n} pals rank 4+` };
    }],
    ['🌙', 'Coruja', ps => {
      const n = nasHoras(ps, 0, 5);
      return { valor: n, det: `${n} capturas entre 0h e 6h` };
    }],
    ['🌅', 'Madrugador', ps => {
      const n = nasHoras(ps, 6, 11);
      return { valor: n, det: `${n} capturas de manhã` };
    }],
    ['⚡', 'Maratonista', ps => {
      const dias = {};
      ps.forEach(p => { if (p.c) dias[p.c] = (dias[p.c] || 0) + 1; });
      const [dia, n] = Object.entries(dias).sort((a, b) => b[1] - a[1])[0] || [];
      return n ? { valor: n, det: `${n} capturas em ${fmtDia(dia)}` } : null;
    }],
    ['❤️', 'Melhor amigo', ps => {
      const p = [...ps].sort((a, b) => b.f - a.f)[0];
      return p && p.f > 0 ? { valor: p.f, det: `${p.e} — amizade ${nUM(p.f)}` } : null;
    }],
    ['🥾', 'Explorador', ps => {
      const dias = new Set(ps.filter(p => p.c).map(p => p.c)).size;
      return { valor: dias, det: `capturou em ${dias} dias diferentes` };
    }],
    ['🧬', 'Geneticista', ps => {
      const n = ps.filter(p => mediaIv(p) >= 85).length;
      return { valor: n, det: `${n} pals com IV médio 85+` };
    }],
  ];

  $('trofeus').innerHTML = categorias.map(([emoji, titulo, fn, direto]) => {
    const v = direto ? fn() : vencedor(fn);
    if (!v) return '';
    return `<button class="trofeu" data-jogador="${esc(v.nome)}">
      <span class="emoji">${emoji}</span>
      <span><b>${titulo}</b>
        <span class="quem">${esc(v.nome)}</span>
        <span class="det">${esc(v.det)}</span></span>
    </button>`;
  }).join('');
}

/* --------------------------------------------------------------- exclusivas */
function desenharExclusivas() {
  const porEspecie = {};
  D.pals.forEach(p => {
    if (!p.d) return;
    (porEspecie[p.e] ||= new Set()).add(p.d);
  });

  const exclusivas = {};
  Object.entries(porEspecie).forEach(([esp, donos]) => {
    if (donos.size === 1) (exclusivas[[...donos][0]] ||= []).push(esp);
  });

  const ordenado = Object.entries(exclusivas).sort((a, b) => b[1].length - a[1].length);
  $('exclusivas').innerHTML = !ordenado.length
    ? '<div class="dim">Todo mundo divide as mesmas espécies.</div>'
    : ordenado.map(([dono, esps]) => `
        <div class="excl">
          <div class="excl-nome"><i style="background:${corDe(dono)}"></i>
            ${esc(dono)} <span class="dim">${esps.length} exclusivas</span></div>
          <div class="dim excl-lista">${esps.sort().map(esc).join(', ')}</div>
        </div>`).join('');
}

/* ---------------------------------------------------------------- ao vivo */
function pintarVivo() {
  if (!VIVO) return;
  const el = $('live');
  el.classList.add('on');

  const online = VIVO.online || [];
  let bolha, texto;
  if (!VIVO.no_ar) { bolha = 'vermelha'; texto = '<b>Servidor fora do ar</b>'; }
  else if (!online.length) { bolha = 'cinza'; texto = '<b>Ninguém online</b>'; }
  else { bolha = 'verde'; texto = `<b>${online.length} online agora</b>`; }

  el.innerHTML = `<span class="bolha ${bolha}"></span>${texto}
    <span class="quem">${online.map(o =>
      `<span class="jog" data-jogador="${esc(o.n)}">${esc(o.n)}
        <span class="dim">nv ${o.nv} · ${o.p}ms</span></span>`).join('')}</span>
    <span class="quando">atualizado ${haQuanto(VIVO.ts)}</span>`;

  el.querySelectorAll('.jog').forEach(j => j.onclick = () => abrir(j.dataset.jogador));

  const nomes = new Set(online.map(o => o.n));
  document.querySelectorAll('#ranking tr[data-jogador]').forEach(tr => {
    const td = tr.querySelector('.nome');
    const ja = td.querySelector('.ponto-on');
    if (nomes.has(tr.dataset.jogador)) {
      if (!ja) td.insertAdjacentHTML('afterbegin',
        '<span class="ponto-on" title="online agora">● </span>');
    } else if (ja) ja.remove();
  });
}

// A URL raw do Gist e servida com 5 min de cache e ignora cache-buster; a API
// devolve o dado fresco, em troca de um teto de 60 requisicoes/hora por IP.
// Dai o intervalo de 90s - o cache dela e de 60s, mais rapido nao traria nada.
async function buscarVivo() {
  if (!D.gist) return;
  try {
    const r = await fetch(`https://api.github.com/gists/${D.gist}`,
      { headers: { Accept: 'application/vnd.github+json' } });
    if (!r.ok) return;                       // 403 = teto atingido; mantem o ultimo
    const g = await r.json();
    const arq = g.files && g.files['live.json'];
    if (arq && arq.content) { VIVO = JSON.parse(arq.content); pintarVivo(); }
  } catch (e) { /* offline: a pagina segue util sem isso */ }
}

/* ------------------------------------------------------------------ eventos */
function ligarEventos() {
  document.addEventListener('mousemove', e => {
    const alvo = e.target.closest('[data-tip]');
    if (alvo) mostrarTip(alvo, e.clientX, e.clientY); else esconderTip();
  });
  document.addEventListener('focusin', e => {
    const alvo = e.target.closest('[data-tip]');
    if (!alvo) return esconderTip();
    const r = alvo.getBoundingClientRect();
    mostrarTip(alvo, r.left + r.width / 2, r.top);
  });
  document.addEventListener('focusout', esconderTip);
  addEventListener('scroll', esconderTip, { passive: true });

  document.addEventListener('click', e => {
    const leg = e.target.closest('.leg[data-jogador]');
    if (leg) return alternarFoco(leg.dataset.jogador);

    const linha = e.target.closest('polyline[data-j]');
    if (linha) return alternarFoco(linha.dataset.j);

    const trof = e.target.closest('.trofeu[data-jogador]');
    if (trof) return abrir(trof.dataset.jogador);

    const tr = e.target.closest('#ranking tr[data-jogador]');
    if (tr) return abrir(tr.dataset.jogador);

    const per = e.target.closest('.periodos button');
    if (per) {
      PERIODO = Number(per.dataset.periodo);
      document.querySelectorAll('.periodos button').forEach(b => b.classList.toggle('on', b === per));
      DIA_SEL = '';
      desenharGraficos();
      filtrar();
      return;
    }

    const dia = e.target.closest('.dia[data-dia]');
    if (dia) {
      DIA_SEL = DIA_SEL === dia.dataset.dia ? '' : dia.dataset.dia;
      desenharCapturas();
      aplicarFoco();
      filtrar();
      if (DIA_SEL) $('explorador').scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    const esp = e.target.closest('.f-esp');
    if (esp) {
      $('busca').value = esp.dataset.e;
      $('dono').value = '';
      filtrar();
      $('explorador').scrollTop = 0;
      return;
    }
    const dn = e.target.closest('.f-dono');
    if (dn) abrir(dn.dataset.d);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && $('painel').classList.contains('on')) return voltar();
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const alvo = e.target.closest('.dia[data-dia], #ranking tr[data-jogador]');
    if (alvo) { e.preventDefault(); alvo.click(); }
  });

  let timer;
  $('busca').addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(filtrar, 160);
  });
  ['dono', 'tipo', 'ordem'].forEach(id => $(id).addEventListener('change', filtrar));
  ['cmpA', 'cmpB'].forEach(id => $(id).addEventListener('change', comparar));

  new IntersectionObserver(e => { if (e[0].isIntersecting) desenharLote(); },
    { root: $('explorador'), rootMargin: '400px' }).observe($('sentinela'));
}

/* -------------------------------------------------------------------- inicio */
async function iniciar() {
  document.body.appendChild(tip);
  D = await (await fetch('dados.json')).json();

  D.jogadores.forEach((j, i) => CORES[j.nome] = PALETA[i % PALETA.length]);
  CORES.selvagem = '#6b7684';
  DONOS = [...new Set(D.pals.map(p => p.d).filter(Boolean))];

  const opcoes = D.jogadores.map(j => `<option value="${esc(j.nome)}">${esc(j.nome)}</option>`).join('');
  $('cmpA').innerHTML = opcoes;
  $('cmpB').innerHTML = opcoes;
  if (D.jogadores[1]) $('cmpB').value = D.jogadores[1].nome;

  DONOS.slice().sort().forEach(n => {
    const o = document.createElement('option');
    o.value = n; o.textContent = n;
    $('dono').appendChild(o);
  });

  desenharTopo();
  desenharRanking();
  desenharListas();
  desenharTrofeus();
  desenharExclusivas();
  comparar();
  desenharGraficos();
  filtrar();
  ligarEventos();

  buscarVivo();
  setInterval(buscarVivo, 90000);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && VIVO && Date.now() - Date.parse(VIVO.ts) > 90000) buscarVivo();
  });
}

iniciar();
