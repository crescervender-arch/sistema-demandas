/* Sistema de Controle de Demandas — SPA (vanilla JS) */
"use strict";

const NIVEL = { master: 5, socio: 4, gestor: 3, advogado: 2, estagiario: 1 };
const state = { token: localStorage.getItem("token"), user: null, meta: null, nucleos: [], usuarios: [] };

const root = document.getElementById("root");
const $ = (sel, ctx = document) => ctx.querySelector(sel);

/* ------------------------------- utils -------------------------------- */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function money(v) {
  if (v == null) return "—";
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(v);
}
function dataBR(iso) {
  if (!iso) return "—";
  const d = new Date(iso.length <= 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString("pt-BR");
}
function can(min) { return state.user && NIVEL[state.user.perfil_acesso] >= NIVEL[min]; }
function iniciais(nome) { return (nome || "?").split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase(); }

function toast(msg, type = "") {
  const t = document.createElement("div");
  t.className = "toast " + type;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 3200);
}

async function api(method, path, body) {
  const opt = { method, headers: {} };
  if (state.token) opt.headers["Authorization"] = "Bearer " + state.token;
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  const res = await fetch("/api" + path, opt);
  if (res.status === 401 && state.user) { logout(); throw new Error("Sessão expirada"); }
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) throw new Error((data && data.detail) || "Erro " + res.status);
  return data;
}

/* ------------------------------- auth --------------------------------- */
async function boot() {
  if (state.token) {
    try { state.user = await api("GET", "/auth/me"); }
    catch (_) { state.token = null; localStorage.removeItem("token"); }
  }
  if (!state.user) return renderLogin();
  await carregarBase();
  window.addEventListener("hashchange", router);
  router();
}

async function carregarBase() {
  try {
    state.meta = await api("GET", "/meta");
    state.nucleos = await api("GET", "/nucleos");
    state.usuarios = await api("GET", "/usuarios");
  } catch (e) { /* perfis baixos podem não ter tudo */ }
}

function logout() {
  state.token = null; state.user = null; localStorage.removeItem("token");
  location.hash = ""; renderLogin();
}

function renderLogin() {
  root.innerHTML = `
  <div class="login-wrap">
    <div class="login-hero">
      <div class="brand">Crescer Tecnologia e Gestão</div>
      <h1>Controle de Demandas Jurídicas</h1>
      <div class="gold-bar"></div>
      <p>Gestão operacional e financeira das demandas do escritório: prazos, alocação por profissional, SLA e KPIs da controladoria em tempo real.</p>
      <div class="login-feats">
        <div><span class="dot"></span> Zero perda de prazo processual</div>
        <div><span class="dot"></span> Controle de acesso por perfil (RBAC)</div>
        <div><span class="dot"></span> Dashboard da controladoria com 6 KPIs</div>
      </div>
    </div>
    <div class="login-form-col">
      <form class="login-card" id="loginForm">
        <h2>Entrar</h2>
        <div class="sub">Acesse o sistema com suas credenciais</div>
        <label class="field"><span>E-mail</span><input type="email" id="email" placeholder="voce@bbz.adv.br" autocomplete="username" required></label>
        <label class="field"><span>Senha</span><input type="password" id="senha" placeholder="••••••••" autocomplete="current-password" required></label>
        <button class="btn block" id="btnLogin" type="submit">Entrar</button>
        <div class="hint"><b>Login master (demonstração):</b><br>master@bbz.adv.br &nbsp;/&nbsp; master123<br>
        Outros: socio@bbz.adv.br · gestor.trab@bbz.adv.br · adv1@bbz.adv.br · estag1@bbz.adv.br</div>
      </form>
    </div>
  </div>`;
  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("#btnLogin"); btn.disabled = true; btn.textContent = "Entrando...";
    try {
      const r = await api("POST", "/auth/login", { email: $("#email").value, senha: $("#senha").value });
      state.token = r.token; state.user = r.usuario; localStorage.setItem("token", r.token);
      await carregarBase();
      window.addEventListener("hashchange", router);
      location.hash = "#/dashboard"; router();
      toast("Bem-vindo(a), " + r.usuario.nome.split(" ")[0] + "!", "ok");
    } catch (err) {
      toast(err.message, "err"); btn.disabled = false; btn.textContent = "Entrar";
    }
  });
}

/* ------------------------------- shell -------------------------------- */
const NAV = [
  { route: "dashboard", label: "Dashboard", min: "gestor", icon: "M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z" },
  { route: "demandas", label: "Demandas", min: "estagiario", icon: "M4 4h16v4H4zM4 10h16v10H4z" },
  { route: "nucleos", label: "Núcleos", min: "gestor", icon: "M12 2l9 4.9V17L12 22 3 17V6.9L12 2z" },
  { route: "acessos", label: "Acessos & Usuários", min: "socio", icon: "M16 11a4 4 0 1 0-8 0 4 4 0 0 0 8 0zM2 21a8 8 0 0 1 16 0" },
  { route: "conta", label: "Minha conta", min: "estagiario", icon: "M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM3 21a9 9 0 0 1 18 0" },
];

