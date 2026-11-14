"""SignalBridge demo app (Gradio). Reads only app/artifacts/.

    python app/app.py            # local
    python app/app.py --share    # public link for recording (Colab)

This project is a prototype and is not medical advice.
"""

import argparse
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
K = 3

slots = pd.read_parquet(ART / "slots.parquet").reset_index(drop=True)
beds = pd.read_parquet(ART / "beds.parquet")
timelines = pd.read_parquet(ART / "timelines.parquet")
reviews = pd.read_parquet(ART / "reviews.parquet")
meta = pd.read_parquet(ART / "patients.parquet").set_index("patient_id")
table = pd.read_csv(ART / "results_table.csv")
diffs = pd.read_csv(ART / "paired_differences.csv")
cases = json.loads((ART / "failure_cases.json").read_text())
beds_by_hour = {h: g for h, g in beds.groupby("unit_hour")}

TIER_STYLE = {"High": ("#b42318", "#fef3f2"), "Medium": ("#b54708", "#fffaeb"), "Low": ("#344054", "#f9fafb")}
CLASS_TEXT = {"early6": "Early catch (6–12 h before recorded onset)", "early": "Early catch (under 6 h before onset)",
              "late": "Late (at or after recorded onset)", "false": "False alert (no onset in the next 12 h)",
              "uncertain": "Uncertain onset (excluded from timing metrics)"}

CSS = """
.sb-grid {display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:8px;}
.sb-bed {border:2px solid #d0d5dd; border-radius:8px; padding:8px; font-size:14px; line-height:1.35;}
.sb-bed b {font-size:15px;}
.sb-pick {border:4px solid #1d4ed8 !important; box-shadow:0 0 0 2px #bfdbfe;}
.sb-banner {background:#fff4e5; border:1px solid #f79009; border-radius:8px; padding:10px 14px;
            font-weight:600; color:#7a2e0e; font-size:15px;}
.sb-why {background:#eff6ff; border-left:5px solid #1d4ed8; padding:10px 14px; border-radius:6px; font-size:15px;}
.sb-label {font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:#475467; margin:10px 0 4px;}
"""


def bed_card(r, picked=False):
    fg, bg = TIER_STYLE[r.tier]
    pick = " sb-pick" if picked else ""
    star = "▶ PICKED · " if picked else ""
    return (f"<div class='sb-bed{pick}' style='background:{bg}; border-color:{fg}'>"
            f"<b style='color:{fg}'>{star}{r.tier}</b><br>"
            f"{r.patient_id}<br>ICU hour {r.record_hour}<br>"
            f"Prototype priority score {r.score:.3f}</div>")


def render_slot(i):
    i = int(i)
    s = slots.iloc[i]
    b = beds_by_hour[s.unit_hour].sort_values("score", ascending=False)
    used = int(((slots["shift"] == s["shift"]) & (slots.index <= i)).sum())
    head = (f"### Shift {s['shift']}, review slot {s['slot']} of {K}\n"
            f"**Slots left this shift: {K - used} of {K}** · "
            f"{len(b)} patients in beds · review {i + 1} of {len(slots)} in this simulated run")
    pick = (f"<div class='sb-label'>Chart to open now</div>"
            f"<div class='sb-why'><b>{s.patient_id}</b> (ICU hour {s.record_hour})<br>{s.why_now}</div>"
            f"<div class='sb-label'>What happened (known only in hindsight)</div>"
            f"<div>{CLASS_TEXT.get(s.review_class, s.review_class)}</div>")
    active = b[~b["recently_reviewed"]]
    recent = b[b["recently_reviewed"]]
    grid = "<div class='sb-label'>Eligible for review now (highest priority first)</div><div class='sb-grid'>"
    grid += "".join(bed_card(r, r.picked) for r in active.itertuples()) + "</div>"
    if len(recent):
        grid += "<div class='sb-label'>Reviewed in the last 12 h (not eligible yet)</div><div class='sb-grid'>"
        grid += "".join(bed_card(r) for r in recent.itertuples()) + "</div>"
    choices = list(b["patient_id"])
    return head, pick, grid, gr.update(choices=choices, value=s.patient_id), timeline(s.patient_id)


