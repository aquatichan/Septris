"""SignalBridge demo app (Gradio). Reads only app/artifacts/.

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
demo_info = json.loads((ART / "demo.json").read_text())
K = demo_info["k"]
beds_by_hour = {h: g.sort_values("bed") for h, g in beds.groupby("unit_hour")}
tl_by_pid = {p: g for p, g in timelines.groupby("patient_id")}
rev_by_pid = reviews.groupby("patient_id")["record_hour"].apply(list).to_dict()

BLUE, RED, GREEN, AMBER, GREY = "#1d4ed8", "#b42318", "#067647", "#b54708", "#475467"
VERDICT_STYLE = {  # icon, text colour, background
    "Good catch": ("✅", GREEN, "#ecfdf3"),
    "Caught, but close": ("🟡", AMBER, "#fffaeb"),
    "Too late": ("🟠", "#c4320a", "#fff4ed"),
    "False alarm": ("⚪", GREY, "#f2f4f7"),
    "Not counted": ("➖", GREY, "#f2f4f7"),
}
TIER = {"High": (RED, "#fef3f2", "High risk"), "Medium": (AMBER, "#fffaeb", "Medium risk"),
        "Low": (GREY, "#ffffff", "Low risk")}

CSS = """
.gradio-container {max-width: 1180px !important; margin: auto; background: #f8fafc;}
.sb, .sb * {box-sizing: border-box; font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;}
.sb {color: #101828;}
.sb-banner {background: #fff4e5; border: 1px solid #f79009; border-radius: 10px; padding: 8px 14px;
             color: #7a2e0e; font-weight: 600; font-size: 14px;}
.sb-hero h1 {font-size: 30px; margin: 6px 0 2px; color: #101828;}
.sb-hero p {font-size: 17px; margin: 0 0 10px; color: #344054;}
.sb-steps {display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;}
.sb-step {background: #fff; border: 1px solid #e4e7ec; border-radius: 12px; padding: 12px 14px; font-size: 15px;
           line-height: 1.45; color: #344054;}
.sb-step b.n {display: inline-block; width: 26px; height: 26px; border-radius: 50%; background: #1d4ed8; color: #fff;
              text-align: center; line-height: 26px; margin-right: 6px; font-size: 14px;}
.sb-step .t {font-weight: 700; color: #101828; font-size: 16px;}
.sb-card {background: #fff; border: 1px solid #e4e7ec; border-radius: 12px; padding: 14px 16px; height: 100%;}
.sb-when {display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px;
           background: #101828; color: #fff; border-radius: 12px; padding: 12px 18px;}
.sb-when .big {font-size: 22px; font-weight: 700; color: #fff;}
.sb-when .sub {font-size: 15px; color: #d0d5dd;}
.sb-dots span {display: inline-block; width: 16px; height: 16px; border-radius: 50%; margin-left: 5px;
                border: 2px solid #98a2b3;}
.sb-dots span.used {background: #84adff; border-color: #84adff;}
.sb-dots span.now {background: #fff; border-color: #fff;}
.sb-label {font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: #667085; font-weight: 700;
            margin: 0 0 6px;}
.sb-pick-title {font-size: 24px; font-weight: 800; color: #1d4ed8; margin: 0 0 8px;}
.sb-pick ul {margin: 4px 0 6px 20px; padding: 0; font-size: 16px; line-height: 1.5;}
.sb-small {font-size: 13px; color: #667085;}
.sb-verdict {border-radius: 10px; padding: 10px 12px; margin-top: 12px; font-size: 15px; line-height: 1.45;}
.sb-verdict b {font-size: 17px;}
.sb-score-row {display: grid; grid-template-columns: 118px 1fr 58px; align-items: center; gap: 8px; margin: 8px 0;
                font-size: 15px;}
.sb-bar {background: #eef2f6; border-radius: 6px; height: 18px; overflow: hidden;}
.sb-bar div {height: 100%; border-radius: 6px;}
.sb-grid {display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px;}
.sb-bed {border: 2px solid #d0d5dd; border-radius: 10px; padding: 8px 10px; font-size: 13.5px; line-height: 1.4;
          background: #fff; min-height: 112px; position: relative;}
.sb-bed .name {font-weight: 800; font-size: 16px;}
.sb-bed .state {font-weight: 700; margin: 2px 0;}
.sb-bed .meter {background: #eef2f6; border-radius: 4px; height: 7px; margin: 3px 0 4px; overflow: hidden;}
.sb-bed .meter div {height: 100%;}
.sb-bed.pick {border: 4px solid #1d4ed8; box-shadow: 0 0 0 3px #c7d7fe;}
.sb-bed.snooze {background: #f2f4f7; color: #667085; border-style: dashed;}
.sb-bed.focus {outline: 4px solid #b42318; outline-offset: 2px;}
.sb-tag {display: inline-block; border-radius: 999px; padding: 1px 8px; font-size: 12px; font-weight: 700;
          margin-top: 3px;}
.sb-legend {display: flex; flex-wrap: wrap; gap: 14px; font-size: 13px; color: #475467; margin-top: 8px;}
.sb-note {background: #fef3f2; border: 1px solid #fda29b; border-radius: 10px; padding: 10px 14px; font-size: 15px;
           color: #7a271a; margin-bottom: 8px;}
.sb-kpis {display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;}
.sb-kpi {background: #fff; border: 1px solid #e4e7ec; border-radius: 12px; padding: 14px 16px;}
.sb-kpi .v {font-size: 34px; font-weight: 800; line-height: 1.1;}
.sb-kpi .l {font-size: 15px; color: #344054; margin-top: 4px;}
.sb-faq h3 {font-size: 18px; margin: 16px 0 4px; color: #101828;}
.sb-faq p, .sb-faq li {font-size: 15.5px; line-height: 1.55; color: #344054;}
@media (max-width: 760px) {
  .gradio-container, .gradio-container .main {width: 100% !important; max-width: 100vw !important;
    min-width: 0 !important;}
  body {overflow-x: hidden;}
  .gradio-container .row {flex-wrap: wrap !important;}
  .gradio-container .row > * {min-width: 0 !important; flex: 1 1 100% !important;}
  .sb-steps, .sb-kpis {grid-template-columns: 1fr;}
  .sb-hero h1 {font-size: 24px;}
  .sb-when .big {font-size: 18px;}
  .sb-grid {grid-template-columns: repeat(2, 1fr);}
}
"""

FORCE_LIGHT = """() => {
  document.documentElement.classList.remove('dark');
  document.body && document.body.classList.remove('dark');
}"""


def esc(s):
    return html.escape(str(s))


# ---------------------------------------------------------------- review tab
def header_html(s):
    dots = "".join(f"<span class='{'now' if c == s.check else 'used' if c < s.check else ''}'></span>"
                   for c in range(1, K + 1))
    return (f"<div class='sb sb-when'><div><div class='big'>Day {s.day} · {s.clock}</div>"
            f"<div class='sub'>{s.shift_name} · check {s.check} of {K} this shift · "
            f"the nurse can only open {K} charts per 12-hour shift</div></div>"
            f"<div class='sb-dots' title='checks used this shift'>{dots}</div></div>")


def verdict_html(label, text, title="What really happened (SignalBridge could not know this)"):
    icon, fg, bg = VERDICT_STYLE[label]
    return (f"<div class='sb-verdict' style='background:{bg}; border:1px solid {fg}33'>"
            f"<div class='sb-label' style='margin-bottom:2px'>{title}</div>"
            f"<b style='color:{fg}'>{icon} {label}.</b> {esc(text)}</div>")


def pick_html(s, n_candidates):
    reasons = [r for r in s.reasons.split(" | ") if r]
    why = ("<ul>" + "".join(f"<li>{esc(r[0].upper() + r[1:])}</li>" for r in reasons) + "</ul>") if reasons \
        else "<p>Several small signals together, none large on its own.</p>"
    rnd = ""
    if s.random_bed is not None and not pd.isna(s.random_bed):
        icon, fg, _ = VERDICT_STYLE[s.random_verdict]
        rnd = (f"<div class='sb-small' style='margin-top:10px; font-size:14px'>For comparison, "
               f"<b>random checking</b> opened <b>Bed {int(s.random_bed)}</b> at this moment: "
               f"<b style='color:{fg}'>{icon} {s.random_verdict}</b>.</div>")
    return (f"<div class='sb sb-card sb-pick'><div class='sb-label'>SignalBridge says</div>"
            f"<div class='sb-pick-title'>👉 Open Bed {s.bed}'s chart now</div>"
            f"<div style='font-size:15px'>It ranks <b>#1 of the {n_candidates} beds</b> not checked in the last "
            f"12 hours. Why it ranks first:</div>{why}"
            f"<div class='sb-small'>These are patterns the model learned from past patients, not a diagnosis. "
            f"The nurse decides what to do.</div>"
            f"{verdict_html(s.verdict, s.verdict_text)}{rnd}</div>")


def score_html(s):
    n = s.sepsis_so_far
    rows = ""
    for name, v, col in (("SignalBridge", s.sb_caught_so_far, BLUE), ("Random checks", s.random_caught_so_far, GREY)):
        w = 100 * v / n if n else 0
        rows += (f"<div class='sb-score-row'><b style='color:{col}'>{name}</b>"
                 f"<div class='sb-bar'><div style='width:{w:.0f}%; background:{col}'></div></div>"
                 f"<b>{v}</b></div>")
    pct = f" ({100 * s.sb_caught_so_far / n:.0f}% vs {100 * s.random_caught_so_far / n:.0f}%)" if n else ""
    return (f"<div class='sb sb-card'><div class='sb-label'>Scoreboard so far (day 1 to day {s.day})</div>"
            f"<div style='font-size:15px'><b>{n}</b> patient{'' if n == 1 else 's'} in this replay "
            f"{'has' if n == 1 else 'have'} developed sepsis so far. "
            f"How many had their chart opened <b>6–12 hours before</b> sepsis was recorded?{pct}</div>"
            f"{rows}<div class='sb-small'>Same beds, same number of checks. Random checking is what a nurse "
            f"would do with no guidance at all.</div></div>")


def bed_tile(r, show_hindsight, focus_bed):
    fg, bg, word = TIER[r.tier]
    cls = "sb-bed"
    if r.picked:
        state, color = "👉 CHECK NOW", BLUE
        cls += " pick"
    elif r.snoozed:
        state, color = f"✓ Checked {r.hours_since_check} h ago", GREY
        cls += " snooze"
    else:
        state, color = f"#{r.rank} in line" + ("" if r.tier == "Low" else f" · {word}"), fg
    if focus_bed == r.bed:
        cls += " focus"
    bar = (f"<div class='meter'><div style='width:{r.percentile:.0f}%; background:{fg}'></div></div>"
           f"<div>Risk {r.percentile:.0f}/100 · in ICU {r.hours_in_icu} h</div>")
    tags = ""
    if r.random_pick:
        tags += "<span class='sb-tag' style='background:#eef2f6; color:#344054'>🎲 random pick</span> "
    if show_hindsight:
        h = r.hours_to_sepsis
        g = meta.loc[r.patient_id, "group"]
        if g == "uncertain_onset":
            tags += "<span class='sb-tag' style='background:#f2f4f7; color:#475467'>septic on arrival</span>"
        elif not pd.isna(h) and 0 < h <= 12:
            tags += (f"<span class='sb-tag' style='background:#fee4e2; color:{RED}'>"
                     f"⚠ sepsis in {h:.0f} h</span>")
        elif not pd.isna(h) and h <= 0:
            tags += f"<span class='sb-tag' style='background:#fff4ed; color:#c4320a'>sepsis already recorded</span>"
    style = "" if (r.picked or r.snoozed) else f"style='background:{bg}; border-color:{fg}66'"
    return (f"<div class='{cls}' {style}><div class='name'>Bed {r.bed}</div>"
            f"<div class='state' style='color:{color}'>{state}</div>{bar}{tags}</div>")


def grid_html(b, show_hindsight, focus_bed):
    tiles = {int(r.bed): bed_tile(r, show_hindsight, focus_bed) for r in b.itertuples()}
    cells = "".join(tiles.get(i, f"<div class='sb-bed snooze'><div class='name'>Bed {i}</div>Empty</div>")
                    for i in range(1, 21))
    legend = ("<div class='sb-legend'><span><b style='color:#1d4ed8'>Blue border</b> = SignalBridge's pick</span>"
              "<span><b>#N in line</b> = SignalBridge's ranking right now (#1 gets checked)</span>"
              "<span><b>Risk N/100</b> = how this hour compares with past ICU hours (100 = most worrying)</span>"
              "<span><b>Grey, dashed</b> = checked in the last 12 h, so skipped for now</span>"
              + ("<span><b style='color:#b42318'>⚠ sepsis in N h</b> = hindsight only, hidden from the model</span>"
                 if show_hindsight else "") + "</div>")
    return (f"<div class='sb sb-card'><div class='sb-label'>The unit right now: 20 beds</div>"
            f"<div class='sb-grid'>{cells}</div>{legend}</div>")


def timeline(i, bed_choice):
    i = int(i)
    s = slots.iloc[i]
    b = beds_by_hour[s.unit_hour]
    try:
        bed = int(str(bed_choice).split()[1])
    except (IndexError, ValueError):
        bed = int(s.bed)
    row = b[b["bed"] == bed]
    if row.empty:
        return None
    row = row.iloc[0]
    pid, now = row.patient_id, int(row.record_hour)
    t = tl_by_pid[pid]
    m = meta.loc[pid]
    onset = m["t_onset"]
    fig, axes = plt.subplots(3, 1, figsize=(10, 6.4), sharex=True, gridspec_kw={"height_ratios": [1.6, 1, 1]})
    end = t["hour"].max()
    for a in axes:
        a.axvspan(now + 0.5, end + 1, color="#f2f4f7", lw=0, zorder=0)
        a.axvline(now, color="#101828", lw=2, zorder=3)
        if not np.isnan(onset):
            a.axvspan(max(0, onset - 12), onset - 6, color="#d1fadf", lw=0, zorder=0)
            a.axvline(onset, color=RED, lw=2.5, zorder=3)
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", color="#eaecf0")
    ax = axes[0]
    ax.axhspan(95, 100, color="#fee4e2", lw=0, zorder=0)
    ax.axhspan(80, 95, color="#fef0c7", lw=0, zorder=0)
    ax.plot(t["hour"], t["percentile"], color=BLUE, lw=2.2, zorder=4)
    for h in rev_by_pid.get(pid, []):
        y = float(t.loc[t["hour"] == h, "percentile"].iloc[0])
        ax.plot([h], [y], marker="v", ms=11, color=BLUE, mec="white", zorder=5)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Risk (0–100)")
    ax.text(now, 101, "  now", fontsize=10, fontweight="bold", va="bottom")
    if not np.isnan(onset):
        ax.text(onset, 101, " sepsis recorded", fontsize=10, color=RED, fontweight="bold", va="bottom")
    ax.text(0.3, 97.5, "high risk zone", fontsize=8.5, va="center", color=RED)
    ax.text(0.3, 87.5, "medium risk zone", fontsize=8.5, va="center", color=AMBER)
    title = f"Bed {bed} · age {m['age']:.0f} · in ICU {now + 1} h so far"
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=18)
    for a, col, lab in ((axes[1], "HR", "Heart rate"), (axes[2], "MAP", "Blood pressure\n(MAP)")):
        a.plot(t["hour"], t[col], marker="o", ms=2.5, lw=1, color="#344054", zorder=4)
        a.set_ylabel(lab, fontsize=10)
    axes[-1].set_xlabel("Hours since this patient arrived in the ICU")
    parts = ["Blue line: SignalBridge risk", "▼ = SignalBridge opened the chart", "grey area = the future"]
    if not np.isnan(onset):
        parts.append("green band = good-catch window (6–12 h before sepsis was recorded)")
    fig.text(0.01, 0.01, " · ".join(parts) + ".", fontsize=9, color="#475467")
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    return fig


def render(i, focus, show_hindsight):
    i = int(i)
    s = slots.iloc[i]
    b = beds_by_hour[s.unit_hour]
    n_cand = int(b["candidates"].iloc[0])
    focus = focus if (focus and focus.get("slot") == i) else None
    focus_bed = focus["bed"] if focus else None
    note = ""
    if focus:
        r = b[b["bed"] == focus_bed].iloc[0]
        rank = f"ranked it #{int(r['rank'])} of {n_cand}" if r["rank"] else "had checked it recently"
        note = (f"<div class='sb sb-note'><b>❌ This is a miss.</b> Bed {focus_bed} (red outline) will develop "
                f"sepsis in {r['hours_to_sepsis']:.0f} hours, but SignalBridge {rank}, so with only {K} checks per "
                f"shift its chart was not opened in time. Its timeline is shown below.</div>")
    choices = [f"Bed {int(x)}" for x in b["bed"]]
    show = f"Bed {focus_bed}" if focus_bed else f"Bed {s.bed}"
    return (note + header_html(s), pick_html(s, n_cand), score_html(s), grid_html(b, show_hindsight, focus_bed),
            gr.update(choices=choices, value=show), timeline(i, show))


def jump(kind, counter):
    xs = examples[kind]
    c = (counter or {}).copy()
    n = c.get(kind, -1) + 1
    c[kind] = n
    x = xs[n % len(xs)]
    if kind == "miss":
        return x["slot"], {"slot": x["slot"], "bed": x["bed"]}, c
    return int(x), None, c


# ---------------------------------------------------------------- results tab
def res_row(test, pol, k):
    r = table[(table.test == test) & (table.k == k) & (table.subgroup == "all") & (table.policy == pol)]
    return None if r.empty else r.iloc[0]


def results_chart(k):
    k = int(k)
    names = [("SignalBridge\n(trained at this hospital)", BLUE, lambda T: f"{T}:lgbm_combined"),
             ("SignalBridge\n(trained at the other hospital)", "#84adff",
              lambda T: f"{'B' if T == 'A' else 'A'}:lgbm_combined"),
             ("SIRS rule\n(standard checklist)", AMBER, lambda T: "sirs"),
             ("Random checks\n(no guidance)", "#98a2b3", lambda T: "random")]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    w = 0.2
    for j, (name, col, pol) in enumerate(names):
        for g, T in enumerate(("A", "B")):
            r = res_row(T, pol(T), k)
            if r is None:
                continue
            x = g + (j - 1.5) * w
            v = 100 * r.caught6
            ax.bar(x, v, w * 0.92, color=col, label=name if g == 0 else None, zorder=3)
            ax.errorbar(x, v, yerr=[[v - 100 * r.caught6_lo], [100 * r.caught6_hi - v]], color="#344054",
                        capsize=3, lw=1, zorder=4)
            ax.text(x, 100 * r.caught6_hi + 1, f"{v:.0f}%", ha="center", fontsize=10.5, fontweight="bold")
    ax.set_xticks([0, 1], [f"Hospital A\n({int(res_row('A', 'random', k).eligible)} sepsis patients)",
                           f"Hospital B\n({int(res_row('B', 'random', k).eligible)} sepsis patients)"], fontsize=11)
    ax.set_ylabel("% of sepsis patients\nflagged 6–12 h early")
    ax.set_ylim(0, 55)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#eaecf0", zorder=0)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=10, labelspacing=1.1)
    ax.set_title(f"With {k} chart check{'s' if k > 1 else ''} per 12-hour shift (20 beds)", loc="left",
                 fontsize=13, fontweight="bold")
    fig.text(0.01, 0.01, "Black whiskers: 95% range from 200 re-samples of the test patients. "
             "Test patients were never used for training.", fontsize=9, color="#475467")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    return fig


def results_cards(k):
    k = int(k)
    out = []
    for T in ("A", "B"):
        sb, rnd, sirs = res_row(T, f"{T}:lgbm_combined", k), res_row(T, "random", k), res_row(T, "sirs", k)
        d = diffs[(diffs.test == T) & (diffs.k == k) & (diffs.comparison == "lgbm_combined (home) minus random")]
        sure = (" The gap is larger than chance (95% range "
                f"+{100 * d.iloc[0].lo:.0f} to +{100 * d.iloc[0].hi:.0f} points).") if len(d) and d.iloc[0].excludes_zero \
            else ""
        out.append(f"<div class='sb-kpi'><div class='sb-label'>Hospital {T}</div>"
                   f"<div class='v' style='color:{BLUE}'>{100 * sb.caught6:.0f}%</div>"
                   f"<div class='l'>of sepsis patients (about {sb.caught6_n:.0f} of {sb.eligible:.0f}) had their chart "
                   f"opened 6–12 hours early by SignalBridge, versus <b>{100 * rnd.caught6:.0f}%</b> with random "
                   f"checks and <b>{100 * sirs.caught6:.0f}%</b> with the SIRS rule.{sure}</div></div>")
    fa = res_row("A", "A:lgbm_combined", k).false_per_shift
    fr = res_row("A", "random", k).false_per_shift
    out.append(f"<div class='sb-kpi'><div class='sb-label'>The honest catch</div>"
               f"<div class='v' style='color:{GREY}'>{fa:.1f} of {k}</div>"
               f"<div class='l'>checks per shift still go to a patient who will not develop sepsis in the next "
               f"12 hours (random: {fr:.1f}). Only about 8% of ICU patients develop sepsis, so most checks "
               f"can't be hits.</div></div>")
    return "<div class='sb sb-kpis'>" + "".join(out) + "</div>"


POLICY_NAMES = [("random", "Random checks"), ("sirs", "SIRS rule"), ("news", "NEWS-inspired score"),
                ("lr", "Logistic regression"), ("lgbm_values", "LightGBM, vital/lab values only"),
                ("lgbm_missing", "LightGBM, which tests were done only"),
                ("lgbm_combined", "SignalBridge (LightGBM, combined)")]


def detail_table(test, k):
    k = int(k)
    out = []
    for train in (test, "B" if test == "A" else "A"):
        for key, name in POLICY_NAMES:
            if key in ("random", "sirs", "news") and train != test:
                continue
            pol = key if key in ("random", "sirs", "news") else f"{train}:{key}"
            r = res_row(test, pol, k)
            if r is None:
                continue
            where = "" if key in ("random", "sirs", "news") else \
                (" · trained here" if train == test else " · trained at other hospital")
            out.append({"Method": name + where,
                        "Flagged 6–12 h early": f"{100 * r.caught6:.1f}% ({100 * r.caught6_lo:.1f}–{100 * r.caught6_hi:.1f})",
                        "Flagged at all before onset": f"{100 * r.caught_any:.1f}%",
                        "False alarms per shift": f"{r.false_per_shift:.2f}",
                        "Median head start (h)": "–" if pd.isna(r.median_lead) else f"{r.median_lead:.1f}"})
    return pd.DataFrame(out)


def intro_html():
    return f"""
<div class='sb'>
 <div class='sb-banner'>⚠️ {DISCLAIMER} SignalBridge never diagnoses sepsis or recommends treatment.
 It only suggests which chart a nurse should look at next.</div>
 <div class='sb-hero'><h1>SignalBridge</h1>
 <p>Helping an ICU nurse decide <b>whose chart to check next</b> for early signs of sepsis.</p></div>
 <div class='sb-steps'>
  <div class='sb-step'><b class='n'>1</b><span class='t'>The problem</span><br>One nurse watches 20 ICU beds
   but only has time to carefully check about <b>{K} charts per 12-hour shift</b>. Sepsis is deadly and easy to
   miss early.</div>
  <div class='sb-step'><b class='n'>2</b><span class='t'>What SignalBridge does</span><br>At each check it ranks
   the beds using only the vitals and lab results recorded <i>so far</i>, and says which chart to open, and why.
   </div>
  <div class='sb-step'><b class='n'>3</b><span class='t'>How we test it</span><br>We replay
   {demo_info['patients']:,} real past ICU patients it never trained on. We know who later got sepsis, so a
   <b>good catch</b> = chart opened 6–12 hours before sepsis was recorded.</div>
 </div>
</div>"""


FAQ = f"""
<div class='sb sb-faq sb-card'>
<h3>What is sepsis, and why does timing matter?</h3>
<p>Sepsis is the body's extreme reaction to an infection. It can damage organs within hours, and every hour of
delayed treatment raises the risk of death. Spotting it a few hours earlier gives the care team time to act.</p>
<h3>Why only {K} checks per shift?</h3>
<p>A careful sepsis review of one chart takes real time. A nurse covering 20 beds cannot do that for everyone,
so the useful question is not "who might be septic?" but "with my next check, whose chart should I open?".
We tested 1, 2, 3 and 5 checks per shift; this demo shows {K}.</p>
<h3>What counts as a good catch?</h3>
<p>The chart was opened 6 to 12 hours <b>before</b> sepsis was recorded in the patient's data. Opening it
less than 6 hours before is shown as "caught, but close"; after is "too late". Opening the chart of someone
who does not develop sepsis in the next 12 hours is a "false alarm".</p>
<h3>Why are most checks false alarms?</h3>
<p>Only about 8% of these ICU patients ever develop sepsis, and at any given hour far fewer are in the
6–12 hour window. Even a perfect ranking would usually have no one in that window to find. What matters is
how many real cases get caught compared with checking at random using the same time.</p>
<h3>What does the model look at?</h3>
<p>Hourly vital signs (heart rate, blood pressure, breathing rate, temperature, oxygen), lab results (such as
lactate and white cell count), age and sex, and <i>which</i> tests were done recently. It only ever sees data
recorded up to the current hour. It does not see length of stay or which unit the patient is on.</p>
<h3>Honest limits</h3>
<ul>
<li>Built and tested on past records from two hospital systems; it has never been used on real patients.</li>
<li>It works less well at a hospital it was not trained on.</li>
<li>Many of its good catches came right after new lab tests were ordered, so it mostly highlights patients the
team had already started working up. It does not prove the model is ahead of clinicians.</li>
<li>The 20-bed unit is a simulation: patients from different times are placed side by side.</li>
</ul>
<p class='sb-small'>Data: PhysioNet/CinC Challenge 2019 (CC BY 4.0). Full methods and pre-registration are in
the project repository.</p>
</div>"""


GRADIO_MAJOR = int(gr.__version__.split(".")[0])
STYLE = {"css": CSS, "theme": gr.themes.Soft(primary_hue="blue"), "js": FORCE_LIGHT}
# open on a good catch once the replay is well under way, and start every example list from there
START = next(i for i in examples["good"] if slots.loc[i, "sepsis_so_far"] >= 40)
for _k, _v in examples.items():
    _cut = next((j for j, x in enumerate(_v) if (x["slot"] if isinstance(x, dict) else x) >= START), 0)
    examples[_k] = _v[_cut:] + _v[:_cut]

with gr.Blocks(title="SignalBridge", **({} if GRADIO_MAJOR >= 6 else STYLE)) as demo:
    gr.HTML(intro_html())
    with gr.Tab("▶ Replay"):
        gr.Markdown("Step through the replay one check at a time, or jump straight to an example.")
        with gr.Row():
            prev_b = gr.Button("◀ Previous check")
            next_b = gr.Button("Next check ▶", variant="primary")
            shift_b = gr.Button("Skip to next shift ⏭")
        with gr.Row():
            good_b = gr.Button("✅ Show me a good catch")
            miss_b = gr.Button("❌ Show me a miss")
            fa_b = gr.Button("⚪ Show me a false alarm")
        head = gr.HTML()
        with gr.Row(equal_height=True):
            with gr.Column(scale=3):
                pick = gr.HTML()
            with gr.Column(scale=2):
                score = gr.HTML()
        hind = gr.Checkbox(value=True, label="Show what happened later on the bed map (hidden from SignalBridge)")
        grid = gr.HTML()
        gr.Markdown("### Look inside a bed's chart")
        bed = gr.Dropdown(label="Pick a bed", choices=[])
        plot = gr.Plot(show_label=False)
        with gr.Accordion("Jump to any check in the replay", open=False):
            slot = gr.Slider(0, len(slots) - 1, value=START, step=1,
                             label=f"Check number (the replay covers {demo_info['days']:.0f} days)")
        focus = gr.State(None)
        counter = gr.State({})
        outs = [head, pick, score, grid, bed, plot]

        def step(i, d):
            return min(len(slots) - 1, max(0, int(i) + d))

        def next_shift(i):
            sh = slots.iloc[int(i)]["shift"]
            later = slots.index[slots["shift"] > sh]
            return int(later[0]) if len(later) else int(i)

        slot.change(render, [slot, focus, hind], outs)
        hind.change(render, [slot, focus, hind], outs)
        prev_b.click(lambda i: step(i, -1), slot, slot)
        next_b.click(lambda i: step(i, 1), slot, slot)
        shift_b.click(next_shift, slot, slot)
        for btn, kind in ((good_b, "good"), (miss_b, "miss"), (fa_b, "false")):
            btn.click(lambda c, k=kind: jump(k, c), counter, [slot, focus, counter]).then(
                render, [slot, focus, hind], outs)
        bed.input(timeline, [slot, bed], plot)
        demo.load(render, [slot, focus, hind], outs)
    with gr.Tab("📊 Results"):
        gr.Markdown(f"Results over **every** test patient (Hospital A and Hospital B), averaged over 5 different "
                    f"admission orders. The replay tab shows one of these runs at {K} checks per shift.")
        k_res = gr.Radio([1, 2, 3, 5], value=K, label="Chart checks per 12-hour shift")
        cards = gr.HTML()
        chart = gr.Plot(show_label=False)
        gr.Markdown("**Trained at the other hospital** shows what happens when the model is moved to a hospital "
                    "it has never seen: it still beats random checks, but loses some of its edge, especially at "
                    "Hospital A.")
        with gr.Accordion("Detailed numbers", open=False):
            test_h = gr.Radio(["A", "B"], value="A", label="Test hospital")
            det = gr.Dataframe(wrap=True)
            gr.Markdown("At 1, 2 and 5 checks per shift only the main methods were run; 3 checks per shift was the "
                        "budget fixed in advance, with every method.")
        k_res.change(lambda k: (results_cards(k), results_chart(k)), k_res, [cards, chart])
        for c in (k_res, test_h):
            c.change(detail_table, [test_h, k_res], det)
        demo.load(lambda k: (results_cards(k), results_chart(k)), k_res, [cards, chart])
        demo.load(detail_table, [test_h, k_res], det)
    with gr.Tab("❓ How it works"):
        gr.HTML(FAQ)
    gr.HTML(f"<div class='sb sb-banner' style='margin-top:8px'>⚠️ {DISCLAIMER}</div>")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", action="store_true")
    ap.add_argument("--port", type=int, default=7860)
    a = ap.parse_args()
    demo.launch(share=a.share, server_port=a.port, **(STYLE if GRADIO_MAJOR >= 6 else {}))