function shell(active, title, subtitle, contentHTML) {
  const navItems = NAV.filter(n => can(n.min)).map(n => `
    <a href="#/${n.route}" class="${active === n.route ? "active" : ""}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="${n.icon}"/></svg>
      ${n.label}
    </a>`).join("");
  root.innerHTML = `
  <div class="app">
    <aside class="sidebar">
      <div class="logo"><div class="mark">D</div><div><b>Demandas</b><br><small>Crescer · Controladoria</small></div></div>
      <nav class="nav">
        <div class="sep">Menu</div>
        ${navItems}
      </nav>
      <div class="who">
        <div class="name">${esc(state.user.nome)}</div>
        <div class="role">${esc(state.user.perfil_acesso)}${state.user.nucleo_nome ? " · " + esc(state.user.nucleo_nome) : ""}</div>
      </div>
    </aside>
    <main class="main">
      <header class="topbar">
        <div><h1>${esc(title)}</h1></div>
        <div class="right">
          <div class="avatar" title="${esc(state.user.nome)}">${iniciais(state.user.nome)}</div>
          <button class="btn ghost sm" id="btnLogout">Sair</button>
        </div>
      </header>
      <div class="content" id="content">${contentHTML}</div>
    </main>
  </div>`;
  $("#btnLogout").addEventListener("click", logout);
}

function loading(title) {
  shell(currentRoute(), title, "", `<div class="spinner"></div>`);
}
function currentRoute() { return (location.hash.replace("#/", "") || "dashboard").split("?")[0]; }

/* ------------------------------- router ------------------------------- */
function router() {
  const r = currentRoute();
  if (r === "dashboard" && can("gestor")) return pageDashboard();
  if (r === "demandas") return pageDemandas();
  if (r === "nucleos" && can("gestor")) return pageNucleos();
  if (r === "acessos" && can("socio")) return pageAcessos();
  if (r === "conta") return pageConta();
  // fallback
  location.hash = "#/demandas";
}

/* ============================== DASHBOARD ============================= */
async function pageDashboard() {
  loading("Dashboard da Controladoria");
  let d;
  try { d = await api("GET", "/dashboard"); } catch (e) { return toast(e.message, "err"); }
  const c = d.cards;
  const html = `
    <div class="kpi-grid">
      ${kpi("teal", "Demandas ativas", c.demandas_ativas, "em aberto no escritório")}
      ${kpi("green", "Encerradas no mês", c.encerradas_mes, "demandas concluídas")}
      ${kpi("navy", "Aderência ao SLA", c.sla_aderencia + "%", "dentro do prazo interno")}
      ${kpi("red", "Vencendo em 48h", c.vencendo_48h, c.vencidas + " já vencidas")}
      ${kpi("purple", "Aguardando triagem", c.aguardando_triagem, "na fila de entrada")}
    </div>

    <div class="grid-2 section-gap">
      <div class="panel">
        <h3>Produção por Núcleo</h3><div class="psub">Demandas encerradas no mês corrente</div>
        ${barChart(d.producao_nucleo.map(x => ({ label: x.nucleo, value: x.total })))}
      </div>
      <div class="panel">
        <h3>Throughput Mensal</h3><div class="psub">Demandas encerradas nos últimos 12 meses</div>
        ${lineChart(d.throughput)}
      </div>
    </div>

    <div class="grid-2-13 section-gap">
      <div class="panel">
        <h3>Aging das Demandas em Aberto</h3><div class="psub">Distribuição por tempo desde a abertura</div>
        ${agingChart(d.aging)}
        <div class="cart-grid" style="margin-top:18px">
          <div class="cell"><div class="n" style="color:var(--teal-dark)">${money(d.carteira.valor_total)}</div><div class="muted">Carteira ativa</div></div>
          <div class="cell"><div class="n">${d.carteira.alto}</div><div class="muted">Causas alto valor</div></div>
          <div class="cell"><div class="n">${d.carteira.medio + d.carteira.baixo}</div><div class="muted">Médio + baixo</div></div>
        </div>
      </div>
      <div class="panel">
        <h3>Aderência ao SLA por Profissional</h3><div class="psub">Meta: 85% · piores destacados</div>
        ${rankChart(d.ranking_sla)}
      </div>
    </div>`;
  shell("dashboard", "Dashboard da Controladoria", "", html);
}

function kpi(cls, label, value, foot) {
  return `<div class="kpi ${cls}"><div class="stripe"></div><div class="label">${label}</div><div class="value">${value}</div><div class="foot">${foot}</div></div>`;
}

function barChart(items) {
  if (!items.length) return `<div class="empty">Sem demandas encerradas neste mês ainda.</div>`;
  const max = Math.max(...items.map(i => i.value), 1);
  const cores = ["#157d8d", "#7c3aed", "#e0a526", "#16a34a", "#dc2626", "#2563eb"];
  return `<div class="bars">${items.map((i, idx) => `
    <div class="bar-col">
      <div class="bval">${i.value}</div>
      <div class="bar" style="height:${Math.max(6, i.value / max * 100)}%;background:${cores[idx % cores.length]}"></div>
      <div class="bcap">${esc(i.label)}</div>
    </div>`).join("")}</div>`;
}

