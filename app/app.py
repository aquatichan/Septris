"""Septris demo app (Gradio). Reads only app/artifacts/.

    python app/app.py            # local, http://127.0.0.1:7860
    python app/app.py --share    # public link (Colab)

This project is a prototype and is not medical advice.
"""

import argparse
import html
import json
from pathlib import Path

import gradio as gr
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ART = Path(__file__).resolve().parent / "artifacts"
DISCLAIMER = "This project is a prototype and is not medical advice."

slots = pd.read_parquet(ART / "slots.parquet").reset_index(drop=True)
beds = pd.read_parquet(ART / "beds.parquet")
timelines = pd.read_parquet(ART / "timelines.parquet")
reviews = pd.read_parquet(ART / "reviews.parquet")
meta = pd.read_parquet(ART / "patients.parquet").set_index("patient_id")
table = pd.read_csv(ART / "results_table.csv")
diffs = pd.read_csv(ART / "paired_differences.csv")
examples = json.loads((ART / "examples.json").read_text())
info = json.loads((ART / "demo.json").read_text())
K, NBEDS = info["k"], info["beds"]
beds_by_hour = {h: g for h, g in beds.groupby("unit_hour")}
tl_by_pid = {p: g for p, g in timelines.groupby("patient_id")}
rev_by_pid = reviews.groupby("patient_id")["record_hour"].apply(list).to_dict()
shift_ids = sorted(slots["shift"].unique())
slots_in_shift = {s: list(g.index) for s, g in slots.groupby("shift")}

BLUE, RED, GREEN, AMBER, GREY = "#1d4ed8", "#b42318", "#067647", "#b54708", "#475467"

# plain-language verdicts: icon, headline, colour, background
VERDICT = {
    "early6": ("✅", "Caught in time", GREEN, "#ecfdf3"),
    "early": ("🟡", "Caught, but with little warning", AMBER, "#fffaeb"),
    "late": ("🟠", "Too late", "#c4320a", "#fff4ed"),
    "false": ("⚪", "False alarm: this patient turned out fine", GREY, "#f2f4f7"),
    "uncertain": ("➖", "Doesn't count", GREY, "#f2f4f7"),
}


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def what_happened(cls, lead, bed):
    """One plain sentence about what happened to the reviewed patient."""
    if cls == "early6":
        return f"Bed {bed} developed sepsis {lead:.0f} hours after this review. That's enough warning for the team to act early."
    if cls == "early":
        return (f"Bed {bed} developed sepsis {lead:.0f} hour{'s' if lead != 1 else ''} after this review: "
                "caught before it happened, but with less than the 6 hours of warning we aim for.")
    if cls == "late":
        ago = -lead
        return (f"Bed {bed} already had sepsis when it was reviewed (it was recorded "
                f"{'in the same hour' if ago == 0 else f'{ago:.0f} hours earlier'}).")
    if cls == "uncertain":
        return f"Bed {bed} already had sepsis when they arrived in the ICU, so this review is not scored either way."
    if not np.isnan(lead) and lead > 12:
        return (f"Bed {bed} did not develop sepsis until {lead:.0f} hours later, too far ahead for this review to "
                "count as a catch.")
    return f"Bed {bed} did not develop sepsis in the next 12 hours."


