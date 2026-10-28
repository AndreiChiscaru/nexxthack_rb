const $ = (id) => document.getElementById(id);
const SESSION_KEY = "raiffDemoSession";
let session = null;
let busy = false;

const TOOL_LABELS = {
  update_profile: "a salvat în profil",
  finish_onboarding: "a finalizat profilul",
  get_financial_state: "a citit situația din joc",
  simulate_event_options: "a simulat opțiunile",
  simulate_plan: "a simulat un plan",
  search_products: "a căutat produse",
  compare_tax_regimes: "a comparat regimurile fiscale",
  calculate_taxes: "a calculat taxele",
  startup_checklist: "a generat checklist-ul",
  apply_business_to_game: "a pornit afacerea în joc",
  fiscal_calendar: "a generat calendarul fiscal",
  search_legislation: "a căutat în legislație",
  review_dossier: "a verificat dosarul ONRC",
  classify_expense: "a verificat deductibilitatea",
  remember: "a notat în fișa comună",
};
const TOOL_RUNNING = {
  update_profile: "salvez în profil…",
  finish_onboarding: "finalizez profilul…",
  get_financial_state: "citesc situația din joc…",
  simulate_event_options: "rulez simularea opțiunilor…",
  simulate_plan: "rulez simularea planului…",
  search_products: "caut în catalogul de produse…",
  compare_tax_regimes: "compar PFA, micro și profit…",
  calculate_taxes: "calculez taxele…",
  startup_checklist: "pregătesc pașii de înființare…",
  apply_business_to_game: "pornesc afacerea în joc…",
  fiscal_calendar: "generez calendarul fiscal…",
  search_legislation: "caut în Codul fiscal și în legislație…",
  review_dossier: "verific dosarul ONRC…",
  classify_expense: "verific deductibilitatea…",
  remember: "notez în fișa comună…",
};
const AGENT_NAMES = { onboarding: "Onboarding", statement: "Analiză extras", consultant: "Consultant", business: "Contabil" };

// ------------------------------------------------------------ helpers

const lei = (x) => `${x < -0.5 ? "-" : ""}${Math.abs(Math.round(x || 0)).toLocaleString("ro-RO")} lei`;

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function markdown(text) {
  const inline = (s) => escapeHtml(s)
    .replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
  const out = [];
  let list = null;
  for (const raw of String(text || "").split("\n")) {
    const line = raw.trimEnd();
    const item = line.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)$/);
    if (item) {
      if (!list) { list = []; out.push(list); }
      list.push(`<li>${inline(item[1])}</li>`);
      continue;
    }
    list = null;
    const head = line.match(/^#{1,4}\s+(.*)$/);
    if (head) out.push(`<h4>${inline(head[1])}</h4>`);
    else if (line.trim() && !/^-{3,}$/.test(line.trim()) && !/^\|?[-:| ]+\|?$/.test(line.trim())) out.push(`<p>${inline(line)}</p>`);
  }
  return out.map((b) => (Array.isArray(b) ? `<ul>${b.join("")}</ul>` : b)).join("");
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.add("hidden"), 6000);
}

async function api(path, options = {}) {
  const res = await fetch(`/api/demo${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Eroare ${res.status}`);
  return body;
}

const post = (path, data) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data || {}) });

// ------------------------------------------------------------ chat rendering + streaming

const CHAT_EL = { onboarding: "onb-chat", consultant: "cons-chat", business: "biz-chat" };
const messagesOf = (kind) => (kind === "onboarding" ? session.onboarding.chat : session[kind]);

function toolChip(t) {
  return `<span class="tool" title="${escapeHtml(JSON.stringify(t.args))}">🔧 <b>${escapeHtml(TOOL_LABELS[t.name] || t.name)}</b> · ${escapeHtml(t.summary)}</span>`;
}

function liveHtml(live) {
  const tools = live.tools.map((t) => t.done ? toolChip(t)
    : `<span class="tool running"><i class="spin"></i> ${escapeHtml(TOOL_RUNNING[t.name] || t.name + "…")}</span>`).join("");
  const status = live.status && !live.text ? `<div class="typing">${escapeHtml(live.status)}</div>` : "";
  const body = live.text ? markdown(live.text) + '<span class="caret"></span>' : (live.tools.length ? "" : '<div class="typing">scrie…</div>');
  return `<div class="msg assistant live">${status}${body}${tools ? `<div class="tools">${tools}</div>` : ""}</div>`;
}

