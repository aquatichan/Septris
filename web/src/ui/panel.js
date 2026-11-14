// Right-hand panel. Tabs:
//   priority  Septris's pick for this review, why, and (optionally) the outcome
//   patient   everything about one bed: status, vitals, labs, history, chart
//   queue     the full priority list of all 20 beds
//   results   how well it works on every test patient
//   model     what is inside Septris and how it was tested
//   faq       plain questions and answers
import { beds, ordinal, VERDICT, whatHappened } from "../data.js";
import { drawChart, chartLegend } from "./chart.js";

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const TIER = [
  { name: "Low", cls: "low", note: "below the top 20% of ICU hours" },
  { name: "Medium", cls: "med", note: "in the top 20% of ICU hours" },
  { name: "High", cls: "high", note: "in the top 5% of ICU hours" },
];

function statusOf(r) {
  if (r.picked) return { text: "Review now", cls: "pick" };
  if (r.snoozed) return { text: `Reviewed ${r.hours_since_check} h ago`, cls: "snooze" };
  return { text: `${ordinal(r.rank)} in line`, cls: TIER[r.tier].cls };
}

function outcomeBlock(s, n, sbar) {
  const v = VERDICT[s.review_class];
  let rnd = "";
  if (s.random_bed != null) {
    rnd = `<p class="small">For comparison, a randomly chosen bed (Bed ${s.random_bed}) would have been: <b>${VERDICT[s.random_class].head.toLowerCase()}</b>.</p>`;
  }
  return `
    <div class="key">
      <div class="eyebrow">Outcome · from the patient's record</div>
      <div class="verdict ${v.tone}"><b>${v.icon} ${v.head}.</b><br>${esc(whatHappened(s.review_class, s.lead_hours, s.bed))}</div>
      ${rnd}
      <p class="small muted">Septris never sees outcomes. These are past patients, so the record shows what happened after each review, and that is how we check its picks.</p>
      ${n ? `<div class="eyebrow" style="margin-top:10px">Track record so far (day 1 to ${s.day})</div>
      <p class="small">${n} patient${n === 1 ? " has" : "s have"} developed sepsis. Flagged 6–12 hours ahead:</p>
      <div class="score"><span>Septris</span>${sbar(s.sb_caught_so_far, "var(--accent)")}<span class="num">${s.sb_caught_so_far}</span>
      <span>Random</span>${sbar(s.random_caught_so_far, "var(--grey)")}<span class="num">${s.random_caught_so_far}</span></div>` : ""}
    </div>`;
}

export function priorityHTML(data, st) {
  const s = data.slots[st.slot];
  const b = beds(data, st.slot);
  const nCand = b[0]?.candidates ?? 0;
  const pick = b.find((x) => x.picked);
  const reasons = (s.reasons || "").split(" | ").filter(Boolean);
  let driver = "";
  if (data.meta.kind === "max" && s.pct_gru != null) {
    const both = Math.min(s.pct_gru, s.pct_lgbm) >= 90;
    driver = `<div class="twobars">
      <span>Deep-learning model (GRU)</span><div class="bar"><i style="width:${s.pct_gru}%;background:var(--accent)"></i></div><span class="num">${Math.round(s.pct_gru)}</span>
      <span>Decision-tree model (LightGBM)</span><div class="bar"><i style="width:${s.pct_lgbm}%;background:var(--accent)"></i></div><span class="num">${Math.round(s.pct_lgbm)}</span>
    </div>
    <p class="small muted">${both ? "Both models rate this bed as high risk." : `The ${s.driver === "GRU" ? "deep-learning" : "decision-tree"} model is the more worried one here.`} Septris uses the higher of the two scores.</p>`;
  }
  const next = b.filter((x) => !x.snoozed && !x.picked).sort((x, y) => x.rank - y.rank).slice(0, 3);
  const n = s.sepsis_so_far;
  const sbar = (v2, c) => `<div class="bar"><i style="width:${n ? (100 * v2) / n : 0}%;background:${c}"></i></div>`;
  return `
    <div class="eyebrow">Review ${s.check} of ${data.meta.k} this shift · ${s.clock}</div>
    <h2 class="pick-title">Highest priority: Bed ${s.bed}</h2>
    <p>Septris recommends reviewing <b>Bed ${s.bed}</b>'s chart now. It has the highest sepsis risk (<b>${pick ? pick.percentile : "–"} of 100</b>) of the ${nCand} beds that haven't been reviewed in the last 12 hours.</p>
    <h3>Why this bed</h3>
    ${reasons.length ? `<ul>${reasons.map((r) => `<li>${esc(cap(r))}</li>`).join("")}</ul>` : "<p>Several small changes together, none big on its own.</p>"}
    ${driver}
    <h3>Next in line</h3>
    <div class="qmini">${next.map((x) => `<button class="qrow" data-bed="${x.bed}"><b>Bed ${x.bed}</b><span class="pill ${TIER[x.tier].cls}">${TIER[x.tier].name}</span><span class="num">${x.percentile}</span></button>`).join("")}</div>
    <p class="small muted">Based only on data recorded up to ${s.clock}. A warning pattern, not a diagnosis: the nurse reads the chart and decides.</p>
    ${st.showKey ? outcomeBlock(s, n, sbar) : `<p class="small muted">Turn on “Show outcomes” to see what the record shows happened after this review.</p>`}`;
}

