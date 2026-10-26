"""
app/analytics/followup_service.py
=================================
Lightweight Follow-Up Analysis Engine for Clinical Analytics.

Provides contextual follow-up answers using existing verified results,
approved schema context, and lightweight read-only SQL
without restarting the LangGraph pipeline or prompting for human approval.
Supports both CDISC clinical-trial relational data and legacy EHR data.
"""

import re
import logging
from typing import Any

from app.schemas.analytics import FollowUpRequest, FollowUpResponse
from app.ai.llm import generate_response
from app.analytics.sql_validator import validate_sql
from app.analytics.query_executor import execute_query
from app.analytics.result_validator import validate_results

logger = logging.getLogger("clinical_analytics.followup")


def _is_clinical_context(
    selected_tables: list[str],
    current_results: list[dict[str, Any]],
    current_question: str | None = None,
    current_sql: str | None = None,
) -> bool:
    """
    Detect whether the follow-up session targets the CDISC clinical-trial dataset
    or legacy EHR dataset. Defaults to clinical-trial dataset as active.
    """
    clinical_markers = {
        "dm", "adsl", "ae", "adae", "adlb", "advs", "adresp",
        "study", "sites", "lb", "ex", "qs", "vs"
    }
    legacy_markers = {
        "encounters", "conditions", "patients", "medications", "observations", "procedures"
    }

    # Check selected tables
    tables_lower = {t.lower() for t in (selected_tables or [])}
    if any(t in tables_lower for t in clinical_markers):
        return True
    if any(t in tables_lower for t in legacy_markers):
        return False

    # Check SQL query if provided
    if current_sql:
        sql_lower = current_sql.lower()
        if any(f" {t} " in f" {sql_lower} " or f"`{t}`" in sql_lower for t in clinical_markers):
            return True
        if any(f" {t} " in f" {sql_lower} " or f"`{t}`" in sql_lower for t in legacy_markers):
            return False

    # Check result keys
    if current_results:
        sample_keys = {k.upper() for k in current_results[0].keys()}
        cdisc_cols = {
            "USUBJID", "STUDYID", "TRT01A", "ARM", "SITEID", "SITE_NAME",
            "AESER", "AEDECOD", "AEBODSYS", "AESEV", "TRTEMFL", "SAFFL",
            "CHG", "AVAL", "BASE", "AVISIT", "PARAM", "PARAMCD", "RESPFL",
            "TOTAL_SUBJECTS", "ENROLLED_SUBJECTS", "ADVERSE_EVENT_RATE_PCT",
            "RESPONSE_RATE_PCT", "MEAN_CHANGE", "TOTAL_SAFETY_SUBJECTS"
        }
        if sample_keys.intersection(cdisc_cols):
            return True

    # Check question terminology
    if current_question:
        q_lower = current_question.lower()
        if any(term in q_lower for term in ["subject", "arm", "treatment", "adverse event", "trial", "site", "cdisc", "efficacy"]):
            return True
        if any(term in q_lower for term in ["patient", "encounter", "inpatient", "length of stay"]):
            return False

    # Default to True (active clinical trial database)
    return True


def _is_unrelated_new_analysis(question: str, current_question: str | None, selected_tables: list[str]) -> bool:
    """
    Detect if the user is asking for a completely new, unrelated analytical topic
    (e.g., asking for payer/financial/allergy metrics when currently looking at trial results).
    """
    q_lower = question.lower()

    # Domains that indicate an entirely new analysis if not in current context
    new_analysis_triggers = [
        ("payer", ["payer", "payers", "insurance", "reimbursement", "coverage"]),
        ("cost", ["cost", "revenue", "billing", "charges", "financial", "expenditure"]),
        ("allergy", ["allergy", "allergies", "allergen"]),
        ("immunization", ["vaccine", "vaccination", "immunization", "immunizations"]),
        ("pharmacokinetics", ["pharmacokinetics", "pk concentration", "auc", "cmax", "half-life"]),
        ("genomics", ["genomics", "dna sequencing", "mrna expression", "variant call"]),
    ]

    current_q_lower = (current_question or "").lower()
    tables_lower = [t.lower() for t in (selected_tables or [])]

    for domain, terms in new_analysis_triggers:
        if any(term in q_lower for term in terms):
            # Check if domain was already in current question or selected tables
            in_current = any(term in current_q_lower for term in terms) or domain in tables_lower
            if not in_current:
                return True

    return False


