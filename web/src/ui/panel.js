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

export function resultsHTML(data) {
  const R = data.results["3"]; // primary evaluation: 3 chart reviews per 20-bed ICU per 12-hour shift
  const lines = {
    A: [["Septris calibrated blend", "septris", "var(--accent)"], ["Septris trained at Hospital B", "septris_new_hospital", "#2f7fb8"],
      ["Temporal GRU alone", "gru", "#7d8fa0"], ["LightGBM alone", "lightgbm", "#7d8fa0"],
      ["Hospital warning checklist, SIRS", "sirs", "var(--warn)"], ["Random picking", "random", "var(--grey)"]],
    B: [["Septris calibrated blend", "septris", "var(--accent)"], ["Septris trained at Hospital A", "septris_new_hospital", "#2f7fb8"],
      ["Temporal GRU alone", "gru", "#7d8fa0"], ["LightGBM alone", "lightgbm", "#7d8fa0"],
      ["Hospital warning checklist, SIRS", "sirs", "var(--warn)"], ["Random picking", "random", "var(--grey)"]],
  };
  const block = (T) => `
    <h3>Hospital ${T} · ${R[T].septris.eligible} eligible sepsis cases</h3>
    <div class="rbars rhead"><span class="muted small">Policy</span><span></span><span class="muted small">Caught early</span></div>
    <div class="rbars">${lines[T].map(([n, key, c]) => {
      const v = R[T][key];
      return v ? `<span>${n}</span><div class="bar"><i style="width:${v.caught * 2}%;background:${c}"></i></div><span class="num">${v.caught.toFixed(1)}%</span>` : "";
    }).join("")}</div>`;
  const A = R.A, B = R.B, q = data.quality;
  const f = (x) => x.toFixed(3);
  return `
    <h2>How well does it work?</h2>
    <h3 class="lead-q">Which patients are caught early?</h3>
    <p>Out of every <b>100 patients who developed sepsis</b>, how many were <b>selected for clinician review 6–12 hours before</b> recorded sepsis onset?</p>
    <p class="pill-row"><span class="pill pick">Primary held-out evaluation</span> <span class="small muted">3 review slots per 20-bed ICU per 12-hour shift</span></p>
    ${block("A")}
    ${block("B")}
    <p class="small muted">Only held-out test patients are counted. Septris never trained on these patients. Each result averages five simulated ICU admission orders.</p>
    <p>At Hospital A, Septris caught <b>${A.septris.caught.toFixed(1)}%</b> of eligible cases early (95% CI: ${A.septris.lo.toFixed(1)}–${A.septris.hi.toFixed(1)}). At Hospital B, it caught <b>${B.septris.caught.toFixed(1)}%</b> (95% CI: ${B.septris.lo.toFixed(1)}–${B.septris.hi.toFixed(1)}).</p>
    <h3>What these numbers mean</h3>
    <ul>
      <li>At Hospital A, Septris caught about <b>${(A.septris.caught / A.random.caught).toFixed(1)} times</b> as many cases early as random selection, using the same three chart reviews.</li>
      <li>At Hospital B, Septris caught about <b>${(B.septris.caught / B.random.caught).toFixed(1)} times</b> as many cases early as random selection.</li>
      <li>Most review slots are still false reviews: about ${A.septris.false_per_shift.toFixed(2)} of 3 at Hospital A and ${B.septris.false_per_shift.toFixed(2)} of 3 at Hospital B did not lead to a recorded sepsis onset in the early-review window.</li>
      <li>Septris performs worse when moved to a hospital it did not train on, but still outperforms SIRS and random review in both transfer directions.</li>
      <li>These results show better retrospective allocation of limited review capacity. They do not prove Septris detects sepsis before clinicians or improves patient outcomes.</li>
    </ul>
    <h3>How well it separates risky hours</h3>
    <p class="small">Each cell shows <b>AUROC / official 2019 Challenge utility score</b>. An AUROC of 0.5 is random; 1.0 is perfect. The official utility score rewards timely alerts and penalizes poorly timed alerts.</p>
    <table class="res"><thead><tr><th>Trained at → tested at</th><th class="n">Septris calibrated blend</th><th class="n">LightGBM</th><th class="n">Temporal GRU</th></tr></thead><tbody>
    ${[["A>A", "A → A"], ["B>B", "B → B"], ["B>A", "B → A, new hospital"], ["A>B", "A → B, new hospital"]].map(([key, lab]) => `<tr><td>${lab}</td>${["septris", "lightgbm", "gru"].map((m) => `<td class="n">${f(q[key][m].auroc)} <span class="muted">/ ${f(q[key][m].utility)}</span></td>`).join("")}</tr>`).join("")}
    </tbody></table>
    <p class="small">The blend improves the hourly scores in all four train-test settings. Its fixed-review queue improved early catches in three of four settings; the standalone GRU was better for A → B queue allocation.</p>
    <p class="small muted">The interactive ward shows five review slots per shift as a demonstration. All results on this page use the primary three-slot evaluation.</p>`;
}