CSS = """
.gradio-container {max-width: 1180px !important; margin: auto; background: #f8fafc;}
.sp, .sp * {box-sizing: border-box; font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;}
.sp {color: #101828; font-size: 16px; line-height: 1.5;}
.sp-banner {background: #fff4e5; border: 1px solid #f79009; border-radius: 10px; padding: 8px 14px;
             color: #7a2e0e; font-weight: 600; font-size: 14px;}
.sp-hero h1 {font-size: 34px; margin: 8px 0 0; letter-spacing: -0.02em;}
.sp-hero .lead {font-size: 18px; color: #344054; margin: 2px 0 10px;}
.sp-box {background: #fff; border: 1px solid #e4e7ec; border-radius: 12px; padding: 14px 18px;}
.sp-box p {margin: 4px 0;}
.sp-label {font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #667085; font-weight: 700;
            margin: 0 0 4px;}
.sp-shift {background: #101828; color: #fff; border-radius: 12px; padding: 10px 16px; text-align: center;}
.sp-shift .big {font-size: 21px; font-weight: 800; color: #fff;}
.sp-shift .sub {font-size: 14px; color: #d0d5dd;}
.sp-pick h2 {font-size: 24px; color: #1d4ed8; margin: 0 0 6px;}
.sp-pick ul {margin: 4px 0 6px 20px; padding: 0;}
.sp-small {font-size: 13.5px; color: #667085;}
.sp-key {background: #fffcf5; border: 2px dashed #f79009; border-radius: 12px; padding: 14px 18px;}
.sp-key .verdict {border-radius: 10px; padding: 10px 12px; margin: 8px 0; font-size: 16px;}
.sp-key .verdict b {font-size: 18px;}
.sp-note {background: #eff8ff; border: 1px solid #84caff; border-radius: 10px; padding: 10px 14px; color: #1849a9;}
.sp-sec {font-size: 19px; font-weight: 800; margin: 14px 0 0; color: #101828;}
.sp-sechelp {font-size: 14.5px; color: #475467; margin: 0 0 4px;}
button.bedbtn {display: block !important; white-space: pre-line !important; text-align: left !important; justify-content: flex-start !important;
               align-items: flex-start !important; min-height: 96px; line-height: 1.35 !important;
               font-weight: 500 !important; font-size: 14px !important; border: 2px solid #d0d5dd !important;
               background: #fff !important; color: #101828 !important; padding: 8px 10px !important;}
button.bedbtn::first-line {font-weight: 800; font-size: 16px;}
button.bed-high {background: #fef3f2 !important; border-color: #fda29b !important;}
button.bed-med {background: #fffaeb !important; border-color: #fec84b !important;}
button.bed-snooze {background: #f2f4f7 !important; color: #667085 !important; border-style: dashed !important;}
button.bed-empty {background: #f9fafb !important; color: #98a2b3 !important;}
button.bed-pick {border: 4px solid #1d4ed8 !important; box-shadow: 0 0 0 3px #c7d7fe !important;}
button.bed-sel {outline: 3px solid #101828 !important; outline-offset: 2px;}
button.bed-miss {border: 4px solid #b42318 !important;}
button.revbtn {white-space: pre-line !important; line-height: 1.3 !important;}
.sp-results .num {font-size: 40px; font-weight: 800; line-height: 1;}
.sp-dots {display: grid; grid-template-columns: repeat(20, 1fr); gap: 3px; max-width: 420px; margin: 8px 0;}
.sp-dots span {aspect-ratio: 1; border-radius: 50%; background: #e4e7ec;}
.sp-row {display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px;}
.sp-tiles {display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-top: 8px;}
.sp-tile {border: 2px solid #d0d5dd; border-radius: 10px; padding: 8px 10px; background: #fff; font-size: 14px;
          line-height: 1.35; min-height: 74px;}
.sp-tile b {font-size: 16px;}
.sp-tile.pick {border: 4px solid #1d4ed8; box-shadow: 0 0 0 3px #c7d7fe;}
.sp-tile.snooze {background: #f2f4f7; color: #667085; border-style: dashed;}
.sp-tile.high {background: #fef3f2; border-color: #fda29b;}
.sp-tile.med {background: #fffaeb; border-color: #fec84b;}
.sp-tile.dim {opacity: .45;}
.sp-steps {display: flex; gap: 6px; margin: 4px 0 10px; flex-wrap: wrap;}
.sp-steps span {padding: 4px 12px; border-radius: 999px; background: #eaecf0; color: #475467; font-size: 13.5px;
                font-weight: 600;}
.sp-steps span.on {background: #1d4ed8; color: #fff;}
.sp-tour h2 {font-size: 26px; margin: 2px 0 8px; color: #101828;}
.sp-tour p.big {font-size: 18px; color: #344054; margin: 4px 0 10px;}
.sp-faq h3 {font-size: 18px; margin: 18px 0 4px;}
.sp-faq p, .sp-faq li {color: #344054;}
@media (max-width: 760px) {
  .gradio-container, .gradio-container .main {width: 100% !important; max-width: 100vw !important; min-width: 0 !important;}
  body {overflow-x: hidden;}
  .sp-hero h1 {font-size: 26px;}
  button.bedbtn {min-height: 84px; font-size: 13px !important;}
  .sp-tiles {grid-template-columns: repeat(2, 1fr);}
}
"""

FORCE_LIGHT = """() => {
  document.documentElement.classList.remove('dark');
  document.body && document.body.classList.remove('dark');
}"""


def esc(s):
    return html.escape(str(s))


# ------------------------------------------------------------------ the ICU tab
def shift_html(i):
    s = slots.iloc[i]
    first = slots.iloc[slots_in_shift[s["shift"]][0]]
    night = s.shift_name == "Night shift"
    hours = "7 PM to 7 AM" if night else "7 AM to 7 PM"
    return (f"<div class='sp sp-shift'><div class='big'>Day {first.day} · {s.shift_name} ({hours})</div>"
            f"<div class='sub'>Shift {s['shift']} of {len(shift_ids)} in this replay</div></div>")


def driver_html(s):
    """Which of the two models raised this bed (only for the 'whichever is more worried' mix)."""
    if info.get("kind") != "max" or "driver" not in s or pd.isna(s.get("pct_gru", np.nan)):
        return ""
    lg, gr_ = s.pct_lgbm, s.pct_gru
    both = min(lg, gr_) >= 90
    who = ("<b>Both models</b> were worried" if both else
           f"Raised by <b>{'the GRU' if s.driver == 'GRU' else 'LightGBM'}</b>")
    return (f"<p class='sp-small' style='font-size:14.5px'>🤝 {who}: GRU risk {gr_:.0f}, LightGBM risk {lg:.0f}. "
            "Septris uses whichever is higher.</p>")


def pick_html(s, n_cand):
    reasons = [r for r in s.reasons.split(" | ") if r]
    why = ("<ul>" + "".join(f"<li>{esc(r[0].upper() + r[1:])}</li>" for r in reasons) + "</ul>") if reasons \
        else "<p>Several small changes together, none big on its own.</p>"
    return (f"<div class='sp sp-box sp-pick'><div class='sp-label'>Review {s.check} of {K} · {s.clock}</div>"
            f"<h2>👉 Septris says: review Bed {s.bed} now</h2>"
            f"<p>Of the {n_cand} beds that haven't had a review in the last 12 hours, Bed {s.bed} has the "
            f"highest risk right now.</p>{driver_html(s)}<p><b>What stood out in Bed {s.bed}'s chart:</b></p>{why}"
            f"<p class='sp-small'>Septris only uses data recorded up to {s.clock}. These are warning patterns, "
            f"not a diagnosis: the nurse reads the chart and decides.</p></div>")


