"""
app/ingestion/relationship_regenerator.py
=========================================

AI-Assisted Relationship Proposal Generator

Purpose:
    When a human analyst rejects a relationship candidate, this module
    asks the LLM to propose another relationship using the available schema.

Architecture:

    Human Reject
         |
         v
    LLM Proposal
         |
         v
    Schema Validation
         |
         v
    Deterministic Data Validation
         |
         v
    Human Review

Important:
    The LLM only proposes.

    Python verifies the schema.

    relationship_detector.py verifies the actual data.

    The LLM never approves relationships and never writes to MySQL.
"""

import json
import re
from typing import Dict, List, Optional, Union, Any, Tuple

from pydantic import BaseModel, Field

from app.core.logging_config import get_logger
from app.ai.llm import generate_response
from app.schemas.relationships import RejectedRelationship


logger = get_logger(__name__)


# =============================================================================
# Proposal Data Contract
# =============================================================================

class ProposedRelationship(BaseModel):
    """
    Structured relationship proposal produced by the LLM.

    Possible statuses:

        VALID_ALTERNATIVE
        NO_ALTERNATIVE
    """

    status: str = Field(
        ...,
        description="VALID_ALTERNATIVE or NO_ALTERNATIVE",
    )

    parent_table: str = Field(
        "",
        description="Proposed parent table name",
    )

    parent_column: str = Field(
        "",
        description="Proposed parent key column",
    )

    child_table: str = Field(
        "",
        description="Proposed child table name",
    )

    child_column: str = Field(
        "",
        description="Proposed child foreign-key column",
    )

    reasoning: str = Field(
        ...,
        description="Reason for the proposal",
    )

    is_valid_schema: bool = Field(
        False,
        description="True when all proposed tables and columns exist",
    )

    validation_error: Optional[str] = Field(
        None,
        description="Schema validation error",
    )


# =============================================================================
# Schema Catalog
# =============================================================================

def extract_schema_catalog(
    available_schema: Union[Dict[str, Any], List[Any]]
) -> Dict[str, List[str]]:
    """
    Normalizes the supplied schema into:

        {
            "patients": ["Id", "BIRTHDATE", ...],
            "encounters": ["Id", "PATIENT", ...]
        }
    """

    catalog: Dict[str, List[str]] = {}

    if isinstance(available_schema, dict):

        for table, columns in available_schema.items():

            if isinstance(columns, list):

                column_names = []

                for item in columns:

                    if isinstance(item, dict) and "name" in item:
                        column_names.append(str(item["name"]))

                    elif isinstance(item, str):
                        column_names.append(item)

                catalog[str(table)] = column_names

    elif isinstance(available_schema, list):

        for item in available_schema:

            if hasattr(item, "dataset_name") and hasattr(
                item,
                "column_names",
            ):

                catalog[str(item.dataset_name)] = [
                    str(column)
                    for column in item.column_names
                ]

    return catalog


def format_catalog_for_prompt(
    catalog: Dict[str, List[str]]
) -> str:
    """
    Formats the schema catalog for the LLM prompt.
    """

    lines = []

    for table, columns in catalog.items():

        lines.append(
            f"- Table `{table}`: "
            f"columns [{', '.join(columns)}]"
        )

    return "\n".join(lines)


# =============================================================================
# JSON Parser
# =============================================================================

