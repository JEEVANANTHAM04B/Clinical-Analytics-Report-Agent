"""
test_relationship_regenerator.py
=================================
Verification script for app/ingestion/relationship_regenerator.py
"""

from app.ingestion.relationship_regenerator import propose_alternative_relationship

# 1. Define sample schema catalog
sample_schema = {
    "patients": ["ID", "BIRTHDATE", "DEATHDATE", "FIRST", "LAST", "GENDER"],
    "encounters": ["ID", "START", "STOP", "PATIENT", "ORGANIZATION", "PROVIDER", "PAYER"],
    "conditions": ["START", "STOP", "PATIENT", "ENCOUNTER", "CODE", "DESCRIPTION"],
}

# 2. Define the rejected relationship
rejected_candidate = {
    "parent_table": "patients",
    "parent_column": "ID",
    "child_table": "encounters",
    "child_column": "PATIENT",
}

# 3. Define human analyst feedback
analyst_note = (
    "Do not link patients directly to encounters here. "
    "We need to link conditions to their corresponding clinical encounters instead."
)

print("\n" + "=" * 70)
print("TESTING AI-ASSISTED RELATIONSHIP REGENERATOR (Qwen3 8B)")
print("=" * 70)
print(f"Rejected Candidate: {rejected_candidate['parent_table']}.{rejected_candidate['parent_column']} -> {rejected_candidate['child_table']}.{rejected_candidate['child_column']}")
print(f"Analyst Feedback  : \"{analyst_note}\"")
print("-" * 70)
print("Consulting Qwen3 8B for alternative proposal...")

proposal = propose_alternative_relationship(
    rejected_relationship=rejected_candidate,
    analyst_feedback=analyst_note,
    available_schema=sample_schema,
)

print("\n=== PROPOSED RELATIONSHIP RESULT ===")
print(f"Parent Table    : {proposal.parent_table}")
print(f"Parent Column   : {proposal.parent_column}")
print(f"Child Table     : {proposal.child_table}")
print(f"Child Column    : {proposal.child_column}")
print(f"Valid in Schema : {proposal.is_valid_schema}")
print(f"Reasoning       : {proposal.reasoning}")
print("=" * 70)
