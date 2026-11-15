// Loads web/data/septris.json (built by scripts/13_web_export.py) and turns
// its column tables into objects, plus helpers shared by the UI and scene.

function rows(table) {
  const { cols, rows } = table;
  return rows.map((r) => Object.fromEntries(cols.map((c, i) => [c, r[i]])));
}

export async function loadData(url = "data/septris.json") {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Could not load ${url} (${res.status})`);
  const raw = await res.json();
  const slots = rows(raw.slots);
  const bedsByHour = new Map();
  for (const b of rows(raw.beds)) {
    if (!bedsByHour.has(b.unit_hour)) bedsByHour.set(b.unit_hour, []);
    bedsByHour.get(b.unit_hour).push(b);
  }
  const shifts = new Map();
  slots.forEach((s, i) => {
    if (!shifts.has(s.shift)) shifts.set(s.shift, []);
    shifts.get(s.shift).push(i);
  });
  return { ...raw, slots, bedsByHour, shifts, shiftIds: [...shifts.keys()].sort((a, b) => a - b) };
}

// Entered patients (manual.js) are layered on through data.overlay, so always
// read beds and the current review through these two helpers.
export const beds = (data, slotIndex) => data.overlay?.get(slotIndex)?.rows ?? (data.bedsByHour.get(data.slots[slotIndex].unit_hour) || []);
export const slotAt = (data, slotIndex) => data.overlay?.get(slotIndex)?.slot ?? data.slots[slotIndex];
export const patient = (data, p) => data.patients[p];

export function ordinal(n) {
  const s = n % 100 >= 11 && n % 100 <= 13 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th";
  return `${n}${s}`;
}

// Plain-language verdicts for a review class (known only in hindsight).
export const VERDICT = {
  early6: { icon: "✓", head: "Sepsis accurately predicted", tone: "good" },
  early: { icon: "•", head: "Sepsis predicted, but with little warning", tone: "warn" },
  late: { icon: "!", head: "Flagged too late", tone: "bad" },
  false: { icon: "○", head: "False alarm: no sepsis followed", tone: "grey" },
  uncertain: { icon: "–", head: "Not scored", tone: "grey" },
  manual: { icon: "–", head: "No outcome to check", tone: "grey" },
};

export function whatHappened(cls, lead, bed) {
  if (cls === "manual") return `Bed ${bed} is a patient you entered, so there is no hospital record to check this pick against.`;
  if (cls === "early6") return `Sepsis was recorded ${Math.round(lead)} hours after this review, inside the 6–12 hour early-warning window.`;
  if (cls === "early") return `Sepsis was recorded ${Math.round(lead)} hours after this review: ahead of time, but with less than the 6 hours of warning we aim for.`;
  if (cls === "late") {
    const ago = -lead;
    return `Bed ${bed} already had sepsis when it was reviewed (recorded ${ago === 0 ? "in the same hour" : `${Math.round(ago)} hours earlier`}).`;
  }
  if (cls === "uncertain") return `Bed ${bed} already had sepsis on arrival, so this review isn't scored.`;
  if (lead != null && lead > 12) return `Bed ${bed} didn't develop sepsis until ${Math.round(lead)} hours later, too far ahead to count as a catch.`;
  return `Bed ${bed} did not develop sepsis in the next 12 hours.`;
}

export function shiftLabel(s) {
  return s.shift_name === "Night shift" ? "Night shift · 7 PM–7 AM" : "Day shift · 7 AM–7 PM";
}