export function modelHTML(data) {
  const m = data.meta;
  const liteA = data.lite ? data.lite.auroc.lite_test.toFixed(2) : "0.68";
  return `
    <h2>How Septris works</h2>
    <h3>1. The data</h3>
    <p>40,336 de-identified ICU patient records from two hospital systems in the public 2019 PhysioNet/Computing in Cardiology Sepsis Challenge dataset.</p>
    <p>Each record includes hourly vital signs, laboratory measurements, age, sex, and the Challenge's official sepsis label. The dataset identifies the sources only as Hospital A and Hospital B.</p>
    <h3>2. What it looks at</h3>
    <ul>
      <li><b>Vital signs:</b> heart rate, blood pressure, breathing rate, temperature, oxygen saturation.</li>
      <li><b>Laboratory values:</b> 26 measurements, including lactate, white blood cells, creatinine, platelets, and blood-gas results.</li>
      <li><b>Past-only trends:</b> recent changes, minimums, maximums, and averages.</li>
      <li><b>Measurement history:</b> which tests were recorded and how long ago.</li>
      <li><b>Age and sex.</b></li>
    </ul>
    <p>It does not use ICU length of stay, hospital-admission time, or unit-type fields because they can become shortcuts tied to local workflow rather than patient physiology.</p>
    <h3>3. Two models, one calibrated priority score</h3>
    <p>Septris combines two complementary models.</p>
    <p><b>Part 1: LightGBM.</b> A gradient-boosted decision-tree model that learns nonlinear combinations of current vital signs, lab values, six-hour trends, and measurement history.</p>
    <p><b>Part 2: Masked temporal GRU.</b> A causal two-layer deep-learning model with 64 hidden units. It reads each patient's history hour by hour using normalized values, observation masks, log time since each measurement, age, and sex. It cannot see future hours.</p>
    <p>Both models are calibrated on patient-disjoint validation data. We then selected the blend weight only on a separate validation slice using the real objective: catching patients 6–12 hours early with three review slots.</p>
    <div class="blendbox"><div><b>Hospital A model</b><span>20% LightGBM + 80% GRU</span></div><div><b>Hospital B model</b><span>10% LightGBM + 90% GRU</span></div></div>
    <p>This is Septris's final scoring policy. It is not a simple average and not a “take the highest score” rule.</p>
    <h3>4. From risk score to priority</h3>
    <p>At each of the three review slots per 12-hour shift, Septris ranks the 20 simulated beds by calibrated priority score.</p>
    <p>It skips patients reviewed in the previous 12 hours and recommends the highest-priority remaining patient. The clinician then opens the full chart and decides whether action is appropriate.</p>
    <p>The interactive ward can show five slots for demonstration, but the primary reported evaluation uses three slots, matching the stated review-capacity constraint.</p>
    <h3>5. How it was tested</h3>
    <ul>
      <li>Patients were split by patient, not hourly row: 70% training, 15% validation, and 15% held-out testing.</li>
      <li>The model-selection, calibration, and blend-weight decisions used validation patients only.</li>
      <li>Hospital A testing used 3,051 held-out patient records, including 238 eligible sepsis cases.</li>
      <li>Hospital B testing used held-out patient records containing 134 eligible sepsis cases.</li>
      <li>Random selection, SIRS, LightGBM, GRU, and Septris faced the same beds at the same simulated review times.</li>
      <li>We used 200 patient-level bootstrap resamples to estimate 95% confidence intervals.</li>
      <li>We tested home-hospital performance and both cross-hospital directions: A → A, B → B, A → B, and B → A.</li>
    </ul>
    <h3>6. How a hospital could use it after validation</h3>
    <p>In a real hospital, clinicians would not manually enter values. Vital signs and laboratory results already flow into the electronic health record. After prospective validation and local calibration, Septris could receive those existing records, re-score active ICU beds, and update a clinician-review queue.</p>
    <p>The <b>“Add a patient”</b> feature in this prototype demonstrates that workflow manually. It uses Septris Lite, a smaller browser-based model that sees only the ${data.lite ? data.lite.fields.length : 11} values on the form. Septris Lite is not the full model and is weaker: its Hospital A held-out AUROC is ${liteA}, compared with 0.79 for the full Septris blend.</p>
    <h3>Limits</h3>
    <ul>
      <li>Septris was evaluated only on retrospective, de-identified records. It has never been used in live clinical care.</li>
      <li>It does not diagnose sepsis, recommend treatment, or replace clinician judgment.</li>
      <li>It performs worse at an unseen hospital, showing that local workflow and measurement practices matter.</li>
      <li>Measurement patterns can reflect tests clinicians already chose to order. Septris may partly prioritize patients the care team was already investigating.</li>
      <li>The simulated ward places patients from different historical time periods side by side, so it is not a real ICU deployment.</li>
      <li>A prospective silent trial, local calibration, clinician feedback, fairness analysis, and outcome study are required before clinical use.</li>
    </ul>
    <p class="small muted">Team: Miheer Parasnis, Aaron Qin, Reyansh Maheshwari<br>Veritas AI Hackathon 2026 · AI + Health<br>Data: PhysioNet/CinC Challenge 2019, CC BY 4.0<br>Prototype · Not medical advice · Clinician review required</p>`;
}

