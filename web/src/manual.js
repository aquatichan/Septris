// Patients entered by hand ("Add a patient").
//
// In a hospital, each patient's readings would flow in automatically from the
// record system. This module shows the same step done by hand: a new patient
// is admitted to a bed, scored, and ranked alongside everyone else.
//
// The full Septris models need hourly history and run in Python, so entered
// patients are scored by "Septris Lite" (web/data/lite.json, built by
// scripts/16_lite_model.py): a small LightGBM model that uses only the
// current readings and runs right here in the browser.
//
// How it plugs in: rebuild(data) writes data.overlay, a Map from slot index
// to { rows, slot }. beds() and slotAt() in data.js read the overlay first,
// so the scene and every panel see entered patients without special cases.

export const FIELDS = [
  { key: "HR", label: "Heart rate", unit: "bpm", min: 20, max: 250, series: "hr" },
  { key: "MAP", label: "Blood pressure (MAP)", unit: "mmHg", min: 20, max: 200, series: "map" },
  { key: "Resp", label: "Breathing rate", unit: "/min", min: 4, max: 70, series: "resp" },
  { key: "Temp", label: "Temperature", unit: "°C", min: 30, max: 43, step: 0.1, series: "temp" },
  { key: "O2Sat", label: "Oxygen saturation", unit: "%", min: 50, max: 100 },
  { key: "Lactate", label: "Lactate", unit: "mmol/L", min: 0.1, max: 25, step: 0.1, lab: true },
  { key: "WBC", label: "White blood cells", unit: "×10³/µL", min: 0.1, max: 100, step: 0.1, lab: true },
  { key: "Creatinine", label: "Creatinine", unit: "mg/dL", min: 0.1, max: 20, step: 0.1, lab: true },
  { key: "Platelets", label: "Platelets", unit: "×10³/µL", min: 1, max: 1500, lab: true },
];
const BY_KEY = Object.fromEntries(FIELDS.map((f) => [f.key, f]));

