// Tiny app state with subscribe/set. Every UI piece and the 3D scene read
// from `state` and re-render when it changes, so new features only need to
// call set({...}) and subscribe(fn).

export const state = {
  data: null,          // loaded septris.json (see data.js)
  slot: 0,             // index into data.slots (one Septris review)
  selectedBed: null,   // bed number whose chart is open (1..20)
  focus: null,         // active example: {kind, slot, bed?}
  showKey: true,       // show the answer key (what really happened)
  narrate: false,      // read picks aloud
  playing: false,      // auto-advance through reviews
  tab: "review",       // right panel tab
  tourStep: null,      // null when the tour is closed
};

const subs = new Set();

export function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

export function set(patch) {
  Object.assign(state, patch);
  for (const fn of subs) fn(state, patch);
}
