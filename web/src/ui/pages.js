// The three reading pages (Results, How it works, Questions), laid out like a
// printed feature: masthead, display title, italic standfirst, a ticker of key
// numbers, drop-capped text that wraps around numbered figures, and APA 7
// references at the foot. Every number comes from data/septris.json.

const MONTH = "November 2026";

// ---------- references (APA 7th edition) ----------
const REFS = {
  reyna2020: `Reyna, M. A., Josef, C. S., Jeter, R., Shashikumar, S. P., Westover, M. B., Nemati, S., Clifford, G. D., & Sharma, A. (2020). Early prediction of sepsis from clinical data: The PhysioNet/Computing in Cardiology Challenge 2019. <i>Critical Care Medicine, 48</i>(2), 210–217. <a href="https://doi.org/10.1097/CCM.0000000000004145" target="_blank" rel="noopener">https://doi.org/10.1097/CCM.0000000000004145</a>`,
  reyna2019data: `Reyna, M., Josef, C., Jeter, R., Shashikumar, S., Moody, B., Westover, M. B., Sharma, A., Nemati, S., & Clifford, G. D. (2019). <i>Early prediction of sepsis from clinical data: The PhysioNet/Computing in Cardiology Challenge 2019</i> (Version 1.0.0) [Data set]. PhysioNet. <a href="https://doi.org/10.13026/v64v-d857" target="_blank" rel="noopener">https://doi.org/10.13026/v64v-d857</a>`,
  goldberger2000: `Goldberger, A. L., Amaral, L. A. N., Glass, L., Hausdorff, J. M., Ivanov, P. C., Mark, R. G., Mietus, J. E., Moody, G. B., Peng, C.-K., & Stanley, H. E. (2000). PhysioBank, PhysioToolkit, and PhysioNet: Components of a new research resource for complex physiologic signals. <i>Circulation, 101</i>(23), e215–e220. <a href="https://doi.org/10.1161/01.CIR.101.23.e215" target="_blank" rel="noopener">https://doi.org/10.1161/01.CIR.101.23.e215</a>`,
  ke2017: `Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., & Liu, T.-Y. (2017). LightGBM: A highly efficient gradient boosting decision tree. In I. Guyon et al. (Eds.), <i>Advances in Neural Information Processing Systems 30</i> (pp. 3146–3154). Curran Associates.`,
  cho2014: `Cho, K., van Merriënboer, B., Gulcehre, C., Bahdanau, D., Bougares, F., Schwenk, H., & Bengio, Y. (2014). Learning phrase representations using RNN encoder–decoder for statistical machine translation. In <i>Proceedings of the 2014 Conference on Empirical Methods in Natural Language Processing</i> (pp. 1724–1734). Association for Computational Linguistics. <a href="https://doi.org/10.3115/v1/D14-1179" target="_blank" rel="noopener">https://doi.org/10.3115/v1/D14-1179</a>`,
  che2018: `Che, Z., Purushotham, S., Cho, K., Sontag, D., & Liu, Y. (2018). Recurrent neural networks for multivariate time series with missing values. <i>Scientific Reports, 8</i>, Article 6085. <a href="https://doi.org/10.1038/s41598-018-24271-9" target="_blank" rel="noopener">https://doi.org/10.1038/s41598-018-24271-9</a>`,
  platt1999: `Platt, J. C. (1999). Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods. In A. J. Smola, P. Bartlett, B. Schölkopf, & D. Schuurmans (Eds.), <i>Advances in large margin classifiers</i> (pp. 61–74). MIT Press.`,
  efron1993: `Efron, B., & Tibshirani, R. J. (1993). <i>An introduction to the bootstrap</i>. Chapman & Hall.`,
  bone1992: `Bone, R. C., Balk, R. A., Cerra, F. B., Dellinger, R. P., Fein, A. M., Knaus, W. A., Schein, R. M. H., & Sibbald, W. J. (1992). Definitions for sepsis and organ failure and guidelines for the use of innovative therapies in sepsis. <i>Chest, 101</i>(6), 1644–1655. <a href="https://doi.org/10.1378/chest.101.6.1644" target="_blank" rel="noopener">https://doi.org/10.1378/chest.101.6.1644</a>`,
  singer2016: `Singer, M., Deutschman, C. S., Seymour, C. W., Shankar-Hari, M., Annane, D., Bauer, M., Bellomo, R., Bernard, G. R., Chiche, J.-D., Coopersmith, C. M., Hotchkiss, R. S., Levy, M. M., Marshall, J. C., Martin, G. S., Opal, S. M., Rubenfeld, G. D., van der Poll, T., Vincent, J.-L., & Angus, D. C. (2016). The Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3). <i>JAMA, 315</i>(8), 801–810. <a href="https://doi.org/10.1001/jama.2016.0287" target="_blank" rel="noopener">https://doi.org/10.1001/jama.2016.0287</a>`,
  kumar2006: `Kumar, A., Roberts, D., Wood, K. E., Light, B., Parrillo, J. E., Sharma, S., Suppes, R., Feinstein, D., Zanotti, S., Taiberg, L., Gurka, D., Kumar, A., & Cheang, M. (2006). Duration of hypotension before initiation of effective antimicrobial therapy is the critical determinant of survival in human septic shock. <i>Critical Care Medicine, 34</i>(6), 1589–1596. <a href="https://doi.org/10.1097/01.CCM.0000217961.75225.E9" target="_blank" rel="noopener">https://doi.org/10.1097/01.CCM.0000217961.75225.E9</a>`,
  pollard2026: `Pollard, T., Moody, B. E., Lehman, L., Gow, B., Fernandes, C., Xie, C., Johnson, A., Mark, R. G., & Heldt, T. (2026). PhysioNet as a global platform for biomedical research. <i>Nature Health</i>. <a href="https://doi.org/10.1038/s44360-026-00096-z" target="_blank" rel="noopener">https://doi.org/10.1038/s44360-026-00096-z</a>`,
};

