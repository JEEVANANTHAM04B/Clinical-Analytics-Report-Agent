"""
app/ai/insight_generator.py
===========================
Generates certified evidence-backed insights from verified SQL query results.
Supports both CDISC clinical-trial relational data and legacy EHR data.
"""

from decimal import Decimal
import re
from typing import Any

from app.ai.llm import generate_response
from app.clinical import build_clinical_question_plan


def _is_clinical_context(
    user_question: str,
    query_results: list[dict[str, Any]],
    clinical_plan: dict[str, Any] | None = None,
) -> bool:
    """
    Determine if the current analysis belongs to the CDISC clinical trial dataset.
    """
    if clinical_plan and clinical_plan.get("is_supported"):
        return True

    if query_results:
        sample_keys = {k.upper() for k in query_results[0].keys()}
        clinical_markers = {
            "USUBJID", "STUDYID", "TRT01A", "ARM", "SITEID", "SITE_NAME",
            "AESER", "AEDECOD", "AEBODSYS", "AESEV", "TRTEMFL", "SAFFL",
            "CHG", "AVAL", "BASE", "AVISIT", "PARAM", "PARAMCD", "RESPFL",
            "TOTAL_SUBJECTS", "ENROLLED_SUBJECTS", "ADVERSE_EVENT_RATE_PCT",
            "RESPONSE_RATE_PCT", "MEAN_CHANGE", "TOTAL_SAFETY_SUBJECTS"
        }
        if sample_keys.intersection(clinical_markers):
            return True

    plan = build_clinical_question_plan(user_question)
    return plan.is_supported


