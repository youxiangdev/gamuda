from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.state import DataFindingsPayload, FindingsPayload
from app.models.document import Document
from app.services.storage_service import StorageService


class DatasetDescriptor(BaseModel):
    dataset_id: str
    dataset_name: str
    source_file: str
    document_id: str
    parquet_path: str
    row_count: int
    column_count: int
    columns: list[dict[str, Any]]
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)


class QueryFilter(BaseModel):
    column: str
    op: str
    value: Any


class QueryAggregation(BaseModel):
    column: str
    fn: str
    as_name: str = Field(alias="as")


class QueryOrderBy(BaseModel):
    column: str
    direction: str = "asc"


class DescribeDatasetInput(BaseModel):
    dataset_id: str


class QueryParquetInput(BaseModel):
    dataset_id: str
    select: list[str] = Field(default_factory=list)
    filters: list[QueryFilter] = Field(default_factory=list)
    aggregations: list[QueryAggregation] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    order_by: list[QueryOrderBy] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=50)


@dataclass(slots=True)
class DataToolRuntime:
    db: Session
    storage_service: StorageService = field(default_factory=StorageService)
    dataset_registry: dict[str, DatasetDescriptor] = field(default_factory=dict)
    query_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    query_counter: int = 0

    def list_datasets(self) -> str:
        datasets = [descriptor.model_dump() for descriptor in self._load_dataset_registry().values()]
        return json.dumps({"datasets": datasets}, ensure_ascii=True)

    def describe_dataset(self, dataset_id: str) -> str:
        descriptor = self._load_dataset_registry().get(dataset_id)
        if descriptor is None:
            return json.dumps({"error": f"Dataset not found: {dataset_id}"}, ensure_ascii=True)
        return json.dumps(descriptor.model_dump(), ensure_ascii=True)

    def query_parquet(
        self,
        dataset_id: str,
        select: list[str],
        filters: list[dict[str, Any]],
        aggregations: list[dict[str, Any]],
        group_by: list[str],
        order_by: list[dict[str, Any]],
        limit: int,
    ) -> str:
        descriptor = self._load_dataset_registry().get(dataset_id)
        if descriptor is None:
            return json.dumps({"error": f"Dataset not found: {dataset_id}"}, ensure_ascii=True)

        dataframe = pd.read_parquet(descriptor.parquet_path)
        frame = self._apply_filters(dataframe, filters)
        frame = self._apply_query_shape(frame, select, aggregations, group_by)
        frame = self._apply_order_by(frame, order_by)
        frame = frame.head(limit).copy()

        query_id = self._next_query_id()
        rows = self._rows_to_records(frame)
        result = {
            "query_id": query_id,
            "dataset_id": descriptor.dataset_id,
            "dataset_name": descriptor.dataset_name,
            "source_file": descriptor.source_file,
            "summary": self._summarize_result(descriptor, rows, filters, aggregations, group_by),
            "row_count": len(rows),
            "rows": rows,
            "query_signature": {
                "select": select,
                "filters": filters,
                "aggregations": aggregations,
                "group_by": group_by,
                "order_by": order_by,
                "limit": limit,
            },
        }
        self.query_results[query_id] = result
        return json.dumps(result, ensure_ascii=True)

    def validate_findings_payload(self, payload: DataFindingsPayload) -> FindingsPayload:
        validated_findings: list[dict[str, Any]] = []
        for finding in payload.findings[:3]:
            claim = str(finding.claim).strip()
            if not claim:
                continue

            validated_evidence: list[dict[str, str]] = []
            for item in finding.evidence:
                result = self.query_results.get(item.query_id)
                if result is None:
                    continue
                validated_evidence.append(
                    {
                        "source": str(result.get("source_file") or ""),
                        "citation": self._format_query_citation(result),
                        "snippet": str(result.get("summary") or ""),
                    }
                )

            if validated_evidence:
                validated_findings.append({"claim": claim, "evidence": validated_evidence})

        return FindingsPayload(
            findings=validated_findings,
            insufficient_evidence=bool(payload.insufficient_evidence or not validated_findings),
        )

    def build_tools(self) -> list[BaseTool]:
        runtime = self

        @tool
        def list_datasets() -> str:
            """List all tabular datasets that were ingested from uploaded CSV or XLSX documents."""
            return runtime.list_datasets()

        @tool(args_schema=DescribeDatasetInput)
        def describe_dataset(dataset_id: str) -> str:
            """Describe a dataset, including columns, row count, source file, and sample rows."""
            return runtime.describe_dataset(dataset_id)

        @tool(args_schema=QueryParquetInput)
        def query_parquet(
            dataset_id: str,
            select: list[str] | None = None,
            filters: list[QueryFilter] | None = None,
            aggregations: list[QueryAggregation] | None = None,
            group_by: list[str] | None = None,
            order_by: list[QueryOrderBy] | None = None,
            limit: int = 10,
        ) -> str:
            """Run a bounded, read-only query against a dataset and return a query_id plus summarized results."""
            return runtime.query_parquet(
                dataset_id=dataset_id,
                select=list(select or []),
                filters=[item.model_dump() for item in filters or []],
                aggregations=[item.model_dump(by_alias=True) for item in aggregations or []],
                group_by=list(group_by or []),
                order_by=[item.model_dump() for item in order_by or []],
                limit=limit,
            )

        return [list_datasets, describe_dataset, query_parquet]

    def _load_dataset_registry(self) -> dict[str, DatasetDescriptor]:
        if self.dataset_registry:
            return self.dataset_registry

        documents = list(
            self.db.scalars(
                select(Document).where(Document.extension.in_((".csv", ".xlsx"))).order_by(Document.created_at.desc())
            )
        )
        registry: dict[str, DatasetDescriptor] = {}
        for document in documents:
            artifact_dir = self.storage_service.ensure_artifact_dir(document.id)
            profile_path = artifact_dir / "tabular_profile.json"
            if not profile_path.exists():
                continue
            payload = json.loads(profile_path.read_text(encoding="utf-8"))
            for dataset in payload.get("datasets", []):
                dataset_name = str(dataset.get("dataset_name") or "").strip()
                if not dataset_name:
                    continue
                dataset_id = f"{document.id}:{dataset_name}"
                registry[dataset_id] = DatasetDescriptor(
                    dataset_id=dataset_id,
                    dataset_name=dataset_name,
                    source_file=document.original_filename,
                    document_id=document.id,
                    parquet_path=str(dataset.get("parquet_path") or ""),
                    row_count=int(dataset.get("row_count") or 0),
                    column_count=int(dataset.get("column_count") or 0),
                    columns=list(dataset.get("columns") or []),
                    sample_rows=list(dataset.get("sample_rows") or []),
                )

        self.dataset_registry = registry
        return self.dataset_registry

    def _apply_filters(self, dataframe: pd.DataFrame, filters: list[dict[str, Any]]) -> pd.DataFrame:
        frame = dataframe.copy()
        for item in filters:
            column = str(item.get("column") or "").strip()
            op = str(item.get("op") or "").strip().lower()
            value = item.get("value")
            if column not in frame.columns:
                raise ValueError(f"Unknown filter column: {column}")

            series = frame[column]
            if op == "=":
                frame = frame[series == value]
            elif op == "!=":
                frame = frame[series != value]
            elif op == ">":
                frame = frame[series > value]
            elif op == ">=":
                frame = frame[series >= value]
            elif op == "<":
                frame = frame[series < value]
            elif op == "<=":
                frame = frame[series <= value]
            elif op == "in":
                values = value if isinstance(value, list) else [value]
                frame = frame[series.isin(values)]
            else:
                raise ValueError(f"Unsupported filter op: {op}")
        return frame

    def _apply_query_shape(
        self,
        dataframe: pd.DataFrame,
        select: list[str],
        aggregations: list[dict[str, Any]],
        group_by: list[str],
    ) -> pd.DataFrame:
        for column in [*select, *group_by]:
            if column and column not in dataframe.columns:
                raise ValueError(f"Unknown column: {column}")

        if aggregations:
            agg_map: dict[str, tuple[str, str]] = {}
            working = dataframe.copy()
            for item in aggregations:
                column = str(item.get("column") or "").strip()
                fn = str(item.get("fn") or "").strip().lower()
                alias = str(item.get("as") or "").strip()
                if column not in dataframe.columns:
                    raise ValueError(f"Unknown aggregation column: {column}")
                if fn not in {"sum", "avg", "mean", "min", "max", "count"}:
                    raise ValueError(f"Unsupported aggregation fn: {fn}")
                if fn != "count":
                    parsed = pd.to_numeric(working[column], errors="coerce")
                    parsed_non_null = parsed[working[column].notna()]
                    if not parsed_non_null.empty and parsed_non_null.notna().all():
                        if bool(((parsed_non_null % 1) == 0).all()):
                            working[column] = parsed.round().astype("Int64")
                        else:
                            working[column] = parsed.astype("Float64")
                    else:
                        raise ValueError(f"Aggregation column is not numeric: {column}")
                agg_map[alias or f"{fn}_{column}"] = (column, "mean" if fn == "avg" else fn)

            if group_by:
                grouped = working.groupby(group_by, dropna=False)
                frame = grouped.agg(**agg_map).reset_index()
            else:
                frame = working.agg(**agg_map).to_frame().T
            return frame

        if select:
            return dataframe[select].copy()
        return dataframe.copy()

    def _apply_order_by(self, dataframe: pd.DataFrame, order_by: list[dict[str, Any]]) -> pd.DataFrame:
        if not order_by:
            return dataframe
        columns: list[str] = []
        ascending: list[bool] = []
        for item in order_by:
            column = str(item.get("column") or "").strip()
            direction = str(item.get("direction") or "asc").strip().lower()
            if column not in dataframe.columns:
                raise ValueError(f"Unknown order_by column: {column}")
            columns.append(column)
            ascending.append(direction != "desc")
        return dataframe.sort_values(by=columns, ascending=ascending)

    def _rows_to_records(self, dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        safe = dataframe.where(pd.notna(dataframe), None).copy()
        records = safe.to_dict(orient="records")
        return [self._coerce_jsonable(record) for record in records]

    def _summarize_result(
        self,
        descriptor: DatasetDescriptor,
        rows: list[dict[str, Any]],
        filters: list[dict[str, Any]],
        aggregations: list[dict[str, Any]],
        group_by: list[str],
    ) -> str:
        if not rows:
            return f"No rows matched for dataset {descriptor.dataset_name} from {descriptor.source_file}."
        if aggregations:
            return (
                f"Query on dataset {descriptor.dataset_name} from {descriptor.source_file} returned "
                f"{len(rows)} row(s) after filters {json.dumps(filters, ensure_ascii=True)} with "
                f"aggregations {json.dumps(aggregations, ensure_ascii=True)} and group_by {group_by}. "
                f"Top row: {json.dumps(rows[0], ensure_ascii=True)}"
            )
        return (
            f"Query on dataset {descriptor.dataset_name} from {descriptor.source_file} returned "
            f"{len(rows)} row(s) after filters {json.dumps(filters, ensure_ascii=True)}. "
            f"Top row: {json.dumps(rows[0], ensure_ascii=True)}"
        )

    def _format_query_citation(self, result: dict[str, Any]) -> str:
        signature = result.get("query_signature") or {}
        return (
            f"dataset={result.get('dataset_id')} | query_id={result.get('query_id')} | "
            f"filters={json.dumps(signature.get('filters', []), ensure_ascii=True)} | "
            f"aggregations={json.dumps(signature.get('aggregations', []), ensure_ascii=True)} | "
            f"group_by={json.dumps(signature.get('group_by', []), ensure_ascii=True)}"
        )

    def _next_query_id(self) -> str:
        self.query_counter += 1
        return f"query_{self.query_counter:03d}"

    def _coerce_jsonable(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._coerce_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._coerce_jsonable(item) for item in value]
        if isinstance(value, tuple):
            return [self._coerce_jsonable(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except TypeError:
                pass
        return str(value)


def build_data_tools(db: Session) -> tuple[DataToolRuntime, list[BaseTool]]:
    runtime = DataToolRuntime(db=db)
    return runtime, runtime.build_tools()