def _extract_metric_key_and_label(row: dict[str, Any]) -> tuple[str, str, str]:
    """
    Identify category key, metric key, and friendly label from a result row.
    Prioritizes CDISC clinical trial dimensions and metrics, with EHR fallback.
    """
    keys = list(row.keys())
    if not keys:
        return "", "", ""

    clinical_dim_candidates = [
        "treatment_arm", "trt01a", "arm", "actarm",
        "site_name", "siteid",
        "aedecod", "aebodsys", "aesev", "aeser",
        "param", "paramcd", "avisit", "visit",
        "sex", "race", "ethnic",
        "encounter_class", "encounterclass", "diagnosis", "description", "class", "name", "condition"
    ]
    label_key = keys[0]
    for cand in clinical_dim_candidates:
        matched = next((k for k in keys if cand == k.lower() or cand in k.lower()), None)
        if matched:
            label_key = matched
            break

    clinical_metric_candidates = [
        "adverse_event_rate_pct", "ae_rate_pct", "response_rate_pct", "efficacy_rate_pct",
        "mean_change", "avg_change", "chg", "aval",
        "total_enrolled_subjects", "enrolled_subjects", "total_subjects", "subject_count",
        "serious_adverse_events", "total_adverse_events", "adverse_event_count",
        "average_age", "avg_age", "patient_count", "avg_length_of_stay",
        "stay", "los", "rate", "pct", "count", "value", "duration"
    ]
    metric_key = keys[1] if len(keys) > 1 else keys[0]
    for cand in clinical_metric_candidates:
        matched = next((k for k in keys if cand == k.lower() or cand in k.lower()), None)
        if matched:
            metric_key = matched
            break

    metric_lower = metric_key.lower()
    if "rate" in metric_lower or "pct" in metric_lower:
        metric_label = "rate"
    elif "age" in metric_lower:
        metric_label = "average age"
    elif "change" in metric_lower or "chg" in metric_lower:
        metric_label = "mean change"
    elif "stay" in metric_lower or "los" in metric_lower:
        metric_label = "average length of stay"
    elif any(w in metric_lower for w in ["subject", "enrolled", "patient", "count", "events"]):
        metric_label = "count"
    else:
        metric_label = metric_key.replace("_", " ")

    return label_key, metric_key, metric_label


def _format_metric_val(val: float, metric_key: str) -> str:
    """Format numeric value with appropriate clinical unit."""
    m_lower = metric_key.lower()
    if "rate" in m_lower or "pct" in m_lower:
        return f"{val:.1f}%"
    if "age" in m_lower:
        return f"{val:.1f} years"
    if "stay" in m_lower or "los" in m_lower:
        return f"{val:.1f} days"
    if any(w in m_lower for w in ["count", "subjects", "events", "enrolled"]):
        return f"{int(val):,}"
    if "change" in m_lower or "chg" in m_lower:
        return f"{val:.2f}"
    if val % 1 != 0:
        return f"{val:.2f}"
    return f"{int(val):,}"


def _get_category_group(label_key: str) -> tuple[str, str]:
    """Return plural category group and singular form."""
    k_lower = label_key.lower()
    if any(w in k_lower for w in ["arm", "trt01a", "treatment"]):
        return "treatment arms", "treatment arm"
    if "site" in k_lower:
        return "clinical sites", "clinical site"
    if "param" in k_lower:
        return "parameters", "parameter"
    if any(w in k_lower for w in ["aedecod", "event"]):
        return "adverse events", "adverse event"
    if "aebodsys" in k_lower:
        return "body systems", "body system"
    if "visit" in k_lower:
        return "study visits", "study visit"
    if "class" in k_lower:
        return "encounter classes", "encounter class"
    if any(w in k_lower for w in ["diag", "desc", "condition"]):
        return "diagnoses", "diagnosis"
    return "cohorts", "cohort"