export async function loadLite(url = "data/lite.json") {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load ${url}`);
  return res.json();
}

function leaf(node, x) {
  while (Array.isArray(node)) {
    const v = x[node[0]];
    node = v == null || Number.isNaN(v) ? (node[2] ? node[3] : node[4]) : v <= node[1] ? node[3] : node[4];
  }
  return node;
}

/** values: {HR, MAP, ..., Age, Male}; missing keys count as "not measured". Returns risk 0-100. */
export function liteRisk(lite, values) {
  const x = lite.fields.map((f) => (values[f] === "" || values[f] == null ? null : Number(values[f])));
  let raw = 0;
  for (const t of lite.trees) raw += leaf(t, x);
  const q = lite.quantiles;
  let lo = 0, hi = q.length - 1;
  while (lo < hi) { const m = (lo + hi) >> 1; q[m] < raw ? (lo = m + 1) : (hi = m); }
  return Math.round((100 * lo) / (q.length - 1));
}

/** Up to three readings that raise the risk most (hide each one and see how far the risk drops). */
export function liteReasons(lite, values) {
  const full = liteRisk(lite, values);
  const drops = [];
  for (const f of FIELDS) {
    if (values[f.key] === "" || values[f.key] == null) continue;
    const d = full - liteRisk(lite, { ...values, [f.key]: null });
    if (d > 0) drops.push([d, `${f.label} ${values[f.key]} ${f.unit}`]);
  }
  return drops.sort((a, b) => b[0] - a[0]).slice(0, 3).map((d) => d[1]);
}

const tierOf = (pct) => (pct >= 95 ? 2 : pct >= 80 ? 1 : 0);

function latestReading(m, hour) {
  let out = m.readings[0];
  for (const r of m.readings) if (r.hour <= hour) out = r;
  return out;
}

/** Builds the chart/monitor series for an entered patient (index = hours since admission). */
function buildPatient(lite, m) {
  const n = m.stay;
  const p = { manual: true, id: m.id, name: m.name, age: m.age, sex: m.sex, onset: null, group: "manual",
    risk: [], hr: [], map: [], resp: [], temp: [], lactate: [], wbc: [], reviews: [], record: m };
  for (let h = 0; h < n; h++) {
    const r = latestReading(m, m.admit + h);
    const v = { ...r.values, Age: m.age, Male: m.sex === "M" ? 1 : 0 };
    p.risk.push(liteRisk(lite, v));
    for (const f of FIELDS) if (f.series) p[f.series].push(r.values[f.key] === "" || r.values[f.key] == null ? null : Number(r.values[f.key]));
  }
  for (const r of m.readings) {
    const h = r.hour - m.admit;
    if (r.values.Lactate !== "" && r.values.Lactate != null) p.lactate.push([h, Number(r.values.Lactate)]);
    if (r.values.WBC !== "" && r.values.WBC != null) p.wbc.push([h, Number(r.values.WBC)]);
  }
  return p;
}

function classify(p, recordHour) {
  if (p.group === "uncertain_onset") return ["uncertain", null];
  if (p.onset == null) return ["false", null];
  const lead = p.onset - recordHour;
  if (lead <= 0) return ["late", lead];
  if (lead > 12) return ["false", lead];
  return [lead >= 6 ? "early6" : "early", lead];
}

/** Recomputes data.overlay from data.manual. Call after any change to entered patients. */
export function rebuild(data, lite) {
  data.overlay = new Map();
  const list = data.manual || [];
  for (const m of list) data.patients[m.id] = buildPatient(lite, m);
  if (!list.length) return;
  const lastReview = new Map();
  data.slots.forEach((s, i) => {
    const uh = s.unit_hour;
    const active = list.filter((m) => m.admit <= uh && uh < m.admit + m.stay);
    if (!active.length) return;
    const taken = new Set(active.map((m) => m.bed));
    const rows = data.bedsByHour.get(uh).filter((r) => !taken.has(r.bed)).map((r) => ({ ...r }));
    for (const m of active) {
      const p = data.patients[m.id];
      const h = uh - m.admit;
      const last = lastReview.get(m.id);
      const pct = p.risk[h];
      rows.push({ unit_hour: uh, bed: m.bed, p: m.id, manual: true, hours_in_icu: h + 1, record_hour: h, percentile: pct,
        tier: tierOf(pct), snoozed: last != null && uh - last < 12, hours_since_check: last != null ? uh - last : -1,
        picked: false, random_pick: false, hours_to_sepsis: null, rank: 0, candidates: 0 });
    }
    // re-rank: the original pick stands unless an entered patient outranks it (or took its bed)
    const cand = rows.filter((r) => !r.snoozed);
    const orig = cand.find((r) => r.picked);
    cand.sort((a, b) => (b.picked - a.picked) || (b.percentile - a.percentile) || (a.rank - b.rank));
    const bestManual = cand.filter((r) => r.manual).sort((a, b) => b.percentile - a.percentile)[0];
    let pick = orig || cand[0];
    if (bestManual && (!orig || bestManual.percentile > orig.percentile)) pick = bestManual;
    cand.sort((a, b) => ((b === pick) - (a === pick)) || (b.percentile - a.percentile) || (a.rank - b.rank));
    cand.forEach((r, j) => { r.rank = j + 1; r.picked = r === pick; });
    for (const r of rows) { r.candidates = cand.length; if (r.snoozed) { r.rank = 0; r.picked = false; } }
    rows.sort((a, b) => a.bed - b.bed);
    let slot = s;
    if (pick && pick !== orig) {
      const p = data.patients[pick.p];
      let cls = "manual", lead = null, reasons = "";
      if (pick.manual) {
        lastReview.set(pick.p, uh);
        p.reviews.push(pick.record_hour);
        const r = latestReading(p.record, uh);
        reasons = liteReasons(lite, { ...r.values, Age: p.age, Male: p.sex === "M" ? 1 : 0 }).join(" | ");
      } else {
        [cls, lead] = classify(p, pick.record_hour);
      }
      slot = { ...s, bed: pick.bed, p: pick.p, record_hour: pick.record_hour, reasons, review_class: cls, lead_hours: lead,
        random_bed: null, changed: true };
    }
    data.overlay.set(i, { rows, slot });
  });
}

let nextId = 1;

/** Adds a patient. Returns the new record. `values` holds the form's readings. */
export function admit(data, { name, age, sex, bed, stay, values, hour }) {
  data.manual = data.manual || [];
  // one entered patient per bed at a time: a new arrival ends the previous one's stay
  for (const m of data.manual) if (m.bed === bed && m.admit + m.stay > hour) m.stay = Math.max(0, hour - m.admit);
  data.manual = data.manual.filter((m) => m.stay > 0);
  const m = { id: `m${nextId++}`, name: name || `Patient ${nextId - 1}`, age, sex, bed, stay, admit: hour, readings: [{ hour, values }] };
  data.manual.push(m);
  return m;
}

export function addReading(m, hour, values) {
  m.readings = m.readings.filter((r) => r.hour !== hour);
  m.readings.push({ hour, values });
  m.readings.sort((a, b) => a.hour - b.hour);
}

export function discharge(data, m, hour) {
  m.stay = Math.max(0, hour - m.admit);
  if (m.stay === 0) data.manual = data.manual.filter((x) => x !== m);
}

/** Ready-made examples so the form can be tried in one click. */
export const EXAMPLES = {
  worrying: { label: "Fill in: early warning signs", name: "Example: early warning signs", age: 71, sex: "M",
    values: { HR: 118, MAP: 62, Resp: 26, Temp: 38.6, O2Sat: 92, Lactate: 3.4, WBC: 17.5, Creatinine: 1.9, Platelets: 110 } },
  stable: { label: "Fill in: stable patient", name: "Example: stable patient", age: 54, sex: "F",
    values: { HR: 76, MAP: 84, Resp: 15, Temp: 36.9, O2Sat: 98, Lactate: "", WBC: 8.2, Creatinine: 0.8, Platelets: 240 } },
};

export { BY_KEY };
