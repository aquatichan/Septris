---
title: Septris
emoji: 🩺
colorFrom: blue
colorTo: gray
sdk: gradio
app_file: app.py
pinned: false
license: cc-by-4.0
---

# Septris demo

**This project is a prototype and is not medical advice.**

Demo of a budgeted sepsis review queue (5 chart checks per 20-bed,
12-hour shift). It replays Hospital A test patients one check at a time,
shows which chart Septris opens and why, what happened in hindsight,
and a running scoreboard against random checking. It is built on the PhysioNet/CinC Challenge 2019 data (CC BY 4.0).
The app reads only the precomputed files in `artifacts/`; it never trains a
model or downloads data.

## Deploy to a free Hugging Face Space

1. Create a new Space (SDK: Gradio, hardware: free CPU).
2. Upload everything in this `app/` folder (`app.py`, `requirements.txt`,
   this `README.md` and the `artifacts/` folder).
3. The Space builds and starts on its own.

Full code, method and results: https://github.com/aquatichan/SignalBridge-Sepsis