def key_html(s):
    icon, head, fg, bg = VERDICT[s.review_class]
    rnd = ""
    if s.random_bed is not None and not pd.isna(s.random_bed):
        ri, rh, rfg, _ = VERDICT[s.random_class]
        rnd = (f"<p>🎲 <b>If the nurse had picked a bed at random</b>, they would have reviewed Bed "
               f"{int(s.random_bed)}: <b style='color:{rfg}'>{ri} {rh}</b>.</p>")
    n = s.sepsis_so_far
    score = (f"<p class='sp-small' style='margin-top:8px'><b>Score so far in this replay</b> (day 1 to day {s.day}): "
             f"{n} patients developed sepsis. Septris caught <b>{s.sb_caught_so_far}</b> of them in time; "
             f"random picking caught <b>{s.random_caught_so_far}</b>.</p>") if n else ""
    return (f"<div class='sp sp-key'><div class='sp-label'>📖 Answer key: what really happened</div>"
            f"<p class='sp-small'>Septris could not see this. We can, because these are real patients from past "
            f"hospital records, so we know how their stay turned out.</p>"
            f"<div class='verdict' style='background:{bg}; border:1px solid {fg}55'>"
            f"<b style='color:{fg}'>{icon} {head}.</b><br>{esc(what_happened(s.review_class, s.lead_hours, s.bed))}"
            f"</div>{rnd}{score}</div>")


def bed_label(r, show_key):
    if r is None:
        return "Empty bed", ["bedbtn", "bed-empty"]
    cls = ["bedbtn"]
    if r.picked:
        lines = [f"Bed {r.bed}", "👉 Septris's pick", f"Risk {r.percentile:.0f} of 100"]
        cls.append("bed-pick")
    elif r.snoozed:
        lines = [f"Bed {r.bed}", f"✓ Reviewed {r.hours_since_check} h ago", "(skipped for now)"]
        cls.append("bed-snooze")
    else:
        lines = [f"Bed {r.bed}", f"{ordinal(int(r.rank))} in line", f"Risk {r.percentile:.0f} of 100"]
    if not r.snoozed:
        cls.append("bed-high" if r.tier == "High" else "bed-med" if r.tier == "Medium" else "bed-low")
    if show_key:
        h = r.hours_to_sepsis
        if meta.loc[r.patient_id, "group"] == "uncertain_onset":
            lines.append("📖 septic on arrival")
        elif not pd.isna(h) and 0 < h <= 12:
            lines.append(f"📖 ⚠ sepsis in {h:.0f} h")
        elif not pd.isna(h) and h <= 0:
            lines.append("📖 already has sepsis")
    return "\n".join(lines), cls


def bed_updates(b, show_key, sel_bed, miss_bed):
    by_bed = {int(r.bed): r for r in b.itertuples()}
    out = []
    for i in range(1, NBEDS + 1):
        r = by_bed.get(i)
        label, cls = bed_label(r, show_key)
        if r is None:
            label = f"Bed {i}\nEmpty"
        if i == sel_bed:
            cls.append("bed-sel")
        if i == miss_bed:
            cls.append("bed-miss")
        out.append(gr.update(value=label, elem_classes=cls))
    return out


def chart(i, bed):
    s = slots.iloc[i]
    b = beds_by_hour[s.unit_hour]
    row = b[b["bed"] == bed]
    if row.empty:
        return f"### Bed {bed} is empty right now", None
    row = row.iloc[0]
    pid, now = row.patient_id, int(row.record_hour)
    t = tl_by_pid[pid]
    m = meta.loc[pid]
    onset = m["t_onset"]
    end = int(t["hour"].max())
    fig, axes = plt.subplots(3, 1, figsize=(10, 6.6), sharex=True, gridspec_kw={"height_ratios": [1.7, 1, 1]})
    for a in axes:
        a.axvspan(now + 0.5, end + 1, color="#eaecf0", lw=0, zorder=0)
        a.axvline(now, color="#101828", lw=2, zorder=3)
        if not np.isnan(onset):
            a.axvspan(max(0, onset - 12), onset - 6, color="#d1fadf", lw=0, zorder=0)
            a.axvline(onset, color=RED, lw=2.5, zorder=3)
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", color="#eaecf0")
    ax = axes[0]
    ax.plot(t["hour"], t["percentile"], color=BLUE, lw=2.4, zorder=4, label="Septris risk (0–100)")
    first = True
    for h in rev_by_pid.get(pid, []):
        y = float(t.loc[t["hour"] == h, "percentile"].iloc[0])
        ax.plot([h], [y], marker="v", ms=12, color=BLUE, mec="white", zorder=5,
                label="Septris had the nurse review this chart" if first else None, ls="none")
        first = False
    x0 = max(0, now - 48)
    x1 = min(end + 1, max(now, 0 if np.isnan(onset) else onset) + 8)
    ax.set_ylim(0, 122)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Septris risk\n(0–100)")
    ax.text(now, 112, "now ", ha="right", fontsize=10, fontweight="bold")
    if x1 - now > 10:
        ax.text((now + x1) / 2, 6, "the future:\nfrom the records,\nhidden from Septris",
                ha="center", fontsize=9, color="#475467")
    if not np.isnan(onset):
        ax.text(onset, 103, " sepsis recorded", fontsize=10, color=RED, fontweight="bold", ha="left"
                if onset < x1 - 6 else "right")
        if onset - 6 > x0:
            ax.text(onset - 9, 96, "caught-in-\ntime window", fontsize=8.5, color=GREEN, va="top", ha="center")
    for a in axes:
        a.set_xlim(x0 - 0.5, x1)
    ax.legend(loc="lower left", fontsize=8.5, frameon=False)
    for a, col, lab in ((axes[1], "HR", "Heart rate\n(beats/min)"), (axes[2], "MAP", "Blood pressure\n(MAP, mmHg)")):
        a.plot(t["hour"], t[col], marker="o", ms=2.5, lw=1, color="#344054", zorder=4)
        a.set_ylabel(lab, fontsize=10)
    axes[-1].set_xlabel("Hours since this patient arrived in the ICU")
    fig.tight_layout()
    title = (f"### Bed {bed}'s chart\nAge {m['age']:.0f}, in the ICU for {now + 1} hours so far. "
             "The black line is this moment. Everything in the grey area happened later: we know it from the "
             "records, but Septris could not see it.")
    return title, fig