def _deterministic_insight_fallback(
    user_question: str,
    query_results: list[dict[str, Any]],
    insight_evidence: dict[str, Any],
    clinical_plan: dict[str, Any] | None = None,
) -> str | None:
    """
    Generate an insight directly from verified query results and
    deterministic evidence when the LLM is temporarily unavailable.
    """
    if not query_results:
        return "No verified results were returned for the requested analysis."

    question = user_question.lower()
    row_count = len(query_results)
    first_row = query_results[0]

    # ---------------------------------------------------------
    # 1. Legacy EHR length of stay pattern
    # ---------------------------------------------------------
    if "average length of stay" in question and ("diagnosis" in question or "encounter" in question):
        maximum = insight_evidence.get("maximum")
        minimum = insight_evidence.get("minimum")

        if maximum and minimum:
            r_count = insight_evidence.get("row_count", len(query_results))
            max_category = maximum.get("category")
            max_value = maximum.get("value")
            min_value = minimum.get("value")
            min_categories = minimum.get("categories", [])
            dimension = "encounter classes" if any("encounter" in k.lower() for k in first_row.keys()) else "categories"

            insight = (
                f"Based on the clinical dataset covering {r_count} {dimension}, "
                f"the highest average length of stay was "
                f"{max_category} at {max_value:.4f} days. "
            )
            if len(min_categories) == 1:
                insight += f"The lowest average length of stay was {min_value:.4f} days for {min_categories[0]}."
            else:
                insight += f"The lowest average length of stay was {min_value:.4f} days across multiple {dimension}."
            return insight

    # ---------------------------------------------------------
    # 2. CDISC Clinical Trial Canonical Patterns
    # ---------------------------------------------------------
    matched_kpi = clinical_plan.get("matched_kpi_id") if clinical_plan else None

    # (a) Total subjects / enrollment count
    if matched_kpi == "TOTAL_SUBJECTS" or ("enrolled" in question and "how many" in question):
        val = (
            first_row.get("total_enrolled_subjects")
            or first_row.get("enrolled_subjects")
            or first_row.get("total_subjects")
            or list(first_row.values())[0]
        )
        return f"The study currently includes {int(val):,} enrolled subjects."

    # (b) Average age
    if matched_kpi == "AVERAGE_AGE" or ("average age" in question or "mean age" in question or "old" in question or "age" in question):
        mean_val = (
            first_row.get("mean_age")
            or first_row.get("average_age")
            or first_row.get("avg_age")
        )
        if mean_val is None:
            for v in first_row.values():
                try:
                    mean_val = float(v)
                    break
                except (ValueError, TypeError):
                    continue
        if mean_val is not None:
            val = float(mean_val)
            val_str = f"{val:.2f}" if val % 1 != 0 else f"{int(val)}"
            return f"The average age of enrolled subjects in the study is {val_str} years."
        return "Demographic age analysis completed across enrolled subjects."

    # (c) Serious adverse event count
    if matched_kpi == "SERIOUS_AE_COUNT" or ("serious adverse events" in question and "how many" in question):
        val = int(
            first_row.get("serious_adverse_events")
            or first_row.get("serious_ae_count")
            or list(first_row.values())[0]
        )
        return f"A total of {val:,} serious adverse events (AESER = 'Y') occurred across the study."

    # (d) Adverse event count
    if matched_kpi == "ADVERSE_EVENT_COUNT" or ("adverse events" in question and "how many" in question):
        val = int(
            first_row.get("total_adverse_events")
            or first_row.get("adverse_event_count")
            or list(first_row.values())[0]
        )
        return f"A total of {val:,} adverse events occurred across the study."

    # (e) Adverse event rate by treatment arm
    if matched_kpi == "AE_RATE_BY_TREATMENT" or ("adverse event rate" in question and "treatment" in question):
        arm_rates = []
        for r in query_results:
            arm = r.get("treatment_arm") or r.get("TRT01A") or r.get("arm")
            rate = r.get("adverse_event_rate_pct") or r.get("ae_rate_pct")
            if arm is not None and rate is not None:
                arm_rates.append(f"{arm} at {float(rate):.2f}%")
        if arm_rates:
            return f"Across treatment arms, the adverse event rate was {', and '.join(arm_rates)}."

    # (f) Efficacy response rate
    if matched_kpi == "EFFICACY_RESPONSE_RATE" or ("efficacy response" in question or "response rate" in question):
        arm_rates = []
        for r in query_results:
            arm = r.get("treatment_arm") or r.get("TRT01A") or r.get("arm")
            rate = r.get("response_rate_pct") or r.get("efficacy_rate_pct")
            if arm is not None and rate is not None:
                arm_rates.append(f"{arm} at {float(rate):.2f}%")
        if arm_rates:
            return f"Across treatment arms, the efficacy response rate (RESPFL = 'Y') was {', and '.join(arm_rates)}."

    # (g) Laboratory change from baseline
    if matched_kpi == "LAB_CHANGE_FROM_BASELINE" or ("lab change" in question or "laboratory change" in question):
        if row_count == 1:
            val = float(first_row.get("mean_change") or first_row.get("avg_change") or list(first_row.values())[0])
            visit_str = f" at {first_row.get('AVISIT')}" if first_row.get("AVISIT") else ""
            return f"The mean laboratory change from baseline{visit_str} was {val:.2f}."
        else:
            changes = []
            for r in query_results:
                arm = r.get("treatment_arm") or r.get("TRT01A") or r.get("PARAM")
                val = r.get("mean_change") or r.get("avg_change")
                if arm is not None and val is not None:
                    changes.append(f"{arm} at {float(val):.2f}")
            if changes:
                return f"The mean laboratory change from baseline was {', and '.join(changes)}."

    # (h) Vital sign change from baseline
    if matched_kpi == "VITAL_SIGN_CHANGE_FROM_BASELINE" or ("vital sign change" in question or "vital signs" in question):
        if row_count == 1:
            val = float(first_row.get("mean_change") or first_row.get("avg_change") or list(first_row.values())[0])
            return f"The mean vital sign change from baseline was {val:.2f}."
        else:
            changes = []
            for r in query_results:
                param = r.get("PARAM") or r.get("treatment_arm") or r.get("AVISIT")
                val = r.get("mean_change") or r.get("avg_change")
                if param is not None and val is not None:
                    changes.append(f"{param} at {float(val):.2f}")
            if changes:
                return f"The mean vital sign change from baseline was {', and '.join(changes)}."

    # (i) Site enrollment / highest site
    if matched_kpi == "ENROLLMENT_BY_SITE" or ("site" in question and "enrollment" in question):
        site_id = first_row.get("SITEID") or first_row.get("siteid")
        site_name = first_row.get("SITE_NAME") or first_row.get("site_name")
        cnt = first_row.get("enrolled_subjects") or first_row.get("enrollment_count") or first_row.get("total_subjects")
        if site_id and cnt is not None:
            name_str = f" ({site_name})" if site_name else ""
            return f"Site {site_id}{name_str} recorded the highest enrollment with {int(cnt):,} enrolled subjects."

    # ---------------------------------------------------------
    # 3. Generic Single-Row Summary
    # ---------------------------------------------------------
    if row_count == 1:
        parts = []
        for col, val in first_row.items():
            col_name = col.replace("_", " ").title()
            if isinstance(val, (int, float, Decimal)):
                val_str = f"{float(val):.2f}" if isinstance(val, (float, Decimal)) and float(val) % 1 != 0 else f"{int(val):,}"
            else:
                val_str = str(val)
            parts.append(f"{col_name} is {val_str}")
        return f"Based on the verified clinical trial dataset, {', and '.join(parts)}."

    # ---------------------------------------------------------
    # 4. Generic Multi-Row Comparison
    # ---------------------------------------------------------
    maximum = insight_evidence.get("maximum")
    dim_keys = [k for k, v in first_row.items() if isinstance(v, str)]
    num_keys = [k for k, v in first_row.items() if isinstance(v, (int, float, Decimal))]
    dim_name = dim_keys[0].replace("_", " ") if dim_keys else "records"

    insight_parts = [f"Based on the verified clinical trial dataset across {row_count} {dim_name}:"]
    if maximum and maximum.get("category"):
        val_str = f"{float(maximum['value']):.2f}" if float(maximum['value']) % 1 != 0 else str(int(maximum['value']))
        insight_parts.append(f"the highest was {maximum['category']} with {val_str}.")
    elif dim_keys and num_keys:
        first_cat = first_row.get(dim_keys[0])
        first_val = first_row.get(num_keys[0])
        insight_parts.append(f"{first_cat} recorded {first_val}.")

    return " ".join(insight_parts)


