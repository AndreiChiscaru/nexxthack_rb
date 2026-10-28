const form = document.getElementById("form");
const input = document.getElementById("file");
const drop = document.getElementById("drop");
const fileLabel = document.getElementById("fileLabel");
const submit = document.getElementById("submit");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let currency = "RON";
const money = (v) => (v === null || v === undefined || isNaN(v)) ? "—"
  : Number(v).toLocaleString("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " " + esc(currency);

function setFile(file) {
  if (!file) return;
  const dt = new DataTransfer();
  dt.items.add(file);
  input.files = dt.files;
  fileLabel.textContent = file.name;
  submit.disabled = false;
}

input.addEventListener("change", () => setFile(input.files[0]));
["dragenter", "dragover"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((e) => drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (ev) => setFile(ev.dataTransfer.files[0]));

function showStatus(html, isError = false) {
  statusEl.className = isError ? "error" : "";
  statusEl.innerHTML = html;
}

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  if (!input.files[0]) return;
  submit.disabled = true;
  resultEl.classList.add("hidden");
  showStatus('<span class="spinner"></span>Se extrage textul și se analizează documentul… (poate dura 30-90 secunde)');

  const body = new FormData();
  body.append("file", input.files[0]);
  try {
    const res = await fetch("/api/analyze", { method: "POST", body });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Eroare ${res.status}`);
    statusEl.classList.add("hidden");
    render(data);
  } catch (err) {
    showStatus(esc(err.message), true);
  } finally {
    submit.disabled = false;
  }
});

const list = (items) => items && items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : '<p class="meta">—</p>';

function kpi(label, value, cls = "") {
  return `<div class="card"><div class="kpi-label">${label}</div><div class="kpi-value ${cls}">${value}</div></div>`;
}

function table(headers, rows) {
  if (!rows || !rows.length) return '<p class="meta">—</p>';
  return `<table><thead><tr>${headers.map(([h, c]) => `<th class="${c || ""}">${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.join("")}</tbody></table>`;
}

function render(data) {
  const a = data.analysis || {};
  currency = a.moneda || "RON";
  const risk = (a.nivel_risc || "mediu").toLowerCase();
  const p = a.perioada || {};
  const net = a.flux_net ?? ((a.total_intrari || 0) - (a.total_iesiri || 0));

  resultEl.innerHTML = `
    <div class="card score">
      <div class="score-circle risk-${esc(risk)}">${esc(a.scor_stabilitate_financiara ?? "?")}</div>
      <div>
        <h2>${esc(a.titular || "Titular necunoscut")} — risc ${esc(risk)}</h2>
        <div class="meta">${esc(a.banca || "")} ${a.iban ? "· " + esc(a.iban) : ""} · perioada ${esc(p.de_la || "?")} – ${esc(p.pana_la || "?")}</div>
        <p>${esc(a.rezumat || "")}</p>
      </div>
    </div>

    <div class="grid">
      ${kpi("Sold inițial", money(a.sold_initial))}
      ${kpi("Sold final", money(a.sold_final))}
      ${kpi("Total intrări", money(a.total_intrari), "pos")}
      ${kpi("Total ieșiri", money(a.total_iesiri), "neg")}
      ${kpi("Flux net", money(net), net >= 0 ? "pos" : "neg")}
      ${kpi("Venit lunar estimat", money(a.venit_lunar_estimat))}
      ${kpi("Cheltuieli lunare reale", money(a.cheltuieli_lunare_estimate))}
      ${kpi("Economii identificate", money(a.economii_identificate))}
      ${kpi("Grad îndatorare", a.grad_indatorare_procent != null ? esc(a.grad_indatorare_procent) + "%" : "—")}
    </div>

    <div class="two">
      <div class="card"><h2>Semnale de risc</h2>${list(a.semnale_de_risc)}</div>
      <div class="card"><h2>Puncte forte</h2>${list(a.puncte_forte)}</div>
    </div>
    <br />

    <div class="card"><h2>Venituri</h2>
      ${table([["Sursă"], ["Tip"], ["Frecvență"], ["Total", "num"]],
        (a.venituri || []).map((v) => `<tr><td>${esc(v.sursa)}</td><td>${esc(v.tip)}</td><td>${esc(v.frecventa)}</td><td class="num">${money(v.suma_totala)}</td></tr>`))}
    </div>

    <div class="card"><h2>Cheltuieli pe categorii</h2>
      ${table([["Categorie"], [""], ["Sumă", "num"], ["%", "num"]],
        (a.cheltuieli_pe_categorii || []).map((c) => `<tr><td>${esc(c.categorie)}</td>
          <td style="width:35%"><div class="bar" style="width:${Math.min(100, Number(c.procent) || 0)}%"></div></td>
          <td class="num">${money(c.suma)}</td><td class="num">${esc(c.procent)}%</td></tr>`))}
    </div>

    <div class="card"><h2>Obligații recurente</h2>
      ${table([["Descriere"], ["Tip"], ["Sumă lunară", "num"]],
        (a.obligatii_recurente || []).map((o) => `<tr><td>${esc(o.descriere)}</td><td>${esc(o.tip)}</td><td class="num">${money(o.suma_lunara)}</td></tr>`))}
    </div>

    <div class="card"><h2>Cele mai mari tranzacții</h2>
      ${table([["Data"], ["Descriere"], ["Sumă", "num"]],
        (a.cele_mai_mari_tranzactii || []).map((t) => `<tr><td>${esc(t.data)}</td><td>${esc(t.descriere)}</td>
          <td class="num ${t.directie === "intrare" ? "pos" : "neg"}">${t.directie === "intrare" ? "+" : "−"}${money(t.suma)}</td></tr>`))}
    </div>

    <div class="card"><h2>Recomandări</h2>${list(a.recomandari)}</div>

    ${data.game_profile ? `<div class="card play">
      <div><h2>Raiff Quest</h2><p class="meta">Pornește jocul cu situația financiară din acest extras.</p></div>
      <button type="button" id="playBtn">Joacă cu acest profil</button>
    </div>` : ""}

    <div class="card">
      <p class="meta">Fișier: ${esc(data.filename)} · metodă extragere: ${esc(data.extraction_method)} · ${esc(data.chars_extracted)} caractere</p>
      ${a.observatii_calitate_date ? `<p class="meta">Calitate date: ${esc(a.observatii_calitate_date)}</p>` : ""}
      <details><summary>Text extras (previzualizare)</summary><pre>${esc(data.text_preview)}</pre></details>
      <details><summary>JSON complet</summary><pre>${esc(JSON.stringify(a, null, 2))}</pre></details>
    </div>`;
  resultEl.classList.remove("hidden");
  const playBtn = document.getElementById("playBtn");
  if (playBtn) {
    playBtn.addEventListener("click", () => {
      localStorage.setItem("raiffQuestProfile", JSON.stringify({ analysis: a, game_profile: data.game_profile }));
      window.location.href = "/joc/";
    });
  }
}