def render(i, sel_bed, focus, show_key):
    i = int(i)
    s = slots.iloc[i]
    b = beds_by_hour[s.unit_hour]
    n_cand = int(b["candidates"].iloc[0])
    focus = focus if (focus and focus.get("slot") == i) else None
    miss_bed = focus["bed"] if focus and focus.get("kind") == "miss" else None
    if sel_bed is None or b[b["bed"] == sel_bed].empty:
        sel_bed = miss_bed or int(s.bed)
    note = ""
    if focus:
        if focus["kind"] == "miss":
            r = b[b["bed"] == miss_bed].iloc[0]
            place = f"{ordinal(int(r['rank']))} in line" if r["rank"] else "recently reviewed"
            note = (f"<div class='sp sp-note'><b>❌ Example of a miss.</b> Bed {miss_bed} (red border) will develop "
                    f"sepsis {r['hours_to_sepsis']:.0f} hours after this moment. But right now Septris has it "
                    f"<b>{place}</b>, and the nurse only has time for one review at {s.clock}, so Bed {miss_bed} "
                    f"is not reviewed in time. Its chart is open below.</div>")
        else:
            note = {"good": f"<div class='sp sp-note'><b>✅ Example of a catch.</b> Septris points the nurse to Bed "
                            f"{s.bed}, which develops sepsis {s.lead_hours:.0f} hours later. "
                            "Click the other example buttons to see more.</div>",
                    "false": f"<div class='sp sp-note'><b>⚪ Example of a false alarm.</b> Septris points the nurse "
                             f"to Bed {s.bed}, but that patient turns out fine. This is the most common outcome: "
                             "only about 8% of ICU patients ever develop sepsis.</div>"}[focus["kind"]]
    rev = []
    ids = slots_in_shift[s["shift"]]
    for j in range(K):
        if j < len(ids):
            sj = slots.iloc[ids[j]]
            rev.append(gr.update(value=f"Review {sj.check}\n{sj.clock}", visible=True,
                                 variant="primary" if ids[j] == i else "secondary"))
        else:
            rev.append(gr.update(visible=False))
    title, fig = chart(i, sel_bed)
    return [i, sel_bed, note, shift_html(i), *rev, pick_html(s, n_cand), key_html(s),
            f"<div class='sp sp-sec'>All {NBEDS} beds at {s.clock}</div>"
            f"<div class='sp sp-sechelp'>Click any bed to open its chart below. Beds are numbered like a real "
            f"unit; when a patient leaves, a new patient takes the bed.</div>",
            *bed_updates(b, show_key, sel_bed, miss_bed), title, fig]


def go_shift(i, d):
    sh = slots.iloc[int(i)]["shift"]
    k = shift_ids.index(sh) + d
    k = min(max(k, 0), len(shift_ids) - 1)
    return slots_in_shift[shift_ids[k]][0]


def go_review(i, j):
    ids = slots_in_shift[slots.iloc[int(i)]["shift"]]
    return ids[min(j, len(ids) - 1)]


def jump(kind, counter):
    xs = examples[kind]
    c = dict(counter or {})
    c[kind] = c.get(kind, -1) + 1
    x = xs[c[kind] % len(xs)]
    if kind == "miss":
        return x["slot"], {"slot": x["slot"], "bed": x["bed"], "kind": "miss"}, c
    return int(x), {"slot": int(x), "kind": kind}, c


# ------------------------------------------------------------------ results tab
NAMES = {"septris": f"Septris ({info['policy_label']})", "lgbm_combined": "LightGBM alone (our first model)",
         "temporal_gru": "Miheer's GRU alone (deep learning)", "sirs": "SIRS checklist (used in hospitals)",
         "random": "Random picking"}