def _answer_deterministically(
    question: str,
    results: list[dict[str, Any]],
) -> str | None:
    """
    Provide an accurate, verified deterministic answer directly from result rows
    as a primary mechanism or fallback when LLM is unavailable.
    """
    if not results:
        return None

    q_lower = question.lower()
    label_key, metric_key, metric_label = _extract_metric_key_and_label(results[0])

    # Parse numbers safely
    parsed_items = []
    for r in results:
        label = str(r.get(label_key, "Unknown"))
        raw_val = r.get(metric_key)
        try:
            val = float(raw_val)
        except (ValueError, TypeError):
            continue
        parsed_items.append((label, val, r))

    if not parsed_items:
        return None

    sorted_by_val = sorted(parsed_items, key=lambda x: x[1], reverse=True)
    highest = sorted_by_val[0]
    lowest = sorted_by_val[-1]

    category_group, singular_cat = _get_category_group(label_key)
    highest_str = _format_metric_val(highest[1], metric_key)
    lowest_str = _format_metric_val(lowest[1], metric_key)

    m_lower = metric_key.lower()
    unit_suffix = "%" if ("rate" in m_lower or "pct" in m_lower) else (" days" if ("stay" in m_lower or "los" in m_lower) else (" years" if "age" in m_lower else ""))

    # Pattern 1: Highest / Peak / Most / Maximum / Longest / Top
    if any(w in q_lower for w in ["highest", "peak", "maximum", "max", "most", "longest", "top"]):
        return (
            f"{highest[0]} has the highest {metric_label} at {highest_str} "
            f"among the {category_group} returned in the current analysis."
        )

    # Pattern 2: Lowest / Minimum / Least / Shortest / Bottom
    if any(w in q_lower for w in ["lowest", "minimum", "min", "least", "shortest", "bottom"]):
        return (
            f"{lowest[0]} has the lowest {metric_label} at {lowest_str} "
            f"among the {category_group} returned in the current analysis."
        )

    # Pattern 3: Threshold check (e.g., "above 2 days", "> 2", "more than 3", "above 20%")
    match_thresh = re.search(r'(?:above|over|greater than|more than|>)\s*(\d+(?:\.\d+)?)', q_lower)
    if match_thresh:
        thresh = float(match_thresh.group(1))
        matching = [item for item in sorted_by_val if item[1] > thresh]
        count = len(matching)
        if count == 0:
            return f"None of the {category_group} in the current verified results have a {metric_label} above {thresh}{unit_suffix}."
        names = ", ".join(f"{m[0]} ({_format_metric_val(m[1], metric_key)})" for m in matching)
        return (
            f"There {'is' if count == 1 else 'are'} {count} {singular_cat if count == 1 else category_group} "
            f"with a {metric_label} above {thresh}{unit_suffix}: {names}."
        )

    # Pattern 4: "Why" or explanation
    if "why" in q_lower or "explain" in q_lower:
        mentioned = None
        for item in parsed_items:
            if item[0].lower() in q_lower or any(word in q_lower for word in item[0].lower().split() if len(word) > 4):
                mentioned = item
                break
        if not mentioned:
            mentioned = highest

        if mentioned:
            return (
                f"The verified results report {metric_label} of "
                f"{_format_metric_val(mentioned[1], metric_key)} for {mentioned[0]}, "
                "but do not establish why."
            )

    # Pattern 5: Specific entity inquiry (e.g., "What about Drug A?", "What about Pneumonia?")
    for item in parsed_items:
        clean_item_name = item[0].lower()
        if clean_item_name in q_lower or any(w in q_lower for w in clean_item_name.split() if len(w) > 4):
            val_display = _format_metric_val(item[1], metric_key)
            return f"{item[0]} recorded a {metric_label} of {val_display} in the current results."

    # Pattern 6: General summary of findings
    return (
        f"The verified analysis encompasses {len(parsed_items)} {category_group}. "
        f"{highest[0]} has the highest ({highest_str}), while {lowest[0]} has the lowest ({lowest_str})."
    )


