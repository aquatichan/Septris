// Turns a typed or spoken sentence into an action. Voice and the command bar
// share this parser, so adding a command here makes it work in both.
// Each rule: [regex, (match) => action]. Actions are handled in main.js.

const WORDS = { one: 1, two: 2, to: 2, too: 2, three: 3, four: 4, for: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9,
  ten: 10, eleven: 11, twelve: 12, thirteen: 13, fourteen: 14, fifteen: 15, sixteen: 16, seventeen: 17, eighteen: 18,
  nineteen: 19, twenty: 20 };

const num = (s) => (/^\d+$/.test(s) ? Number(s) : WORDS[s]);

const RULES = [
  [/\b(bed|patient)\s+(\d+|[a-z]+)\b/, (m) => (num(m[2]) ? { type: "bed", bed: num(m[2]) } : null)],
  [/\b(next|forward)\s+(review|check)\b|^next$/, () => ({ type: "review", delta: 1 })],
  [/\b(previous|last|back)\s+(review|check)\b|^back$|^previous$/, () => ({ type: "review", delta: -1 })],
  [/\bnext\s+shift\b/, () => ({ type: "shift", delta: 1 })],
  [/\b(previous|last)\s+shift\b/, () => ({ type: "shift", delta: -1 })],
  [/\breview\s+(\d|one|two|three|four|five)\b/, (m) => ({ type: "reviewN", n: num(m[1]) })],
  [/\b(miss|missed)\b/, () => ({ type: "example", kind: "miss" })],
  [/\bfalse\s*alarm\b/, () => ({ type: "example", kind: "false" })],
  [/\b(catch|caught|good)\b/, () => ({ type: "example", kind: "good" })],
  [/\b(zoom out|overview|whole unit|everything)\b/, () => ({ type: "overview" })],
  [/\b(play|start)\b(?!.*tour)/, () => ({ type: "play", on: true })],
  [/\b(pause|stop)\b/, () => ({ type: "play", on: false })],
  [/\b(why|explain|reason)/, () => ({ type: "explain" })],
  [/\b(answer\s*key|outcomes?)\s*(off|hide)|hide\s+(the\s+)?(answer|outcomes?)/, () => ({ type: "key", on: false })],
  [/\banswer\s*key|outcomes?|show\s+(the\s+)?answer/, () => ({ type: "key", on: true })],
  [/\bresults?\b|how well/, () => ({ type: "tab", tab: "results" })],
  [/\btour\b/, () => ({ type: "tour" })],
  [/\b(queue|ranking|priority list|line)\b/, () => ({ type: "tab", tab: "queue" })],
  [/\b(how (does )?it works?|model)\b/, () => ({ type: "tab", tab: "model" })],
  [/\b(help|what can i say|faq|questions?)\b/, () => ({ type: "tab", tab: "faq" })],
];

export function parse(text) {
  const t = text.toLowerCase().replace(/[.,!?]/g, " ").replace(/\s+/g, " ").trim();
  for (const [re, fn] of RULES) {
    const m = t.match(re);
    if (m) {
      const a = fn(m);
      if (a) return a;
    }
  }
  return null;
}