COLORS = {"septris": BLUE, "lgbm_combined": "#84adff", "temporal_gru": "#7a5af8", "sirs": AMBER, "random": "#98a2b3"}


def pol_name(key, T, home=True):
    if key in ("sirs", "random"):
        return key
    H = T if home else ("B" if T == "A" else "A")
    return f"{H}:{info['policy_key']}" if key == "septris" else f"{H}:{key}"


def res(T, key, k, home=True):
    r = table[(table.test == T) & (table.k == k) & (table.subgroup == "all") & (table.policy == pol_name(key, T, home))]
    return None if r.empty else r.iloc[0]


def dots(share, color):
    n = int(round(100 * share))
    return "<div class='sp-dots'>" + "".join(
        f"<span style='background:{color if j < n else '#e4e7ec'}'></span>" for j in range(100)) + "</div>"


def results_html(k):
    k = int(k)
    cards = []
    for T in ("A", "B"):
        sp, rnd = res(T, "septris", k), res(T, "random", k)
        if sp is None:
            continue
        cards.append(
            f"<div class='sp-box'><div class='sp-label'>Hospital {T} · {int(sp.eligible)} patients who got sepsis</div>"
            f"<p>Out of every <b>100</b> patients who developed sepsis, Septris had the nurse review about</p>"
            f"<div class='num' style='color:{BLUE}'>{100 * sp.caught6:.0f}</div>{dots(sp.caught6, BLUE)}"
            f"<p>of them <b>6 to 12 hours before</b> sepsis was recorded. Picking at random: about "
            f"<b>{100 * rnd.caught6:.0f}</b>.</p>{dots(rnd.caught6, '#98a2b3')}</div>")
    fa = res("A", "septris", k).false_per_shift
    cards.append(f"<div class='sp-box'><div class='sp-label'>The honest part</div>"
                 f"<div class='num' style='color:{GREY}'>{fa:.1f} of {k}</div>"
                 f"<p>reviews per shift still go to a patient who turns out fine (random picking: "
                 f"{res('A', 'random', k).false_per_shift:.1f}). Only about 8% of ICU patients develop sepsis, so "
                 "most reviews cannot be catches, even for a perfect model. What matters is catching more of the "
                 "real cases with the same amount of nurse time.</p></div>")
    return "<div class='sp sp-results sp-row'>" + "".join(cards) + "</div>"


def results_chart(k, home):
    k = int(k)
    home = home.startswith("Same")
    keys = [x for x in NAMES if res("A", x, k, home) is not None]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    w = 0.8 / len(keys)
    for j, key in enumerate(keys):
        for g, T in enumerate(("A", "B")):
            r = res(T, key, k, home)
            if r is None:
                continue
            x = g + (j - (len(keys) - 1) / 2) * w
            v = 100 * r.caught6
            ax.bar(x, v, w * 0.9, color=COLORS[key], label=NAMES[key] if g == 0 else None, zorder=3)
            ax.errorbar(x, v, yerr=[[v - 100 * r.caught6_lo], [100 * r.caught6_hi - v]], color="#344054",
                        capsize=3, lw=1, zorder=4)
            ax.text(x, 100 * r.caught6_hi + 1, f"{v:.0f}", ha="center", fontsize=10.5, fontweight="bold")
    ax.set_xticks([0, 1], ["Hospital A", "Hospital B"], fontsize=12)
    ax.set_ylabel("Caught in time\n(out of 100 sepsis patients)")
    ax.set_ylim(0, 58)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#eaecf0", zorder=0)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=10, labelspacing=1.0)
    where = "trained at the same hospital" if home else "trained at the OTHER hospital (a hospital it has never seen)"
    ax.set_title(f"{k} reviews per 12-hour shift · models {where}", loc="left", fontsize=12, fontweight="bold")
    fig.text(0.01, 0.01, "Black whiskers: the range the number could reasonably be in (95% interval from 200 "
             "re-samples). Test patients were never used for training.", fontsize=8.5, color="#475467")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def detail_table(k):
    k = int(k)
    out = []
    for T in ("A", "B"):
        for key in NAMES:
            for home in ((True, False) if key not in ("sirs", "random") else (True,)):
                r = res(T, key, k, home)
                if r is None:
                    continue
                out.append({"Hospital tested": T,
                            "Method": NAMES[key] + ("" if key in ("sirs", "random") else
                                                    (" · trained here" if home else " · trained at other hospital")),
                            "Caught in time (6–12 h early)": f"{100 * r.caught6:.1f}% ({100 * r.caught6_lo:.1f}–{100 * r.caught6_hi:.1f})",
                            "Caught at all before sepsis": f"{100 * r.caught_any:.1f}%",
                            "False alarms per shift": f"{r.false_per_shift:.2f}"})
    return pd.DataFrame(out)


def intro_html():
    return f"""
<div class='sp'>
 <div class='sp-banner'>⚠️ {DISCLAIMER} Septris never diagnoses sepsis or recommends treatment.
 It only suggests which patient's chart a nurse should review next.</div>
 <div class='sp-hero'><h1>Septris</h1>
 <div class='lead'>Tells a busy ICU nurse <b>whose chart to review next</b>, so sepsis gets spotted earlier.
 New here? Start with the <b>guided tour</b> below.</div></div>
</div>"""


TOUR_STEPS = ["The ICU", "Septris ranks", "Why this bed", "What happened", "The big picture"]