export function faqHTML(data) {
  const k = data.meta.k;
  const qa = [
    ["What is sepsis?", "Sepsis is the body's extreme reaction to an infection. It can damage organs within hours. Each hour of delayed treatment raises the risk of death. That is why spotting it early matters."],
    ["What problem does Septris solve?", `Checking one chart for signs of sepsis takes real time, and one nurse may cover 20 beds. Septris answers one question: whose chart should the nurse open next? The ward shows ${k} chart checks per 12-hour shift as a demonstration. The reported results use 3 per shift.`],
    ["What do the colours mean?", "Blue: check this bed now. Red: high risk (top 5% of ICU hours). Yellow: medium risk (top 20%). Green: low risk. Grey: checked in the last 12 hours, so skipped for now."],
    ["What does “risk score 92 of 100” mean?", "It is a ranking. This patient's data right now looks more worrying than about 92% of ICU hours at the training hospital. It does not tell you the chance of having sepsis."],
    ["How do you know if a pick was right?", "These are real patients from past records, so each stay is already written down. Septris only gets the data up to each moment. Afterwards we look at the record. If sepsis was recorded 6–12 hours after the chart check, the patient counts as caught early."],
    ["Why are most picks false alarms?", "Only about 8% of these ICU patients ever develop sepsis. At any moment, very few are 6–12 hours away from it. So most of the time there is no one to catch. A false alarm is a check on a patient who did not get sepsis. What counts is catching more real cases with the same nurse time."],
    ["Can I add my own patient?", "Yes. Click “＋ Add a patient” at the top of the ward, type in their readings (or use an example), and choose how long they stay. They are wheeled in from the elevator, scored and ranked with the other beds. In a real hospital, this information would come in automatically from the patient record."],
    ["Does it diagnose sepsis?", "No. It never diagnoses or recommends treatment. It only sorts the nurse's list of charts to check and explains why."],
    ["Can I control it by voice?", "Yes, when the page is allowed to use the microphone. You can also type: “add John, a 62 year old man, with heart rate 118 and temperature 38.6 to bed 4”, “show bed 6”, “next check”, “next shift”, “queue”, “results”, “show me a miss”, “why?”, “zoom out”, “play”."],
  ];
  return `<h2>Questions</h2>${qa.map(([q, a]) => `<h3>${q}</h3><p>${a}</p>`).join("")}`;
}
