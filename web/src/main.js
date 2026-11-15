// Entry point: load data, build the 3D unit, wire the HUD, panel, tour,
// examples and commands to the shared state.
import { loadData, beds, slotAt, shiftLabel, ordinal } from "./data.js";
import { FIELDS, EXAMPLES, loadLite, liteRisk, rebuild, admit, addReading, discharge } from "./manual.js";
import { state, set, subscribe } from "./store.js";
import { createWorld } from "./scene/world.js";
import { createBeds } from "./scene/beds.js";
import { createCameraRig } from "./scene/camera.js";
import { createLobby } from "./scene/lobby.js";
import { createDecor } from "./scene/decor.js";
import { priorityHTML, patientHTML, drawBedChart, queueHTML, resultsHTML, modelHTML, faqHTML } from "./ui/panel.js";
import { tourSteps, renderTour } from "./ui/tour.js";
import { parse } from "./commands.js";
import { createVoice } from "./voice.js";

const $ = (id) => document.getElementById(id);

// A clear first example: caught 7-11 h ahead, the patient's first review,
// risk rising over the last 12 h, reasons that cite real values.
function tourSlot(data) {
  let best = null;
  data.slots.forEach((s, i) => {
    if (s.review_class !== "early6" || s.sepsis_so_far < 1 || s.lead_hours < 7 || s.lead_hours > 11) return;
    const p = data.patients[s.p];
    if (p.reviews.some((h) => h < s.record_hour) || s.record_hour < 12) return;
    const reasons = (s.reasons || "").split(" | ").filter(Boolean);
    if (reasons.length < 3 || reasons.filter((r) => /\d/.test(r)).length < 2) return;
    if (!best && s.day >= 2 && data.bedsByHour.get(s.unit_hour).length >= 19) best = [0, i]; // the first clear one
  });
  return best ? best[1] : data.examples.good[0];
}

