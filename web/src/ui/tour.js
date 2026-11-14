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
      text: `Septris reads each bed's vital signs, lab results and which tests were done, using only what has been recorded up to ${s.clock}. The ring on the floor and the bedside monitor show each bed's risk (0 to 100). Grey beds were reviewed in the last 12 hours, so they're skipped.`,
      apply: (go) => go({ showKey: false, camera: "overview" }),
    },
    {
      title: `It points to Bed ${s.bed}`,
      text: `Bed ${s.bed} is first in line (the blue light). The panel on the right shows what stood out in its chart, so the nurse knows where to look. It's a pointer, not a diagnosis: the nurse decides.`,
      apply: (go) => go({ showKey: false, camera: s.bed, tab: "review" }),
    },
    {
      title: "What really happened",
      text: "These are real patients from past hospital records, so we already know how each stay turned out. That's our answer key. Septris never saw it. Red rings mark beds that developed sepsis within 12 hours.",
      apply: (go) => go({ showKey: true, camera: s.bed, tab: "bed", selectedBed: s.bed }),
    },
    {
      title: "Now you drive",
      text: "Click any bed to open its chart. Use the review buttons at the top to move through the shift, or try the example buttons. You can also type or say commands like “show bed 6”, “next review” or “show me a miss”.",
      apply: (go) => go({ showKey: true, camera: "overview", tab: "review" }),
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