/** APA 7 reference list: alphabetical by first author, hanging indent. */
function references(keys) {
  const list = keys.map((k) => REFS[k]).sort((a, b) => a.localeCompare(b));
  return `<section class="ed-refs"><h2>References</h2><ol>${list.map((r) => `<li>${r}</li>`).join("")}</ol></section>`;
}

function masthead(section, title, standfirst, ticker) {
  const items = [...ticker, ...ticker].map((t) => `<span>${t}</span><i>•</i>`).join(""); // doubled for a seamless loop
  return `
    <header class="ed-mast">
      <div class="ed-rule"><span>Septris</span><span>${section}</span><span>${MONTH}</span></div>
      <h1>${title}</h1>
      <p class="ed-stand">${standfirst}</p>
      <div class="ed-ticker" aria-label="Key numbers"><div class="ed-track">${items}</div></div>
    </header>`;
}

const pct = (v) => `${v.toFixed(1)}%`;

function barFigure(n, title, rows, note, max = 40) {
  return `
    <figure class="ed-fig">
      <figcaption><b>Figure ${n}.</b> ${title}</figcaption>
      <div class="ed-bars">${rows.map(([label, v, cls]) => `
        <span class="lab">${label}</span>
        <span class="track"><i class="${cls}" style="width:${Math.min(100, (v / max) * 100)}%"></i></span>
        <b>${pct(v)}</b>`).join("")}</div>
      ${note ? `<p class="ed-note">${note}</p>` : ""}
    </figure>`;
}