function lineChart(series) {
  const w = 560, h = 190, pad = 28;
  const max = Math.max(...series.map(s => s.total), 1);
  const stepX = (w - pad * 2) / Math.max(series.length - 1, 1);
  const pts = series.map((s, i) => {
    const x = pad + i * stepX;
    const y = h - pad - (s.total / max) * (h - pad * 2);
    return [x, y];
  });
  const path = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const area = path + ` L${pts[pts.length - 1][0].toFixed(1)} ${h - pad} L${pts[0][0].toFixed(1)} ${h - pad} Z`;
  const labels = series.map((s, i) => {
    if (series.length > 8 && i % 2) return "";
    const [y, m] = s.mes.split("-");
    const nomes = ["", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
    return `<text x="${(pad + i * stepX).toFixed(1)}" y="${h - 8}" font-size="10" fill="#6b7787" text-anchor="middle">${nomes[+m]}</text>`;
  }).join("");
  const dots = pts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3" fill="#157d8d"/>`).join("");
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto">
    <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#157d8d" stop-opacity=".18"/><stop offset="1" stop-color="#157d8d" stop-opacity="0"/></linearGradient></defs>
    <path d="${area}" fill="url(#g1)"/>
    <path d="${path}" fill="none" stroke="#157d8d" stroke-width="2.5" stroke-linejoin="round"/>
    ${dots}${labels}
  </svg>`;
}

function agingChart(a) {
  const total = a.normal + a.monitorar + a.atencao + a.critico || 1;
  const segs = [
    { k: "normal", l: "Normal (≤15d)", v: a.normal, c: "#16a34a" },
    { k: "monitorar", l: "Monitorar (16-30d)", v: a.monitorar, c: "#e0a526" },
    { k: "atencao", l: "Atenção (31-60d)", v: a.atencao, c: "#f97316" },
    { k: "critico", l: "Crítico (>60d)", v: a.critico, c: "#dc2626" },
  ];
  return `
    <div class="aging-bar">${segs.filter(s => s.v).map(s => `<div style="flex:${s.v};background:${s.c}">${Math.round(s.v / total * 100)}%</div>`).join("")}</div>
    <div class="legend">${segs.map(s => `<span><i style="background:${s.c}"></i>${s.l}: <b>${s.v}</b></span>`).join("")}</div>`;
}

function rankChart(rows) {
  if (!rows.length) return `<div class="empty">Sem dados de responsáveis ainda.</div>`;
  return rows.map(r => {
    const c = r.pct >= 85 ? "#16a34a" : r.pct >= 75 ? "#e0a526" : "#dc2626";
    return `<div class="rank-row">
      <div class="rname" title="${esc(r.profissional)}">${esc(r.profissional)}</div>
      <div class="rank-track"><div class="rank-fill" style="width:${r.pct}%;background:${c}"></div></div>
      <div class="rpct" style="color:${c}">${r.pct}%</div>
    </div>`;
  }).join("");
}

/* ============================== DEMANDAS ============================= */
const STATUS_LABEL = { triagem: "Triagem", alocacao: "Alocação", execucao: "Execução", encerrado: "Encerrado", arquivado: "Arquivado" };
function badgeStatus(s) { return `<span class="badge b-${s}"><span class="d" style="background:currentColor"></span>${STATUS_LABEL[s] || s}</span>`; }
function badgePrio(p) { return `<span class="badge b-${p}">${p}</span>`; }
function badgePerfil(p) { return `<span class="badge pill-perfil b-${p}">${p}</span>`; }
function slaCell(d) {
  if (!d.prazo_interno) return `<span class="muted">—</span>`;
  const cls = d.sla_status === "vencida" ? "sla-vencida" : d.sla_status === "vencendo" ? "sla-vencendo" : "sla-ok";
  return `<span class="${cls}">${dataBR(d.prazo_interno)}</span>`;
}

async function pageDemandas() {
  loading("Demandas");
  let demandas;
  try { demandas = await api("GET", "/demandas"); } catch (e) { return toast(e.message, "err"); }
  const optsNucleo = `<option value="">Todos os núcleos</option>` + state.nucleos.map(n => `<option value="${n.id}">${esc(n.nome)}</option>`).join("");
  const optsStatus = `<option value="">Todos os status</option>` + Object.entries(STATUS_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  const novoBtn = can("advogado") ? `<button class="btn" id="btnNova">+ Nova demanda</button>` : "";

  const html = `
    <div class="toolbar">
      <input type="text" id="fBusca" placeholder="Buscar por título...">
      <select id="fNucleo">${optsNucleo}</select>
      <select id="fStatus">${optsStatus}</select>
      <div class="grow"></div>
      ${novoBtn}
    </div>
    <div id="tabela"></div>`;
  shell("demandas", "Demandas", "", html);

  function pinta(list) {
    const body = list.length ? list.map(d => `
      <tr class="clickable" data-id="${d.id}">
        <td><b>${esc(d.titulo)}</b><br><span class="muted" style="font-size:12px">${esc(d.tipo_demanda)}${d.numero_processo ? " · " + esc(d.numero_processo) : ""}</span></td>
        <td>${esc(d.nucleo_nome || "—")}</td>
        <td>${esc(d.responsavel_nome || "<span class='muted'>sem responsável</span>")}</td>
        <td>${badgeStatus(d.status)}</td>
        <td>${badgePrio(d.prioridade)}</td>
        <td>${slaCell(d)}</td>
        <td>${money(d.valor_causa)}</td>
        <td class="muted">${d.dias_aberto}d</td>
      </tr>`).join("") : `<tr><td colspan="8"><div class="empty"><div class="big">📭</div>Nenhuma demanda encontrada.</div></td></tr>`;
    $("#tabela").innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Demanda</th><th>Núcleo</th><th>Responsável</th><th>Status</th><th>Prioridade</th><th>Prazo interno</th><th>Valor da causa</th><th>Aberta há</th></tr></thead>
      <tbody>${body}</tbody></table></div>`;
    $("#tabela").querySelectorAll("tr[data-id]").forEach(tr => tr.addEventListener("click", () => abrirDemanda(tr.dataset.id)));
  }
  pinta(demandas);

  function filtra() {
    const b = $("#fBusca").value.toLowerCase(), nuc = $("#fNucleo").value, st = $("#fStatus").value;
    pinta(demandas.filter(d =>
      (!b || d.titulo.toLowerCase().includes(b)) &&
      (!nuc || d.nucleo_id === nuc) &&
      (!st || d.status === st)));
  }
  $("#fBusca").addEventListener("input", filtra);
  $("#fNucleo").addEventListener("change", filtra);
  $("#fStatus").addEventListener("change", filtra);
  if (novoBtn) $("#btnNova").addEventListener("click", () => formDemanda());
}

