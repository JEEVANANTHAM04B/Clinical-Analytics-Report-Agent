"""
app/clinical
============
Clinical-trial schema registry, dataset metadata, relational mappings,
and KPI question planner foundation for CDISC SDTM and ADaM analytics.
"""

from app.clinical.dataset_metadata import (
    ColumnMetadata,
    DatasetMetadata,
    DATASETS,
)
from app.clinical.relationship_map import (
    ClinicalRelationship,
    RELATIONSHIPS,
    get_all_relationships,
    find_direct_relationship,
    are_tables_connected,
    get_join_condition,
)
from app.clinical.kpi_definitions import (
    KPIDefinition,
    KPIS,
    get_kpi,
    list_kpis_by_category,
)
from app.clinical.question_mapping import (
    ClinicalQuestionPlan,
    build_clinical_question_plan,
)
from app.clinical.schema_registry import (
    ClinicalSchemaRegistry,
    registry,
)

__all__ = [
    "ColumnMetadata",
    "DatasetMetadata",
    "DATASETS",
    "ClinicalRelationship",
    "RELATIONSHIPS",
    "get_all_relationships",
    "find_direct_relationship",
    "are_tables_connected",
    "get_join_condition",
    "KPIDefinition",
    "KPIS",
    "get_kpi",
    "list_kpis_by_category",
    "ClinicalQuestionPlan",
    "build_clinical_question_plan",
    "ClinicalSchemaRegistry",
    "registry",
]