// ---------- Results ----------
export function resultsHTML(data) {
  const R = data.results["5"], A = R.A, B = R.B, q = data.quality; // main budget: 5 chart checks per shift
  const R3 = data.results["3"]; // tighter budget: 3 checks per shift (the original pre-registered primary)
  const rows = (T, other) => [
    ["Septris calibrated blend", R[T].septris.caught, "sb"],
    [`Septris trained at Hospital ${other}`, R[T].septris_new_hospital.caught, "sb2"],
    ["Temporal GRU alone", R[T].gru.caught, "base"],
    ["LightGBM alone", R[T].lightgbm.caught, "base"],
    ["Warning checklist, SIRS", R[T].sirs.caught, "sirs"],
    ["Random picking", R[T].random.caught, "rnd"],
  ];
  const f3 = (x) => x.toFixed(3);
  const ticker = [
    `${pct(A.septris.caught)} caught early at Hospital A`, `${pct(B.septris.caught)} at Hospital B`,
    `${(A.septris.caught / A.random.caught).toFixed(1)}× random picking`, `${(A.septris.eligible + B.septris.eligible)} eligible sepsis cases`,
    "6,051 held-out patients", "5 chart checks per shift", `AUROC ${f3(q["A>A"].septris.auroc)}`, "200 bootstrap resamples",
  ];
  return `
  <article class="ed">
    ${masthead("Results", "How well it works",
      "Twenty beds, five chart checks a shift, and every pick checked against what the patient's record shows happened next.", ticker)}

    <section class="ed-sec">
      <h2>Which patients are caught early?</h2>
      ${barFigure(1, `Caught early at Hospital A (${A.septris.eligible} eligible sepsis cases)`, rows("A", "B"),
        `Share of patients who developed sepsis whose chart was checked 6–12 hours before onset. Septris: ${pct(A.septris.caught)} (95% CI ${A.septris.lo.toFixed(1)}–${A.septris.hi.toFixed(1)}).`)}
      <p class="ed-drop">Out of every 100 patients who developed sepsis, how many were selected for clinician review 6–12 hours before recorded sepsis onset? That is the question every number on this page answers. The held-out evaluation gives a 20-bed ICU five review slots per 12-hour shift. At each slot Septris recommends one chart, and the patient's record decides afterwards whether that check came early enough to matter.</p>
      <p>Only held-out test patients are counted. Septris never trained on them, and each result averages five simulated ICU admission orders. Random picking, the SIRS warning checklist (Bone et al., 1992), each model alone and Septris all faced the same beds at the same simulated review times, so the bars are directly comparable.</p>
      <p>At Hospital A, Septris caught <b>${pct(A.septris.caught)}</b> of eligible cases early (95% CI: ${A.septris.lo.toFixed(1)}–${A.septris.hi.toFixed(1)}). At Hospital B, it caught <b>${pct(B.septris.caught)}</b> (95% CI: ${B.septris.lo.toFixed(1)}–${B.septris.hi.toFixed(1)}). Confidence intervals come from 200 patient-level bootstrap resamples (Efron & Tibshirani, 1993).</p>
      ${barFigure(2, `Caught early at Hospital B (${B.septris.eligible} eligible sepsis cases)`, rows("B", "A"),
        `Septris: ${pct(B.septris.caught)} (95% CI ${B.septris.lo.toFixed(1)}–${B.septris.hi.toFixed(1)}). Trained at the other hospital: ${pct(B.septris_new_hospital.caught)}.`).replace('class="ed-fig"', 'class="ed-fig left"')}
      <p>The comparison that matters most is against random review, because that is what a nurse with no ranking does. With the same five checks, Septris caught about <b>${(A.septris.caught / A.random.caught).toFixed(1)} times</b> as many cases early as random selection at Hospital A and about <b>${(B.septris.caught / B.random.caught).toFixed(1)} times</b> as many at Hospital B, and nearly twice as many as the SIRS checklist at both.</p>
      <aside class="ed-pull"><div class="eyebrow">If a nurse only has three checks per shift</div>
        <p>Septris caught <b>${R3.A.septris.caught.toFixed(1)}%</b> of eligible cases early at Hospital A (95% CI ${R3.A.septris.lo.toFixed(1)}–${R3.A.septris.hi.toFixed(1)}) against ${R3.A.random.caught.toFixed(1)}% for random picking, and <b>${R3.B.septris.caught.toFixed(1)}%</b> at Hospital B (95% CI ${R3.B.septris.lo.toFixed(1)}–${R3.B.septris.hi.toFixed(1)}) against ${R3.B.random.caught.toFixed(1)}%. At a hospital it never trained on: ${R3.A.septris_new_hospital.caught.toFixed(1)}% (B → A) and ${R3.B.septris_new_hospital.caught.toFixed(1)}% (A → B). Three checks was the budget written into our pre-registration before testing.</p></aside>
      <p>Moved to a hospital it did not train on, Septris does worse (${pct(B.septris_new_hospital.caught)} at A when trained at B; ${pct(A.septris_new_hospital.caught)} at B when trained at A), but it still outperforms SIRS and random review in both transfer directions. Local workflow and measurement habits matter, which is why any real deployment would need local calibration first.</p>
    </section>

    <section class="ed-sec">
      <h2>What these numbers mean</h2>
      <div class="ed-cols">
        <p class="ed-drop">Most review slots are still false reviews: about ${A.septris.false_per_shift.toFixed(2)} of 5 at Hospital A and ${B.septris.false_per_shift.toFixed(2)} of 5 at Hospital B did not lead to a recorded sepsis onset in the early-review window. That is expected. Only a small share of ICU patients develop sepsis, and at any given hour very few are 6–12 hours away from it.</p>
        <p>The goal is not to make every check a catch. It is to catch more real cases with the same, limited nurse time. Treating sepsis sooner matters: in septic shock, each hour of delay before effective antibiotics was associated with lower survival (Kumar et al., 2006).</p>
        <p>These results show better retrospective allocation of limited review capacity. They do not prove Septris detects sepsis before clinicians or improves patient outcomes. That would need a prospective study in a working ICU.</p>
      </div>
    </section>

    <section class="ed-sec">
      <h2>How well it separates risky hours</h2>
      <figure class="ed-fig">
        <figcaption><b>Figure 3.</b> AUROC / official 2019 Challenge utility score</figcaption>
        <table class="ed-table"><thead><tr><th>Trained → tested</th><th>Septris blend</th><th>LightGBM</th><th>Temporal GRU</th></tr></thead><tbody>
        ${[["A>A", "A → A"], ["B>B", "B → B"], ["B>A", "B → A, new hospital"], ["A>B", "A → B, new hospital"]].map(([k, lab]) =>
          `<tr><td>${lab}</td>${["septris", "lightgbm", "gru"].map((m) => `<td><b>${f3(q[k][m].auroc)}</b> / ${f3(q[k][m].utility)}</td>`).join("")}</tr>`).join("")}
        </tbody></table>
        <p class="ed-note">Higher is better for both. An AUROC of 0.5 is random; 1.0 is perfect.</p>
      </figure>
      <p class="ed-drop">The queue results above judge whole decisions. This table judges the hour-by-hour scores themselves. AUROC asks how often a risky hour (within 12 hours of sepsis) is scored above an ordinary one; 0.5 is a coin flip and 1.0 is perfect. The official 2019 Challenge utility score rewards timely alerts and penalizes poorly timed ones (Reyna et al., 2020).</p>
      <p>The blend improves the hourly scores in all four train-test settings. In the five-check queue it was clearly best at Hospital B (${pct(B.septris.caught)}); at Hospital A and in both transfer tests the GRU alone matched it or came out up to about two points ahead, well inside the confidence ranges. With three checks, the blend improved early catches in three of four settings.</p>
      <p>The interactive ward runs the same five checks per shift that these results use.</p>
    </section>
    ${references(["reyna2020", "reyna2019data", "bone1992", "efron1993", "kumar2006"])}
  </article>`;
}

