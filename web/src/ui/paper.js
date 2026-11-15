// The clipboard the nurse lifts in first-person mode: the patient's details,
// risk score and how it has moved, the latest readings, why Septris flagged
// the bed, the stay-so-far chart and, when it applies, the caught-early result.
// Septris only says which chart to check next, so the clipboard is for reading;
// what to do about it stays the clinician's call.
import { slotAt, beds } from "../data.js";
import { drawChart } from "./chart.js";

const TIERS = ["Low", "Medium", "High"];

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
function latest(series, h, back = 12) {
  if (!series) return null;
  for (let i = Math.min(h, series.length - 1); i >= Math.max(0, h - back); i--) if (series[i] != null) return { v: series[i], ago: h - i };
  return null;
}
// lab tests are stored as [hour, value] pairs because they are measured rarely
function latestSparse(pairs, h) {
  let out = null;
  for (const [t, v] of pairs || []) if (t <= h) out = { v, ago: h - t };
  return out;
}
const ago = (x) => (x.ago === 0 ? "this hour" : `${x.ago} h ago`);
const clock = (s, hoursBack) => {
  const [hm, ap] = s.clock.split(" ");
  let h = (Number(hm.split(":")[0]) % 12) + (ap === "PM" ? 12 : 0) - hoursBack;
  h = ((h % 24) + 24) % 24;
  return `${((h + 11) % 12) + 1} ${h < 12 ? "AM" : "PM"}`;
};

/**
 * A standard ward sepsis screen applied to the chart as it stands now (no
 * peeking at the outcome): SIRS signs, blood pressure, breathing and lactate.
 */
function nurseActions(p, h) {
  const v = (s) => latest(s, h)?.v ?? null;
  const hr = v(p.hr), map = v(p.map), rr = v(p.resp), temp = v(p.temp);
  const lac = latestSparse(p.lactate, h), wbc = latestSparse(p.wbc, h);
  const sirs = [temp != null && (temp > 38 || temp < 36), hr != null && hr > 90, rr != null && rr > 20,
    wbc != null && (wbc.v > 12 || wbc.v < 4)].filter(Boolean).length;
  const lowBP = map != null && map < 65, fastRR = rr != null && rr >= 22;
  const lacOld = !lac || lac.ago > 24, lacHigh = lac && lac.v >= 2;
  const cultures = sirs >= 2;
  const doctor = lowBP || (lac && lac.v >= 4) || (sirs >= 2 && (fastRR || lacHigh));
  const labs = lacOld || lacHigh || sirs >= 2;
  return [
    { on: true, text: "Read the chart and repeat a full set of vital signs" },
    { on: true, always: true, text: "Run the bedside sepsis screen", note: `${sirs} of 4 SIRS signs present (temperature, heart rate, breathing, white cells)` },
    { on: labs, text: "Order a lactate", note: lac ? `last ${lac.v} mmol/L, ${lac.ago} h ago` : "none on the chart yet" },
    { on: cultures, text: "Send blood cultures before any antibiotics" },
    { on: doctor, text: "Call the doctor to see the patient now", note: [lowBP && `MAP ${map} mmHg`, fastRR && `breathing ${rr}/min`, lacHigh && `lactate ${lac.v}`].filter(Boolean).join(" · ") || null },
    { on: !labs && !cultures && !doctor, text: "No red flags: recheck at the next round" },
  ];
}