def _generate_llm_answer(
    question: str,
    results: list[dict[str, Any]],
    original_results: list[dict[str, Any]],
    current_question: str | None,
    current_insight: str | None,
    current_plan: str | None,
    conversation_history: list[Any],
    selected_tables: list[str],
    is_clinical: bool = True,
) -> str | None:
    """
    Generate a natural, clinician-friendly answer using Gemini over the verified data context.
    """
    if not results and not original_results:
        return None

    try:
        results_summary = "\n".join(
            f"- {', '.join(f'{k}: {v}' for k, v in r.items())}"
            for r in results[:10]
        ) if results else "No rows returned."
        original_results_summary = "\n".join(
            f"- {', '.join(f'{k}: {v}' for k, v in r.items())}"
            for r in original_results[:10]
        ) if original_results else "No original analysis rows supplied."

        history_str = ""
        if conversation_history:
            recent_turns = conversation_history[-4:]
            history_str = "\n".join(
                f"{getattr(t, 'role', 'user').upper()}: {getattr(t, 'content', '')}"
                for t in recent_turns
            )

        active_tables_str = ', '.join(selected_tables) if selected_tables else ('dm, ae, adsl, adae, adlb, advs, adresp' if is_clinical else 'patients, encounters, conditions')

        clinical_guidelines = """
CLINICAL TRIAL SPECIFIC CONSTRAINTS:
- Refer to study participants as 'subjects' or 'study participants'. Never use 'patients'.
- Reference trial dimensions (treatment arms, adverse events, study visits, lab/vital parameters) appropriately.
- Do NOT mention hospital inpatient stays or encounter classes.
- Do NOT make unsupported causal claims or claim statistical significance without explicit test results.
""" if is_clinical else ""

        prompt = f"""
You are an expert Clinical Healthcare Analytics Intelligence Assistant.
Answer the following follow-up question from a clinical data analyst.

CURRENT ANALYSIS SESSION CONTEXT:
- Primary Question: {current_question or 'Clinical Analytics Overview'}
- Approved Analysis Plan: {current_plan or 'None supplied'}
- Active Selected Tables: {active_tables_str}
- Original Verified Analysis Results:
{original_results_summary}
- Latest Verified Follow-Up Results:
{results_summary}
- Certified Clinical Insight: {current_insight or 'None'}

CONVERSATION HISTORY:
{history_str if history_str else 'No prior follow-up questions in this session.'}

NEW FOLLOW-UP QUESTION:
"{question}"
{clinical_guidelines}
CRITICAL CONCISENESS RULES:
1. OUTPUT EXACTLY 1, 2, OR 3 SHORT LINES (maximum 3 sentences). NEVER exceed 3 lines under any circumstance.
2. Directly answer the question with exact clinical figures from the verified results immediately.
3. NO conversational filler or preamble (do not say "Based on the verified results" or "According to the dataset").
4. Base your answer ONLY on the supplied analysis context and verified data. Do not invent statistics, clinical facts, or explanations.
5. If the supplied results do not answer the question, state that the evidence is insufficient and recommend a new analysis.
6. Plain text only. No markdown headers, bullet points, or multiple paragraphs.
"""
        response = generate_response(prompt)
        if response and len(response.strip()) > 5:
            clean_resp = response.strip()
            # Enforce max 3 lines/sentences strictly
            raw_lines = [l.strip() for l in clean_resp.split("\n") if l.strip()]
            if len(raw_lines) > 3:
                clean_resp = "\n".join(raw_lines[:3])

            # If formatted as a single block of prose, ensure at most 3 sentences
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_resp) if s.strip()]
            if len(sentences) > 3:
                clean_resp = " ".join(sentences[:3])

            return clean_resp
    except Exception as exc:
        logger.warning("LLM follow-up generation failed: %s", exc)

    return None