def parse_llm_json_response(
    raw_text: str,
) -> Dict[str, Any]:
    """
    Safely extracts a JSON object from LLM output.

    Supported formats:

        1. Plain JSON

        2. Markdown JSON:
           ```json
           {...}
           ```

        3. Conversational text containing a JSON object

    Safety behavior:

        - Never converts natural-language reasoning into a relationship.
        - Only returns a result when valid JSON can be parsed.
        - Removes common markdown wrappers.
        - Handles JSON surrounded by explanatory text.
        - Raises a controlled ValueError when no valid JSON exists.
    """

    if not raw_text or not raw_text.strip():
        raise ValueError(
            "LLM returned an empty response while generating "
            "an alternative relationship."
        )

    cleaned = raw_text.strip()

    # =========================================================================
    # STEP 1: Remove markdown code fences
    # =========================================================================

    code_block_match = re.search(
        r"```(?:json)?\s*([\s\S]*?)\s*```",
        cleaned,
        re.IGNORECASE,
    )

    if code_block_match:
        cleaned = code_block_match.group(1).strip()

    # =========================================================================
    # STEP 2: Try parsing the complete response directly
    # =========================================================================

    try:

        parsed = json.loads(cleaned)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # =========================================================================
    # STEP 3: Find JSON object inside conversational text
    #
    # Use JSONDecoder.raw_decode instead of a greedy regex.
    # This allows explanatory text before/after a valid JSON object.
    # =========================================================================

    decoder = json.JSONDecoder()

    for match in re.finditer(r"\{", cleaned):

        start_index = match.start()

        candidate = cleaned[start_index:]

        try:

            parsed, _ = decoder.raw_decode(candidate)

            if isinstance(parsed, dict):
                logger.info(
                    "Successfully extracted JSON object from "
                    "conversational LLM output."
                )

                return parsed

        except json.JSONDecodeError:
            continue

    # =========================================================================
    # STEP 4: No valid JSON was found
    #
    # IMPORTANT:
    # Do NOT convert natural-language output into a relationship.
    # The relationship must come from structured LLM output and then undergo
    # deterministic validation.
    # =========================================================================

    logger.warning(
        "Failed to parse valid JSON from LLM output. "
        f"Raw response: {raw_text[:1000]}"
    )

    raise ValueError(
        "LLM did not return a valid JSON relationship proposal. "
        "The model returned non-JSON output. "
        f"Raw response: {raw_text[:500]}"
    )


# =============================================================================
# Core Function
# =============================================================================