function latest(series, hour) {
  for (let h = hour; h >= 0; h--) if (series[h] != null) return { v: series[h], ago: hour - h };
  return null;
}
function latestSparse(pairs, hour) {
  let out = null;
  for (const [h, v] of pairs) if (h <= hour) out = { v, ago: hour - h };
  return out;
}
function trend(series, hour) {
  const now = latest(series, hour), then = latest(series, Math.max(0, hour - 6));
  if (!now || !then || hour < 6) return "";
  const d = now.v - then.v;
  if (Math.abs(d) < 0.05 * Math.max(1, Math.abs(then.v))) return "steady";
  return `${d > 0 ? "▲ up" : "▼ down"} ${Math.abs(Math.round(d * 10) / 10)} in 6 h`;
}
const when = (x) => (x.ago === 0 ? "this hour" : `${x.ago} h ago`);

export function patientHTML(data, st) {
  const s = data.slots[st.slot];
  const bed = st.selectedBed ?? s.bed;
  const all = beds(data, st.slot);
  const r = all.find((x) => x.bed === bed);
  if (!r) return `<h2>Bed ${bed}</h2><p>This bed is empty right now.</p>`;
  const p = data.patients[r.p];
  const h = r.record_hour;
  const status = statusOf(r);
  const tier = TIER[r.tier];
  const riskTrend = trend(p.risk, h);
  const peak = Math.max(...p.risk.slice(0, h + 1).filter((v) => v != null));
  const rows = [
    ["Heart rate", latest(p.hr, h), "bpm", trend(p.hr, h)],
    ["Blood pressure (MAP)", latest(p.map, h), "mmHg", trend(p.map, h)],
    ["Breathing rate", latest(p.resp, h), "/min", trend(p.resp, h)],
    ["Temperature", latest(p.temp, h), "°C", trend(p.temp, h)],
    ["Lactate", latestSparse(p.lactate, h), "mmol/L", ""],
    ["White blood cells", latestSparse(p.wbc, h), "×10³/µL", ""],
  ];
  const past = p.reviews.filter((x) => x < h);
  const hist = past.length
    ? `Septris had this chart reviewed ${past.length} time${past.length > 1 ? "s" : ""} before (${past.map((x) => `${h - x} h ago`).join(", ")}).`
    : "Not reviewed yet during this stay.";
  let why = "";
  if (r.picked) {
    const reasons = (s.reasons || "").split(" | ").filter(Boolean);
    if (reasons.length) why = `<h3>Why Septris flagged it</h3><ul>${reasons.map((x) => `<li>${esc(cap(x))}</li>`).join("")}</ul>`;
  }
  let outcome = "";
  if (st.showKey) {
    let text;
    if (p.group === "uncertain_onset") text = "This patient already had sepsis on arrival, so they aren't counted in the results.";
    else if (p.onset == null) text = "This patient did not develop sepsis during their ICU stay.";
    else {
      const d = Math.round(p.onset - h);
      if (r.picked && d >= 6 && d <= 12) text = `Sepsis was accurately predicted: it was recorded ${d} hours after this review.`;
      else if (d > 0) text = `The record shows sepsis ${d} hours after this point.`;
      else text = `The record shows sepsis began ${-d} hours before this point.`;
    }
    outcome = `<div class="key"><div class="eyebrow">Outcome · from the patient's record</div><p class="small">${text}</p></div>`;
  }
  return `
    <div class="eyebrow">Day ${s.day} · ${s.clock}</div>
    <h2>Bed ${bed} <span class="pill ${status.cls}">${status.text}</span></h2>
    <div class="facts">
      <div><span>Patient</span><b>${p.sex === "M" ? "Man" : "Woman"}, ${Math.round(p.age)}</b></div>
      <div><span>Time in ICU</span><b>${r.hours_in_icu} h</b></div>
      <div><span>Sepsis risk</span><b>${r.percentile} of 100</b></div>
      <div><span>Risk level</span><b>${tier.name}</b></div>
      <div><span>6-hour trend</span><b>${riskTrend || "–"}</b></div>
      <div><span>Highest so far</span><b>${peak} of 100</b></div>
    </div>
    <p class="small muted">${tier.name} risk: ${tier.note}. ${r.snoozed ? "Skipped for now because it was reviewed in the last 12 hours." : r.picked ? "This is the bed Septris recommends reviewing now." : `${r.rank - 1} bed${r.rank - 1 === 1 ? " is" : "s are"} ahead of it in line.`}</p>
    ${why}
    <h3>Latest readings</h3>
    <table class="res vit"><tbody>${rows.map(([name, x, unit, tr]) => `<tr><td>${name}</td><td class="n">${x ? `${x.v} ${unit}` : "not measured"}</td><td class="muted small">${x ? when(x) : ""}${tr ? ` · ${tr}` : ""}</td></tr>`).join("")}</tbody></table>
    <h3>Review history</h3>
    <p class="small">${hist}</p>
    ${outcome}
    <h3>Stay so far</h3>
    <canvas class="chart" id="bedChart" aria-label="Chart of Bed ${bed}'s risk, heart rate and blood pressure"></canvas>
    ${chartLegend(st.showKey)}`;
}