def _try_follow_up_sql(
    question: str,
    selected_tables: list[str],
    current_question: str | None,
    is_clinical: bool = True,
) -> tuple[str | None, list[dict[str, Any]] | None, str | None]:
    """
    If additional data is genuinely needed, generate and execute a minimal,
    safe read-only SQL query against MySQL using only approved tables.
    """
    q_lower = question.lower()

    # Only attempt SQL if question asks for numbers/counts not in current results
    sql_indicators = [
        "how many total", "count of all", "number of patients with",
        "number of subjects", "count of subjects", "how many subjects",
        "how many serious", "total subjects", "total enrolled", "list all"
    ]
    if not any(ind in q_lower for ind in sql_indicators):
        return None, None, None

    # 1. Clinical trial context
    if is_clinical:
        # Check for known safe clinical trial patterns:

        # (a) Total enrolled subjects
        if any(w in q_lower for w in ["total subjects", "total enrolled", "how many subjects are enrolled", "how many total subjects"]):
            sql = "SELECT COUNT(DISTINCT USUBJID) as total_enrolled_subjects FROM dm"
            is_valid, _ = validate_sql(sql)
            if is_valid:
                rows = execute_query(sql)
                if rows:
                    cnt = rows[0].get("total_enrolled_subjects", 0)
                    answer = f"There are {cnt:,} total enrolled subjects in the study."
                    return sql, rows, answer

        # (b) Serious adverse events count
        if "serious" in q_lower and ("adverse" in q_lower or "ae" in q_lower):
            sql = "SELECT COUNT(*) as serious_adverse_events FROM ae WHERE AESER = 'Y'"
            is_valid, _ = validate_sql(sql)
            if is_valid:
                rows = execute_query(sql)
                if rows:
                    cnt = rows[0].get("serious_adverse_events", 0)
                    answer = f"There are {cnt:,} serious adverse events recorded across the study."
                    return sql, rows, answer

        # (c) Subjects in a specific treatment arm
        if "arm" in q_lower or "treatment" in q_lower or "drug" in q_lower or "placebo" in q_lower:
            for arm in ["drug a", "drug b", "placebo", "standard care"]:
                if arm in q_lower:
                    sql = f"SELECT COUNT(DISTINCT USUBJID) as subject_count FROM dm WHERE LOWER(ARM) LIKE '%{arm}%'"
                    is_valid, _ = validate_sql(sql)
                    if is_valid:
                        rows = execute_query(sql)
                        if rows:
                            cnt = rows[0].get("subject_count", 0)
                            answer = f"There are {cnt:,} subjects assigned to {arm.title()}."
                            return sql, rows, answer

        # (d) Subjects with a specific adverse event
        for ae_term in ["headache", "nausea", "fatigue", "dizziness", "rash", "vomiting", "pyrexia"]:
            if ae_term in q_lower:
                sql = (
                    f"SELECT COUNT(DISTINCT USUBJID) as subject_count "
                    f"FROM ae "
                    f"WHERE LOWER(AEDECOD) LIKE '%{ae_term}%'"
                )
                is_valid, _ = validate_sql(sql)
                if is_valid:
                    rows = execute_query(sql)
                    if rows:
                        cnt = rows[0].get("subject_count", 0)
                        answer = f"There are {cnt:,} subjects who experienced {ae_term.title()} in the study."
                        return sql, rows, answer

        # (e) Enrollment at a specific site
        site_match = re.search(r'site\s*(\d+)', q_lower)
        if site_match:
            site_id = site_match.group(1)
            sql = f"SELECT COUNT(DISTINCT USUBJID) as subject_count FROM dm WHERE SITEID = '{site_id}'"
            is_valid, _ = validate_sql(sql)
            if is_valid:
                rows = execute_query(sql)
                if rows:
                    cnt = rows[0].get("subject_count", 0)
                    answer = f"There are {cnt:,} subjects enrolled at Site {site_id}."
                    return sql, rows, answer

    # 2. Legacy EHR fallback
    else:
        if "patient" in q_lower and ("with" in q_lower or "diagnosed" in q_lower):
            for diag in ["anemia", "pneumonia", "appendectomy", "diabetes", "migraine"]:
                if diag in q_lower:
                    sql = (
                        f"SELECT COUNT(DISTINCT encounters.PATIENT) as patient_count "
                        f"FROM conditions "
                        f"JOIN encounters ON conditions.ENCOUNTER = encounters.Id "
                        f"WHERE LOWER(conditions.DESCRIPTION) LIKE '%{diag}%'"
                    )
                    is_valid, msg = validate_sql(sql)
                    if is_valid:
                        rows = execute_query(sql)
                        if rows:
                            count = rows[0].get("patient_count", 0)
                            answer = f"There are {count:,} patients diagnosed with {diag.capitalize()} in the active dataset."
                            return sql, rows, answer

    return None, None, None


