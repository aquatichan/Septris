// Right-hand panel: "This review" (Septris's pick + answer key + score),
// "Bed chart" (any bed's stay so far), "Results" and "About".
import { beds, ordinal, VERDICT, whatHappened } from "../data.js";
import { drawChart, chartLegend } from "./chart.js";

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

export function reviewHTML(data, st) {
  const s = data.slots[st.slot];
  const b = beds(data, st.slot);
  const nCand = b[0]?.candidates ?? 0;
  const reasons = (s.reasons || "").split(" | ").filter(Boolean);
  const v = VERDICT[s.review_class];
  let driver = "";
  if (data.meta.kind === "max" && s.pct_gru != null) {
    const both = Math.min(s.pct_gru, s.pct_lgbm) >= 90;
    driver = `<p class="small muted">${both ? "Both models were worried" : `Raised by ${s.driver === "GRU" ? "the GRU" : "LightGBM"}`}: GRU risk ${Math.round(s.pct_gru)}, LightGBM risk ${Math.round(s.pct_lgbm)}. Septris uses whichever is higher.</p>`;
  }
  let rnd = "";
  if (s.random_bed != null) {
    const rv = VERDICT[s.random_class];
    rnd = `<p class="small">Picking a bed at random instead would have reviewed Bed ${s.random_bed}: <b>${rv.head}</b>.</p>`;
  }
  const n = s.sepsis_so_far;
  const bar = (v2, c) => `<div class="bar"><i style="width:${n ? (100 * v2) / n : 0}%;background:${c}"></i></div>`;
  return `
    <div class="eyebrow">Review ${s.check} of ${data.meta.k} · ${s.clock}</div>
    <h2 class="pick-title">Septris says: review Bed ${s.bed} now</h2>
    <p>Of the ${nCand} beds not reviewed in the last 12 hours, Bed ${s.bed} has the highest risk right now.</p>
    ${driver}
    <h3>What stood out in Bed ${s.bed}'s chart</h3>
    ${reasons.length ? `<ul>${reasons.map((r) => `<li>${esc(cap(r))}</li>`).join("")}</ul>` : "<p>Several small changes together, none big on its own.</p>"}
    <p class="small muted">Septris only uses data recorded up to ${s.clock}. These are warning patterns, not a diagnosis.</p>
    ${st.showKey ? `
    <div class="key">
      <div class="eyebrow">Answer key · what really happened</div>
      <p class="small muted">Septris couldn't see this. These are real past patients, so their records show how the stay turned out.</p>
      <div class="verdict ${v.tone}"><b>${v.icon} ${v.head}.</b><br>${esc(whatHappened(s.review_class, s.lead_hours, s.bed))}</div>
      ${rnd}
      ${n ? `<div class="eyebrow" style="margin-top:10px">Score so far (day 1 to ${s.day})</div>
      <p class="small">${n} patient${n === 1 ? " has" : "s have"} developed sepsis. Reviewed in time:</p>
      <div class="score"><span>Septris</span>${bar(s.sb_caught_so_far, "var(--accent)")}<span class="num">${s.sb_caught_so_far}</span>
      <span>Random</span>${bar(s.random_caught_so_far, "var(--grey)")}<span class="num">${s.random_caught_so_far}</span></div>` : ""}
    </div>` : `<p class="small muted">Turn on “Answer key” to see what really happened.</p>`}`;
}

export function bedHTML(data, st) {
  const s = data.slots[st.slot];
  const bed = st.selectedBed ?? s.bed;
  const r = beds(data, st.slot).find((x) => x.bed === bed);
  if (!r) return `<h2>Bed ${bed}</h2><p>This bed is empty right now.</p>`;
  const p = data.patients[r.p];
  const status = r.picked ? "Septris's pick right now" : r.snoozed ? `Reviewed ${r.hours_since_check} hours ago, so skipped for now` : `${ordinal(r.rank)} in line for review`;
  let key = "";
  if (st.showKey) {
    if (p.group === "uncertain_onset") key = "Already septic on arrival.";
    else if (p.onset == null) key = "This patient never developed sepsis during the stay.";
    else {
      const d = p.onset - r.record_hour;
      key = d > 0 ? `Sepsis was recorded ${Math.round(d)} hours after this moment.` : `Sepsis had been recorded ${Math.round(-d)} hours before this moment.`;
    }
  }
  return `
    <div class="eyebrow">${s.clock} · day ${s.day}</div>
    <h2>Bed ${bed}</h2>
    <p>${p.sex === "M" ? "Man" : "Woman"}, ${Math.round(p.age)}. In the ICU for ${r.hours_in_icu} hours. Risk <b>${r.percentile}</b> of 100. ${status}.</p>
    ${key ? `<div class="key"><div class="eyebrow">Answer key</div><p class="small">${key}</p></div>` : ""}
    <canvas class="chart" id="bedChart" aria-label="Chart of Bed ${bed}'s risk, heart rate and blood pressure"></canvas>
    ${chartLegend}
    <p class="small muted">Risk N of 100 means this hour looks more worrying than N% of ICU hours at the training hospital.</p>`;
}

