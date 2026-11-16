// Right-hand panel. Tabs:
//   priority  Septris's pick for this review, why, and (optionally) the outcome
//   patient   everything about one bed: status, vitals, labs, history, chart
//   queue     the full priority list of all 20 beds
//   results   how well it works on every test patient
//   model     what is inside Septris and how it was tested
//   faq       plain questions and answers
import { beds, slotAt, ordinal, VERDICT, whatHappened } from "../data.js";
import { FIELDS } from "../manual.js";
import { drawChart, chartLegend } from "./chart.js";

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const TIER = [
  { name: "Low", cls: "low", note: "below the top 20% of ICU hours" },
  { name: "Medium", cls: "med", note: "in the top 20% of ICU hours" },
  { name: "High", cls: "high", note: "in the top 5% of ICU hours" },
];

function statusOf(r) {
  if (r.picked) return { text: "Check now", cls: "pick" };
  if (r.snoozed) return { text: `Checked ${r.hours_since_check} h ago`, cls: "snooze" };
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
      <p class="small muted">Septris never sees outcomes. These are past patients, so their records show what happened after each chart check. That is how we judge its picks.</p>
      ${n ? `<div class="eyebrow" style="margin-top:10px">Track record so far (day 1 to ${s.day})</div>
      <p class="small">${n} patient${n === 1 ? " has" : "s have"} developed sepsis. Caught early (chart checked 6–12 hours before sepsis was recorded):</p>
      <div class="score"><span>Septris</span>${sbar(s.sb_caught_so_far, "var(--accent)")}<span class="num">${s.sb_caught_so_far}</span>
      <span>Random</span>${sbar(s.random_caught_so_far, "var(--grey)")}<span class="num">${s.random_caught_so_far}</span></div>` : ""}
    </div>`;
}

export function priorityHTML(data, st) {
  const s = slotAt(data, st.slot);
  const b = beds(data, st.slot);
  const nCand = b[0]?.candidates ?? 0;
  const pick = b.find((x) => x.picked);
  const reasons = (s.reasons || "").split(" | ").filter(Boolean);
  const next = b.filter((x) => !x.snoozed && !x.picked).sort((x, y) => x.rank - y.rank).slice(0, 3);
  let hero = "";
  if (st.showKey && (s.review_class === "early6" || s.review_class === "early")) {
    const lead = Math.round(s.lead_hours);
    hero = `<div class="hero-hit"><div class="big">✓ Sepsis flagged <b>${lead}</b> hour${lead === 1 ? "" : "s"} early</div>
      <div class="small">The patient's record shows sepsis ${lead} hour${lead === 1 ? "" : "s"} after Septris pointed the nurse to this bed.</div>
      ${s.review_class === "early6" ? `<span class="star">★ Caught early: checked 6–12 hours before sepsis was recorded</span>` : ""}</div>`;
  }
  let nextNote = "";
  const ns = st.slot + 1 < data.slots.length ? slotAt(data, st.slot + 1) : null;
  if (ns) {
    const nb = b.find((x) => x.bed === ns.bed && x.p === ns.p);
    const was = !nb ? "a patient who hasn't arrived yet" : nb.snoozed ? "paused for now (checked in the last 12 hours)" : `${ordinal(nb.rank)} in line right now`;
    nextNote = ` For example, the next chart check (${ns.clock}) goes to Bed ${ns.bed}, which is ${was}.`;
  }
  const n = s.sepsis_so_far;
  const sbar = (v2, c) => `<div class="bar"><i style="width:${n ? (100 * v2) / n : 0}%;background:${c}"></i></div>`;
  return `
    <div class="eyebrow">Chart check ${s.check} of ${data.meta.k} this shift · ${s.clock}</div>
    <h2 class="pick-title">Highest priority: Bed ${s.bed}</h2>
    <p>Septris recommends checking <b>Bed ${s.bed}</b>'s chart now. It has the highest risk score (<b>${pick ? pick.percentile : "–"} of 100</b>) of the ${nCand} beds not checked in the last 12 hours.</p>
    ${hero}
    <h3>Why this bed</h3>
    ${reasons.length ? `<ul>${reasons.map((r) => `<li>${esc(cap(r))}</li>`).join("")}</ul>` : "<p>Several small changes together, none big on its own.</p>"}
    <h3>Also high right now</h3>
    <div class="qmini">${next.map((x) => `<button class="qrow" data-bed="${x.bed}"><b>Bed ${x.bed}</b><span class="pill ${TIER[x.tier].cls}">${TIER[x.tier].name}</span><span class="num">${x.percentile}</span></button>`).join("")}</div>
    <p class="small muted">This is <b>not</b> the order of the next chart checks. Septris re-ranks every bed from fresh data before each check, so the next check goes to whoever is highest <i>then</i>.${nextNote}</p>
    <p class="small muted">Septris uses only data recorded up to ${s.clock}. It points to a chart and does not diagnose. The nurse reads the chart and decides.</p>
    ${st.showKey ? outcomeBlock(s, n, sbar) : `<p class="small muted">What the record shows happened next is revealed a little later in the tour.</p>`}`;
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
  const s = slotAt(data, st.slot);
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
    ["Average blood pressure (MAP)", latest(p.map, h), "mmHg", trend(p.map, h)],
    ["Breathing rate", latest(p.resp, h), "/min", trend(p.resp, h)],
    ["Temperature", latest(p.temp, h), "°C", trend(p.temp, h)],
    ["Lactate (a blood test that rises when the body is under strain)", latestSparse(p.lactate, h), "mmol/L", ""],
    ["White blood cells (they fight infection)", latestSparse(p.wbc, h), "×10³/µL", ""],
  ];
  if (p.manual) {
    const rd = [...p.record.readings].reverse().find((x) => x.hour <= s.unit_hour) || p.record.readings[0];
    for (const f of FIELDS.filter((x) => !x.series && !["Lactate", "WBC"].includes(x.key))) {
      const v = rd.values[f.key];
      rows.push([f.label, v === "" || v == null ? null : { v, ago: s.unit_hour - rd.hour }, f.unit, ""]);
    }
  }
  const past = p.reviews.filter((x) => x < h);
  const hist = past.length
    ? `Septris sent the nurse to check this chart ${past.length} time${past.length > 1 ? "s" : ""} before (${past.map((x) => `${h - x} h ago`).join(", ")}).`
    : "Not checked yet during this stay.";
  let why = "";
  if (r.picked) {
    const reasons = (s.reasons || "").split(" | ").filter(Boolean);
    if (reasons.length) why = `<h3>Why Septris flagged it</h3><ul>${reasons.map((x) => `<li>${esc(cap(x))}</li>`).join("")}</ul>`;
  }
  let outcome = "";
  if (st.showKey) {
    let text;
    if (p.manual) text = "You entered this patient, so there is no hospital record to check the prediction against.";
    else if (p.group === "uncertain_onset") text = "This patient already had sepsis on arrival, so they aren't counted in the results.";
    else if (p.onset == null) text = "This patient did not develop sepsis during their ICU stay.";
    else {
      const d = Math.round(p.onset - h);
      if (r.picked && d >= 6 && d <= 12) text = `Caught early: sepsis was recorded ${d} hours after this chart check.`;
      else if (d > 0) text = `The record shows sepsis ${d} hours after this point.`;
      else text = `The record shows sepsis began ${-d} hours before this point.`;
    }
    outcome = `<div class="key"><div class="eyebrow">Outcome · from the patient's record</div><p class="small">${text}</p></div>`;
  }
  // big green banner whenever this patient was (or is now being) caught 6-12 h early
  let caughtBanner = "";
  if (!p.manual && p.onset != null && p.group !== "uncertain_onset") {
    const hitNow = r.picked && (s.review_class === "early6" || s.review_class === "early");
    const prior = [...p.reviews.filter((x) => x <= h)].reverse().find((x) => p.onset - x >= 6 && p.onset - x <= 12);
    const at = hitNow ? h : prior;
    if (at != null) {
      const lead = Math.round(p.onset - at);
      caughtBanner = `<div class="hero-hit"><div class="big">✓ Sepsis caught <b>${lead}</b> hours early</div>
        <div class="small">${at === h ? "Septris sent the nurse to this bed now" : `Septris sent the nurse here ${h - at} h ago`}; the record shows sepsis ${lead} hours after that check.</div></div>`;
    }
  }
  return `
    ${caughtBanner}
    <div class="eyebrow">Day ${s.day} · ${s.clock}</div>
    <h2>Bed ${bed} <span class="pill ${status.cls}">${status.text}</span></h2>
    ${p.manual ? `<div class="entered"><b>${esc(p.name)}</b> · entered by hand · stay ends in ${p.record.admit + p.record.stay - s.unit_hour} h
      <div class="row"><button class="btn" data-manual="update">Update readings</button><button class="btn ghost" data-manual="discharge">Discharge now</button></div></div>` : ""}
    <div class="facts">
      <div><span>Patient</span><b>${p.sex === "M" ? "Man" : "Woman"}, ${Math.round(p.age)}</b></div>
      <div><span>Time in ICU</span><b>${r.hours_in_icu} h</b></div>
      <div><span>Risk score</span><b>${r.percentile} of 100</b></div>
      <div><span>Risk level</span><b>${tier.name}</b></div>
      <div><span>6-hour trend</span><b>${riskTrend || "–"}</b></div>
      <div><span>Highest so far</span><b>${peak} of 100</b></div>
    </div>
    <p class="small muted">${tier.name} risk: ${tier.note}. ${r.snoozed ? "Skipped for now because it was checked in the last 12 hours." : r.picked ? "Septris recommends checking this bed now." : `${r.rank - 1} bed${r.rank - 1 === 1 ? " is" : "s are"} ahead of it in line.`}</p>
    ${why}
    <h3>Latest readings</h3>
    <table class="res vit"><tbody>${rows.map(([name, x, unit, tr]) => `<tr><td>${name}</td><td class="n">${x ? `${x.v} ${unit}` : "not measured"}</td><td class="muted small">${x ? when(x) : ""}${tr ? ` · ${tr}` : ""}</td></tr>`).join("")}</tbody></table>
    <h3>Check history</h3>
    <p class="small">${hist}</p>
    ${p.manual ? `<p class="small muted">Risk scores for entered patients come from a small model that runs in your browser. It sees only the readings typed in. The full Septris reads each patient's hour-by-hour history.</p>` : ""}
    ${outcome}
    <h3>Stay so far</h3>
    <canvas class="chart" id="bedChart" aria-label="Chart of Bed ${bed}'s risk score, heart rate and blood pressure"></canvas>
    ${chartLegend(st.showKey)}`;
}

export function drawBedChart(data, st) {
  const c = document.getElementById("bedChart");
  if (!c) return;
  const s = slotAt(data, st.slot);
  const bed = st.selectedBed ?? s.bed;
  const r = beds(data, st.slot).find((x) => x.bed === bed);
  if (r) drawChart(c, data.patients[r.p], r.record_hour, st.showKey);
}

export function queueHTML(data, st) {
  const s = slotAt(data, st.slot);
  const b = [...beds(data, st.slot)].sort((x, y) => (x.snoozed - y.snoozed) || (x.rank - y.rank));
  return `
    <div class="eyebrow">Day ${s.day} · ${s.clock}</div>
    <h2>Priority queue</h2>
    <p>All ${b.length} occupied beds, most urgent first. The nurse checks the top one now. The rest wait for the next chart check.</p>
    <div class="queue">${b.map((x) => {
      const stt = statusOf(x);
      return `<button class="qrow ${x.picked ? "top" : ""}" data-bed="${x.bed}">
        <span class="rank">${x.snoozed ? "–" : x.rank}</span><b>Bed ${x.bed}</b>
        <div class="bar"><i class="${stt.cls}" style="width:${x.percentile}%"></i></div>
        <span class="num">${x.percentile}</span><span class="pill ${stt.cls}">${x.picked ? "Check now" : x.snoozed ? "Checked" : TIER[x.tier].name}</span></button>`;
    }).join("")}</div>
    <p class="small"><b>This order only holds for this moment.</b> Before the next chart check, every bed is scored again with its newest data. So the bed that is 2nd now is often not the next one checked.</p>
    <p class="small muted">The risk score runs from 0 to 100. It shows how worrying this hour looks compared with past ICU hours (100 = most worrying). Beds checked in the last 12 hours go to the bottom, so the nurse isn't sent back to the same patient.</p>`;
}

// Results, How it works and Questions now live in pages.js (editorial layout).