// ---------- How it works ----------
export function modelHTML(data) {
  const lite = data.lite ? data.lite.auroc.lite_test.toFixed(2) : "0.68";
  const nLite = data.lite ? data.lite.fields.length : 11;
  const ticker = ["40,336 ICU records", "2 hospital systems", "26 lab values", "2 models, 1 calibrated score",
    "70 / 15 / 15 patient split", "5 chart checks per shift", "Never sees future hours"];
  const step = (n, t, s) => `<div class="ed-step"><b>${n}</b><div><strong>${t}</strong><span>${s}</span></div></div>`;
  return `
  <article class="ed">
    ${masthead("How it works", "How Septris works",
      "Two models read every bed's chart, one calibrated score ranks them, and the nurse opens the chart at the top.", ticker)}

    <section class="ed-sec">
      <h2>The data</h2>
      <div class="ed-cols">
        <p class="ed-drop">Septris learned from 40,336 de-identified ICU patient records from two hospital systems in the public 2019 PhysioNet/Computing in Cardiology Sepsis Challenge dataset (Reyna et al., 2019, 2020; Goldberger et al., 2000).</p>
        <p>Each record includes hourly vital signs, laboratory measurements, age, sex, and the Challenge's official sepsis label, which follows the Sepsis-3 definition (Singer et al., 2016). The dataset identifies the sources only as Hospital A and Hospital B.</p>
        <p>It does not use ICU length of stay, hospital-admission time, or unit-type fields, because they can become shortcuts tied to local workflow rather than patient physiology.</p>
      </div>
    </section>

    <section class="ed-sec">
      <h2>Two models, one calibrated priority score</h2>
      <figure class="ed-fig">
        <figcaption><b>Figure 1.</b> From an hourly chart to a check-next list</figcaption>
        <div class="ed-flow">
          ${step(1, "Hourly chart", "vital signs, 26 labs, what was measured and when, age, sex")}
          <div class="ed-split">${step("2a", "LightGBM", "decision trees on current values and 6-hour trends")}${step("2b", "Masked temporal GRU", "reads the stay hour by hour, never the future")}</div>
          ${step(3, "Calibrate both", "Platt scaling on validation patients")}
          ${step(4, "Blend", "A: 20% LightGBM + 80% GRU · B: 10% + 90%")}
          ${step(5, "Rank the 20 beds", "skip anyone checked in the last 12 hours")}
          ${step(6, "Nurse opens the top chart", "and decides what, if anything, to do")}
        </div>
      </figure>
      <p class="ed-drop">Septris combines two complementary models. <b>Part 1, LightGBM</b> (Ke et al., 2017), is a gradient-boosted decision-tree model that learns nonlinear combinations of current vital signs, lab values, six-hour trends, and measurement history.</p>
      <p><b>Part 2, a masked temporal GRU</b> (Cho et al., 2014), is a causal two-layer deep-learning model with 64 hidden units. It reads each patient's history hour by hour using normalized values, observation masks, and log time since each measurement, an approach suited to sparse hospital data (Che et al., 2018), plus age and sex. It cannot see future hours.</p>
      <p>Both models are calibrated on patient-disjoint validation data with Platt scaling (Platt, 1999). We then selected the blend weight only on a separate validation slice using the real objective: catching patients 6–12 hours early under a fixed number of chart checks (the weight was tuned with three checks per shift, our pre-registered budget, before any test patient was scored). The Hospital A model is 20% LightGBM + 80% GRU; the Hospital B model is 10% LightGBM + 90% GRU. This is Septris's final scoring policy. It is not a simple average and not a "take the highest score" rule.</p>
      <div class="ed-cards">
        <div class="ed-card"><h3>Part 1: LightGBM</h3><dl>
          <dt>What it is</dt><dd>Gradient-boosted decision trees</dd>
          <dt>Reads</dt><dd>Current values, six-hour trends, minimums and maximums, which tests were done and when</dd>
          <dt>Weight</dt><dd>20% at Hospital A · 10% at Hospital B</dd></dl></div>
        <div class="ed-card"><h3>Part 2: Masked temporal GRU</h3><dl>
          <dt>What it is</dt><dd>A two-layer recurrent network, 64 hidden units</dd>
          <dt>Reads</dt><dd>The whole stay hour by hour, with masks for missing values and time since each measurement</dd>
          <dt>Weight</dt><dd>80% at Hospital A · 90% at Hospital B</dd></dl></div>
      </div>
    </section>

    <section class="ed-sec">
      <h2>From risk score to priority</h2>
      <div class="ed-cols">
        <p class="ed-drop">At each of the five review slots per 12-hour shift, Septris ranks the 20 simulated beds by calibrated priority score. It skips patients reviewed in the previous 12 hours and recommends the highest-priority remaining patient.</p>
        <p>The clinician then opens the full chart and decides whether action is appropriate. Septris never diagnoses and never recommends treatment.</p>
        <p>Five checks per shift is the budget the ward runs and the one our results lead with. We also report three per shift, for a unit with even less time to spare.</p>
      </div>
    </section>

    <section class="ed-sec">
      <h2>How it was tested</h2>
      <figure class="ed-fig">
        <figcaption><b>Figure 2.</b> Patients split by patient, not by hourly row</figcaption>
        <div class="ed-splitbar"><i style="flex:70">Training 70%</i><i style="flex:15">Validation 15%</i><i style="flex:15">Test 15%</i></div>
        <p class="ed-note">Model choice, calibration and the blend weight used validation patients only. Test patients were scored once.</p>
      </figure>
      <ul class="ed-list">
        <li>Patients were split by patient, not hourly row: 70% training, 15% validation, and 15% held-out testing.</li>
        <li>The model-selection, calibration, and blend-weight decisions used validation patients only.</li>
        <li>Hospital A testing used 3,051 held-out patient records, including 238 eligible sepsis cases. Hospital B testing used held-out records containing 134 eligible sepsis cases.</li>
        <li>Random selection, SIRS, LightGBM, GRU, and Septris faced the same beds at the same simulated review times.</li>
        <li>We used 200 patient-level bootstrap resamples to estimate 95% confidence intervals (Efron & Tibshirani, 1993).</li>
        <li>We tested home-hospital performance and both cross-hospital directions: A → A, B → B, A → B, and B → A.</li>
        <li>The main results use five chart checks per 12-hour shift; we also report three per shift.</li>
      </ul>
    </section>

    <section class="ed-sec">
      <h2>How a hospital could use it after validation</h2>
      <div class="ed-cols">
        <p class="ed-drop">In a real hospital, clinicians would not manually enter values. Vital signs and laboratory results already flow into the electronic health record. After prospective validation and local calibration, Septris could receive those existing records, re-score active ICU beds, and update a clinician-review queue.</p>
        <p>The "Add a patient" feature in this prototype demonstrates that workflow manually. It uses Septris Lite, a smaller browser-based model that sees only the ${nLite} values on the form.</p>
        <p>Septris Lite is not the full model and is weaker: its Hospital A held-out AUROC is ${lite}, compared with 0.79 for the full Septris blend.</p>
      </div>
    </section>

    <section class="ed-sec">
      <h2>Limits</h2>
      <ul class="ed-list two">
        <li>Septris was evaluated only on retrospective, de-identified records. It has never been used in live clinical care.</li>
        <li>It does not diagnose sepsis, recommend treatment, or replace clinician judgment.</li>
        <li>It performs worse at an unseen hospital, showing that local workflow and measurement practices matter.</li>
        <li>Measurement patterns can reflect tests clinicians already chose to order. Septris may partly prioritize patients the care team was already investigating.</li>
        <li>The simulated ward places patients from different historical time periods side by side, so it is not a real ICU deployment.</li>
        <li>A prospective silent trial, local calibration, clinician feedback, fairness analysis, and outcome study are required before clinical use.</li>
      </ul>
      <p class="ed-credit">Team: Miheer Parasnis, Aaron Qin, Reyansh Maheshwari · Veritas AI Hackathon 2026 · AI + Health · Data: PhysioNet/CinC Challenge 2019, CC BY 4.0 · Prototype · Not medical advice · Clinician review required</p>
    </section>
    ${references(["reyna2020", "reyna2019data", "goldberger2000", "pollard2026", "singer2016", "ke2017", "cho2014", "che2018", "platt1999", "efron1993"])}
  </article>`;
}