def generate_insight(
    user_question: str,
    query_results: list[dict[str, Any]],
    rag_context: str = "",
    insight_evidence: dict[str, Any] | None = None,
    clinical_plan: dict[str, Any] | None = None,
    analysis_plan: str | None = None,
) -> str:
    """
    Generate a clinical analytics insight using:
    1. Verified SQL results
    2. RAG reference context
    3. Deterministically calculated evidence
    4. CDISC clinical trial domain context

    The LLM explains the verified evidence and comparisons.
    If the LLM is temporarily unavailable or rate-limited,
    the deterministic fallback provides verified facts.
    """
    if insight_evidence is None:
        insight_evidence = {}

    is_clinical = _is_clinical_context(
        user_question=user_question,
        query_results=query_results,
        clinical_plan=clinical_plan,
    )

    if is_clinical:
        domain_guidelines = """
CLINICAL TRIAL DOMAIN GUIDANCE & CONSTRAINTS:
- The data is CDISC Clinical Trial Relational Data (SDTM / ADaM standards).
- Always refer to participants as "subjects" or "study participants". Never use "patients" or "inpatient encounters".
- Key Dimensions:
  * dm / adsl: Subject demographics, randomized treatment arms (TRT01A), and safety population (SAFFL).
  * ae / adae: Adverse events, severity (AESEV), seriousness (AESER = 'Y'), and treatment-emergent status (TRTEMFL = 'Y').
  * lb / adlb: Laboratory parameters (PARAM), visits (AVISIT), baseline (BASE), and change from baseline (CHG).
  * vs / advs: Vital signs (PARAM), visits (AVISIT), baseline (BASE), and change from baseline (CHG).
  * adresp: Efficacy response indicators (RESPFL = 'Y').
  * sites: Clinical trial investigation sites and enrollment counts.
- STRICT SCIENTIFIC & SAFETY CONSTRAINTS:
  1. Use ONLY the verified SQL results for numerical figures and categories.
  2. For highest/maximum claims, use the deterministic insight evidence.
  3. For lowest/minimum claims, use the deterministic insight evidence.
  4. NO CAUSAL CLAIMS: Do NOT state that a treatment "caused" an adverse event or improvement. State observations, comparisons, and associations only (e.g. "subjects in Drug X had an adverse event rate of...").
  5. NO UNSUPPORTED STATISTICAL CLAIMS: Do NOT claim "statistical significance", "p < 0.05", or "statistically proven" unless specific statistical test figures are in the verified results.
  6. NO EHR CONFUSION: Do NOT interpret percentages or changes as hospital length of stay, diagnosis counts, or inpatient admissions.
"""
    else:
        domain_guidelines = """
LEGACY HEALTHCARE EHR DOMAIN GUIDANCE:
- Data is hospital Electronic Health Record (EHR) data covering patients, encounters, and conditions.
- Interpret encounters, encounter classes (inpatient, emergency, etc.), and diagnostic categories accurately.
"""

    prompt = f"""
You are an expert clinical analytics intelligence assistant.

Answer the user's question using ONLY:
1. The verified SQL results.
2. The provided reference context.
3. The deterministic insight evidence.

User question:
{user_question}

Verified SQL results:
{query_results}

Deterministic insight evidence:
{insight_evidence}

Reference context:
{rag_context}

{domain_guidelines}

General Rules:
- Do not invent statistics, percentages, or values.
- Do not invent categories, treatment arms, or visits.
- Do not calculate rankings yourself; use the deterministic evidence.
- Answer the user's specific question directly and prioritize the key findings needed to answer it.
- Do not provide medical diagnosis or treatment recommendations.
- Keep the answer concise (2-4 sentences) and suitable for a clinical data review team.
- Return only the final insight text.
"""

    try:
        return generate_response(prompt)

    except RuntimeError as error:
        print(
            "LLM insight generation unavailable. "
            "Checking deterministic insight fallback..."
        )

        fallback_insight = _deterministic_insight_fallback(
            user_question=user_question,
            query_results=query_results,
            insight_evidence=insight_evidence,
            clinical_plan=clinical_plan,
        )

        if fallback_insight is not None:
            print("Using deterministic insight fallback.")
            return fallback_insight

        raise error