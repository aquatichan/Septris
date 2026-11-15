// Turns a typed or spoken sentence into an action. Voice and the command bar
// share this parser, so adding a command here makes it work in both.
// Each rule: [regex, (match) => action]. Actions are handled in main.js.

const WORDS = { one: 1, two: 2, to: 2, too: 2, three: 3, four: 4, for: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
  ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
  nineteen: 19, twenty: 20 };

const num = (s) => (/^\d+$/.test(s) ? Number(s) : WORDS[s]);

const RULES = [
  [/\b(add|admit)\b/, (m, t) => ({ type: "admit", details: admitDetails(t) })],
  [/\bnew patient\b|\bcheck ?in\b/, () => ({ type: "admit", details: null })],
  [/\b(bed|patient)\s+(?:number\s+|no\.?\s+|#\s*)?(\d+|[a-z]+)\b/, (m) => (num(m[2]) ? { type: "bed", bed: num(m[2]) } : null)],
  [/\b(first[- ]?person|be the nurse|walk (around|the ward)|roam)\b/, () => ({ type: "firstperson" })],
  [/\b(leave|exit|quit)\b/, () => ({ type: "leave" })],
  [/\b(replay|play)\s+(the\s+)?intro\b|\belevator\b/, () => ({ type: "intro" })],
  [/\b(sound|audio|volume)\s+(off|mute)|\bmute\b/, () => ({ type: "sound", on: false })],
  [/\b(sound|audio|volume)\s+on\b|\bunmute\b/, () => ({ type: "sound", on: true })],
  [/\b(open|show)\s+(the\s+)?chart\b|\bpatient tab\b/, () => ({ type: "tab", tab: "patient" })],
  [/\bpriority\b|\bcheck next\b|\bwho('s| is) next\b/, () => ({ type: "tab", tab: "priority" })],
  [/\b(next|forward)\s+(review|check)\b|^next$/, () => ({ type: "review", delta: 1 })],
  [/\b(previous|last|back)\s+(review|check)\b|^back$|^previous$/, () => ({ type: "review", delta: -1 })],
  [/\bnext\s+shift\b/, () => ({ type: "shift", delta: 1 })],
  [/\b(previous|last)\s+shift\b/, () => ({ type: "shift", delta: -1 })],
  [/\b(?:review|check)\s+(\d|one|two|three|four|five)\b/, (m) => ({ type: "reviewN", n: num(m[1]) })],
  [/\b(miss|missed)\b/, () => ({ type: "example", kind: "miss" })],
  [/\bfalse\s*alarm\b/, () => ({ type: "example", kind: "false" })],
  [/\b(catch|caught|good)\b/, () => ({ type: "example", kind: "good" })],
  [/\b(zoom out|overview|whole unit|everything|ward)\b/, () => ({ type: "overview" })],
  [/\b(play|start)\b(?!.*(tour|intro))/, () => ({ type: "play", on: true })],
  [/\b(pause|stop)\b/, () => ({ type: "play", on: false })],
  [/\b(why|explain|reason)/, () => ({ type: "explain" })],
  [/\b(answer\s*key|outcomes?)\s*(off|hide)|hide\s+(the\s+)?(answer|outcomes?)/, () => ({ type: "key", on: false })],
  [/\banswer\s*key|outcomes?|show\s+(the\s+)?answer/, () => ({ type: "key", on: true })],
  [/\bresults?\b|how well/, () => ({ type: "page", page: "results" })],
  [/\btour\b/, () => ({ type: "tour" })],
  [/\b(queue|ranking|priority list|line)\b/, () => ({ type: "tab", tab: "queue" })],
  [/\b(how (does )?it works?|model)\b/, () => ({ type: "page", page: "model" })],
  [/\b(help|what can i say|faq|questions?)\b/, () => ({ type: "page", page: "faq" })],
];

// Readings the "add a patient" sentence can carry, with the words people use for them.
const READINGS = {
  HR: "heart rate|pulse|hr",
  MAP: "blood pressure|pressure|map",
  Resp: "breathing rate|respiratory rate|respiration rate|respirations?|breathing|resp rate",
  Temp: "temperature|temp|fever",
  O2Sat: "oxygen saturation|oxygen level|oxygen|o2 sats?|o2|sats?|spo2",
  Lactate: "lactate",
  WBC: "white blood cells?(?: count)?|white cells?(?: count)?|white count|wbc",
  Creatinine: "creatinine",
  Platelets: "platelets?(?: count)?",
};
const NUM = "(\\d+(?:\\.\\d+)?)";
const NOT_NAMES = new Set(["a", "an", "the", "new", "patient", "man", "woman", "male", "female", "who", "with", "to", "bed",
  "aged", "age", "someone", "somebody", "person", "one", "another", "him", "her", "them"]);

/**
 * Pulls patient details out of a sentence such as
 * "add John who is 32 years old with heart rate 118 and temperature 38.6 to bed 4 for 2 days".
 * Returns null when the sentence carries no details ("add a patient").
 */
export function admitDetails(t) {
  const d = { values: {} };
  const name = t.match(/\b(?:add|admit)\s+(?:a\s+)?(?:new\s+)?(?:patient\s+)?(?:named\s+|called\s+)?([a-z][a-z'-]*)(?:\s+([a-z][a-z'-]*))?/);
  if (name && !NOT_NAMES.has(name[1])) {
    const cap = (w) => w.charAt(0).toUpperCase() + w.slice(1);
    d.name = cap(name[1]) + (name[2] && !NOT_NAMES.has(name[2]) && !/^(is|was|aged?|in|for|on|at|he|she)$/.test(name[2]) ? ` ${cap(name[2])}` : "");
  }
  const age = t.match(/\b(\d{1,3})[\s-]*(?:years?|yrs?|yo\b|y o\b)/) || t.match(/\baged?\s+(\d{1,3})\b/) || t.match(/\b(?:who|that|he|she) (?:is|'s) (\d{1,3})\b(?!\s*(?:bpm|beats|breaths|degrees|mmhg|%))/);
  if (age) d.age = Number(age[1]);
  if (/\b(woman|female|she|her|girl|lady)\b/.test(t)) d.sex = "F";
  else if (/\b(man|male|he|him|his|guy)\b/.test(t)) d.sex = "M";
  const bed = t.match(/\bbed\s+(\d+|[a-z]+)\b/);
  if (bed && num(bed[1])) d.bed = num(bed[1]);
  const stay = t.match(/\b(?:for|stay(?:ing|s)?(?: of)?)\s+(\d+)\s*(hours?|hrs?|days?)/);
  if (stay) d.stay = Number(stay[1]) * (stay[2].startsWith("d") ? 24 : 1);
  for (const [key, words] of Object.entries(READINGS)) {
    const after = t.match(new RegExp(`\\b(?:${words})\\s*(?:of|is|at|was|as|=|:)?\\s*${NUM}`));
    const before = t.match(new RegExp(`${NUM}\\s*(?:%|percent|bpm|degrees?)?\\s*(?:${words})\\b`));
    const hit = after || before;
    if (hit) d.values[key] = Number(hit[1]);
  }
  const empty = !d.name && d.age == null && !d.sex && d.bed == null && d.stay == null && !Object.keys(d.values).length;
  return empty ? null : d;
}

export function parse(text) {
  // keep decimal points ("38.6") but drop other punctuation
  const t = text.toLowerCase().replace(/(?<!\d)[.,!?]|[.,!?](?!\d)/g, " ").replace(/\s+/g, " ").trim();
  for (const [re, fn] of RULES) {
    const m = t.match(re);
    if (m) {
      const a = fn(m, t);
      if (a) return a;
    }
  }
  return null;
}