function formDemanda(d) {
  const m = state.meta;
  const opt = (arr, sel) => arr.map(x => `<option value="${x}" ${x === sel ? "selected" : ""}>${x}</option>`).join("");
  const nucOpt = state.nucleos.map(n => `<option value="${n.id}" ${d && d.nucleo_id === n.id ? "selected" : ""}>${esc(n.nome)}</option>`).join("");
  openModal(d ? "Editar demanda" : "Nova demanda", `
    <label class="field"><span>Título *</span><input id="d_titulo" value="${d ? esc(d.titulo) : ""}" placeholder="Ex.: Reclamatória trabalhista — horas extras"></label>
    <div class="form-row-3">
      <label class="field"><span>Tipo *</span><select id="d_tipo">${opt(m.tipos_demanda, d && d.tipo_demanda)}</select></label>
      <label class="field"><span>Prioridade</span><select id="d_prio">${opt(m.prioridades, (d && d.prioridade) || "normal")}</select></label>
      <label class="field"><span>Núcleo *</span><select id="d_nucleo">${nucOpt}</select></label>
    </div>
    <div class="form-row-3">
      <label class="field"><span>Valor da causa (R$)</span><input type="number" id="d_valor" value="${d && d.valor_causa != null ? d.valor_causa : ""}" placeholder="0"></label>
      <label class="field"><span>Prazo interno</span><input type="date" id="d_prazoi" value="${d && d.prazo_interno ? d.prazo_interno : ""}"></label>
      <label class="field"><span>Prazo legal</span><input type="date" id="d_prazol" value="${d && d.prazo_legal ? d.prazo_legal : ""}"></label>
    </div>
    <div class="form-row-3">
      <label class="field"><span>Nº do processo</span><input id="d_proc" value="${d ? esc(d.numero_processo || "") : ""}"></label>
      <label class="field"><span>Tribunal</span><input id="d_trib" value="${d ? esc(d.tribunal || "") : ""}"></label>
      <label class="field"><span>Fase processual</span><input id="d_fase" value="${d ? esc(d.fase_processual || "") : ""}"></label>
    </div>
    <label class="field"><span>Descrição</span><textarea id="d_desc" placeholder="Detalhes da demanda...">${d ? esc(d.descricao || "") : ""}</textarea></label>
  `, async () => {
    const body = {
      titulo: $("#d_titulo").value.trim(), tipo_demanda: $("#d_tipo").value, prioridade: $("#d_prio").value,
      nucleo_id: $("#d_nucleo").value, valor_causa: $("#d_valor").value ? parseFloat($("#d_valor").value) : null,
      prazo_interno: $("#d_prazoi").value || null, prazo_legal: $("#d_prazol").value || null,
      numero_processo: $("#d_proc").value.trim() || null, tribunal: $("#d_trib").value.trim() || null,
      fase_processual: $("#d_fase").value.trim() || null, descricao: $("#d_desc").value.trim() || null,
    };
    if (!body.titulo) throw new Error("Informe o título");
    if (d) { await api("PUT", "/demandas/" + d.id, body); toast("Demanda atualizada", "ok"); }
    else { await api("POST", "/demandas", body); toast("Demanda criada", "ok"); }
    closeModal(); pageDemandas();
  });
}