def timeline(pid):
    if not pid:
        return None
    t = timelines[timelines["patient_id"] == pid]
    m = meta.loc[pid]
    fig, axes = plt.subplots(4, 1, figsize=(9, 7.5), sharex=True,
                             gridspec_kw={"height_ratios": [1.4, 1, 1, 1]})
    ax = axes[0]
    ax.plot(t["hour"], t["score"], color="#1d4ed8", lw=2)
    ax.set_ylabel("Priority score")
    ax.set_title(f"{pid} · age {m['age']:.0f} · {m['n_hours']} ICU hours", loc="left", fontsize=12)
    for a in axes:
        for h in reviews.loc[reviews["patient_id"] == pid, "record_hour"]:
            a.axvline(h, color="#1d4ed8", ls="--", lw=1.2)
        if not np.isnan(m["t_onset"]):
            a.axvline(m["t_onset"], color="#b42318", lw=2)
            a.axvspan(max(0, m["t_onset"] - 12), m["t_onset"], color="#fee4e2", alpha=.5, lw=0)
    for a, col, lab in zip(axes[1:], ["HR", "MAP", "Resp"],
                           ["Heart rate (bpm)", "MAP (mmHg)", "Resp. rate (/min)"]):
        a.plot(t["hour"], t[col], marker="o", ms=3, lw=1, color="#344054")
        a.set_ylabel(lab, fontsize=9)
    axes[-1].set_xlabel("ICU hour of this patient's record")
    note = ("Blue dashed: SignalBridge reviews. Red line: recorded onset; shaded: 12-hour target window."
            if not np.isnan(m["t_onset"]) else "Blue dashed: SignalBridge reviews. No sepsis onset recorded.")
    fig.text(0.01, 0.005, note + " Retrospective record; associations, not causes.", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    return fig


def find_slot(pid):
    hits = slots.index[slots["patient_id"] == pid]
    if len(hits):
        return int(hits[0])
    hrs = beds.loc[beds["patient_id"] == pid, "unit_hour"]
    if len(hrs):
        return int(np.searchsorted(slots["unit_hour"], hrs.min()))
    return 0


POLICY_NAMES = [("random", "Random review (same budget)"), ("sirs", "SIRS ranking"),
                ("news", "NEWS-inspired score"), ("lr", "Logistic regression"),
                ("lgbm_values", "LightGBM, values only"), ("lgbm_missing", "LightGBM, measurement pattern only"),
                ("lgbm_combined", "SignalBridge (LightGBM, combined)")]


def fmt(v, lo, hi, pct=True):
    if pd.isna(v):
        return "–"
    if pct:
        return f"{100 * v:.1f}% ({100 * lo:.1f}–{100 * hi:.1f})"
    return f"{v:.2f} ({lo:.2f}–{hi:.2f})"


def results(test, which, k):
    k = int(k)
    other = "B" if test == "A" else "A"
    train = test if which.startswith("Home") else other
    t = table[(table.test == test) & (table.k == k) & (table.subgroup == "all")]
    out = []
    for key, name in POLICY_NAMES:
        pol = key if key in ("random", "sirs", "news") else f"{train}:{key}"
        r = t[t.policy == pol]
        if r.empty:
            continue
        r = r.iloc[0]
        out.append({
            "Policy": name,
            "Caught 6–12 h early": f"{int(r.caught6_n)} of {int(r.eligible)} · " + fmt(r.caught6, r.caught6_lo, r.caught6_hi),
            "Missed": f"{int(r.missed_n)} · " + fmt(r.missed, r.missed_lo, r.missed_hi),
            "False reviews / shift": fmt(r.false_per_shift, r.false_per_shift_lo, r.false_per_shift_hi, False),
            "Median lead (h)": "–" if pd.isna(r.median_lead) else f"{r.median_lead:.1f}",
        })
    d = diffs[(diffs.test == test) & (diffs.k == k)]
    lines = []
    want = [f"lgbm_combined (home) minus random", f"lgbm_combined: home minus external",
            "reliance: combined minus values-only (home)", "missingness-only (home) minus random"]
    for w in want:
        r = d[d.comparison == w]
        if len(r):
            r = r.iloc[0]
            verdict = "interval excludes 0" if r.excludes_zero else "interval includes 0 (not shown)"
            lines.append(f"- **{w.replace('lgbm_combined', 'SignalBridge')}**: "
                         f"{100 * r.point:+.1f} points (95% CI {100 * r.lo:+.1f} to {100 * r.hi:+.1f}); {verdict}")
    note = (f"Test patients: Hospital {test}. Models trained at Hospital {train} "
            f"({'home' if train == test else 'never saw this hospital'}). "
            f"Mean of 5 admission orders; 95% intervals from 200 patient-level bootstrap replicates. "
            "Paired differences (caught 6–12 h early, percentage points):\n" + "\n".join(lines))
    return pd.DataFrame(out), note


with gr.Blocks(title="SignalBridge", css=CSS, theme=gr.themes.Default()) as demo:
    gr.HTML(f"<div class='sb-banner'>{DISCLAIMER} SignalBridge orders a human review queue. "
            "It does not diagnose sepsis or recommend treatment.</div>")
    gr.Markdown("# SignalBridge\nA tele-ICU or charge nurse can deeply review **3 of 20 charts per 12-hour shift**. "
                "SignalBridge picks which chart to open at each review slot, using only data recorded up to that hour.")
    with gr.Tab("Review round"):
        gr.Markdown("Simulated 20-bed unit built from Hospital A test patients (a capacity-stress "
                    "simulation, not a real ward census).")
        with gr.Row():
            prev_b = gr.Button("◀ Previous slot")
            slot = gr.Slider(0, len(slots) - 1, value=0, step=1, label="Review slot")
            next_b = gr.Button("Next slot ▶")
        with gr.Row():
            miss_b = gr.Button("Jump to the missed case")
            fa_b = gr.Button("Jump to the false alert")
        head = gr.Markdown()
        pick = gr.HTML()
        grid = gr.HTML()
        bed = gr.Dropdown(label="Open a bed's timeline", choices=[])
        plot = gr.Plot(label="Timeline")
        outs = [head, pick, grid, bed, plot]
        slot.change(render_slot, slot, outs)
        prev_b.click(lambda i: max(0, int(i) - 1), slot, slot)
        next_b.click(lambda i: min(len(slots) - 1, int(i) + 1), slot, slot)
        miss_b.click(lambda: find_slot(cases["missed"]["patient_id"]), None, slot).then(
            lambda: timeline(cases["missed"]["patient_id"]), None, plot)
        fa_b.click(lambda: find_slot(cases["false_alert"]["patient_id"]), None, slot)
        bed.change(timeline, bed, plot)
        demo.load(render_slot, slot, outs)
    with gr.Tab("Results"):
        with gr.Row():
            test = gr.Radio(["A", "B"], value="A", label="Test hospital")
            which = gr.Radio(["Home hospital model", "Unseen-hospital model"], value="Home hospital model",
                             label="Model trained at")
            k = gr.Radio([1, 2, 3, 5], value=3, label="Reviews per 12-hour shift")
        res = gr.Dataframe(wrap=True)
        note = gr.Markdown()
        for c in (test, which, k):
            c.change(results, [test, which, k], [res, note])
        demo.load(results, [test, which, k], [res, note])
        gr.Markdown(f"**Missed case:** {cases['missed']['patient_id']} · **False alert:** "
                    f"{cases['false_alert']['patient_id']} (use the buttons on the Review round tab).")
    gr.HTML(f"<div class='sb-banner'>{DISCLAIMER}</div>")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", action="store_true")
    ap.add_argument("--port", type=int, default=7860)
    a = ap.parse_args()
    demo.launch(share=a.share, server_port=a.port)