export function drawBedChart(data, st) {
  const c = document.getElementById("bedChart");
  if (!c) return;
  const s = data.slots[st.slot];
  const bed = st.selectedBed ?? s.bed;
  const r = beds(data, st.slot).find((x) => x.bed === bed);
  if (r) drawChart(c, data.patients[r.p], r.record_hour, st.showKey);
}

export function queueHTML(data, st) {
  const s = data.slots[st.slot];
  const b = [...beds(data, st.slot)].sort((x, y) => (x.snoozed - y.snoozed) || (x.rank - y.rank));
  return `
    <div class="eyebrow">Day ${s.day} · ${s.clock}</div>
    <h2>Priority queue</h2>
    <p>All ${b.length} occupied beds, most urgent first. The nurse reviews the top one now; the rest wait for the next review time.</p>
    <div class="queue">${b.map((x) => {
      const stt = statusOf(x);
      return `<button class="qrow ${x.picked ? "top" : ""}" data-bed="${x.bed}">
        <span class="rank">${x.snoozed ? "–" : x.rank}</span><b>Bed ${x.bed}</b>
        <div class="bar"><i class="${stt.cls}" style="width:${x.percentile}%"></i></div>
        <span class="num">${x.percentile}</span><span class="pill ${stt.cls}">${x.picked ? "Review now" : x.snoozed ? "Reviewed" : TIER[x.tier].name}</span></button>`;
    }).join("")}</div>
    <p class="small muted">Risk is 0–100: how this hour compares with past ICU hours (100 = most worrying). Beds reviewed in the last 12 hours go to the bottom so the nurse isn't sent back to the same patient.</p>`;
}

