"""
app/clinical/relationship_map.py
================================
Defines clinical relational topology, foreign key relationships, join conditions,
and path discovery across the CDISC SDTM and ADaM clinical-trial database.
"""

from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass


@dataclass
class ClinicalRelationship:
    """Represents an approved relational link between two clinical tables."""
    parent_table: str
    parent_column: str
    child_table: str
    child_column: str
    cardinality: str  # "1:1", "1:N", "N:1"
    relationship_type: str  # "physical_fk" or "logical"
    description: str

    @property
    def join_condition(self) -> str:
        """Returns the SQL join expression."""
        return f"{self.parent_table}.{self.parent_column} = {self.child_table}.{self.child_column}"

    @property
    def key_pair(self) -> Tuple[str, str]:
        """Returns (parent_table, child_table)."""
        return (self.parent_table.lower(), self.child_table.lower())


# =============================================================================
# VERIFIED CLINICAL RELATIONSHIPS
# =============================================================================

RELATIONSHIPS: List[ClinicalRelationship] = [
    # ── Study Level ──────────────────────────────────────────────────────────
    ClinicalRelationship(
        parent_table="study",
        parent_column="STUDYID",
        child_table="sites",
        child_column="STUDYID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="A clinical study has one or more participating investigator research sites."
    ),
    ClinicalRelationship(
        parent_table="study",
        parent_column="STUDYID",
        child_table="dm",
        child_column="STUDYID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="A clinical study has multiple enrolled subjects across its centers."
    ),

    # ── Site Level ───────────────────────────────────────────────────────────
    ClinicalRelationship(
        parent_table="sites",
        parent_column="SITEID",
        child_table="dm",
        child_column="SITEID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="A clinical research site enrolls multiple study subjects."
    ),

    # ── SDTM Subject Level ───────────────────────────────────────────────────
    ClinicalRelationship(
        parent_table="dm",
        parent_column="USUBJID",
        child_table="ae",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="A subject can experience zero, one, or multiple adverse events."
    ),
    ClinicalRelationship(
        parent_table="dm",
        parent_column="USUBJID",
        child_table="ex",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="A subject has study drug exposure and dosing records."
    ),
    ClinicalRelationship(
        parent_table="dm",
        parent_column="USUBJID",
        child_table="lb",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="A subject has multiple laboratory test specimen assessments across visits."
    ),
    ClinicalRelationship(
        parent_table="dm",
        parent_column="USUBJID",
        child_table="qs",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="A subject has questionnaire and clinical scale scoring results across visits."
    ),
    ClinicalRelationship(
        parent_table="dm",
        parent_column="USUBJID",
        child_table="vs",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="A subject has vital signs observations recorded at multiple visits."
    ),

    # ── SDTM to ADaM Subject Link ────────────────────────────────────────────
    ClinicalRelationship(
        parent_table="dm",
        parent_column="USUBJID",
        child_table="adsl",
        child_column="USUBJID",
        cardinality="1:1",
        relationship_type="physical_fk",
        description="1-to-1 subject mapping between SDTM demographics and ADaM subject-level analysis master."
    ),

    # ── ADaM Analysis Subject Level ──────────────────────────────────────────
    ClinicalRelationship(
        parent_table="adsl",
        parent_column="USUBJID",
        child_table="adae",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="ADSL subjects link to adverse event analysis records in ADAE."
    ),
    ClinicalRelationship(
        parent_table="adsl",
        parent_column="USUBJID",
        child_table="adlb",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="ADSL subjects link to laboratory analysis parameter assessments in ADLB."
    ),
    ClinicalRelationship(
        parent_table="adsl",
        parent_column="USUBJID",
        child_table="advs",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="ADSL subjects link to vital signs analysis parameter assessments in ADVS."
    ),
    ClinicalRelationship(
        parent_table="adsl",
        parent_column="USUBJID",
        child_table="adresp",
        child_column="USUBJID",
        cardinality="1:N",
        relationship_type="physical_fk",
        description="ADSL subjects link to efficacy response assessments in ADRESP."
    ),
]


# =============================================================================
# RELATIONSHIP DISCOVERY & PATH FINDING HELPERS
# =============================================================================

def get_all_relationships() -> List[ClinicalRelationship]:
    """Returns all verified clinical relationships."""
    return list(RELATIONSHIPS)


def find_direct_relationship(table_a: str, table_b: str) -> Optional[ClinicalRelationship]:
    """
    Finds a direct relationship between table_a and table_b regardless of parent/child order.
    """
    ta, tb = table_a.lower(), table_b.lower()
    for rel in RELATIONSHIPS:
        p, c = rel.parent_table.lower(), rel.child_table.lower()
        if (p == ta and c == tb) or (p == tb and c == ta):
            return rel
    return None


def are_tables_connected(tables: List[str]) -> bool:
    """
    Verifies whether a given list of clinical tables forms a connected relational component.
    """
    if len(tables) <= 1:
        return True

    target_set = {t.lower() for t in tables}
    adj: Dict[str, Set[str]] = {t: set() for t in target_set}

    for rel in RELATIONSHIPS:
        p = rel.parent_table.lower()
        c = rel.child_table.lower()
        if p in target_set and c in target_set:
            adj[p].add(c)
            adj[c].add(p)

    # Breadth-first search
    start = next(iter(target_set))
    visited: Set[str] = set()
    queue = [start]

    while queue:
        curr = queue.pop(0)
        if curr not in visited:
            visited.add(curr)
            queue.extend(adj[curr] - visited)

    return len(visited) == len(target_set)


def get_join_condition(table_a: str, table_b: str) -> Optional[str]:
    """
    Returns SQL JOIN ON condition between table_a and table_b if directly related.
    """
    rel = find_direct_relationship(table_a, table_b)
    if not rel:
        return None
    return rel.join_condition