def process_followup_question(request: FollowUpRequest) -> FollowUpResponse:
    """
    Main entry point for processing a follow-up analysis question.
    """
    question = request.question.strip()
    results = request.current_results or request.original_results

    is_clinical = _is_clinical_context(
        selected_tables=request.selected_tables,
        current_results=results,
        current_question=request.current_question,
        current_sql=request.current_sql,
    )

    # 1. Check if this is a completely new, unrelated analytical topic
    if _is_unrelated_new_analysis(question, request.current_question, request.selected_tables):
        return FollowUpResponse(
            status="new_analysis_suggested",
            question=question,
            answer=(
                "This question requests an independent analytical domain outside the current context. "
                "Please submit it via the primary analysis trigger above to execute the complete pipeline."
            ),
            source="new_analysis",
            is_new_analysis=True,
            verified=False,
            confidence=0.5,
        )

    # 2. Check if lightweight follow-up SQL is genuinely required
    sql, sql_rows, sql_answer = _try_follow_up_sql(
        question=question,
        selected_tables=request.selected_tables,
        current_question=request.current_question,
        is_clinical=is_clinical,
    )
    if sql and sql_answer:
        validation = validate_results(sql_rows or [])
        if not validation["valid"]:
            raise ValueError(
                f"Follow-up SQL results failed validation: {validation['message']}"
            )
        return FollowUpResponse(
            status="success",
            question=question,
            answer=sql_answer,
            source="follow_up_sql",
            is_new_analysis=False,
            sql_query=sql,
            verified=True,
            confidence=0.98,
            follow_up_results=validation["rows"],
        )

    # Validate supplied context too; client-provided rows are not automatically verified.
    validation = validate_results(results)
    if not validation["valid"]:
        return FollowUpResponse(question=question, status="insufficient_context", answer=validation["message"], verified=False, confidence=0.0)
    results = validation["rows"]

    # 3. Answer from verified results using LLM reasoning
    llm_answer = _generate_llm_answer(
        question=question,
        results=results,
        original_results=request.original_results,
        current_question=request.current_question,
        current_insight=request.current_insight,
        current_plan=request.current_plan,
        conversation_history=request.conversation_history,
        selected_tables=request.selected_tables,
        is_clinical=is_clinical,
    )
    if llm_answer:
        from app.ai.insight_validator import validate_insight
        from app.analytics.insight_evidence import build_insight_evidence
        if not validate_insight(llm_answer, results, build_insight_evidence(results))["valid"]:
            llm_answer = None
    if llm_answer:
        return FollowUpResponse(
            status="success",
            question=question,
            answer=llm_answer,
            source="verified_results",
            is_new_analysis=False,
            sql_query=None,
            verified=True,
            confidence=0.95,
        )

    # 4. Deterministic reasoning fallback from verified result rows
    deterministic_answer = _answer_deterministically(
        question=question,
        results=results,
    )
    if deterministic_answer:
        return FollowUpResponse(
            status="success",
            question=question,
            answer=deterministic_answer,
            source="verified_results",
            is_new_analysis=False,
            sql_query=None,
            verified=True,
            confidence=0.99,
        )

    # 5. Do not imply an answer is verified when no supplied results support it.
    return FollowUpResponse(
        status="insufficient_context",
        question=question,
        answer=(
            "The supplied verified results do not provide enough information to answer this follow-up. "
            "Run a new analysis with the required data."
        ),
        source="verified_results",
        is_new_analysis=False,
        sql_query=None,
        verified=False,
        confidence=0.0,
    )