def tiles_html(b, mode, bed):
    """Static 20-bed picture for the tour. mode: plain, ranked or key."""
    by_bed = {int(r.bed): r for r in b.itertuples()}
    cells = []
    for i in range(1, NBEDS + 1):
        r = by_bed.get(i)
        if r is None:
            cells.append(f"<div class='sp-tile snooze'><b>Bed {i}</b><br>Empty</div>")
            continue
        if mode == "plain":
            cells.append(f"<div class='sp-tile'><b>Bed {i}</b><br>Age {meta.loc[r.patient_id, 'age']:.0f}<br>"
                         f"In ICU {r.hours_in_icu} h</div>")
            continue
        cls = ["sp-tile"]
        if r.picked:
            cls.append("pick")
            line = "👉 1st in line"
        elif r.snoozed:
            cls.append("snooze")
            line = f"✓ reviewed {r.hours_since_check} h ago"
        else:
            cls.append("high" if r.tier == "High" else "med" if r.tier == "Medium" else "")
            line = f"{ordinal(int(r.rank))} in line"
        extra = ""
        if mode == "key":
            if i != bed:
                cls.append("dim")
            h = r.hours_to_sepsis
            if not pd.isna(h) and 0 < h <= 12:
                extra = f"<br><span style='color:{RED}; font-weight:700'>⚠ sepsis in {h:.0f} h</span>"
        risk = "" if r.snoozed else f"<br>Risk {r.percentile:.0f} of 100"
        cells.append(f"<div class='{' '.join(cls)}'><b>Bed {i}</b><br>{line}{risk}{extra}</div>")
    return "<div class='sp-tiles'>" + "".join(cells) + "</div>"


def tour(step):
    step = int(step)
    s = slots.iloc[TOUR]
    b = beds_by_hour[s.unit_hour]
    n_cand = int(b["candidates"].iloc[0])
    dots_ = "".join(f"<span class='{'on' if j == step else ''}'>{j + 1}. {t}</span>" for j, t in enumerate(TOUR_STEPS))
    head = f"<div class='sp-steps'>{dots_}</div>"
    fig = None
    if step == 0:
        body = (f"<h2>Meet the ICU</h2><p class='big'>It's <b>{s.clock}</b> on the {s.shift_name.lower()}. One nurse is "
                f"responsible for these {NBEDS} patients. A careful sepsis review of one chart takes a lot of time, so "
                f"the nurse can only do about <b>{K} per 12-hour shift</b>.</p><p class='big'>Sepsis is the body's "
                "extreme reaction to an infection. It is much easier to treat when it is spotted early. "
                "<b>The question: whose chart should the nurse review first?</b></p>" + tiles_html(b, "plain", s.bed))
    elif step == 1:
        body = (f"<h2>Septris ranks the beds</h2><p class='big'>Septris reads every bed's heart rate, blood "
                f"pressure, breathing, temperature, lab results and which tests were done, <b>using only what has "
                f"been recorded up to {s.clock}</b>. It gives each bed a risk from 0 to 100 and lines them up. "
                f"Beds reviewed in the last 12 hours (grey) are skipped.</p><p class='big'>Right now "
                f"<b>Bed {s.bed} is 1st in line</b> (blue border), so that is the chart Septris says to review.</p>"
                + tiles_html(b, "ranked", s.bed))
    elif step == 2:
        body = (f"<h2>Why Bed {s.bed}?</h2><p class='big'>Septris also shows what stood out, so the nurse knows "
                "what to look at first. It's a pointer, not a diagnosis: the nurse reads the chart and decides.</p>"
                + pick_html(s, n_cand))
    elif step == 3:
        icon, headline, fg, bg = VERDICT[s.review_class]
        body = (f"<h2>What really happened</h2><p class='big'>Here's the trick that lets us test Septris: these "
                f"are <b>real patients from past hospital records</b>, so we already know how their stay turned out. "
                f"Septris never saw any of this.</p>"
                f"<div class='sp-key'><div class='verdict' style='background:{bg}; border:1px solid {fg}55'>"
                f"<b style='color:{fg}'>{icon} {headline}.</b><br>"
                f"{esc(what_happened(s.review_class, s.lead_hours, s.bed))}</div></div>"
                f"<p class='big' style='margin-top:10px'>Below is Bed {s.bed}'s chart. The black line is {s.clock}. "
                "The grey area is the future (from the records). The red line is when sepsis was recorded, and the "
                "green band is the \"caught in time\" window, 6 to 12 hours before it.</p>")
        fig = chart(TOUR, int(s.bed))[1]
    else:
        sp = res("A", "septris", K)
        rnd = res("A", "random", K)
        body = (f"<h2>The big picture</h2><p class='big'>One catch could be luck, so we replayed <b>every</b> test "
                f"patient: {int(sp.eligible)} people who developed sepsis at Hospital A, plus another hospital, B. "
                f"With {K} reviews per shift:</p>"
                f"<div class='sp-row'><div class='sp-box'><div class='num' style='font-size:44px; font-weight:800; "
                f"color:{BLUE}'>{100 * sp.caught6:.0f} of 100</div><p>sepsis patients were reviewed <b>in time</b> "
                f"(6 to 12 hours early) when Septris chose.</p>{dots(sp.caught6, BLUE)}</div>"
                f"<div class='sp-box'><div class='num' style='font-size:44px; font-weight:800; color:{GREY}'>"
                f"{100 * rnd.caught6:.0f} of 100</div><p>when the nurse picked charts <b>at random</b>, with the "
                f"same amount of time.</p>{dots(rnd.caught6, '#98a2b3')}</div></div>"
                "<p class='big' style='margin-top:10px'>Now try it yourself: step through shifts, click any bed, and "
                "use the example buttons to see catches, misses and false alarms.</p>")
    return head + f"<div class='sp sp-box sp-tour'>{body}</div>", gr.update(value=fig, visible=fig is not None), \
        gr.update(interactive=step > 0), \
        gr.update(value="Next ▶" if step < len(TOUR_STEPS) - 1 else "Try it yourself ▶")