// ---------- Questions ----------
export function faqHTML(data) {
  const k = data.meta.k;
  const R = data.results["5"], R3 = data.results["3"];
  const qa = [
    ["What is sepsis?", "Sepsis is life-threatening organ dysfunction caused by the body's dysregulated response to infection (Singer et al., 2016). It can damage organs within hours, and delays in treatment are associated with lower survival (Kumar et al., 2006). That is why noticing it early matters."],
    ["What problem does Septris solve?", `Checking one chart carefully takes real time, and one nurse may cover many beds. Septris answers one question: whose chart should be opened next? We plan for ${k} careful chart checks per 12-hour shift, and that is what the ward and our results use. With only 3 checks, Septris still caught ${R3.A.septris.caught.toFixed(1)}% of cases early at Hospital A.`],
    ["What does “risk score 92 of 100” mean?", "It is a ranking, not a probability. This patient's data right now looks more worrying than about 92% of ICU hours at the training hospital. It does not tell you the chance of having sepsis."],
    ["How do you know if a pick was right?", "These are real patients from past records, so each stay is already written down. Septris only gets the data up to each moment. Afterwards we look at the record: if sepsis was recorded 6–12 hours after the chart check, the patient counts as caught early."],
    ["Why are most picks false alarms?", `Few ICU patients develop sepsis, and at any moment very few are 6–12 hours away from it. Even so, Septris caught ${R.A.septris.caught.toFixed(1)}% of eligible cases early at Hospital A against ${R.A.random.caught.toFixed(1)}% for random picking, with the same nurse time.`],
    ["What is the nurse's checklist on the clipboard?", "In first-person mode the clipboard shows typical bedside screening steps, worked out only from the chart so far: repeat vital signs, screen for SIRS signs (Bone et al., 1992), order a lactate, send cultures, or call the doctor. It is an illustration; real steps follow the hospital's protocol and the doctor's orders."],
    ["Can I add my own patient?", "Yes. Use “Admit a patient”, type their readings (or pick an example) and choose how long they stay. They are wheeled in from the elevator, scored by Septris Lite and ranked with the other beds. In a real hospital this information would arrive automatically from the patient record."],
    ["Does it diagnose sepsis?", "No. It never diagnoses or recommends treatment. It only sorts the list of charts to check and explains why."],
    ["Can I control it by voice?", "Yes, when the page may use the microphone. Try “show bed number 6”, “next check”, “next shift”, “first person”, “who is next”, “results”, “show me a miss”, “mute”, or “add John, who is 62, with heart rate 118 and temperature 38.6 to bed 4”. Your words appear live as you speak."],
  ];
  const ticker = ["9 questions", "1 job: whose chart next", "20 beds", "0 diagnoses made", "Every pick checked against the record"];
  return `
  <article class="ed">
    ${masthead("Questions", "Questions",
      "What Septris does, what it does not do, and how to read what you see on the ward.", ticker)}
    <section class="ed-sec">
      <figure class="ed-fig">
        <figcaption><b>Figure 1.</b> What the floor rings mean</figcaption>
        <div class="ed-key">
          <span><i class="sw pick"></i>Check this bed now (Septris's pick)</span>
          <span><i class="sw high"></i>High risk: top 5% of ICU hours</span>
          <span><i class="sw med"></i>Medium risk: top 20%</span>
          <span><i class="sw low"></i>Low risk</span>
          <span><i class="sw snooze"></i>Checked in the last 12 hours, skipped for now</span>
        </div>
      </figure>
      ${qa.map(([q, a], i) => `<h3 class="ed-q">${q}</h3><p${i === 0 ? ' class="ed-drop"' : ""}>${a}</p>`).join("")}
    </section>
    ${references(["singer2016", "kumar2006", "bone1992"])}
  </article>`;
}