async function abrirDemanda(id) {
  let d;
  try { d = await api("GET", "/demandas/" + id); } catch (e) { return toast(e.message, "err"); }
  const podeEditar = can("socio") || (state.user.perfil_acesso === "gestor" && d.nucleo_id === state.user.nucleo_id)
    || (state.user.perfil_acesso === "advogado" && d.responsavel_nome === state.user.nome);

  const acoesStatus = d.proximos_status.map(s => {
    const precisaGestor = (s === "encerrado" || s === "arquivado");
    if (precisaGestor && !can("gestor")) return "";
    return `<button class="btn ghost sm" data-novo="${s}">→ ${STATUS_LABEL[s]}</button>`;
  }).join("");

  const alocs = d.alocacoes.length ? d.alocacoes.map(a => `
    <tr><td>${esc(a.profissional_nome)} ${a.responsavel_principal ? '<span class="badge b-socio">responsável</span>' : ""}</td>
    <td class="muted">${esc(a.papel)}</td><td class="muted">${a.horas_realizadas || 0}h / ${a.horas_estimadas || "—"}h</td>
    <td>${can("gestor") ? `<button class="btn danger sm" data-rem="${a.id}">Remover</button>` : ""}</td></tr>`).join("")
    : `<tr><td colspan="4" class="muted">Nenhum profissional alocado.</td></tr>`;

  const timeline = d.movimentacoes.map(m => `
    <div class="ev"><div class="when">${dataBR(m.ocorrido_em)} · ${esc(m.autor || "")}</div>
      <div>${m.status_anterior ? STATUS_LABEL[m.status_anterior] + " → " : ""}<b>${STATUS_LABEL[m.status_novo] || m.status_novo}</b>${m.observacao ? " — " + esc(m.observacao) : ""}</div>
    </div>`).join("");

  openModalRaw(`
    <div class="modal wide">
      <div class="modal-head">
        <div><h3>${esc(d.titulo)}</h3><div class="psub" style="margin:4px 0 0">${badgeStatus(d.status)} ${badgePrio(d.prioridade)} · ${esc(d.tipo_demanda)}</div></div>
        <button class="x" id="mClose">&times;</button>
      </div>
      <div class="modal-body">
        <div class="grid-2">
          <dl class="kv">
            <dt>Núcleo</dt><dd>${esc(d.nucleo_nome || "—")}</dd>
            <dt>Responsável</dt><dd>${esc(d.responsavel_nome || "—")}</dd>
            <dt>Valor da causa</dt><dd>${money(d.valor_causa)}</dd>
            <dt>Prazo interno</dt><dd>${slaCell(d)}</dd>
            <dt>Prazo legal</dt><dd>${dataBR(d.prazo_legal)}</dd>
            <dt>Processo</dt><dd>${esc(d.numero_processo || "—")}</dd>
            <dt>Tribunal / Fase</dt><dd>${esc(d.tribunal || "—")} · ${esc(d.fase_processual || "—")}</dd>
            <dt>Aberta há</dt><dd>${d.dias_aberto} dias</dd>
          </dl>
          <div>
            <div style="font-weight:600;margin-bottom:6px">Descrição</div>
            <div class="muted" style="line-height:1.6">${esc(d.descricao || "Sem descrição.")}</div>
            <div style="font-weight:600;margin:18px 0 8px">Mover status</div>
            <div class="statusflow">${acoesStatus || '<span class="muted">Sem ações disponíveis para seu perfil.</span>'}</div>
          </div>
        </div>

        <div class="section-gap">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div style="font-weight:600">Equipe alocada</div>
            ${can("gestor") ? `<button class="btn gold sm" id="btnAlocar">+ Alocar profissional</button>` : ""}
          </div>
          <div class="table-wrap"><table><tbody>${alocs}</tbody></table></div>
        </div>

        <div class="section-gap">
          <div style="font-weight:600;margin-bottom:10px">Histórico (audit trail)</div>
          <div class="timeline">${timeline}</div>
        </div>
      </div>
      <div class="modal-foot">
        ${podeEditar ? `<button class="btn ghost" id="btnEditar">Editar</button>` : ""}
        <button class="btn" id="mFechar">Fechar</button>
      </div>
    </div>`);

  $("#mClose").onclick = $("#mFechar").onclick = closeModal;
  if (podeEditar) $("#btnEditar").onclick = () => { closeModal(); formDemanda(d); };
  root.querySelectorAll("[data-novo]").forEach(b => b.onclick = async () => {
    const obs = prompt("Observação (opcional) para a mudança de status:") || null;
    try { await api("POST", `/demandas/${d.id}/status`, { status: b.dataset.novo, observacao: obs }); toast("Status atualizado", "ok"); closeModal(); abrirDemanda(d.id); pageRefreshIfNeeded(); }
    catch (e) { toast(e.message, "err"); }
  });
  root.querySelectorAll("[data-rem]").forEach(b => b.onclick = async () => {
    if (!confirm("Remover esta alocação?")) return;
    try { await api("DELETE", `/demandas/${d.id}/alocacoes/${b.dataset.rem}`); toast("Alocação removida", "ok"); closeModal(); abrirDemanda(d.id); }
    catch (e) { toast(e.message, "err"); }
  });
  if (can("gestor")) { const ba = $("#btnAlocar"); if (ba) ba.onclick = () => formAlocacao(d); }
}