def propose_alternative_relationship(
    rejected_relationship: Union[
        RejectedRelationship,
        Dict[str, Any],
    ],
    analyst_feedback: str,
    available_schema: Union[
        Dict[str, Any],
        List[Any],
    ],
) -> ProposedRelationship:
    """
    Ask LLM to propose an alternative relationship.

    The LLM must:

        1. Inspect every available table.
        2. Inspect available columns.
        3. Avoid the rejected relationship.
        4. Look for another logical parent/child key relationship.
        5. Return VALID_ALTERNATIVE if one exists.
        6. Return NO_ALTERNATIVE only after considering the full schema.

    The LLM does NOT validate actual row-level referential integrity.
    That is handled by relationship_detector.py.
    """

    # =========================================================================
    # 1. Extract rejected relationship
    # =========================================================================

    if isinstance(
        rejected_relationship,
        RejectedRelationship,
    ):

        rejected_parent_table = (
            rejected_relationship.parent_table
        )

        rejected_parent_column = (
            rejected_relationship.parent_column
        )

        rejected_child_table = (
            rejected_relationship.child_table
        )

        rejected_child_column = (
            rejected_relationship.child_column
        )

    elif isinstance(
        rejected_relationship,
        dict,
    ):

        rejected_parent_table = str(
            rejected_relationship.get(
                "parent_table",
                "",
            )
        ).strip()

        rejected_parent_column = str(
            rejected_relationship.get(
                "parent_column",
                "",
            )
        ).strip()

        rejected_child_table = str(
            rejected_relationship.get(
                "child_table",
                "",
            )
        ).strip()

        rejected_child_column = str(
            rejected_relationship.get(
                "child_column",
                "",
            )
        ).strip()

    else:

        raise TypeError(
            "rejected_relationship must be a "
            "RejectedRelationship instance or dictionary"
        )

    # =========================================================================
    # 2. Extract schema
    # =========================================================================

    catalog = extract_schema_catalog(
        available_schema
    )

    if not catalog:

        raise ValueError(
            "available_schema must contain at least one "
            "valid table with columns"
        )

    catalog_text = format_catalog_for_prompt(
        catalog
    )

    # =========================================================================
    # 3. Build LLM prompt
    # =========================================================================

    prompt = f"""
You are a database relationship analysis assistant for a clinical
healthcare analytics platform.

A human clinical analyst rejected one automatically detected relationship.

Your job is to search the ENTIRE AVAILABLE DATABASE SCHEMA and determine
whether another reasonable foreign-key relationship can be proposed.

==================================================
REJECTED RELATIONSHIP
==================================================

Parent table:
{rejected_parent_table}

Parent column:
{rejected_parent_column}

Child table:
{rejected_child_table}

Child column:
{rejected_child_column}

==================================================
ANALYST FEEDBACK
==================================================

{analyst_feedback}

==================================================
AVAILABLE DATABASE SCHEMA
==================================================

{catalog_text}

==================================================
IMPORTANT INSTRUCTIONS
==================================================

You MUST inspect ALL tables listed above.

Do NOT stop after examining only the rejected parent and child tables.

Look across every available table for another possible relationship.

A relationship normally has this structure:

parent_table.primary_or_unique_key
        ->
child_table.foreign_key

Common examples include:

patients.Id -> encounters.PATIENT

patients.Id -> conditions.PATIENT

patients.Id -> medications.PATIENT

patients.Id -> observations.PATIENT

patients.Id -> procedures.PATIENT

encounters.Id -> conditions.ENCOUNTER

encounters.Id -> medications.ENCOUNTER

encounters.Id -> observations.ENCOUNTER

encounters.Id -> procedures.ENCOUNTER

These are ONLY examples.

You must use the actual tables and columns supplied in the schema.

==================================================
STRICT RULES
==================================================

1. Use ONLY tables present in the schema.

2. Use ONLY columns present in the schema.

3. Never invent a table.

4. Never invent a column.

5. Do NOT return the exact rejected relationship.

6. Search ALL available tables before deciding NO_ALTERNATIVE.

7. If another reasonable relationship exists, return VALID_ALTERNATIVE.

8. If multiple alternatives exist, return ONE alternative that is
   different from the rejected relationship.

9. Prefer relationships where:
   - parent column looks like an identifier/key
   - child column looks like a foreign key
   - column names indicate a logical relationship
   - the relationship is meaningful for clinical analytics

10. Do NOT claim that a relationship has been proven from row values.
    Python will perform deterministic data validation after your response.

11. Do NOT approve the relationship.

12. Do NOT write to a database.

13. Do NOT generate SQL.

14. Return ONLY JSON.

15. Do NOT return markdown.

==================================================
DECISION PROCESS
==================================================

Before returning your answer, mentally perform these steps:

STEP 1:
List all available tables.

STEP 2:
Inspect their available columns.

STEP 3:
Exclude the exact rejected relationship.

STEP 4:
Look for another logical parent-key -> child-foreign-key relationship
across ALL remaining tables.

STEP 5:
If an alternative exists, return it.

STEP 6:
Only if no reasonable alternative exists, return NO_ALTERNATIVE.

==================================================
OUTPUT FORMAT — CRITICAL
==================================================

Return ONLY a single valid JSON object.

DO NOT return:
- explanations
- reasoning
- analysis
- markdown
- code fences
- ```json
- text before the JSON
- text after the JSON
- partial JSON

The response must begin with {{ and end with }}.

For a valid alternative, return exactly this structure:

{{
  "status": "VALID_ALTERNATIVE",
  "parent_table": "table_name",
  "parent_column": "column_name",
  "child_table": "table_name",
  "child_column": "column_name",
  "reasoning": "short explanation"
}}

For no alternative, return:

{{
  "status": "NO_ALTERNATIVE",
  "parent_table": null,
  "parent_column": null,
  "child_table": null,
  "child_column": null,
  "reasoning": "No valid alternative relationship was identified from the supplied schema."
}}

IMPORTANT:
- Use only tables from AVAILABLE_SCHEMA.
- Use only columns from AVAILABLE_SCHEMA.
- Do not return the rejected relationship.
- Do not invent relationships.
- Do not generate SQL.
- Do not approve the relationship.
- Python deterministic validation will decide whether the proposal is actually valid.

Again:
YOUR ENTIRE RESPONSE MUST BE ONE VALID JSON OBJECT.
NOTHING ELSE.
"""

    logger.info(
        "Requesting alternative relationship proposal for rejected: "
        f"{rejected_parent_table}.{rejected_parent_column} -> "
        f"{rejected_child_table}.{rejected_child_column}"
    )

    # =========================================================================
    # 4. Call LLM
    # =========================================================================

    raw_response = generate_response(
        prompt
    )

    # =========================================================================
    # 5. Parse JSON (with exactly one controlled retry if non-JSON)
    # =========================================================================

    try:
        parsed = parse_llm_json_response(
            raw_response
        )
    except ValueError as exc:
        logger.warning(
            f"Initial LLM response was not valid JSON: {exc}. "
            "Retrying once with strict JSON correction prompt."
        )

        retry_prompt = (
            "Your previous response was invalid because it was not valid JSON.\n\n"
            "Return ONLY the JSON object.\n"
            "No explanation.\n"
            "No reasoning.\n"
            "No markdown.\n"
            "No code fences.\n"
            "No text before or after the JSON.\n\n"
            "The entire response must start with { and end with }.\n\n"
            "Use exactly the required schema:\n"
            "{\n"
            '  "status": "VALID_ALTERNATIVE",\n'
            '  "parent_table": "...",\n'
            '  "parent_column": "...",\n'
            '  "child_table": "...",\n'
            '  "child_column": "...",\n'
            '  "reasoning": "..."\n'
            "}\n\n"
            "If no valid alternative exists:\n"
            "{\n"
            '  "status": "NO_ALTERNATIVE",\n'
            '  "parent_table": null,\n'
            '  "parent_column": null,\n'
            '  "child_table": null,\n'
            '  "child_column": null,\n'
            '  "reasoning": "..."\n'
            "}"
        )

        retry_response = generate_response(
            retry_prompt
        )

        parsed = parse_llm_json_response(
            retry_response
        )

    status = str(
        parsed.get(
            "status",
            "",
        )
    ).strip().upper()

    reasoning = str(
        parsed.get(
            "reasoning",
            "",
        )
    ).strip()

    # =========================================================================
    # 6. NO_ALTERNATIVE
    # =========================================================================

    if status == "NO_ALTERNATIVE":

        logger.info(
            "LLM found no alternative relationship."
        )

        return ProposedRelationship(
            status="NO_ALTERNATIVE",
            parent_table="",
            parent_column="",
            child_table="",
            child_column="",
            reasoning=reasoning,
            is_valid_schema=False,
            validation_error=None,
        )

    # =========================================================================
    # 7. Validate status
    # =========================================================================

    if status != "VALID_ALTERNATIVE":

        raise ValueError(
            f"Unexpected relationship proposal status: {status}"
        )

    # =========================================================================
    # 8. Extract proposal
    # =========================================================================

    proposed_parent_table = str(
        parsed.get("parent_table") or ""
    ).strip()

    proposed_parent_column = str(
        parsed.get("parent_column") or ""
    ).strip()

    proposed_child_table = str(
        parsed.get("child_table") or ""
    ).strip()

    proposed_child_column = str(
        parsed.get("child_column") or ""
    ).strip()

    # =========================================================================
    # 9. Reject exact same relationship
    # =========================================================================

    same_relationship = (
        proposed_parent_table.lower()
        == rejected_parent_table.lower()
        and
        proposed_parent_column.lower()
        == rejected_parent_column.lower()
        and
        proposed_child_table.lower()
        == rejected_child_table.lower()
        and
        proposed_child_column.lower()
        == rejected_child_column.lower()
    )

    if same_relationship:

        logger.warning(
            "LLM returned the exact rejected relationship."
        )

        return ProposedRelationship(
            status="NO_ALTERNATIVE",
            parent_table="",
            parent_column="",
            child_table="",
            child_column="",
            reasoning=(
                "LLM returned the exact rejected relationship. "
                "It cannot be used as an alternative."
            ),
            is_valid_schema=False,
            validation_error=(
                "Proposed relationship is identical to rejected relationship."
            ),
        )

    # =========================================================================
    # 10. Deterministic schema validation
    # =========================================================================

    catalog_lower = {
        table.lower(): (
            table,
            [column.lower() for column in columns],
            columns,
        )
        for table, columns in catalog.items()
    }

    validation_errors = []

    # -------------------------------------------------------------------------
    # Parent table
    # -------------------------------------------------------------------------

    if (
        proposed_parent_table.lower()
        not in catalog_lower
    ):

        validation_errors.append(
            f"Parent table '{proposed_parent_table}' "
            "does not exist in schema catalog."
        )

    else:

        (
            actual_parent_table,
            parent_columns_lower,
            parent_columns,
        ) = catalog_lower[
            proposed_parent_table.lower()
        ]

        proposed_parent_table = (
            actual_parent_table
        )

        if (
            proposed_parent_column.lower()
            not in parent_columns_lower
        ):

            validation_errors.append(
                f"Parent column '{proposed_parent_column}' "
                f"does not exist in table "
                f"'{proposed_parent_table}'. "
                f"Available: {parent_columns}"
            )

        else:

            index = parent_columns_lower.index(
                proposed_parent_column.lower()
            )

            proposed_parent_column = (
                parent_columns[index]
            )

    # -------------------------------------------------------------------------
    # Child table
    # -------------------------------------------------------------------------

    if (
        proposed_child_table.lower()
        not in catalog_lower
    ):

        validation_errors.append(
            f"Child table '{proposed_child_table}' "
            "does not exist in schema catalog."
        )

    else:

        (
            actual_child_table,
            child_columns_lower,
            child_columns,
        ) = catalog_lower[
            proposed_child_table.lower()
        ]

        proposed_child_table = (
            actual_child_table
        )

        if (
            proposed_child_column.lower()
            not in child_columns_lower
        ):

            validation_errors.append(
                f"Child column '{proposed_child_column}' "
                f"does not exist in table "
                f"'{proposed_child_table}'. "
                f"Available: {child_columns}"
            )

        else:

            index = child_columns_lower.index(
                proposed_child_column.lower()
            )

            proposed_child_column = (
                child_columns[index]
            )

    # =========================================================================
    # 11. Final schema validation
    # =========================================================================

    is_valid_schema = (
        len(validation_errors) == 0
    )

    validation_message = (
        "; ".join(validation_errors)
        if validation_errors
        else None
    )

    if is_valid_schema:

        logger.info(
            "LLM proposal verified against schema: "
            f"{proposed_parent_table}."
            f"{proposed_parent_column} -> "
            f"{proposed_child_table}."
            f"{proposed_child_column}"
        )

    else:

        logger.warning(
            "LLM proposal failed schema validation: "
            f"{validation_message}"
        )

    # =========================================================================
    # 12. Return structured result
    # =========================================================================

    return ProposedRelationship(
        status="VALID_ALTERNATIVE",
        parent_table=proposed_parent_table,
        parent_column=proposed_parent_column,
        child_table=proposed_child_table,
        child_column=proposed_child_column,
        reasoning=reasoning,
        is_valid_schema=is_valid_schema,
        validation_error=validation_message,
    )