function renderChat(el, messages, live) {
  el.innerHTML = messages.map((m) => {
    const tools = (m.tool_calls || []).map(toolChip).join("");
    const body = m.role === "user" ? `<p>${escapeHtml(m.text)}</p>` : markdown(m.text);
    return `<div class="msg ${m.role}">${body}${tools ? `<div class="tools">${tools}</div>` : ""}</div>`;
  }).join("") + (live ? liveHtml(live) : "");
  el.scrollTop = el.scrollHeight;
}

async function streamTurn(kind, path, options) {
  if (busy) return;
  busy = true;
  const el = $(CHAT_EL[kind]);
  const live = { text: "", tools: [], status: "" };
  let frame = null;
  const paint = () => {
    if (frame) return;
    frame = requestAnimationFrame(() => { frame = null; renderChat(el, messagesOf(kind), live); });
  };
  paint();
  try {
    const res = await fetch(`/api/demo${path}`, options);
    if (!res.ok || !res.body) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Eroare ${res.status}`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let cut;
      while ((cut = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, cut).trim();
        buffer = buffer.slice(cut + 2);
        if (!chunk.startsWith("data:")) continue;
        const ev = JSON.parse(chunk.slice(5));
        if (ev.type === "text") live.text += ev.delta;
        else if (ev.type === "status") live.status = ev.text;
        else if (ev.type === "tool_start") live.tools.push({ name: ev.name, done: false });
        else if (ev.type === "tool_end") {
          const t = live.tools.find((x) => x.name === ev.name && !x.done) || {};
          Object.assign(t, { name: ev.name, args: ev.args, summary: ev.summary, done: true });
          if (!live.tools.includes(t)) live.tools.push(t);
        } else if (ev.type === "view") session = ev.view;
        else if (ev.type === "error") throw new Error(ev.message);
        paint();
      }
    }
  } catch (err) {
    toast(err.message);
    try { session = await api(`/session/${session.session_id}`); } catch { /* keep local state */ }
  } finally {
    busy = false;
    if (frame) cancelAnimationFrame(frame);
    render();
  }
}

const postJsonOptions = (data) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

function uploadOptions(file, extra = {}) {
  const form = new FormData();
  form.append("file", file);
  for (const [k, v] of Object.entries(extra)) form.append(k, v);
  return { method: "POST", body: form };
}

function chatForm(formId, inputId, kind, path) {
  $(formId).addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $(inputId).value.trim();
    if (!text || busy) return;
    $(inputId).value = "";
    messagesOf(kind).push({ role: "user", text });
    streamTurn(kind, `/${path}/${session.session_id}/message`, postJsonOptions({ text }));
  });
}

function renderMemory() {
  const notes = session.memory || [];
  const html = notes.length
    ? notes.slice().reverse().map((n) => `<li><small>${escapeHtml(AGENT_NAMES[n.agent] || n.agent)} · ${escapeHtml(n.topic)}${n.month != null ? ` · luna ${n.month}` : ""}</small><br>${escapeHtml(n.text)}</li>`).join("")
    : '<li class="desc">Încă nimic. Agenții notează aici ce află despre tine, ca să nu te întrebe de două ori.</li>';
  document.querySelectorAll(".memory-list").forEach((el) => { el.innerHTML = html; });
  document.querySelectorAll(".memory-count").forEach((el) => { el.textContent = notes.length; });
}

// ------------------------------------------------------------ onboarding view

function fieldValue(f) {
  const v = f.value;
  if (v === null || v === undefined) return null;
  if (f.format === "money") return lei(v);
  if (f.format === "months") return `${v} luni`;
  if (f.format === "bool") return v ? "da" : "nu";
  if (f.format === "debts") return v.length ? v.map((d) => `${d.name}: ${lei(d.monthly_payment)}/lună`).join("<br>") : "niciunul";
  return escapeHtml(v);
}

function renderOnboarding() {
  renderChat($("onb-chat"), session.onboarding.chat);
  const { fields, missing } = session.profile;
  const required = fields.filter((f) => f.required);
  const done = required.length - missing.length;
  $("profile-progress").firstElementChild.style.width = `${(100 * done) / required.length}%`;
  $("profile-missing").textContent = missing.length
    ? `${done}/${required.length} câmpuri obligatorii completate. Lipsesc: ${missing.join(", ")}.`
    : "Profil complet ✔";
  $("profile-fields").innerHTML = fields
    .filter((f) => f.required || f.value !== null)
    .map((f) => {
      const value = fieldValue(f);
      const src = f.source ? `<span class="src ${f.source === "extras" ? "extras" : ""}">${f.source === "extras" ? "din extras" : "din chat"}</span>` : "";
      return `<dt>${escapeHtml(f.label)}${f.required ? "" : " ·"}</dt><dd class="${value === null ? "empty" : ""}">${value ?? "—"}${src}</dd>`;
    }).join("");
  const st = session.statement;
  $("statement-card").classList.toggle("hidden", !st);
  if (st) {
    const cats = (st.categories || []).map((c) => `<li>${escapeHtml(c.label)} <b>${lei(c.monthly)}</b></li>`).join("");
    const months = st.months ? ` · medii pe ${st.months} luni` : "";
    $("statement-card").innerHTML = `<b>📄 ${escapeHtml(st.filename)}</b> · scor ${st.score}/100 · risc ${escapeHtml(st.risk)}${months}<br>${escapeHtml(st.summary || "")}`
      + (cats ? `<ul>${cats}</ul>` : "");
  }
  $("start-game").disabled = missing.length > 0;
  $("start-game").textContent = session.onboarding.scenario ? `Începe: ${session.onboarding.scenario.title} ▶` : "Începe jocul ▶";
}

// ------------------------------------------------------------ game view

function renderHud(g) {
  const b = g.balance;
  const stats = [
    [`Luna ${g.month}`, g.calendar, ""],
    ["Cont curent", lei(b.cash), b.cash < 0 ? "neg" : ""],
    ["Economii", lei(b.savings), "pos"],
    ["Investiții", lei(b.investments), ""],
    ["Datorii", lei(b.debt), b.debt > 0 ? "neg" : ""],
    ...(b.taxes_due > 0.5 ? [["Taxe de plată", lei(b.taxes_due), "neg"]] : []),
    ["Patrimoniu", lei(b.net_worth), b.net_worth < 0 ? "neg" : "pos"],
    ["Surplus/lună", lei(g.monthly.surplus), g.monthly.surplus < 0 ? "neg" : "pos"],
  ];
  $("hud").innerHTML = stats.map(([k, v, c]) => `<div class="stat ${c}">${k}<b>${v}</b></div>`).join("");
}

function bankActions() {
  return `<div class="actions">
    <select id="bank-action">
      <option value="auto_savings">Transfer automat lunar → economii</option>
      <option value="auto_investments">Investiție automată lunară</option>
      <option value="to_savings">Mută acum în economii</option>
      <option value="prepay">Rambursează anticipat (cel mai scump credit)</option>
    </select>
    <input id="bank-amount" type="number" min="0" step="50" placeholder="Sumă (lei)">
    <button class="small" id="bank-go">Aplică</button>
  </div>`;
}

function renderInstitutions(g) {
  const ev = g.pending_event;
  $("institutions").innerHTML = g.institutions.map((inst) => {
    const items = inst.items.map((i) => `<li><span>${escapeHtml(i.label)}</span><span class="${i.amount >= 0 ? "pos" : "neg"}">${i.amount >= 0 ? "+" : ""}${lei(i.amount)}</span></li>`).join("");
    let extra = "";
    if (inst.id === "business") {
      const obligations = g.fiscal.obligations.map((o) => `<li title="${escapeHtml(o.when)}"><span>🗓 ${escapeHtml(o.declaration)} · ${escapeHtml(o.next_due || "-")}</span><span class="neg">${lei(o.accrued)}</span></li>`).join("");
      const arrears = g.fiscal.arrears.map((a) => `<li><span>⚠ Restanță: ${escapeHtml(a.label)}</span><span class="neg">${lei(a.amount)}</span></li>`).join("");
      extra = (obligations || arrears ? `<div class="desc">Taxe acumulate și următorul termen:</div><ul>${obligations}${arrears}</ul>` : "")
        + `<div class="actions"><button class="small primary" data-open-business>Deschide contabilul AI</button></div>`;
    }
    if (inst.id === "bank") {
      const auto = g.auto.savings || g.auto.investments ? `<li><span>Automat: economii / investiții</span><span>${lei(g.auto.savings)} / ${lei(g.auto.investments)}</span></li>` : "";
      extra = `<ul>${auto}<li><span>Fond de urgență</span><span>${g.emergency_months} luni</span></li></ul>${bankActions()}`;
    }
    if (inst.id === "hospital") extra = `<ul><li><span>Asigurare privată</span><span>${g.insured ? "da" : "nu"}</span></li></ul>`;
    return `<div class="inst ${ev && ev.institution === inst.id ? "active" : ""}">
      <div class="head"><span class="icon">${inst.icon}</span><div><div class="name">${inst.name}${ev && ev.institution === inst.id ? " ❗" : ""}</div><div class="desc">${inst.desc}</div></div></div>
      <div class="flows"><span class="pos">+${lei(inst.in)}</span><span class="neg">-${lei(inst.out)}</span></div>
      <ul>${items || '<li><span class="desc">nimic momentan</span></li>'}</ul>${extra}
    </div>`;
  }).join("");
}

function renderEvent(g) {
  const ev = g.pending_event;
  $("event").classList.toggle("hidden", !ev);
  $("next-month").disabled = !!ev;
  $("consultant-fab").classList.toggle("pulse", !!ev);
  if (!ev) return;
  const inst = g.institutions.find((i) => i.id === ev.institution);
  const tag = ev.kind === "suggestion" ? "sugestie de reducere" : "eveniment";
  $("event").innerHTML = `<div class="tag">${inst.icon} ${inst.name} · ${tag}</div><h3>${escapeHtml(ev.title)}</h3><div>${escapeHtml(ev.text)}</div>
    <div class="options">${ev.options.map((o) => `<button class="option" data-option="${o.id}"><b>${escapeHtml(o.label)}</b><small>${escapeHtml(o.desc)}</small></button>`).join("")}</div>
    <button class="ghost small ask" data-ask-event>💬 Ce m-ar sfătui consultantul?</button>`;
}

function renderGame() {
  const g = session.game;
  renderHud(g);
  const goal = g.goal;
  $("goal-title").textContent = `🎯 ${goal.description} — ${lei(goal.target_amount)}`;
  $("goal-progress").firstElementChild.style.width = `${Math.min(goal.progress * 100, 100)}%`;
  $("goal-meta").textContent = `${Math.round(goal.progress * 100)}% strâns · ${goal.months_left} luni rămase din ${goal.horizon_months} · `
    + (goal.on_track ? "pe drumul cel bun ✔" : "în urmă față de plan ⚠") + ` · venit ${lei(g.monthly.income)} / cheltuieli ${lei(g.monthly.expenses)}`;
  const averages = g.averages || [];
  $("averages").innerHTML = averages.length
    ? `<span class="hint">Medii din extras${g.statement_months ? `, ${g.statement_months} luni` : ""}:</span>`
      + averages.map((c) => `<span class="avg">${escapeHtml(c.label)} <b>${lei(c.monthly)}</b></span>`).join("")
    : "";
  renderEvent(g);
  renderInstitutions(g);
  $("log").innerHTML = g.log.map((l) => {
    const inst = g.institutions.find((i) => i.id === l.institution);
    const delta = l.delta == null ? "" : ` <b class="${l.delta >= 0 ? "pos" : "neg"}">${l.delta >= 0 ? "+" : ""}${lei(l.delta)}</b>`;
    return `<li><small>Luna ${l.month} · ${inst ? inst.icon : ""}</small><br>${escapeHtml(l.text)}${delta}</li>`;
  }).join("");
  renderChat($("cons-chat"), session.consultant);
  renderChat($("biz-chat"), session.business);
}

// ------------------------------------------------------------ top-level render

function render() {
  const inGame = !!session.game;
  $("view-onboarding").classList.toggle("hidden", inGame);
  $("view-game").classList.toggle("hidden", !inGame);
  $("hud").classList.toggle("hidden", !inGame);
  $("consultant-fab").classList.toggle("hidden", !inGame);
  if (inGame) renderGame();
  else renderOnboarding();
  renderMemory();
  suggestions();
}

function suggestions() {
  const cons = session.game?.pending_event
    ? ["Ce opțiune aleg la evenimentul ăsta?", "Cum mă afectează pe termen lung?"]
    : ["Sunt pe drumul cel bun spre scop?", "Cât ar trebui să economisesc lunar?", "Ce produs bancar mi se potrivește?"];
  const biz = ["PFA sau SRL pentru 5.000 lei/lună venit?", "Care sunt termenele mele fiscale?",
    "Verifică-mi dosarul pentru ONRC", "Ce cheltuieli pot deduce?"];
  const fill = (id, list, input) => {
    $(id).innerHTML = list.map((s) => `<button type="button">${escapeHtml(s)}</button>`).join("");
    [...$(id).children].forEach((b) => b.addEventListener("click", () => { $(input).value = b.textContent; $(input).focus(); }));
  };
  fill("cons-suggestions", cons, "cons-input");
  fill("biz-suggestions", biz, "biz-input");
}

// ------------------------------------------------------------ events

async function gameAction(fn) {
  if (busy) return;
  busy = true;
  try { session = await fn(); } catch (err) { toast(err.message); } finally { busy = false; render(); }
}

function bindEvents() {
  chatForm("onb-form", "onb-input", "onboarding", "onboarding");
  chatForm("cons-form", "cons-input", "consultant", "consultant");
  chatForm("biz-form", "biz-input", "business", "business");

  $("onb-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    session.onboarding.chat.push({ role: "user", text: `📎 ${file.name}` });
    streamTurn("onboarding", `/onboarding/${session.session_id}/statement`, uploadOptions(file));
  });

  $("use-sample").addEventListener("click", async () => {
    if (busy || !session) return;
    try {
      const res = await fetch("/static/demo/extras_student.pdf");
      if (!res.ok) throw new Error("Extrasul de student nu e pe server.");
      const blob = await res.blob();
      const file = new File([blob], "extras_student_matei.pdf", { type: "application/pdf" });
      session.onboarding.chat.push({ role: "user", text: "📎 extras_student_matei.pdf" });
      render();
      streamTurn("onboarding", `/onboarding/${session.session_id}/statement`, uploadOptions(file));
    } catch (err) {
      toast(err.message);
    }
  });

  $("biz-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const note = $("biz-input").value.trim();
    $("biz-input").value = "";
    session.business.push({ role: "user", text: `📎 ${file.name}${note ? ` — ${note}` : ""}` });
    streamTurn("business", `/business/${session.session_id}/document`, uploadOptions(file, { note }));
  });

  $("start-game").addEventListener("click", () => gameAction(() => post(`/game/${session.session_id}/start`)));
  $("next-month").addEventListener("click", () => gameAction(() => post(`/game/${session.session_id}/advance`)));

  document.addEventListener("click", (e) => {
    const option = e.target.closest("[data-option]");
    if (option) gameAction(() => post(`/game/${session.session_id}/choose`, { option_id: option.dataset.option }));
    if (e.target.closest("[data-open-business]")) { $("business").classList.remove("hidden"); $("biz-input").focus(); }
    if (e.target.closest("[data-ask-event]")) {
      $("consultant").classList.remove("hidden");
      $("cons-input").value = "Ce opțiune aleg la evenimentul ăsta și de ce?";
      $("cons-form").requestSubmit();
    }
    const close = e.target.closest("[data-close]");
    if (close) $(close.dataset.close).classList.add("hidden");
    if (e.target.closest("[data-open-memory]")) { renderMemory(); $("memory").classList.toggle("hidden"); }
    if (e.target.id === "memory") $("memory").classList.add("hidden");
    if (e.target.id === "business") $("business").classList.add("hidden");
    if (e.target.id === "bank-go") {
      const action = $("bank-action").value;
      const amount = Number($("bank-amount").value || 0);
      gameAction(() => post(`/game/${session.session_id}/bank`, { action, amount }));
    }
  });

  $("consultant-fab").addEventListener("click", () => {
    $("consultant").classList.toggle("hidden");
    renderChat($("cons-chat"), session.consultant);
    $("cons-input").focus();
  });

  $("reset").addEventListener("click", async () => {
    if (!confirm("Începi o sesiune nouă? Profilul și jocul curent se pierd.")) return;
    localStorage.removeItem(SESSION_KEY);
    await init();
  });
}

async function init() {
  const saved = localStorage.getItem(SESSION_KEY);
  try {
    session = saved ? await api(`/session/${saved}`) : null;
  } catch {
    session = null;
  }
  if (!session) {
    session = await post("/session");
    localStorage.setItem(SESSION_KEY, session.session_id);
  }
  render();
  $("onb-input").focus();
}

bindEvents();
init().catch((err) => toast(err.message));
