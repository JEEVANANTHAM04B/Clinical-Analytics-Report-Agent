"""
app/clinical/schema_registry.py
===============================
Unified Clinical Schema Registry providing centralized access to CDISC dataset
metadata, verified relationships, clinical KPI definitions, and question planning.
"""

from typing import Dict, List, Optional, Tuple, Any

from app.clinical.dataset_metadata import DATASETS, DatasetMetadata, ColumnMetadata
from app.clinical.relationship_map import (
    RELATIONSHIPS,
    ClinicalRelationship,
    get_all_relationships,
    find_direct_relationship,
    are_tables_connected,
    get_join_condition,
)
from app.clinical.kpi_definitions import KPIS, KPIDefinition, get_kpi, list_kpis_by_category
from app.clinical.question_mapping import ClinicalQuestionPlan, build_clinical_question_plan


class ClinicalSchemaRegistry:
    """
    Central registry for CDISC SDTM and ADaM clinical-trial metadata,
    relational topology, KPI logic, and deterministic question planning.
    """

    def __init__(self):
        self._datasets: Dict[str, DatasetMetadata] = dict(DATASETS)
        self._relationships: List[ClinicalRelationship] = list(RELATIONSHIPS)
        self._kpis: Dict[str, KPIDefinition] = KPIS

    # ── Dataset Operations ───────────────────────────────────────────────────
    def get_dataset(self, name: str) -> Optional[DatasetMetadata]:
        """Retrieves dataset metadata by name (case-insensitive), dynamically loading new tables if present."""
        if not name:
            return None
        clean = name.lower().strip()
        if clean in self._datasets:
            return self._datasets[clean]

        # Dynamically discover newly created table in MySQL
        try:
            from app.database.schema_service import get_database_schema
            schema = get_database_schema()
            tables = schema.get("tables", {})
            actual_name = next((t for t in tables.keys() if t.lower() == clean), None)
            if actual_name:
                cols = tables[actual_name]
                col_meta_dict = {}
                for c in cols:
                    cname = c["name"].upper().strip()
                    col_meta_dict[cname] = ColumnMetadata(
                        name=cname,
                        data_type=c["type"],
                        semantic_type="text" if "VARCHAR" in c["type"].upper() or "TEXT" in c["type"].upper() else ("numeric" if "INT" in c["type"].upper() or "DOUBLE" in c["type"].upper() else "categorical"),
                        nullable=c.get("nullable", True),
                        is_primary_key=False,
                        is_foreign_key=False,
                        description=f"Column from {actual_name}",
                    )
                ds_meta = DatasetMetadata(
                    name=actual_name.lower(),
                    domain=actual_name.upper(),
                    category="Custom Clinical Dataset",
                    description=f"User-uploaded clinical dataset table '{actual_name}'",
                    purpose="Custom clinical data analysis",
                    primary_key=[],
                    foreign_keys={},
                    subject_level=False,
                    analysis_level="custom",
                    clinical_role="Custom analytical dataset",
                    important_columns=col_meta_dict,
                    kpi_usage=[],
                )
                self._datasets[clean] = ds_meta
                return ds_meta
        except Exception:
            pass

        return None

    def has_dataset(self, name: str) -> bool:
        """Checks if dataset exists by name (case-insensitive)."""
        return self.get_dataset(name) is not None

    def list_datasets(self) -> List[DatasetMetadata]:
        """Returns metadata for all approved clinical datasets that exist in MySQL."""
        try:
            from app.database.schema_service import get_database_schema
            schema = get_database_schema(approved_only=True)
            approved_names = set(t.lower() for t in schema.get("tables", {}).keys())

            for tbl in approved_names:
                if tbl not in self._datasets:
                    self.get_dataset(tbl)

            return [ds for ds in self._datasets.values() if ds.name.lower() in approved_names]
        except Exception:
            return list(self._datasets.values())

    def get_dataset_names(self) -> List[str]:
        """Returns sorted list of all approved clinical dataset table names."""
        return sorted([ds.name.lower() for ds in self.list_datasets()])

    def register_dataset(self, metadata: DatasetMetadata) -> None:
        """Explicitly registers a new clinical dataset metadata object."""
        if metadata and metadata.name:
            self._datasets[metadata.name.lower().strip()] = metadata

    def get_column(self, dataset_name: str, column_name: str) -> Optional[ColumnMetadata]:
        """Retrieves column metadata for a specific dataset and column."""
        ds = self.get_dataset(dataset_name)
        if not ds:
            return None
        return ds.important_columns.get(column_name.upper().strip())

    def validate_required_columns(self, dataset_name: str, columns: List[str]) -> Tuple[bool, List[str]]:
        """
        Validates whether specified columns exist in the given dataset.
        Returns: (all_valid, missing_columns)
        """
        ds = self.get_dataset(dataset_name)
        if not ds:
            return False, columns

        missing = [c for c in columns if c.upper().strip() not in ds.important_columns]
        return len(missing) == 0, missing

    # ── Relational Operations ────────────────────────────────────────────────
    def get_relationships(self) -> List[ClinicalRelationship]:
        """Returns all approved relational connections."""
        return list(self._relationships)

    def get_relationship(self, table_a: str, table_b: str) -> Optional[ClinicalRelationship]:
        """Finds direct relationship between two tables."""
        return find_direct_relationship(table_a, table_b)

    def are_connected(self, tables: List[str]) -> bool:
        """Checks if a group of tables can be legitimately joined."""
        return are_tables_connected(tables)

    def get_join_sql(self, table_a: str, table_b: str) -> Optional[str]:
        """Gets SQL join expression between two tables."""
        return get_join_condition(table_a, table_b)

    # ── KPI Operations ───────────────────────────────────────────────────────
    def get_kpi(self, kpi_id: str) -> Optional[KPIDefinition]:
        """Retrieves KPI definition by its unique identifier."""
        return get_kpi(kpi_id)

    def list_kpis(self, category: Optional[str] = None) -> List[KPIDefinition]:
        """Lists all KPIs, optionally filtered by domain category."""
        return list_kpis_by_category(category)

    def get_kpi_ids(self) -> List[str]:
        """Returns list of all registered KPI identifiers."""
        return sorted(list(self._kpis.keys()))

    # ── Question Planning Interface ──────────────────────────────────────────
    def plan_question(self, question: str) -> ClinicalQuestionPlan:
        """
        Builds a deterministic clinical question plan identifying required datasets,
        columns, join conditions, and statistical formula.
        """
        return build_clinical_question_plan(question)

    # ── LLM Prompt Context Helper ────────────────────────────────────────────
    def build_schema_context_for_prompt(self, relevant_tables: Optional[List[str]] = None) -> str:
        """
        Generates a clean, factual schema representation suitable for injection
        into future SQL generation prompts or analytics planners.
        """
        target_names = [t.lower().strip() for t in relevant_tables] if relevant_tables else self.get_dataset_names()
        lines = ["### Clinical Trial Relational Schema (CDISC SDTM / ADaM)\n"]

        for name in target_names:
            ds = self.get_dataset(name)
            if not ds:
                continue
            pk_str = ", ".join(ds.primary_key)
            lines.append(f"Table `{ds.name}` ({ds.domain} - {ds.category}):")
            lines.append(f"  Description: {ds.description}")
            lines.append(f"  Primary Key: [{pk_str}]")
            if ds.foreign_keys:
                fk_strs = [f"{col} -> {target}" for col, target in ds.foreign_keys.items()]
                lines.append(f"  Foreign Keys: {', '.join(fk_strs)}")
            col_strs = [f"{c.name} ({c.data_type})" for c in ds.important_columns.values()]
            lines.append(f"  Columns: {', '.join(col_strs)}")
            lines.append("")

        lines.append("### Approved Clinical Relationships:")
        for rel in self._relationships:
            if not relevant_tables or (rel.parent_table.lower() in target_names and rel.child_table.lower() in target_names):
                lines.append(f"  - {rel.parent_table}.{rel.parent_column} = {rel.child_table}.{rel.child_column} ({rel.cardinality})")

        return "\n".join(lines)

    # ── Summary / Health ─────────────────────────────────────────────────────
    def get_summary(self) -> Dict[str, Any]:
        """Returns high-level statistics of the clinical metadata registry."""
        return {
            "total_datasets": len(self._datasets),
            "datasets": list(self._datasets.keys()),
            "total_relationships": len(self._relationships),
            "total_kpis": len(self._kpis),
            "kpi_categories": sorted(list({k.category for k in self._kpis.values()})),
        }


# Global singleton instance
registry = ClinicalSchemaRegistry()