export function resultsHTML(data, k) {
  const R = data.results[String(k)];
  const lines = [
    ["Septris", "septris", "var(--accent)"],
    ["Septris at a hospital it never saw", "septris_new_hospital", "#2f7fb8"],
    ["Decision-tree model alone", "lightgbm", "#7d8fa0"],
    ["Deep-learning model alone", "gru", "#7d8fa0"],
    ["SIRS checklist (used in hospitals)", "sirs", "var(--warn)"],
    ["Random picking", "random", "var(--grey)"],
  ];
  const block = (T, name) => `
    <h3>${name}</h3>
    <div class="rbars">${lines.map(([n, key, c]) => {
      const v = R[T][key];
      return v ? `<span>${n}</span><div class="bar"><i style="width:${v.caught * 2}%;background:${c}"></i></div><span class="num">${v.caught.toFixed(0)}</span>` : "";
    }).join("")}</div>`;
  const a = R.A.septris, rnd = R.A.random, q = data.quality;
  return `
    <h2>How well does it work?</h2>
    <p>Out of every <b>100 patients who developed sepsis</b>, how many had their chart reviewed <b>6–12 hours before</b> sepsis was recorded.</p>
    <div class="seg" role="group" aria-label="Reviews per shift">${[1, 2, 3, 5].map((x) => `<button class="btn ${x === k ? "on" : ""}" data-k="${x}">${x} per shift</button>`).join("")}</div>
    ${block("A", `Hospital A · Boston · ${a.eligible} sepsis patients`)}
    ${block("B", `Hospital B · Atlanta · ${R.B.septris.eligible} sepsis patients`)}
    <p class="small muted">Test patients only; no model was trained on them. Mean of 5 patient-arrival orders. Septris at Hospital A: ${a.caught.toFixed(1)}% (95% range ${a.lo.toFixed(1)}–${a.hi.toFixed(1)}).</p>
    <h3>What these numbers mean</h3>
    <ul>
      <li><b>About ${(a.caught / rnd.caught).toFixed(1)}× random picking</b> at Hospital A with the same nurse time.</li>
      <li><b>Most reviews are still false alarms:</b> about ${a.false_per_shift.toFixed(1)} of ${k} per shift go to a patient who turns out fine (random: ${rnd.false_per_shift.toFixed(1)}). Only about 8% of ICU patients develop sepsis.</li>
      <li><b>It loses some accuracy at a new hospital</b>, but still beats the checklist.</li>
    </ul>
    <h3>Hour-by-hour accuracy</h3>
    <p class="small">How well each model separates hours that are within 12 hours of sepsis from hours that aren't (AUROC: 0.5 is a coin flip, 1.0 is perfect), and the official PhysioNet 2019 Challenge score (higher is better; the 2019 winner scored 0.43 on Hospital A).</p>
    <table class="res"><thead><tr><th>Trained → tested</th><th class="n">Septris</th><th class="n">Tree</th><th class="n">Deep</th></tr></thead><tbody>
    ${[["A>A", "A → A"], ["B>B", "B → B"], ["B>A", "B → A (new)"], ["A>B", "A → B (new)"]].map(([key, lab]) => `<tr><td>${lab}</td>${["septris", "lightgbm", "gru"].map((m) => `<td class="n">${q[key][m].auroc.toFixed(2)} <span class="muted">/ ${q[key][m].utility.toFixed(2)}</span></td>`).join("")}</tr>`).join("")}
    </tbody></table>
    <p class="small muted">Each cell: AUROC / Challenge score.</p>`;
}