export function drawBedChart(data, st) {
  const c = document.getElementById("bedChart");
  if (!c) return;
  const s = data.slots[st.slot];
  const bed = st.selectedBed ?? s.bed;
  const r = beds(data, st.slot).find((x) => x.bed === bed);
  if (r) drawChart(c, data.patients[r.p], r.record_hour);
}

export function resultsHTML(data, k) {
  const R = data.results[String(k)];
  const row = (name, key, T) => {
    const v = R[T][key];
    return v ? `<td class="n">${v.caught.toFixed(1)}</td>` : "<td class='n'>–</td>";
  };
  const lines = [
    ["Septris (mix)", "septris"],
    ["Septris at a new hospital", "septris_new_hospital"],
    ["LightGBM alone", "lightgbm"],
    ["GRU alone", "gru"],
    ["SIRS checklist", "sirs"],
    ["Random picking", "random"],
  ];
  const a = R.A.septris, rnd = R.A.random;
  return `
    <h2>How well does it work?</h2>
    <p>Out of every 100 patients who developed sepsis, how many had their chart reviewed <b>6–12 hours before</b> sepsis was recorded. Every test patient at both hospitals; the models never trained on them.</p>
    <div class="seg" role="group" aria-label="Reviews per shift">${[1, 2, 3, 5].map((x) => `<button class="btn ${x === k ? "on" : ""}" data-k="${x}">${x} per shift</button>`).join("")}</div>
    <table class="res"><thead><tr><th>Method</th><th class="n">Hospital A</th><th class="n">Hospital B</th></tr></thead>
    <tbody>${lines.map(([n, key]) => `<tr><td>${n}</td>${row(n, key, "A")}${row(n, key, "B")}</tr>`).join("")}</tbody></table>
    <p class="small muted">Hospital A: Beth Israel Deaconess Medical Center (Boston). Hospital B: Emory University Hospital (Atlanta). PhysioNet 2019 data, de-identified. “New hospital” means the model trained at the other hospital.</p>
    ${a ? `<p class="small">About ${a.false_per_shift.toFixed(1)} of ${k} reviews per shift still go to a patient who turns out fine (random: ${rnd.false_per_shift.toFixed(1)}). Only about 8% of ICU patients develop sepsis, so most reviews can't be catches.</p>` : ""}`;
}

export function aboutHTML(data) {
  return `
    <h2>About Septris</h2>
    <p>One ICU nurse covers 20 beds but only has time for about ${data.meta.k} careful sepsis reviews per 12-hour shift. Septris ranks the beds using only what has been recorded so far and says whose chart to review next.</p>
    <h3>How can we see what happens next?</h3>
    <p>These are real patients from past hospital records, so their whole stay is already written down. Septris only gets data up to each moment; the rest is an answer key we use to grade it.</p>
    <h3>What's inside</h3>
    <p>${data.meta.model_text}</p>
    <h3>Voice and typed commands</h3>
    <ul>
      <li>“next review”, “previous review”, “next shift”, “previous shift”</li>
      <li>“show bed 6”, “zoom out”, “play”, “pause”</li>
      <li>“show me a catch”, “show me a miss”, “show me a false alarm”</li>
      <li>“why?” (reads the reasons aloud), “answer key on/off”, “results”, “start tour”</li>
    </ul>
    <h3>Limits</h3>
    <ul>
      <li>Tested only on past records from two hospital systems; never used on real patients.</li>
      <li>It works less well at a hospital it wasn't trained on.</li>
      <li>The 20-bed unit is a simulation: patients from different times share the unit.</li>
    </ul>
    <p class="small muted">Prototype. Not medical advice. Data: PhysioNet/CinC Challenge 2019 (CC BY 4.0).</p>`;
}