function formAlocacao(d) {
  const ativos = state.usuarios.filter(u => u.ativo && u.perfil_acesso !== "master");
  const opts = ativos.map(u => `<option value="${u.id}">${esc(u.nome)} — ${u.perfil_acesso} (${u.carga_atual}/${u.carga_maxima})</option>`).join("");
  openModal("Alocar profissional", `
    <label class="field"><span>Profissional *</span><select id="a_prof">${opts}</select></label>
    <div class="form-row">
      <label class="field"><span>Papel</span><select id="a_papel">${state.meta.papeis.map(p => `<option>${p}</option>`).join("")}</select></label>
      <label class="field"><span>Horas estimadas</span><input type="number" id="a_horas" placeholder="0"></label>
    </div>
    <label class="field" style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="a_resp" style="width:auto"> <span style="margin:0">Responsável principal</span></label>
  `, async () => {
    await api("POST", `/demandas/${d.id}/alocacoes`, {
      profissional_id: $("#a_prof").value, papel: $("#a_papel").value,
      responsavel_principal: $("#a_resp").checked,
      horas_estimadas: $("#a_horas").value ? parseInt($("#a_horas").value) : null,
    });
    toast("Profissional alocado", "ok"); closeModal(); abrirDemanda(d.id);
  });
}

function pageRefreshIfNeeded() { /* hook para atualizações futuras */ }

/* ============================== NÚCLEOS ============================= */
async function pageNucleos() {
  loading("Núcleos");
  let nucleos;
  try { nucleos = await api("GET", "/nucleos"); state.nucleos = nucleos; } catch (e) { return toast(e.message, "err"); }
  const novo = can("socio") ? `<button class="btn" id="btnNovoN">+ Novo núcleo</button>` : "";
  const rows = nucleos.map(n => `
    <tr>
      <td><b>${esc(n.nome)}</b></td>
      <td><span class="badge b-execucao">${esc(n.sigla)}</span></td>
      <td>${esc(n.gestor_nome || "<span class='muted'>—</span>")}</td>
      <td>${n.total_profissionais}</td>
      <td>${n.total_demandas}</td>
      <td>${n.ativo ? '<span class="sla-ok">Ativo</span>' : '<span class="muted">Inativo</span>'}</td>
      <td>${can("socio") ? `<button class="btn ghost sm" data-edit="${n.id}">Editar</button>` : ""}</td>
    </tr>`).join("");
  shell("nucleos", "Núcleos Jurídicos", "", `
    <div class="toolbar"><div class="grow"></div>${novo}</div>
    <div class="table-wrap"><table>
      <thead><tr><th>Núcleo</th><th>Sigla</th><th>Gestor</th><th>Profissionais</th><th>Demandas</th><th>Status</th><th></th></tr></thead>
      <tbody>${rows || `<tr><td colspan="7"><div class="empty">Nenhum núcleo.</div></td></tr>`}</tbody>
    </table></div>`);
  if (novo) $("#btnNovoN").onclick = () => formNucleo();
  root.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => formNucleo(nucleos.find(n => n.id === b.dataset.edit)));
}

function formNucleo(n) {
  const gestores = state.usuarios.filter(u => u.ativo && NIVEL[u.perfil_acesso] >= NIVEL.gestor && u.perfil_acesso !== "master");
  const opts = `<option value="">— sem gestor —</option>` + gestores.map(u => `<option value="${u.id}" ${n && n.gestor_id === u.id ? "selected" : ""}>${esc(u.nome)}</option>`).join("");
  openModal(n ? "Editar núcleo" : "Novo núcleo", `
    <div class="form-row">
      <label class="field"><span>Nome *</span><input id="n_nome" value="${n ? esc(n.nome) : ""}" placeholder="Ex.: Trabalhista"></label>
      <label class="field"><span>Sigla *</span><input id="n_sigla" value="${n ? esc(n.sigla) : ""}" placeholder="Ex.: TRAB" maxlength="10"></label>
    </div>
    <label class="field"><span>Gestor responsável</span><select id="n_gestor">${opts}</select></label>
    <label class="field" style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="n_ativo" style="width:auto" ${!n || n.ativo ? "checked" : ""}> <span style="margin:0">Núcleo ativo</span></label>
  `, async () => {
    const body = { nome: $("#n_nome").value.trim(), sigla: $("#n_sigla").value.trim(), gestor_id: $("#n_gestor").value || null, ativo: $("#n_ativo").checked };
    if (!body.nome || !body.sigla) throw new Error("Nome e sigla são obrigatórios");
    if (n) await api("PUT", "/nucleos/" + n.id, body); else await api("POST", "/nucleos", body);
    toast("Núcleo salvo", "ok"); closeModal(); await carregarBase(); pageNucleos();
  });
}

