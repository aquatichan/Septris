// Five-step guided tour. Each step sets app state and moves the camera, so
// the 3D view and the text explain the same thing at the same time.

export function tourSteps(data, slot) {
  const s = data.slots[slot];
  return [
    {
      title: "Meet the ICU",
      text: `It's ${s.clock} on the ${s.shift_name.toLowerCase()}. One nurse looks after these 20 beds but only has time for about ${data.meta.k} careful sepsis reviews per 12-hour shift. Sepsis is the body's extreme reaction to an infection, and it's much easier to treat when caught early. Whose chart should the nurse open first?`,
      apply: (go) => go({ showKey: false, camera: "overview" }),
    },
    {
      title: "Septris ranks every bed",
      text: `Septris reads each bed's vital signs, lab results and which tests were done, using only what has been recorded up to ${s.clock}. The ring on the floor and the bedside monitor show each bed's risk: red is high, yellow is medium, green is low. Grey beds were reviewed in the last 12 hours, so they're skipped.`,
      apply: (go) => go({ showKey: false, camera: "overview" }),
    },
    {
      title: `It points to Bed ${s.bed}`,
      text: `Bed ${s.bed} is first in line (the blue light). The panel on the right shows what stood out in its chart, so the nurse knows where to look. It's a pointer, not a diagnosis: the nurse decides.`,
      apply: (go) => go({ showKey: false, camera: s.bed, tab: "priority" }),
    },
    {
      title: "Was it right?",
      text: `These are real patients from past hospital records, so we can check each pick afterwards. Here the record shows sepsis ${Math.round(s.lead_hours)} hours after this review: Septris flagged Bed ${s.bed} early enough to act. Septris itself never sees outcomes. “Show outcomes” at the top turns this on and off.`,
      apply: (go) => go({ showKey: true, camera: s.bed, tab: "patient", selectedBed: s.bed }),
    },
    {
      title: "Explore",
      text: "Click any bed for its full patient card. The Queue tab lists all 20 beds in priority order, and Results and How it works explain the evidence. Use the review buttons at the top to move through the shift. You can also type or say commands like “show bed 6”, “next review” or “show me a miss”.",
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
