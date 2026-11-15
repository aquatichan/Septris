// The paper chart that flies in when you are the nurse: the patient's details,
// risk score and how it has moved, the latest readings, the stay-so-far chart,
// why Septris flagged them, and a short list of decisions to tick and sign.
// After signing, the paper shows what the patient's record says happened next.
import { slotAt, beds } from "../data.js";
import { drawChart } from "./chart.js";

const DECISIONS = [
  ["vitals", "Repeat a full set of vital signs now"],
  ["labs", "Order lactate and blood cultures"],
  ["doctor", "Ask the doctor to see the patient"],
  ["bundle", "Start the sepsis bundle (fluids and antibiotics)"],
  ["none", "No concerns. Recheck at the next round"],
];
const ESCALATE = new Set(["labs", "doctor", "bundle"]);
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

export function createPaper({ el, getData, getState, onOpen }) {
  const signed = new Map(); // "slot:bed" -> { picks, verdict }
  let current = null, touched = false, openedAt = 0;

  function render(bed) {
    const data = getData(), st = getState();
    const s = slotAt(data, st.slot);
    const r = beds(data, st.slot).find((x) => x.bed === bed);
    current = { slot: st.slot, bed };
    touched = false;
    if (!r) {
      el.innerHTML = `<div class="clip"></div><button class="pclose" aria-label="Put the chart down">✕</button><h2>Bed ${bed}</h2><p>This bed is empty right now.</p>`;
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
    const key = `${st.slot}:${bed}`;
    const done = signed.get(key);
    el.innerHTML = `
      <div class="clip"></div>
      <button class="pclose" aria-label="Put the chart down">✕</button>
      <div class="phead">
        <div><div class="pk">Bedside chart · Day ${s.day} · ${s.clock}</div><h2>Bed ${bed}</h2>
          <div class="pwho">${p.sex === "M" ? "Man" : "Woman"}, ${Math.round(p.age)} · ${r.hours_in_icu} h in the ICU</div></div>
        <div class="prisk t${r.tier}"><b>${r.percentile}</b><span>risk / 100</span><em>${TIERS[r.tier]}</em></div>
      </div>
      ${r.picked ? `<p class="pflag">Septris sent you here: highest risk of the beds not checked in the last 12 hours.</p>` : r.snoozed ? `<p class="pnote">Checked ${r.hours_since_check} h ago, so Septris is not asking for this bed yet.</p>` : `<p class="pnote">${r.rank - 1} bed${r.rank === 2 ? " is" : "s are"} ahead of this one in line.</p>`}
      ${reasons.length ? `<h3>Why Septris flagged it</h3><ul class="preasons">${reasons.map((x) => `<li>${esc(x.charAt(0).toUpperCase() + x.slice(1))}</li>`).join("")}</ul>` : ""}
      <h3>Risk updates (every 2 hours)</h3>
      <ol class="pups">${updates}</ol>
      <h3>Latest readings</h3>
      <table class="pvit"><tbody>${vit}</tbody></table>
      <h3>Stay so far</h3>
      <canvas class="pchart" id="paperChart" aria-label="Risk score, heart rate and blood pressure over the stay"></canvas>
      <div class="plegend"><span class="r">risk</span><span class="h">heart rate</span><span class="m">blood pressure</span></div>
      <h3>Your decision</h3>
      <form class="pdec" ${done ? "data-done" : ""}>
        ${DECISIONS.map(([k, t]) => `<label><input type="checkbox" name="${k}" ${done?.picks.includes(k) ? "checked" : ""} ${done ? "disabled" : ""}><span>${t}</span></label>`).join("")}
        ${done ? "" : `<button class="btn on psign" type="submit">Sign the chart</button>`}
      </form>
      <div class="pverdict" ${done ? "" : "hidden"}>${done ? done.verdict : ""}</div>
      <div class="ptally">${tally()}</div>`;
    requestAnimationFrame(() => {
      const c = el.querySelector("#paperChart");
      if (c) drawChart(c, p, h, false, true); // no peeking at the future until the chart is signed
    });
    el.querySelector(".pdec").addEventListener("change", (e) => {
      touched = true;
      if (e.target.name === "none" && e.target.checked) el.querySelectorAll(".pdec input").forEach((i) => { if (i.name !== "none") i.checked = false; });
      else if (e.target.checked) el.querySelector('.pdec input[name="none"]').checked = false;
    });
    el.querySelector(".pdec").addEventListener("submit", (e) => {
      e.preventDefault();
      const picks = [...el.querySelectorAll(".pdec input:checked")].map((i) => i.name);
      if (!picks.length) { el.querySelector(".psign").textContent = "Tick at least one box first"; return; }
      signed.set(key, { picks, verdict: verdict(p, h, picks), right: rightCall(p, h, picks) });
      render(bed);
      requestAnimationFrame(() => {
        const c = el.querySelector("#paperChart");
        if (c) drawChart(c, p, h, true, true); // now show what happened next
      });
    });
  }

  function rightCall(p, h, picks) {
    const esc8 = picks.some((k) => ESCALATE.has(k));
    if (p.manual || p.group === "uncertain_onset") return null;
    const soon = p.onset != null && p.onset - h > 0 && p.onset - h <= 12;
    return soon === esc8;
  }

  function verdict(p, h, picks) {
    const esc8 = picks.some((k) => ESCALATE.has(k));
    if (p.manual) return "<b>Signed.</b> You entered this patient by hand, so there is no record to compare with.";
    if (p.group === "uncertain_onset") return "<b>Signed.</b> This patient already had sepsis on arrival, so this check isn't scored.";
    if (p.onset == null) return esc8
      ? "<b>No sepsis followed.</b> The extra tests were a precaution. That is the cost of a false alarm: some time and a blood test."
      : "<b>Good call.</b> The record shows this patient never developed sepsis.";
    const d = Math.round(p.onset - h);
    if (d <= 0) return `<b>Sepsis was already recorded ${-d} hour${d === -1 ? "" : "s"} before this check.</b> ${esc8 ? "Escalating was right, but this one was found late." : "This patient needed treatment now."}`;
    if (d <= 12) return esc8
      ? `<b>Good call.</b> The record shows sepsis ${d} hour${d === 1 ? "" : "s"} later. Escalating now gives the team a ${d}-hour head start.`
      : `<b>The record shows sepsis ${d} hour${d === 1 ? "" : "s"} later.</b> Escalating here would have caught it early.`;
    return `<b>Sepsis came much later (${d} hours).</b> ${esc8 ? "Escalating did no harm and put the patient on the team's radar." : "Nothing pointed to it yet, so waiting was reasonable."}`;
  }

  function tally() {
    const scored = [...signed.values()].filter((x) => x.right != null);
    if (!signed.size) return "Tick what you would do, then sign. The record will tell you what happened next.";
    return `Charts signed: <b>${signed.size}</b> · matched what the record shows: <b>${scored.filter((x) => x.right).length} of ${scored.length}</b>`;
  }

  el.addEventListener("click", (e) => { if (e.target.closest(".pclose")) hide(); });

  function show(bed) {
    const again = current && current.bed === bed && current.slot === getState().slot && !el.hidden;
    if (!again) { render(bed); openedAt = performance.now(); }
    if (el.hidden) {
      el.hidden = false;
      el.classList.remove("fly");
      void el.offsetWidth; // restart the fly-in animation
      el.classList.add("fly");
    }
    onOpen?.(bed);
  }
  function hide() { el.hidden = true; current = null; }

  return {
    show, hide,
    get open() { return !el.hidden; },
    get bed() { return current?.bed ?? null; },
    /** true while the user has ticked boxes on the open chart but not signed it */
    /** seconds the current chart has been in front of the user */
    shownFor: () => (el.hidden ? 0 : (performance.now() - openedAt) / 1000),
    busy: () => !el.hidden && touched && !signed.has(`${current?.slot}:${current?.bed}`),
    refresh() { if (!el.hidden && current) render(current.bed); },
  };
}
