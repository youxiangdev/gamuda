import json
import re
from pathlib import Path

import pandas as pd

from app.services.storage_service import StorageService


class CsvLoader:
    def __init__(self) -> None:
        self.storage_service = StorageService()

    def ingest(self, file_path: str, document_id: str, source_name: str | None = None) -> str:
        path = Path(file_path)
        artifact_dir = self.storage_service.ensure_artifact_dir(document_id)

        if path.suffix.lower() == ".csv":
            dataframe = pd.read_csv(path, encoding="utf-8-sig")
            dataset_name = self._slugify(Path(source_name or path.name).stem)
            profile = [self._write_dataset_artifacts(dataframe, dataset_name, artifact_dir)]
        else:
            workbook = pd.read_excel(path, sheet_name=None)
            profile = []
            for sheet_name, dataframe in workbook.items():
                dataset_name = self._slugify(sheet_name)
                profile.append(self._write_dataset_artifacts(dataframe, dataset_name, artifact_dir))

        profile_path = artifact_dir / "tabular_profile.json"
        profile_path.write_text(json.dumps({"datasets": profile}, indent=2), encoding="utf-8")

        dataset_count = len(profile)
        total_rows = sum(item["row_count"] for item in profile)
        return (
            f"Tabular file normalized into {dataset_count} dataset(s) with {total_rows} total row(s). "
            f"Artifacts saved to {artifact_dir}."
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