export function createPaper({ el, getData, getState, onOpen }) {
  let current = null, openedAt = 0;

  function render(bed) {
    const data = getData(), st = getState();
    const s = slotAt(data, st.slot);
    const r = beds(data, st.slot).find((x) => x.bed === bed);
    current = { slot: st.slot, bed };
    if (!r) {
      el.innerHTML = `<div class="board"><div class="clip"></div><div class="sheet"><button class="pclose" aria-label="Put the clipboard down">✕</button><h2>Bed ${bed}</h2><p>This bed is empty right now.</p></div></div>`;
      return;
    }
    const p = data.patients[r.p], h = r.record_hour;
    // risk updates: the score every 2 hours over the last 12
    const ups = [];
    for (let k = 12; k >= 0; k -= 2) {
      const v = p.risk[h - k];
      if (v != null) ups.push({ at: k === 0 ? "now" : clock(s, k), v });
    }
    const updates = ups.map((u, i) => {
      const d = i ? u.v - ups[i - 1].v : 0;
      return `<li><span>${u.at}</span><b>${u.v}</b>${i ? `<i class="${d > 4 ? "up" : d < -4 ? "down" : ""}">${d > 0 ? "+" : ""}${d}</i>` : "<i></i>"}</li>`;
    }).join("");
    const vit = [
      ["Heart rate", latest(p.hr, h), "bpm"],
      ["Blood pressure (MAP)", latest(p.map, h), "mmHg"],
      ["Breathing rate", latest(p.resp, h), "/min"],
      ["Temperature", latest(p.temp, h), "°C"],
      ["Lactate", latestSparse(p.lactate, h), "mmol/L"],
      ["White cells", latestSparse(p.wbc, h), "×10³/µL"],
    ].map(([n, x, u]) => `<tr><td>${n}</td><td class="n">${x ? `${x.v} <small>${u}</small>` : "—"}</td><td class="when">${x ? ago(x) : "not measured"}</td></tr>`).join("");
    const reasons = r.picked ? (s.reasons || "").split(" | ").filter(Boolean) : [];
    let caught = "";
    if (!p.manual && p.onset != null && p.group !== "uncertain_onset") {
      const hitNow = r.picked && (s.review_class === "early6" || s.review_class === "early");
      const prior = p.reviews.filter((x) => x <= h).reverse().find((x) => p.onset - x >= 6 && p.onset - x <= 12);
      const at = hitNow ? h : prior;
      if (at != null) caught = `<div class="pcaught">✓ Sepsis caught ${Math.round(p.onset - at)} hours early</div>`;
    }
    el.innerHTML = `
      <div class="board"><div class="clip"></div><div class="pen"></div>
      <div class="sheet">
      <button class="pclose" aria-label="Put the clipboard down">✕</button>
      ${caught}
      <div class="pcols"><div class="pcol">
      <div class="phead">
        <div><div class="pk">Bedside chart · Day ${s.day} · ${s.clock}</div><h2>Bed ${bed}</h2>
          <div class="pwho">${p.sex === "M" ? "Man" : "Woman"}, ${Math.round(p.age)} · ${r.hours_in_icu} h in the ICU</div></div>
        <div class="prisk t${r.tier}"><b>${r.percentile}</b><span>risk / 100</span><em>${TIERS[r.tier]}</em></div>
      </div>
      ${r.picked ? `<p class="pflag">Septris sent you here: highest priority of the beds not checked in the last 12 hours.</p>` : r.snoozed ? `<p class="pnote">Checked ${r.hours_since_check} h ago, so Septris is not asking for this bed yet.</p>` : `<p class="pnote">${r.rank - 1} bed${r.rank === 2 ? " is" : "s are"} ahead of this one in line.</p>`}
      ${reasons.length ? `<h3>Why Septris flagged it</h3><ul class="preasons">${reasons.map((x) => `<li>${esc(x.charAt(0).toUpperCase() + x.slice(1))}</li>`).join("")}</ul>` : ""}
      <h3>Risk updates (every 2 hours)</h3>
      <ol class="pups">${updates}</ol>
      <h3>Latest readings</h3>
      <table class="pvit"><tbody>${vit}</tbody></table>
      </div><div class="pcol">
      <h3>Stay so far</h3>
      <canvas class="pchart" id="paperChart" aria-label="Risk score, heart rate and blood pressure over the stay"></canvas>
      <div class="plegend"><span class="r">risk</span><span class="h">heart rate</span><span class="m">blood pressure</span></div>
      <h3>What the nurse does next</h3>
      <ol class="pacts">${nurseActions(p, h).map((x) => `<li class="${x.on ? "do" : "skip"}"><i class="tick"></i><span>${x.text}${x.note && (x.on || x.always) ? `<small>${x.note}</small>` : ""}</span></li>`).join("")}</ol>
      <p class="pfoot">A typical bedside sepsis screen, worked out only from this chart up to now. Illustrative: real steps follow the hospital's own protocol and the doctor's orders. Septris itself only ranks charts.</p>
      </div></div>
      </div></div>`;
    // the nurse works down the list: ticks appear one after another
    el.querySelectorAll(".pacts li").forEach((li, i) => setTimeout(() => li.classList.add("shown"), 700 + i * 650));
    requestAnimationFrame(() => {
      const c = el.querySelector("#paperChart");
      if (c) drawChart(c, p, h, true, true);
    });
  }

  let dismissed = null; // the chart the user put down; don't push it back up until something changes
  el.addEventListener("click", (e) => { if (e.target.closest(".pclose")) { dismissed = `${getState().slot}:${current?.bed}`; hide(); } });

  function show(bed) {
    if (dismissed === `${getState().slot}:${bed}`) return;
    const again = current && current.bed === bed && current.slot === getState().slot && !el.hidden;
    if (!again) { render(bed); openedAt = performance.now(); }
    document.body.classList.add("clip");
    if (el.hidden) {
      el.hidden = false;
      el.classList.remove("fly");
      void el.offsetWidth; // restart the fly-in animation
      el.classList.add("fly");
    }
    onOpen?.(bed);
  }
  function hide() { el.hidden = true; current = null; document.body.classList.remove("clip"); }

  return {
    show, hide,
    get open() { return !el.hidden; },
    get bed() { return current?.bed ?? null; },
    /** seconds the current chart has been in front of the user */
    shownFor: () => (el.hidden ? 0 : (performance.now() - openedAt) / 1000),
    refresh() { if (!el.hidden && current) render(current.bed); },
  };
}
