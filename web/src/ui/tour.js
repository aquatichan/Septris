// Five-step guided tour. Each step sets app state and moves the camera, so
// the 3D view and the text explain the same thing at the same time.

export function tourSteps(data, slot) {
  const s = data.slots[slot];
  return [
    {
      title: "Meet the ICU",
      text: `It's ${s.clock} on the ${s.shift_name.toLowerCase()}. One nurse looks after these 20 beds. In a 12-hour shift, there is time to check only about ${data.meta.k} charts carefully for signs of sepsis. Sepsis is the body's extreme reaction to an infection. It is much easier to treat when found early. The question is whose chart to open first.`,
      apply: (go) => go({ showKey: false, camera: "overview" }),
    },
    {
      title: "Septris ranks every bed",
      text: `Septris reads each bed's vital signs (like heart rate) and lab results (blood tests), and notes which tests were done. It uses only what has been recorded up to ${s.clock}. The ring on the floor and the bedside monitor show each bed's risk score. Red is high, yellow is medium, green is low. Grey beds were checked in the last 12 hours, so Septris skips them.`,
      apply: (go) => go({ showKey: false, camera: "overview" }),
    },
    {
      title: `It points to Bed ${s.bed}`,
      text: `Bed ${s.bed} is first in line (the blue light). The panel on the right shows what stood out in its chart, so the nurse knows where to look. It points to a chart and does not diagnose. The nurse decides.`,
      apply: (go) => go({ showKey: false, camera: s.bed, tab: "priority" }),
    },
    {
      title: "Was it right?",
      text: `These are real patients from past hospital records, so we can check each pick afterwards. Here the record shows sepsis ${Math.round(s.lead_hours)} hours after this chart check. Septris flagged Bed ${s.bed} early enough to act. Septris itself never sees outcomes. “Show outcomes” at the top turns this view on and off.`,
      apply: (go) => go({ showKey: true, camera: s.bed, tab: "patient", selectedBed: s.bed }),
    },
    {
      title: "Explore",
      text: "Click any bed to see its patient card. The Queue tab lists all 20 beds in priority order. Results, How it works and FAQ at the top show the evidence. Use the Review buttons to move through the shift. When a patient leaves, a new one is wheeled in from the elevator. You can also type or say commands like “show bed 6”, “next check” or “show me a miss”.",
      apply: (go) => go({ showKey: true, camera: "overview", tab: "priority" }),
    },
  ];
}

export function renderTour(el, steps, i, { onNext, onBack, onClose }) {
  if (i == null) {
    el.hidden = true;
    return;
  }
  const st = steps[i];
  el.hidden = false;
  el.innerHTML = `
    <div class="steps">${steps.map((_, j) => `<i class="${j <= i ? "on" : ""}"></i>`).join("")}</div>
    <div class="eyebrow" style="margin-top:8px">Guided tour · ${i + 1} of ${steps.length}</div>
    <h2>${st.title}</h2>
    <p>${st.text}</p>
    <div class="row">
      <button class="btn ghost" data-a="close">Skip tour</button>
      <span style="display:flex;gap:6px">
        <button class="btn ghost" data-a="back" ${i === 0 ? "disabled" : ""}>Back</button>
        <button class="btn on" data-a="next">${i === steps.length - 1 ? "Start exploring" : "Next"}</button>
      </span>
    </div>`;
  el.querySelector("[data-a=next]").onclick = onNext;
  el.querySelector("[data-a=back]").onclick = onBack;
  el.querySelector("[data-a=close]").onclick = onClose;
}