def faq_html():
    return f"""
<div class='sp sp-faq sp-box'>
<h3>How can the app show what happens in the future?</h3>
<p>It isn't predicting the future live. These are real patients from past hospital records (the PhysioNet 2019
sepsis dataset), so their whole stay is already written down. At each moment we only give Septris the data up to
that moment, then use the rest of the record as an answer key to grade it. That is the standard way to test an
early-warning tool before anyone uses it on real patients.</p>
<h3>What does "Risk 92 of 100" mean?</h3>
<p>The patient's current data looks more worrying than about 92% of patient-hours in our training hospital. It is a
ranking, not a probability of having sepsis.</p>
<h3>What does "2nd in line" mean?</h3>
<p>Septris's ranking at that moment. The bed that is 1st in line is the one Septris says to review now. Beds
reviewed in the last 12 hours are skipped so the nurse doesn't keep looking at the same patient.</p>
<h3>Why only {K} reviews per shift?</h3>
<p>A careful sepsis review takes real time, and the nurse has other work. So the useful question isn't "who might
have sepsis?" but "with the time I have, whose chart should I open next?". We tested 1, 2, 3 and 5 reviews per
shift; the app shows {K}.</p>
<h3>What counts as "caught in time"?</h3>
<p>The patient's chart was reviewed 6 to 12 hours before sepsis was recorded. Less than 6 hours is "caught, but with
little warning". After is "too late". Reviewing someone who doesn't develop sepsis in the next 12 hours is a
"false alarm".</p>
<h3>What is a "miss"?</h3>
<p>A patient who developed sepsis but whose chart was never reviewed in the 6 to 12 hours before it. Usually that's
because other beds looked more worrying at the time.</p>
<h3>Why are most reviews false alarms?</h3>
<p>Only about 8% of these ICU patients ever develop sepsis, and at any given moment very few are in the 6 to 12 hour
window before it. Most of the time there is simply no one to catch. The fair comparison is how many real cases are
caught with the same nurse time, compared with picking at random.</p>
<h3>What is inside Septris?</h3>
<p>{info['model_text']}</p>
<h3>Honest limits</h3>
<ul>
<li>Built and tested only on past records from two hospital systems. It has never been used on real patients.</li>
<li>It works less well at a hospital it wasn't trained on.</li>
<li>Many catches came right after new lab tests were ordered, so it mostly highlights patients the team had already
started to work up. It does not show that the model is ahead of doctors.</li>
<li>The 20-bed unit is a simulation: patients from different times are placed side by side.</li>
</ul>
</div>"""


GRADIO_MAJOR = int(gr.__version__.split(".")[0])
STYLE = {"css": CSS, "theme": gr.themes.Soft(primary_hue="blue"), "js": FORCE_LIGHT}
START = next(i for i in examples["good"] if slots.loc[i, "sepsis_so_far"] >= 40)


def _tour_slot():
    """A clear first example: a catch 7-11 h ahead, the patient's first review, risk rising over the last 12 h."""
    best = None
    for i in slots.index[(slots["review_class"] == "early6") & (slots["sepsis_so_far"] >= 20)]:
        r = slots.loc[i]
        if not 7 <= r.lead_hours <= 11 or min(rev_by_pid.get(r.patient_id, [10**6])) < r.record_hour:
            continue
        t = tl_by_pid[r.patient_id].set_index("hour")["percentile"]
        values = sum(any(c.isdigit() for c in x) for x in r.reasons.split(" | "))
        if r.record_hour < 12 or len(r.reasons.split(" | ")) < 3 or values < 2:
            continue
        rise = t.loc[r.record_hour] - t.loc[r.record_hour - 12]
        if best is None or rise > best[0]:
            best = (rise, int(i))
    return best[1] if best else START


TOUR = _tour_slot()
for _k, _v in examples.items():
    _cut = next((j for j, x in enumerate(_v) if (x["slot"] if isinstance(x, dict) else x) >= START), 0)
    examples[_k] = _v[_cut:] + _v[:_cut]