# =============================================================================
# Deterministic Validation
# =============================================================================

def validate_proposed_relationship(
    proposal: ProposedRelationship,
    datasets: Dict[str, Tuple[str, Any]],
) -> Optional[Any]:
    """
    Validates the LLM proposal against the actual DataFrames.

    LLM:
        proposes

    relationship_detector.py:
        verifies actual referential integrity

    Returns:
        RelationshipAnalysis
        or None
    """

    if proposal.status != "VALID_ALTERNATIVE":
        return None

    if not proposal.is_valid_schema:
        return None

    from app.ingestion.relationship_detector import (
        evaluate_relationship,
    )

    # -------------------------------------------------------------------------
    # Normalize dataset names
    # -------------------------------------------------------------------------

    normalized_datasets = {}

    for key, value in datasets.items():

        filename, dataframe = value

        clean_name = (
            key.lower()
            .replace("analytics_", "")
            .replace(".csv", "")
            .replace(".xlsx", "")
        )

        normalized_datasets[clean_name] = dataframe

    parent_table = (
        proposal.parent_table.lower()
    )

    child_table = (
        proposal.child_table.lower()
    )

    # -------------------------------------------------------------------------
    # Ensure tables exist
    # -------------------------------------------------------------------------

    if parent_table not in normalized_datasets:

        logger.warning(
            f"Proposed parent table not found: "
            f"{proposal.parent_table}"
        )

        return None

    if child_table not in normalized_datasets:

        logger.warning(
            f"Proposed child table not found: "
            f"{proposal.child_table}"
        )

        return None

    # -------------------------------------------------------------------------
    # Get actual DataFrames
    # -------------------------------------------------------------------------

    parent_df = normalized_datasets[
        parent_table
    ]

    child_df = normalized_datasets[
        child_table
    ]

    # -------------------------------------------------------------------------
    # Deterministic relationship verification
    # -------------------------------------------------------------------------

    result = evaluate_relationship(
        parent_df=parent_df,
        parent_col=proposal.parent_column,
        child_df=child_df,
        child_col=proposal.child_column,
        parent_name=proposal.parent_table,
        child_name=proposal.child_table,
    )

    if result is None:

        logger.warning(
            "Deterministic validation could not evaluate "
            "the proposed relationship."
        )

        return None

    logger.info(
        "Deterministic relationship validation result: "
        f"{result.parent_table}.{result.parent_column} -> "
        f"{result.child_table}.{result.child_column} "
        f"[{result.status}] "
        f"match={result.match_percentage}%"
    )

    return result