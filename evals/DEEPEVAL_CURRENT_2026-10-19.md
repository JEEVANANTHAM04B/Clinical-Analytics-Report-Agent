# Clinical Analytics Platform — DeepEval evaluation report

**Run date:** 19 October 2026  
**Project state:** current local checkout  
**Outcome:** local evaluation completed; external LLM judging requires explicit approval

## What was evaluated

The existing project has a 25-question CDISC golden benchmark, a 12-case pipeline evaluation dataset, and a 5-case DeepEval insight dataset. This run used **DeepEval 4.2.8 `ExactMatchMetric` offline** to compare the application's deterministic clinical-domain classification against the 25 golden questions. The per-case machine-readable output is in [DEEPEVAL_OFFLINE_2026-10-19.json](DEEPEVAL_OFFLINE_2026-10-19.json).

DeepEval's Gemini-based `FaithfulnessMetric` and `AnswerRelevancyMetric` were **not run**. An automatic approval review rejected the judge-based suite because it could transmit clinical workflow questions, result rows, and insights to Google. Thus no current faithfulness or answer-relevancy score is available. The older `DEEPEVAL_CLINICAL_REPORT` and `INSIGHT_DEEPEVAL_REPORT` files are historical results, not evidence for this run.

## Results

| Check | Result | Interpretation |
| --- | ---: | --- |
| Offline DeepEval domain exact match | **24/25 (96%)** | One benchmark-label mismatch |
| Local evaluation suite: question mapping, visualization, security, registry, synthetic KPI | **19/19 passed** | No external model call |
| CDISC golden benchmark and SQL regression tests | **21/21 passed** | Includes local MySQL query checks |
| Backend dashboard, schema, ingestion, identity, PDF, report history, reliability tests | **133/133 passed** | No external model call |
| Frontend component tests | **37/37 passed** | Initial sandbox-temp failure resolved by rerun |
| Frontend production build | **Passed** | Vite warned about `pdfjs-dist` eval and a large bundle |
| Python environment dependency check | **Passed** | `pip check` reported no broken requirements |
| DeepEval faithfulness and answer relevancy | **Not measured** | External Gemini judge blocked pending explicit authorization |
| Full 12-case live pipeline runner and 5-case insight judge runner | **Not run** | These invoke external generation or judging and may transmit clinical data |

### DeepEval mismatch

`gold_enr_004`, “What is the treatment-arm distribution?”, expects the **enrollment** domain, while `build_clinical_question_plan` returns **demographics**. The returned plan is supported and uses `adsl`, `TRT01A`, and `COUNT(DISTINCT adsl.USUBJID) GROUP BY adsl.TRT01A`. The observed failure is therefore a **domain-label mismatch**; this evaluation does not establish an incorrect count or SQL calculation. The benchmark label and the application's question taxonomy should be reviewed together before changing clinical logic.

All other golden-domain matches passed: demographics 3/3, disposition 3/3, efficacy 4/4, enrollment 3/4, laboratory 3/3, safety 5/5, vital signs 3/3.

## Coverage limits and next step

DeepEval exact match tests only deterministic question classification. The accompanying pytest suites cover additional local functionality, but the current run does **not** prove end-to-end model quality, insight faithfulness, answer relevance, clinical correctness of every generated answer, or full UI behavior. No clinical source records, database schema, SQL-generation logic, or expected results were changed.

To complete the existing Gemini-based DeepEval evaluation, explicit authorization is needed to send the selected clinical questions, verified result rows, and generated insights to Google's Gemini service. After authorization, run the judge cases, record scores and reasons for every case, and update this report. If such transmission is not allowed, a locally hosted compatible judge or a data-minimized evaluation dataset would be required.