/* ============================== ACESSOS / USUÁRIOS ============================= */
async function pageAcessos() {
  loading("Acessos & Usuários");
  let usuarios;
  try { usuarios = await api("GET", "/usuarios"); state.usuarios = usuarios; } catch (e) { return toast(e.message, "err"); }
  const rows = usuarios.map(u => {
    const pct = u.carga_maxima ? Math.min(100, Math.round(u.carga_atual / u.carga_maxima * 100)) : 0;
    const cor = pct >= 100 ? "#dc2626" : pct >= 80 ? "#e0a526" : "#16a34a";
    const carga = u.perfil_acesso === "master" ? "—" : `<span class="carga-track"><span class="carga-fill" style="width:${pct}%;background:${cor}"></span></span> <span class="muted">${u.carga_atual}/${u.carga_maxima}</span>`;
    return `<tr>
      <td><b>${esc(u.nome)}</b><br><span class="muted" style="font-size:12px">${esc(u.email)}</span></td>
      <td>${badgePerfil(u.perfil_acesso)}</td>
      <td>${esc(u.nucleo_nome || "—")}</td>
      <td class="muted">${esc(u.cargo || "—")}</td>
      <td>${carga}</td>
      <td>${u.ativo ? '<span class="sla-ok">Ativo</span>' : '<span class="muted">Inativo</span>'}</td>
      <td style="white-space:nowrap">
        <button class="btn ghost sm" data-edit="${u.id}">Editar</button>
        ${u.perfil_acesso !== "master" && u.id !== state.user.id && u.ativo ? `<button class="btn danger sm" data-del="${u.id}">Desativar</button>` : ""}
      </td>
    </tr>`;
  }).join("");
  shell("acessos", "Acessos & Usuários", "", `
    <div class="page-head"><div><p>O login master configura todos os acessos, perfis e cadastros do sistema.</p></div>
      <button class="btn" id="btnNovoU">+ Novo usuário / login</button></div>
    <div class="table-wrap"><table>
      <thead><tr><th>Usuário</th><th>Perfil</th><th>Núcleo</th><th>Cargo</th><th>Carga</th><th>Status</th><th></th></tr></thead>
      <tbody>${rows}</tbody></table></div>`);
  $("#btnNovoU").onclick = () => formUsuario();
  root.querySelectorAll("[data-edit]").forEach(b => b.onclick = () => formUsuario(usuarios.find(u => u.id === b.dataset.edit)));
  root.querySelectorAll("[data-del]").forEach(b => b.onclick = async () => {
    if (!confirm("Desativar este usuário? Ele perderá o acesso ao sistema.")) return;
    try { await api("DELETE", "/usuarios/" + b.dataset.del); toast("Usuário desativado", "ok"); await carregarBase(); pageAcessos(); }
    catch (e) { toast(e.message, "err"); }
  });
}

function formUsuario(u) {
  const perfis = state.meta.perfis;
  const perfilOpt = perfis.map(p => `<option value="${p}" ${u && u.perfil_acesso === p ? "selected" : ""}>${p}</option>`).join("");
  const nucOpt = `<option value="">— nenhum —</option>` + state.nucleos.map(n => `<option value="${n.id}" ${u && u.nucleo_id === n.id ? "selected" : ""}>${esc(n.nome)}</option>`).join("");
  const gestores = state.usuarios.filter(x => x.ativo && NIVEL[x.perfil_acesso] >= NIVEL.gestor && (!u || x.id !== u.id));
  const gestorOpt = `<option value="">— nenhum —</option>` + gestores.map(g => `<option value="${g.id}" ${u && u.gestor_id === g.id ? "selected" : ""}>${esc(g.nome)}</option>`).join("");
  openModal(u ? "Editar usuário" : "Novo usuário / login", `
    <div class="form-row">
      <label class="field"><span>Nome completo *</span><input id="u_nome" value="${u ? esc(u.nome) : ""}"></label>
      <label class="field"><span>E-mail (login) *</span><input type="email" id="u_email" value="${u ? esc(u.email) : ""}"></label>
    </div>
    <div class="form-row">
      <label class="field"><span>Perfil de acesso *</span><select id="u_perfil">${perfilOpt}</select></label>
      <label class="field"><span>${u ? "Nova senha (deixe vazio p/ manter)" : "Senha *"}</span><input type="password" id="u_senha" placeholder="${u ? "••••••" : "defina uma senha"}"></label>
    </div>
    <div class="form-row-3">
      <label class="field"><span>Cargo</span><input id="u_cargo" value="${u ? esc(u.cargo || "") : ""}" placeholder="Ex.: Advogado"></label>
      <label class="field"><span>OAB</span><input id="u_oab" value="${u ? esc(u.oab || "") : ""}"></label>
      <label class="field"><span>Celular</span><input id="u_cel" value="${u ? esc(u.celular || "") : ""}"></label>
    </div>
    <div class="form-row-3">
      <label class="field"><span>Núcleo</span><select id="u_nucleo">${nucOpt}</select></label>
      <label class="field"><span>Gestor</span><select id="u_gestor">${gestorOpt}</select></label>
      <label class="field"><span>Carga máxima</span><input type="number" id="u_carga" value="${u ? u.carga_maxima : 30}"></label>
    </div>
    <label class="field" style="display:flex;align-items:center;gap:8px"><input type="checkbox" id="u_ativo" style="width:auto" ${!u || u.ativo ? "checked" : ""}> <span style="margin:0">Acesso ativo</span></label>
  `, async () => {
    const body = {
      nome: $("#u_nome").value.trim(), email: $("#u_email").value.trim(), perfil_acesso: $("#u_perfil").value,
      senha: $("#u_senha").value || null, cargo: $("#u_cargo").value.trim() || null, oab: $("#u_oab").value.trim() || null,
      celular: $("#u_cel").value.trim() || null, nucleo_id: $("#u_nucleo").value || null, gestor_id: $("#u_gestor").value || null,
      carga_maxima: parseInt($("#u_carga").value) || 30, ativo: $("#u_ativo").checked,
    };
    if (!body.nome || !body.email) throw new Error("Nome e e-mail são obrigatórios");
    if (!u && !body.senha) throw new Error("Defina uma senha para o novo usuário");
    if (u) await api("PUT", "/usuarios/" + u.id, body); else await api("POST", "/usuarios", body);
    toast("Usuário salvo", "ok"); closeModal(); await carregarBase(); pageAcessos();
  });
}

