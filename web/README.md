# Septris 3D (web/)

A static 3D website: a 20-bed ICU you can orbit and zoom, with each bed's
risk on its floor ring and bedside monitor, Septris's pick lit in blue, an
answer key, clickable beds, a guided tour, and typed or spoken commands.

> Prototype. Not medical advice.

## Run it

```bash
cd web
python -m http.server 8000     # then open http://localhost:8000
```

It needs to be served over http (opening index.html as a file won't load the
data). Voice input uses the browser's speech recognition (Chrome, Edge,
Safari) and needs microphone permission; typed commands always work.

To host it, publish the `web/` folder as a static site (GitHub Pages, Netlify,
Vercel). Nothing is built or installed: three.js loads from a CDN.

## Data

`data/septris.json` is written by `python scripts/13_web_export.py` from
`app/artifacts/` (run after `05_app_artifacts.py`). The site reads nothing else.

## Where things live

| File | What it does |
| --- | --- |
| `index.html`, `styles.css` | Page shell and all styling (colour tokens at the top of the CSS) |
| `src/main.js` | Wires everything: actions (`goSlot`, `selectBed`, `example`, `runCommand`), rendering, events |
| `src/store.js` | Shared state + `set()` / `subscribe()` |
| `src/data.js` | Loads the JSON; verdict wording |
| `src/scene/world.js` | Renderer, lights, bloom, room, nurse station |
| `src/scene/beds.js` | The 20 bed bays; `update()` restyles them for the current review |
| `src/scene/camera.js` | Camera moves (`overview()`, `bed(n)`) |
| `src/ui/panel.js` | Right panel: This review, Bed chart, Results, About |
| `src/ui/chart.js` | Canvas chart of one patient's stay |
| `src/ui/tour.js` | The 5-step guided tour |
| `src/commands.js` | Sentence → action rules, shared by voice and typing |
| `src/voice.js` | Speech recognition and read-aloud |

## Adding things

- **A new command:** add one line to `RULES` in `src/commands.js`, then handle
  its action type in `runCommand` in `src/main.js`.
- **A new object in the room:** add meshes in `buildRoom` (`world.js`) or per
  bed in `createBeds` (`beds.js`).
- **A new panel tab:** add a tab button and `tabbody` in `index.html`, an
  HTML function in `ui/panel.js`, and one line in `renderPanel` (`main.js`).
- **Anything that reacts to time or selection:** `subscribe()` to the store.

## Commands

next review · previous review · next shift · previous shift · review 3 ·
show bed 6 · zoom out · play · pause · show me a catch · show me a miss ·
show me a false alarm · why? · answer key on/off · results · start tour

## Credits

- Night-sky background: shader adapted from the **Galaxy** background in [React Bits](https://reactbits.dev/backgrounds/galaxy) by David Haz (MIT + Commons Clause), ported to a three.js material in `src/scene/galaxy.js`.
