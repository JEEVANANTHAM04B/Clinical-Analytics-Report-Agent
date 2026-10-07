# DeepEval Insight Generation Evaluation Report — Clinical Analytics

## 1. Objective

This report documents the LLM-assisted evaluation of the **Insight Generation** layer in the Clinical Analytics platform using the **DeepEval** framework. The goal is to evaluate whether generated clinical narrative insights produced from verified SQL results and clinical reference context maintain factual consistency (Faithfulness) and directly address the clinical user question (Answer Relevancy), without introducing hallucinations, medical overreach, or unsupported numerical claims.

---

## 2. Model & Execution Configuration

The evaluation reuses the project's standardized Gemini configuration and DeepEval async parameters:

- **Generation Model**: `gemini-3.5-flash-lite` (via production `generate_insight` in `app/ai/insight_generator.py`)
- **Evaluation Judge Model**: `gemini-3.5-flash-lite` (via `GeminiModel` in `deepeval.models`)
- **DeepEval Framework Version**: `4.2.8`
- **Execution Mode**: Sequential execution with rate-limit resiliency (`max_concurrent=1`, `throttle_value=1`)
- **Passing Threshold**: `0.70` for all metrics

---

## 3. Evaluation Metrics

Each test case is evaluated across two core DeepEval evaluation dimensions:

### A. FaithfulnessMetric
Measures whether the statements in the generated insight are strictly grounded in the verified SQL results, deterministic statistical evidence summary, and reference context. Any factual contradictions or unsupported statistics penalize the score.
- **Threshold**: `0.70`
- **Evaluation Criteria**: Grounding against verified query result rows, calculated row counts, and min/max evidence.

### B. AnswerRelevancyMetric
Measures how concisely, directly, and completely the generated insight answers the specific clinical question without drifting into tangential topics or unsolicited medical advice.
- **Threshold**: `0.70`
- **Evaluation Criteria**: Direct answering of ranking, comparison, or status requested in the prompt.

---

## 4. Benchmark Dataset

The evaluation suite comprises 5 curated clinical analytics test cases defined in `evals/datasets/insight_deepeval_test_cases.json`, derived from the production deterministic insight evaluation suite:

| Test Case ID | Category | Clinical Question | Verified Data Characteristics |
| :--- | :--- | :--- | :--- |
| **`insight_deepeval_001`** | `average_length_of_stay` | *Which diagnosis has the highest average length of stay?* | 3 rows; Anemia (4.0), Hypertension (3.0), Diabetes (2.0) |
| **`insight_deepeval_002`** | `encounter_counts` | *Compare the number of inpatient and emergency encounters.* | 2 rows; Inpatient (120), Emergency (80) |
| **`insight_deepeval_003`** | `cost_analysis` | *Which encounter class has the highest total claim cost?* | 2 rows; Inpatient ($50,000 cost / $30,000 coverage), Emergency ($35,000 / $20,000) |
| **`insight_deepeval_004`** | `demographics` | *Which gender and race combination has the highest patient count?* | 3 rows; Female White (150), Male White (120), Female Black (90) |
| **`insight_deepeval_005`** | `empty_result` | *Show encounters matching an impossible filter.* | 0 rows (`[]`); empty result set safety verification |

---

## 5. Results Table

All generated insights were produced dynamically using the real production `generate_insight()` function and evaluated against `FaithfulnessMetric` and `AnswerRelevancyMetric`:

| Test ID | Category | Faithfulness Score | Faithfulness Status | Relevancy Score | Relevancy Status | Overall Result |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`insight_deepeval_001`** | Average LOS | **1.00** | PASS ✅ | **1.00** | PASS ✅ | **PASS** |
| **`insight_deepeval_002`** | Encounter Counts | **1.00** | PASS ✅ | **1.00** | PASS ✅ | **PASS** |
| **`insight_deepeval_003`** | Cost Analysis | **1.00** | PASS ✅ | **1.00** | PASS ✅ | **PASS** |
| **`insight_deepeval_004`** | Demographics | **1.00** | PASS ✅ | **1.00** | PASS ✅ | **PASS** |
| **`insight_deepeval_005`** | Empty Result Safety | **1.00** | PASS ✅ | **1.00** | PASS ✅ | **PASS** |

---

## 6. Aggregate Summary & Pass Rates

| Metric | Passed / Total | Average Score | Pass Rate |
| :--- | :---: | :---: | :---: |
| **Faithfulness** | 5 / 5 | **1.00** | **100.0%** |
| **Answer Relevancy** | 5 / 5 | **1.00** | **100.0%** |
| **Overall (Both Metrics Passed)** | **5 / 5** | — | **100.0%** |

- **Total Test Cases**: `5`
- **Total Metric Evaluations**: `10`
- **Total Metric Passed**: `10`
- **Total Metric Failed**: `0`
- **Overall Pass Rate**: `100.0%` (on the 5-case benchmark)

---

## 7. Observations & Key Insights

1. **Deterministic Grounding Prevents Hallucination**:
   The production architecture separates calculation from summarization. By computing min/max rankings and row counts in Python (`app/analytics/insight_evidence.py`) and providing them explicitly to `generate_insight`, the LLM reliably cites correct maximums (e.g., Anemia at 4.0 days, Inpatient costs at $50,000.0) without hallucinating unverified figures.
2. **Safe Handling of Empty Results**:
   When queried with an impossible filter resulting in `0` rows, the model explicitly acknowledges that 0 encounters matched without inventing phantom clinical cohorts or patterns, achieving a Faithfulness and Relevancy score of `1.00`.
3. **Concise, Professional Tone**:
   The generated answers stay focused on the clinical analytic dimensions requested without injecting unsolicited diagnostic opinions, clinical disclaimers, or conversational filler.

---

## 8. Limitations & Scope

> **Important Scope Statement:**  
> This evaluation assesses **only the predefined 5-case benchmark evaluation suite**. These results do **not** prove comprehensive clinical correctness across arbitrary medical questions, complex longitudinal cohorts, or uncurated database schemas.

Key limitations include:
- **Benchmark Coverage**: The current suite covers 5 canonical patterns (length of stay, encounter volumes, financial claims, patient demographics, and empty result safety). It does not test edge cases such as extreme outliers, multi-level hierarchy rollups, or contradictory evidence sets.
- **Single Judge Architecture**: DeepEval evaluations were performed using `gemini-3.5-flash-lite`. Cross-model validation (e.g., GPT-4o or Claude 3.5 Sonnet as dual judges) was not executed.
- **Free-Tier Rate Constraints**: In free-tier environments, sequential execution with pacing (`throttle_value=1`) is required to respect the 15 RPM quota.

---

## 9. Conclusion

The production Insight Generation layer (`app/ai/insight_generator.py`) successfully passes the DeepEval evaluation benchmark with a **100% pass rate** across both Faithfulness and Answer Relevancy metrics (average score **1.00** on both). The combination of SQL execution guarantees, Python-based deterministic evidence extraction, and targeted LLM prompting provides a robust baseline for evidence-backed clinical analytics reporting.