/* ============================== CONTA ============================= */
function pageConta() {
  const u = state.user;
  shell("conta", "Minha conta", "", `
    <div class="grid-2">
      <div class="panel">
        <h3>Dados do perfil</h3><div class="psub">Informações da sua conta</div>
        <dl class="kv">
          <dt>Nome</dt><dd>${esc(u.nome)}</dd>
          <dt>E-mail</dt><dd>${esc(u.email)}</dd>
          <dt>Perfil</dt><dd>${badgePerfil(u.perfil_acesso)}</dd>
          <dt>Núcleo</dt><dd>${esc(u.nucleo_nome || "—")}</dd>
          <dt>Cargo</dt><dd>${esc(u.cargo || "—")}</dd>
          <dt>OAB</dt><dd>${esc(u.oab || "—")}</dd>
        </dl>
      </div>
      <div class="panel">
        <h3>Alterar senha</h3><div class="psub">Defina uma nova senha de acesso</div>
        <label class="field"><span>Senha atual</span><input type="password" id="c_atual"></label>
        <label class="field"><span>Nova senha</span><input type="password" id="c_nova"></label>
        <label class="field"><span>Confirmar nova senha</span><input type="password" id="c_conf"></label>
        <button class="btn" id="btnSenha">Salvar nova senha</button>
      </div>
    </div>
    ${can("master") ? `
    <div class="panel section-gap" style="border-color:#f3c9c9">
      <h3 style="color:var(--red)">Zona de administração</h3>
      <div class="psub">Ações exclusivas do master. Use com cuidado.</div>
      <div style="display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap">
        <div style="max-width:520px">
          <b>Limpar dados de demonstração</b>
          <div class="muted" style="line-height:1.6;margin-top:4px">Remove todas as demandas, núcleos e usuários fictícios, mantendo apenas o seu login master. Use isto para começar a cadastrar os dados reais do escritório do zero. <b>Esta ação não pode ser desfeita.</b></div>
        </div>
        <button class="btn danger" id="btnLimpar">Limpar dados de demonstração</button>
      </div>
    </div>` : ""}`);
  if (can("master")) $("#btnLimpar").onclick = async () => {
    const txt = prompt('Isso vai APAGAR todas as demandas, núcleos e usuários (exceto você).\nPara confirmar, digite:  LIMPAR');
    if (txt !== "LIMPAR") return toast("Cancelado — nada foi apagado.");
    try {
      const r = await api("POST", "/admin/limpar-demo");
      await carregarBase();
      toast(r.mensagem || "Dados removidos", "ok");
      location.hash = "#/demandas"; router();
    } catch (e) { toast(e.message, "err"); }
  };
  $("#btnSenha").onclick = async () => {
    const nova = $("#c_nova").value, conf = $("#c_conf").value;
    if (nova.length < 4) return toast("A nova senha deve ter ao menos 4 caracteres", "err");
    if (nova !== conf) return toast("As senhas não conferem", "err");
    try { await api("POST", "/auth/senha", { senha_atual: $("#c_atual").value || null, nova_senha: nova }); toast("Senha alterada com sucesso", "ok"); $("#c_atual").value = $("#c_nova").value = $("#c_conf").value = ""; }
    catch (e) { toast(e.message, "err"); }
  };
}

/* ============================== MODAL ============================= */
let overlayEl = null;
function openModalRaw(innerHTML) {
  closeModal();
  overlayEl = document.createElement("div");
  overlayEl.className = "overlay";
  overlayEl.innerHTML = innerHTML;
  overlayEl.addEventListener("mousedown", (e) => { if (e.target === overlayEl) closeModal(); });
  document.body.appendChild(overlayEl);
}
function openModal(titulo, bodyHTML, onSave) {
  openModalRaw(`
    <div class="modal">
      <div class="modal-head"><h3>${esc(titulo)}</h3><button class="x" id="mX">&times;</button></div>
      <div class="modal-body">${bodyHTML}</div>
      <div class="modal-foot"><button class="btn ghost" id="mCancel">Cancelar</button><button class="btn" id="mSave">Salvar</button></div>
    </div>`);
  $("#mX").onclick = $("#mCancel").onclick = closeModal;
  $("#mSave").onclick = async () => {
    const b = $("#mSave"); b.disabled = true; b.textContent = "Salvando...";
    try { await onSave(); }
    catch (e) { toast(e.message, "err"); b.disabled = false; b.textContent = "Salvar"; }
  };
}
function closeModal() { if (overlayEl) { overlayEl.remove(); overlayEl = null; } }

/* ------------------------------- start -------------------------------- */
boot();