async function main() {
  let data;
  try {
    data = await loadData();
  } catch (e) {
    $("loading").textContent = `Couldn't load the data: ${e.message}. Serve this folder over http (for example: python -m http.server).`;
    return;
  }
  const world = createWorld($("stage"));
  const rig = createCameraRig(world);
  const lobby = createLobby(world);
  createDecor(world);
  window.__septris = { lobby, rig, state };
  const bedsView = createBeds(world, (bed) => selectBed(bed), lobby);
  const voice = createVoice({
    onText: (t) => runCommand(t, true),
    onState: (s) => {
      $("mic").classList.toggle("listening", s === "listening");
      const msg = { unsupported: "Voice isn't supported in this browser. Type a command instead.",
        blocked: "Microphone access is blocked here. Type a command instead.", error: "Didn't catch that. Try again or type it." }[s];
      if (msg) $("cmdEcho").textContent = msg;
    },
  });
  const lite = await loadLite();
  data.lite = lite;
  data.manual = [];
  const TOUR = tourSlot(data);
  const steps = tourSteps(data, TOUR);
  let resultsK = data.meta.k;
  const exampleCounter = { good: -1, miss: -1, false: -1 };

  // ---------- actions ----------
  function goSlot(i, extra = {}) {
    i = Math.max(0, Math.min(data.slots.length - 1, i));
    set({ slot: i, selectedBed: null, ...extra });
    if (state.narrate) speakPick();
  }
  function selectBed(bed) {
    set({ selectedBed: bed, tab: "patient" });
    rig.bed(bed);
  }
  function goShift(delta) {
    const sh = data.slots[state.slot].shift;
    const k = data.shiftIds.indexOf(sh) + delta;
    const id = data.shiftIds[Math.max(0, Math.min(data.shiftIds.length - 1, k))];
    goSlot(data.shifts.get(id)[0], { focus: null });
  }
  function example(kind) {
    const xs = data.examples[kind];
    exampleCounter[kind] = (exampleCounter[kind] + 1) % xs.length;
    const x = xs[exampleCounter[kind]];
    const slot = typeof x === "object" ? x.slot : x;
    const focus = { kind, slot, bed: typeof x === "object" ? x.bed : data.slots[slot].bed };
    goSlot(slot, { focus, tab: "priority", showKey: true });
    rig.bed(focus.bed);
    if (kind === "miss") set({ selectedBed: focus.bed });
  }
  function speakPick() {
    const s = slotAt(data, state.slot);
    const r = (s.reasons || "").split(" | ").filter(Boolean);
    voice.say(`${s.clock}. Highest priority is bed ${s.bed}. ${r.length ? "What stood out: " + r.join(", ") + "." : ""}`);
  }
  function runCommand(text, spoken = false) {
    const a = parse(text);
    $("cmdEcho").textContent = a ? `“${text}”` : `Didn't understand “${text}”. Try “show bed 6” or “next review”.`;
    if (!a) return;
    const shiftIdx = data.shifts.get(data.slots[state.slot].shift);
    switch (a.type) {
      case "bed": if (a.bed >= 1 && a.bed <= 20) selectBed(a.bed); break;
      case "review": goSlot(state.slot + a.delta, { focus: null }); break;
      case "reviewN": goSlot(shiftIdx[Math.min(a.n, shiftIdx.length) - 1], { focus: null }); break;
      case "shift": goShift(a.delta); break;
      case "example": example(a.kind); break;
      case "overview": set({ page: "" }); rig.overview(); break;
      case "page": set({ page: a.page }); break;
      case "play": set({ playing: a.on }); break;
      case "explain": speakPick(); set({ tab: "priority" }); break;
      case "key": set({ showKey: a.on }); break;
      case "tab": set({ tab: a.tab }); break;
      case "tour": set({ tourStep: 0 }); break;
      case "admit": admitFromCommand(a.details); break;
    }
    if (spoken && a.type !== "explain" && state.narrate) speakPick();
  }

  // ---------- render ----------
  function renderHud() {
    const s = slotAt(data, state.slot);
    $("clock").innerHTML = `Day ${s.day} · ${s.clock} <small>${shiftLabel(s)}</small>`;
    const ids = data.shifts.get(s.shift);
    $("reviewChips").innerHTML = ids.map((i) => {
      const x = data.slots[i];
      return `<button class="chip ${i === state.slot ? "on" : ""}" data-slot="${i}"><b>Review ${x.check}</b>${x.clock}</button>`;
    }).join("");
    $("play").textContent = state.playing ? "❚❚ Pause" : "▶ Play";
    $("showKey").checked = state.showKey;
    $("narrate").checked = state.narrate;
  }
  function renderPanel() {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.tab === state.tab));
    for (const t of ["priority", "patient", "queue"]) $(`tab-${t}`).hidden = t !== state.tab;
    if (state.tab === "priority") $("tab-priority").innerHTML = priorityHTML(data, state);
    if (state.tab === "patient") { $("tab-patient").innerHTML = patientHTML(data, state); requestAnimationFrame(() => drawBedChart(data, state)); }
    if (state.tab === "queue") $("tab-queue").innerHTML = queueHTML(data, state);
    // full-page sections
    $("page").hidden = !state.page;
    document.querySelectorAll(".btn.pg").forEach((b) => b.classList.toggle("on", b.dataset.page === state.page));
    if (state.page === "results") $("pageBody").innerHTML = resultsHTML(data, resultsK);
    if (state.page === "model") $("pageBody").innerHTML = modelHTML(data);
    if (state.page === "faq") $("pageBody").innerHTML = faqHTML(data);
    // running tally of early predictions
    const s = data.slots[state.slot];
    const tally = $("tally");
    tally.hidden = !state.showKey || !s.sepsis_so_far;
    tally.innerHTML = `<b>${s.sb_caught_so_far} of ${s.sepsis_so_far}</b>sepsis cases so far were flagged 6–12 hours early by Septris (random picking: ${s.random_caught_so_far}).`;
  }
  function renderNote() {
    const f = state.focus;
    const el = $("note");
    const s = slotAt(data, state.slot);
    const hit = state.showKey && (s.review_class === "early6" || s.review_class === "early");
    el.className = "note" + (hit ? " hit" : "");
    let text = "";
    if (f && f.slot === state.slot && f.kind !== "good") {
      const b = beds(data, state.slot).find((x) => x.bed === f.bed);
      text = f.kind === "false"
        ? `Example of a false alarm: Septris put Bed ${s.bed} first, but no sepsis followed. This is the most common outcome, because only about 8% of ICU patients develop sepsis.`
        : b ? `Example of a miss: the record shows Bed ${f.bed} developed sepsis ${Math.round(b.hours_to_sepsis)} hours after this point, but Septris had it ${b.rank ? `${ordinal(b.rank)} in line` : "marked as recently reviewed"}, so it wasn't reviewed in time.` : "";
      el.className = "note";
    } else if (hit && state.tourStep == null) {
      const lead = Math.round(s.lead_hours);
      text = `<b>✓ Sepsis predicted ${lead} hour${lead === 1 ? "" : "s"} early.</b> Septris sent the nurse to Bed ${s.bed} at ${s.clock}; the record shows sepsis ${lead} hour${lead === 1 ? "" : "s"} later${s.review_class === "early6" ? ", inside the 6–12 hour early-warning window" : ""}.`;
    }
    el.innerHTML = text;
    el.hidden = !text || !!state.page;
  }
  function render(patch) {
    const s = slotAt(data, state.slot);
    if (!patch || "slot" in patch || "showKey" in patch || "selectedBed" in patch || "focus" in patch || "manualVersion" in patch) {
      bedsView.update(data, s, beds(data, state.slot), state);
    }
    renderHud();
    renderPanel();
    renderNote();
    renderTour($("tour"), steps, state.tourStep, {
      onNext: () => (state.tourStep >= steps.length - 1 ? set({ tourStep: null, showKey: true }) : set({ tourStep: state.tourStep + 1 })),
      onBack: () => set({ tourStep: Math.max(0, state.tourStep - 1) }),
      onClose: () => set({ tourStep: null, showKey: true }),
    });
  }
  subscribe((st, patch) => {
    if ("tourStep" in patch && st.tourStep != null) {
      steps[st.tourStep].apply(({ camera, ...p }) => {
        set({ slot: TOUR, focus: null, selectedBed: null, ...p });
        camera === "overview" ? rig.overview() : rig.bed(camera);
      });
      return;
    }
    render(patch);
  });

  // ---------- add a patient ----------
  let editing = null; // the entered patient whose readings are being updated, or null when admitting
  const fval = (id) => $(id).value.trim();
  function formValues() {
    return Object.fromEntries(FIELDS.map((f) => [f.key, fval(`f_${f.key}`) === "" ? "" : Number(fval(`f_${f.key}`))]));
  }
  function refreshEstimate() {
    const age = editing ? editing.age : Number(fval("f_age")) || 65;
    const sex = editing ? editing.sex : $("f_sex").value;
    const filled = FIELDS.filter((f) => fval(`f_${f.key}`) !== "").length;
    const pct = liteRisk(lite, { ...formValues(), Age: age, Male: sex === "M" ? 1 : 0 });
    const tier = pct >= 95 ? ["high", "High"] : pct >= 80 ? ["med", "Medium"] : ["low", "Low"];
    const el = $("admitEstimate");
    el.className = `estimate ${tier[0]}`;
    el.innerHTML = filled
      ? `Estimated sepsis risk: <b>${pct} of 100</b> · ${tier[1]} · from ${filled} of ${FIELDS.length} readings`
      : `<span class="muted">Enter at least one reading to see the estimated risk.</span>`;
  }
  function openAdmit(m = null) {
    editing = m;
    const s = slotAt(data, state.slot);
    $("admitTitle").textContent = m ? `Update readings: ${m.name}` : "Add a patient";
    $("admitEyebrow").textContent = `${m ? `Bed ${m.bed}` : "Check-in desk"} · day ${s.day}, ${s.clock}`;
    $("admitIntro").textContent = m
      ? "Enter the newest readings. The patient is re-scored from this moment on, and their place in the queue updates."
      : "In a hospital these readings would arrive automatically from the patient record. Here you can enter them by hand. Leave anything blank that hasn't been measured.";
    $("admitWho").hidden = !!m;
    $("admitSubmit").textContent = m ? "Save readings" : "Admit patient";
    $("admitError").hidden = true;
    const rows = beds(data, state.slot);
    const free = [...Array(20)].map((_, i) => i + 1).filter((b) => !rows.some((r) => r.bed === b));
    const lowest = [...rows].filter((r) => !r.manual && !r.picked).sort((a, b) => a.percentile - b.percentile)[0];
    const auto = free[0] ?? lowest?.bed ?? 20;
    $("f_bed").innerHTML = `<option value="${auto}">Auto: Bed ${auto} (${free.length ? "free" : "lowest-risk patient moves out"})</option>`
      + [...Array(20)].map((_, i) => `<option value="${i + 1}">Bed ${i + 1}${free.includes(i + 1) ? " (free)" : ""}</option>`).join("");
    const cur = m ? m.readings[m.readings.length - 1].values : {};
    for (const f of FIELDS) $(`f_${f.key}`).value = cur[f.key] ?? "";
    refreshEstimate();
    $("admit").hidden = false;
    (m ? $(`f_${FIELDS[0].key}`) : $("f_name")).focus();
  }
  /** "add John who is 32 with heart rate 118 to bed 4": fill the form from the sentence and admit if enough was heard. */
  function admitFromCommand(d) {
    openAdmit();
    if (!d) return;
    if (d.name) $("f_name").value = d.name;
    if (d.age != null) $("f_age").value = d.age;
    if (d.sex) $("f_sex").value = d.sex;
    if (d.bed >= 1 && d.bed <= 20) $("f_bed").value = String(d.bed);
    if (d.stay) $("f_stay").value = d.stay;
    for (const f of FIELDS) $(`f_${f.key}`).value = d.values[f.key] ?? "";
    refreshEstimate();
    const missing = [];
    if (d.age == null) missing.push("age");
    if (!d.sex) missing.push("man or woman");
    if (!Object.keys(d.values).length) missing.push("at least one reading");
    if (missing.length) {
      $("admitError").textContent = `I filled in what I heard. Still needed: ${missing.join(", ")}. Add it and press Admit patient.`;
      $("admitError").hidden = false;
      return;
    }
    $("admitForm").requestSubmit();
  }
  function closeAdmit() { $("admit").hidden = true; editing = null; }
  $("admitFields").innerHTML = FIELDS.map((f) => `<label>${f.label} <span>${f.unit}</span>
    <input id="f_${f.key}" type="number" inputmode="decimal" min="${f.min}" max="${f.max}" step="${f.step ?? 1}" placeholder="${f.lab ? "not measured" : `typical ${lite.typical[f.key]}`}"></label>`).join("");
  $("admitExamples").innerHTML = Object.entries(EXAMPLES).map(([k, e]) => `<button type="button" class="btn" data-example="${k}">${e.label}</button>`).join("");
  $("admitExamples").onclick = (e) => {
    const ex = EXAMPLES[e.target.dataset.example];
    if (!ex) return;
    if (!editing) { $("f_name").value = ex.name; $("f_age").value = ex.age; $("f_sex").value = ex.sex; }
    for (const f of FIELDS) $(`f_${f.key}`).value = ex.values[f.key];
    refreshEstimate();
  };
  $("admitForm").oninput = refreshEstimate;
  $("admitCancel").onclick = closeAdmit;
  $("addPatient").onclick = () => openAdmit();
  $("admitForm").onsubmit = (e) => {
    e.preventDefault();
    const values = formValues();
    const err = (msg) => { $("admitError").textContent = msg; $("admitError").hidden = false; };
    if (!FIELDS.some((f) => values[f.key] !== "")) return err("Enter at least one reading so the patient can be scored.");
    for (const f of FIELDS) {
      const v = values[f.key];
      if (v !== "" && (Number.isNaN(v) || v < f.min || v > f.max)) return err(`${f.label} should be between ${f.min} and ${f.max} ${f.unit}.`);
    }
    const hour = slotAt(data, state.slot).unit_hour;
    let bed;
    if (editing) {
      addReading(editing, hour, values);
      bed = editing.bed;
    } else {
      const age = Number(fval("f_age")), stay = Number(fval("f_stay"));
      if (!(age >= 18 && age <= 110)) return err("Age should be between 18 and 110.");
      if (!(stay >= 6 && stay <= 240)) return err("Expected stay should be between 6 and 240 hours.");
      bed = Number($("f_bed").value);
      admit(data, { name: fval("f_name"), age, sex: $("f_sex").value, bed, stay: Math.round(stay), values, hour });
    }
    rebuild(data, lite);
    closeAdmit();
    set({ manualVersion: state.manualVersion + 1, selectedBed: bed, tab: "patient", page: "", focus: null });
    rig.bed(bed);
  };
  $("tab-patient").onclick = (e) => {
    const act = e.target.dataset.manual;
    if (!act) return;
    const s = slotAt(data, state.slot);
    const r = beds(data, state.slot).find((x) => x.bed === (state.selectedBed ?? s.bed));
    const m = r && data.patients[r.p]?.record;
    if (!m) return;
    if (act === "update") openAdmit(m);
    if (act === "discharge") {
      discharge(data, m, s.unit_hour);
      rebuild(data, lite);
      set({ manualVersion: state.manualVersion + 1 });
    }
  };

  // ---------- events ----------
  $("prevShift").onclick = () => goShift(-1);
  $("nextShift").onclick = () => goShift(1);
  $("reviewChips").onclick = (e) => {
    const b = e.target.closest("[data-slot]");
    if (b) goSlot(Number(b.dataset.slot), { focus: null });
  };
  $("play").onclick = () => set({ playing: !state.playing });
  $("showKey").onchange = (e) => set({ showKey: e.target.checked });
  $("narrate").onchange = (e) => { set({ narrate: e.target.checked }); if (e.target.checked) speakPick(); };
  $("overview").onclick = () => rig.overview();
  $("startTour").onclick = () => set({ tourStep: 0 });
  document.querySelectorAll(".btn.ex").forEach((b) => (b.onclick = () => example(b.dataset.kind)));
  document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => set({ tab: t.dataset.tab })));
  for (const id of ["tab-priority", "tab-queue"]) $(id).onclick = (e) => {
    const b = e.target.closest("[data-bed]");
    if (b) selectBed(Number(b.dataset.bed));
  };
  document.querySelectorAll(".btn.pg").forEach((b) => (b.onclick = () => set({ page: b.dataset.page })));
  $("pageClose").onclick = () => set({ page: "" });
  $("pageBody").onclick = (e) => {
    const b = e.target.closest("[data-k]");
    if (b) { resultsK = Number(b.dataset.k); renderPanel(); }
  };
  $("command").onsubmit = (e) => {
    e.preventDefault();
    const t = $("cmdInput").value.trim();
    if (t) runCommand(t);
    $("cmdInput").value = "";
  };
  $("mic").onclick = () => voice.listen();
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !$("admit").hidden) closeAdmit();
    if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName) || !$("admit").hidden) return;
    if (e.key === "ArrowRight") goSlot(state.slot + 1, { focus: null });
    if (e.key === "ArrowLeft") goSlot(state.slot - 1, { focus: null });
    if (e.key === "/") { e.preventDefault(); $("cmdInput").focus(); }
  });
  window.addEventListener("resize", () => state.tab === "patient" && drawBedChart(data, state));

  // autoplay: one review every 3.5 s
  setInterval(() => { if (state.playing && state.tourStep == null) goSlot(state.slot + 1, { focus: null }); }, 3500);

  // start: the tour moment, overview camera, tour open
  // start: ride the elevator into the lobby, through to the ward, then open the tour
  $("loading").hidden = true;
  set({ data, slot: TOUR });
  document.body.classList.add("intro");
  $("skipIntro").hidden = false;
  $("skipIntro").onclick = () => rig.skipIntro();
  rig.intro(lobby, () => {
    document.body.classList.remove("intro");
    $("skipIntro").hidden = true;
    set({ tourStep: 0 });
  });
}

main();
