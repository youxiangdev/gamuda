import json
import re
import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.services.storage_service import StorageService


@dataclass
class CsvReadResult:
    dataframe: pd.DataFrame
    repair_summary: dict[str, int]
    repair_log: list[dict[str, object]]


class CsvLoader:
    def __init__(self) -> None:
        self.storage_service = StorageService()

    def ingest(self, file_path: str, document_id: str, source_name: str | None = None) -> str:
        path = Path(file_path)
        artifact_dir = self.storage_service.ensure_artifact_dir(document_id)
        repair_summary = self._empty_repair_summary()
        repair_log: list[dict[str, object]] = []

        if path.suffix.lower() == ".csv":
            csv_result = self._read_csv(path)
            dataframe = csv_result.dataframe
            repair_summary = csv_result.repair_summary
            repair_log = csv_result.repair_log
            dataset_name = self._slugify(Path(source_name or path.name).stem)
            profile = [self._write_dataset_artifacts(dataframe, dataset_name, artifact_dir)]
        else:
            workbook = pd.read_excel(path, sheet_name=None)
            profile = []
            for sheet_name, dataframe in workbook.items():
                dataset_name = self._slugify(sheet_name)
                profile.append(self._write_dataset_artifacts(dataframe, dataset_name, artifact_dir))

        profile_path = artifact_dir / "tabular_profile.json"
        tabular_profile = {
            "datasets": profile,
            "repair_summary": repair_summary,
            "repair_log": repair_log,
        }
        profile_path.write_text(json.dumps(tabular_profile, indent=2), encoding="utf-8")

        if path.suffix.lower() == ".csv":
            repair_report_path = artifact_dir / "csv_repair_report.json"
            repair_report_path.write_text(
                json.dumps(
                    {
                        "source_name": source_name or path.name,
                        "repair_summary": repair_summary,
                        "repair_log": repair_log,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        dataset_count = len(profile)
        total_rows = sum(item["row_count"] for item in profile)
        repaired_rows = repair_summary["rows_repaired"]
        repair_suffix = ""
        if repaired_rows:
            repair_suffix = f" Repaired {repaired_rows} malformed row(s); see csv_repair_report.json for details."
        return (
            f"Tabular file normalized into {dataset_count} dataset(s) with {total_rows} total row(s). "
            f"Artifacts saved to {artifact_dir}.{repair_suffix}"
        )

    def _write_dataset_artifacts(self, dataframe: pd.DataFrame, dataset_name: str, artifact_dir: Path) -> dict[str, object]:
        normalized = dataframe.copy()
        normalized.columns = [self._normalize_column_name(str(column)) for column in normalized.columns]
        normalized = normalized.replace(r"^\s*$", pd.NA, regex=True)
        normalized = normalized.convert_dtypes()
        normalized = self._normalize_date_columns(normalized)

        parquet_path = artifact_dir / f"{dataset_name}.parquet"
        normalized.to_parquet(parquet_path, index=False)

        return {
            "dataset_name": dataset_name,
            "row_count": int(len(normalized.index)),
            "column_count": int(len(normalized.columns)),
            "columns": [
                {"name": column, "dtype": str(normalized[column].dtype)}
                for column in normalized.columns
            ],
            "sample_rows": self._sample_rows(normalized),
            "parquet_path": str(parquet_path),
        }

    def _read_csv(self, path: Path) -> CsvReadResult:
        try:
            return CsvReadResult(
                dataframe=pd.read_csv(path, encoding="utf-8-sig"),
                repair_summary=self._empty_repair_summary(),
                repair_log=[],
            )
        except pd.errors.ParserError:
            return self._read_csv_with_row_repair(path)

    def _read_csv_with_row_repair(self, path: Path) -> CsvReadResult:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            rows = list(reader)

        if not rows:
            return CsvReadResult(
                dataframe=pd.DataFrame(),
                repair_summary=self._empty_repair_summary(),
                repair_log=[],
            )

        header = rows[0]
        expected_columns = len(header)
        repaired_rows: list[list[str | None]] = []
        repair_summary = self._empty_repair_summary()
        repair_log: list[dict[str, object]] = []
        date_like_indexes = [
            index
            for index, column in enumerate(header)
            if any(token in column.lower() for token in ("date", "updated", "month", "period"))
        ]

        for row_number, row in enumerate(rows[1:], start=2):
            if len(row) == expected_columns:
                repaired_rows.append(row)
                continue

            if len(row) < expected_columns:
                repaired_rows.append(row + [None] * (expected_columns - len(row)))
                repair_summary["rows_repaired"] += 1
                repair_summary["rows_padded"] += 1
                repair_log.append(
                    {
                        "row_number": row_number,
                        "issue": "missing_columns",
                        "strategy": "pad_missing_columns",
                        "expected_columns": expected_columns,
                        "actual_columns": len(row),
                    }
                )
                continue

            overflow = len(row) - expected_columns
            repaired, strategy = self._repair_overflow_row(row, expected_columns, overflow, date_like_indexes)
            repaired_rows.append(repaired)
            repair_summary["rows_repaired"] += 1
            repair_summary[strategy] += 1
            repair_log.append(
                {
                    "row_number": row_number,
                    "issue": "extra_columns",
                    "strategy": strategy,
                    "expected_columns": expected_columns,
                    "actual_columns": len(row),
                }
            )

        return CsvReadResult(
            dataframe=pd.DataFrame(repaired_rows, columns=header),
            repair_summary=repair_summary,
            repair_log=repair_log,
        )

    def _repair_overflow_row(
        self,
        row: list[str],
        expected_columns: int,
        overflow: int,
        date_like_indexes: list[int],
    ) -> tuple[list[str], str]:
        for index in date_like_indexes:
            if index + overflow >= len(row):
                continue

            merged_value = ", ".join(part.strip() for part in row[index : index + overflow + 1] if part is not None)
            candidate = row[:index] + [merged_value] + row[index + overflow + 1 :]
            if len(candidate) == expected_columns and self._looks_like_date(merged_value):
                return candidate, "rows_merged_into_date_column"

        tail_index = expected_columns - 1
        merged_tail = ", ".join(part.strip() for part in row[tail_index:] if part is not None)
        candidate = row[:tail_index] + [merged_tail]
        if len(candidate) == expected_columns:
            return candidate, "rows_merged_into_tail_column"

        return (
            row[: expected_columns - 1] + [", ".join(part.strip() for part in row[expected_columns - 1 :])],
            "rows_truncated_with_tail_merge",
        )

    def _normalize_date_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        date_like_tokens = ("date", "updated", "month", "period")
        for column in dataframe.columns:
            if not any(token in column for token in date_like_tokens):
                continue

            parsed = pd.to_datetime(
                dataframe[column],
                errors="coerce",
                format="mixed",
                dayfirst=True,
            )
            valid_ratio = parsed.notna().mean() if len(parsed.index) else 0
            if valid_ratio >= 0.6:
                dataframe[column] = parsed.dt.strftime("%Y-%m-%d").astype("string")
        return dataframe

    def _looks_like_date(self, value: str) -> bool:
        parsed = pd.to_datetime([value], errors="coerce", format="mixed", dayfirst=True)
        return bool(pd.notna(parsed[0]))

    def _sample_rows(self, dataframe: pd.DataFrame, limit: int = 3) -> list[dict[str, object]]:
        sample = dataframe.head(limit).copy()
        sample = sample.where(pd.notna(sample), None)
        return sample.to_dict(orient="records")

    def _normalize_column_name(self, value: str) -> str:
        normalized = value.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized or "column"

    def _slugify(self, value: str) -> str:
        slug = value.strip().lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug or "dataset"

    def _empty_repair_summary(self) -> dict[str, int]:
        return {
            "rows_repaired": 0,
            "rows_padded": 0,
            "rows_merged_into_date_column": 0,
            "rows_merged_into_tail_column": 0,
            "rows_truncated_with_tail_merge": 0,
        }