with gr.Blocks(title="Septris", **({} if GRADIO_MAJOR >= 6 else STYLE)) as demo:
    gr.HTML(intro_html())
    with gr.Tabs() as tabs:
     with gr.Tab("👋 Guided tour (start here)", id="tour"):
        step = gr.State(0)
        tour_html = gr.HTML()
        tour_plot = gr.Plot(show_label=False)
        with gr.Row():
            t_back = gr.Button("◀ Back")
            t_next = gr.Button("Next ▶", variant="primary")

        def t_go(st, d):
            n = int(st) + d
            if n >= len(TOUR_STEPS):
                return st, *tour(st), gr.Tabs(selected="try")
            n = max(0, n)
            return n, *tour(n), gr.Tabs()

        t_outs = [step, tour_html, tour_plot, t_back, t_next, tabs]
        t_next.click(lambda st: t_go(st, 1), step, t_outs)
        t_back.click(lambda st: t_go(st, -1), step, t_outs)
        demo.load(lambda: tour(0), None, [tour_html, tour_plot, t_back, t_next])
     with gr.Tab("🏥 Try it yourself", id="try"):
        cur = gr.State(TOUR)
        sel = gr.State(None)
        focus = gr.State(None)
        counter = gr.State({})
        gr.HTML("<div class='sp sp-sec'>Not sure where to start? Jump to an example:</div>")
        with gr.Row():
            good_b = gr.Button("✅ Septris catches sepsis in time")
            miss_b = gr.Button("❌ Septris misses a sepsis patient")
            fa_b = gr.Button("⚪ A false alarm (patient turns out fine)")
        note = gr.HTML()
        gr.HTML("<div class='sp sp-sec'>Or move through time yourself</div>")
        with gr.Row(equal_height=True):
            prev_s = gr.Button("◀ Previous shift", scale=1)
            shift_box = gr.HTML()
            next_s = gr.Button("Next shift ▶", scale=1)
        gr.HTML(f"<div class='sp sp-sechelp'>The nurse's {K} review times in this shift. Click one to see who "
                "Septris picked at that time.</div>")
        with gr.Row():
            rev_btns = [gr.Button(f"Review {j + 1}", elem_classes=["revbtn"]) for j in range(K)]
        with gr.Row(equal_height=True):
            with gr.Column(scale=1):
                pick = gr.HTML()
            with gr.Column(scale=1):
                key = gr.HTML()
        bed_head = gr.HTML()
        show_key = gr.Checkbox(value=True, label="Show the 📖 answer key on the beds (who later develops sepsis)")
        bed_btns = []
        for row in range(NBEDS // 5):
            with gr.Row():
                for c in range(5):
                    bed_btns.append(gr.Button(f"Bed {row * 5 + c + 1}", elem_classes=["bedbtn"]))
        chart_title = gr.Markdown()
        plot = gr.Plot(show_label=False)
        outs = [cur, sel, note, shift_box, *rev_btns, pick, key, bed_head, *bed_btns, chart_title, plot]
        ins = [cur, sel, focus, show_key]

        prev_s.click(lambda i: (go_shift(i, -1), None, None), cur, [cur, sel, focus]).then(render, ins, outs)
        next_s.click(lambda i: (go_shift(i, 1), None, None), cur, [cur, sel, focus]).then(render, ins, outs)
        for j, btn in enumerate(rev_btns):
            btn.click(lambda i, j=j: (go_review(i, j), None), cur, [cur, sel]).then(render, ins, outs)
        for b_i, btn in enumerate(bed_btns):
            btn.click(lambda b=b_i + 1: b, None, sel).then(render, ins, outs)
        for btn, kind in ((good_b, "good"), (miss_b, "miss"), (fa_b, "false")):
            btn.click(lambda c, k=kind: (*jump(k, c), None), counter, [cur, focus, counter, sel]).then(
                render, ins, outs)
        show_key.change(render, ins, outs)
        demo.load(render, ins, outs)
     with gr.Tab("📊 How well does it work?", id="results"):
        gr.HTML(f"<div class='sp sp-box'><p>These numbers cover <b>every</b> test patient from two hospital systems "
                f"(A and B), not just the replay, averaged over 5 different orders of patient arrivals.</p>"
                f"<p><b>Caught in time</b> = the patient's chart was reviewed 6 to 12 hours before sepsis was "
                f"recorded.</p></div>")
        k_res = gr.Radio([1, 2, 3, 5], value=K, label="Reviews per 12-hour shift")
        cards = gr.HTML()
        gr.HTML("<div class='sp sp-sec'>Septris compared with the alternatives</div>")
        home = gr.Radio(["Same hospital it was trained at", "A hospital it has never seen"],
                        value="Same hospital it was trained at", label="Where the models are tested")
        rchart = gr.Plot(show_label=False)
        gr.HTML(f"<div class='sp sp-box'>{info['comparison_html']}</div>")
        with gr.Accordion("All the numbers", open=False):
            det = gr.Dataframe(wrap=True)
        k_res.change(results_html, k_res, cards)
        for c in (k_res, home):
            c.change(results_chart, [k_res, home], rchart)
        k_res.change(detail_table, k_res, det)
        demo.load(results_html, k_res, cards)
        demo.load(results_chart, [k_res, home], rchart)
        demo.load(detail_table, k_res, det)
     with gr.Tab("❓ Questions", id="faq"):
        gr.HTML(faq_html())
    gr.HTML(f"<div class='sp sp-banner' style='margin-top:8px'>⚠️ {DISCLAIMER}</div>")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", action="store_true")
    ap.add_argument("--port", type=int, default=7860)
    a = ap.parse_args()
    demo.launch(share=a.share, server_port=a.port, **(STYLE if GRADIO_MAJOR >= 6 else {}))