export function modelHTML(data) {
  const m = data.meta;
  return `
    <h2>How Septris works</h2>
    <h3>1. The data</h3>
    <p>40,336 real ICU stays from two US hospital systems (Beth Israel Deaconess in Boston and Emory in Atlanta), released for the PhysioNet 2019 sepsis challenge with names and dates removed. Each stay has hourly vital signs and lab results.</p>
    <h3>2. What it looks at</h3>
    <ul>
      <li>Vital signs: heart rate, blood pressure, breathing rate, temperature, oxygen level.</li>
      <li>26 lab results such as lactate, white blood cells and creatinine.</li>
      <li>How each value has changed, and which tests were done recently.</li>
      <li>Age and sex. It does <b>not</b> see how long the patient has been in hospital or which unit they're on.</li>
    </ul>
    <h3>3. Two models, one score</h3>
    <p><b>A decision-tree model (LightGBM)</b> reads summaries of the last few hours. <b>A deep-learning model (GRU, three copies averaged)</b> reads the whole stay hour by hour. Each gives every bed a 0–100 risk, and Septris uses the <b>higher</b> of the two, so a bed moves up if either model is worried. The two models catch largely different patients, which is why using both helps.</p>
    <h3>4. From score to priority</h3>
    <p>At each of the nurse's ${m.k} review times per 12-hour shift, Septris sorts the ${m.beds} beds by risk, skips anyone reviewed in the last 12 hours, and recommends the top one, with the reasons that raised its score.</p>
    <h3>5. How it was tested</h3>
    <ul>
      <li>Patients were split 70 / 15 / 15: train, tune, test. Every number shown is from test patients the models never saw.</li>
      <li>${m.patients.toLocaleString()} Hospital A test patients (${m.eligible_septic} developed sepsis) pass through this ${m.beds}-bed unit over ${Math.round(m.days)} simulated days.</li>
      <li>Random picking and the SIRS checklist face the same beds at the same moments.</li>
      <li>The main settings were written down before any test result was seen; later changes are logged in the project repository.</li>
    </ul>
    <h3>Limits</h3>
    <ul>
      <li>Tested on past records only. It has never been used on real patients.</li>
      <li>It is less accurate at a hospital it wasn't trained on.</li>
      <li>Many of its early flags came after new lab tests were ordered, so it mostly highlights patients the team was already working up. It doesn't show the model is ahead of doctors.</li>
      <li>The unit places patients from different times side by side.</li>
    </ul>
    <p class="small muted">Team: Miheer Parasnis, Aaron Qin, Reyansh Maheshwari · Veritas AI Hackathon 2026, AI + Health. Data: PhysioNet/CinC Challenge 2019 (CC BY 4.0). Prototype; not medical advice.</p>`;
}

export function faqHTML(data) {
  const k = data.meta.k;
  const qa = [
    ["What is sepsis?", "The body's extreme reaction to an infection. It can damage organs within hours, and each hour of delayed treatment raises the risk of death, so spotting it early matters."],
    ["What problem does Septris solve?", `A careful sepsis review of one chart takes real time, and one nurse may cover 20 beds. Septris answers one question: with my next review, whose chart should I open? This page shows ${k} reviews per 12-hour shift; we also tested 1, 2 and 3.`],
    ["What do the colours mean?", "Blue: review this bed now. Red: high risk (top 5% of ICU hours). Yellow: medium risk (top 20%). Green: low risk. Grey: reviewed in the last 12 hours, so skipped for now."],
    ["What does “Risk 92 of 100” mean?", "This patient's current data looks more worrying than about 92% of ICU hours at the training hospital. It's a ranking, not the chance of having sepsis."],
    ["How do you know if a pick was right?", "These are real patients from past records, so each stay is already written down. Septris only gets the data up to each moment. Afterwards we look at the record: if sepsis was recorded 6–12 hours after the review, the pick counts as an accurate early flag. Turn on “Show outcomes” to see this."],
    ["Why are most picks false alarms?", "Only about 8% of these ICU patients ever develop sepsis, and at any moment very few are 6–12 hours away from it. Usually there is no one to catch. What matters is catching more real cases with the same nurse time."],
    ["Does it diagnose sepsis?", "No. It never diagnoses or recommends treatment. It only orders the nurse's review list and explains why."],
    ["Can I control it by voice?", "Yes, when the page is allowed to use the microphone. You can also type: “show bed 6”, “next review”, “next shift”, “queue”, “results”, “show me a miss”, “why?”, “zoom out”, “play”."],
  ];
  return `<h2>Questions</h2>${qa.map(([q, a]) => `<h3>${q}</h3><p>${a}</p>`).join("")}`;
}
