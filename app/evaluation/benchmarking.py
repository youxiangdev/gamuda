from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

import requests
from langchain_community.embeddings.jina import JinaEmbeddings
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from ragas import EvaluationDataset, evaluate
from ragas.dataset_schema import SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import ContextPrecision, ContextRecall, Faithfulness, FactualCorrectness, ResponseRelevancy

from app.ai import build_initial_state, get_chat_graph
from app.db.session import init_db


class BenchmarkCase(BaseModel):
    id: str
    difficulty: str
    question: str
    ground_truth: str
    expected_answer_points: list[str] = Field(default_factory=list)
    expected_sources: list[str] = Field(default_factory=list)
    primary_metrics: list[str] = Field(default_factory=list)
    route_expectation: str
    generated_answer: str = ""
    retrieved_contexts: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    route: str = ""
    notes: str = ""


class BenchmarkDataset(BaseModel):
    dataset_name: str
    created_at: str
    samples: list[BenchmarkCase]


class BenchmarkEvalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    benchmark_eval_provider: str
    benchmark_eval_model: str
    groq_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    jina_api_key: SecretStr | None = None
    jina_embedding_model: str = "jina-embeddings-v5-text-small"


@dataclass(slots=True)
class BenchmarkRunSettings:
    dataset_path: Path
    output_dir: Path
    case_id: str | None = None
    use_ragas: bool = True
    save_current: bool = False


@dataclass(slots=True)
class BenchmarkResult:
    id: str
    difficulty: str
    question: str
    route_expectation: str
    route: str = ""
    runtime_success: bool = False
    error_type: str | None = None
    error_detail: str | None = None
    generated_answer: str = ""
    retrieved_contexts: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    document_findings: dict[str, Any] = field(default_factory=dict)
    data_findings: dict[str, Any] = field(default_factory=dict)
    route_match: bool = False
    has_citations: bool = False
    has_retrieved_contexts: bool = False
    primary_metrics: list[str] = field(default_factory=list)
    metric_scores: dict[str, float | None] = field(default_factory=dict)
    metric_errors: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    expected_sources: list[str] = field(default_factory=list)
    expected_answer_points: list[str] = field(default_factory=list)
    scope: str = "extended"

    @property
    def average_metric_score(self) -> float | None:
        values = [value for value in self.metric_scores.values() if value is not None]
        if not values:
            return None
        return round(mean(values), 4)


METRIC_NAME_MAP = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answer_relevancy",
    "context_precision": "context_precision",
    "context_recall": "context_recall",
    "answer_correctness": "factual_correctness",
}


def load_benchmark_cases(dataset_path: Path) -> list[BenchmarkCase]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    dataset = BenchmarkDataset.model_validate(payload)
    return dataset.samples


def build_output_dir(base_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return base_dir / stamp


def dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def extract_contexts_and_citations(result_state: dict[str, Any]) -> tuple[list[str], list[str]]:
    contexts: list[str] = []
    citations: list[str] = []
    for key in ("document_findings", "data_findings"):
        findings = ((result_state.get(key) or {}).get("findings") or []) if isinstance(result_state.get(key), dict) else []
        for finding in findings:
            for evidence in finding.get("evidence", []):
                snippet = str(evidence.get("snippet") or "").strip()
                citation = str(evidence.get("citation") or "").strip()
                if snippet:
                    contexts.append(snippet)
                if citation:
                    citations.append(citation)
    return dedupe_preserve_order(contexts), dedupe_preserve_order(citations)


def build_result(case: BenchmarkCase, state: dict[str, Any], *, duration_ms: float) -> BenchmarkResult:
    retrieved_contexts, citations = extract_contexts_and_citations(state)
    route = str(state.get("route") or "")
    scope = "core" if case.id in {f"TC-{index:02d}" for index in range(1, 9)} else "extended"
    return BenchmarkResult(
        id=case.id,
        difficulty=case.difficulty,
        question=case.question,
        route_expectation=case.route_expectation,
        route=route,
        runtime_success=True,
        generated_answer=str(state.get("final_answer") or ""),
        retrieved_contexts=retrieved_contexts,
        citations=citations,
        document_findings=dict(state.get("document_findings") or {}),
        data_findings=dict(state.get("data_findings") or {}),
        route_match=route == case.route_expectation,
        has_citations=bool(citations),
        has_retrieved_contexts=bool(retrieved_contexts),
        primary_metrics=list(case.primary_metrics),
        duration_ms=round(duration_ms, 2),
        expected_sources=list(case.expected_sources),
        expected_answer_points=list(case.expected_answer_points),
        scope=scope,
    )


def build_failure_result(case: BenchmarkCase, exc: Exception, *, duration_ms: float) -> BenchmarkResult:
    scope = "core" if case.id in {f"TC-{index:02d}" for index in range(1, 9)} else "extended"
    return BenchmarkResult(
        id=case.id,
        difficulty=case.difficulty,
        question=case.question,
        route_expectation=case.route_expectation,
        runtime_success=False,
        error_type=type(exc).__name__,
        error_detail=str(exc),
        primary_metrics=list(case.primary_metrics),
        duration_ms=round(duration_ms, 2),
        expected_sources=list(case.expected_sources),
        expected_answer_points=list(case.expected_answer_points),
        notes=["Runtime failed before a complete final answer was produced."],
        scope=scope,
    )


async def execute_case(case: BenchmarkCase) -> BenchmarkResult:
    graph = get_chat_graph()
    state = build_initial_state(messages=[HumanMessage(content=case.question)])
    config = {
        "configurable": {"thread_id": f"benchmark-{case.id.lower()}"},
        "metadata": {"thread_id": f"benchmark-{case.id.lower()}", "run_id": state["id"], "benchmark_case_id": case.id},
        "tags": ["benchmark", case.id.lower()],
    }
    started = perf_counter()
    try:
        result_state = await graph.ainvoke(state, config=config)
        return build_result(case, result_state, duration_ms=(perf_counter() - started) * 1000)
    except Exception as exc:
        return build_failure_result(case, exc, duration_ms=(perf_counter() - started) * 1000)


async def execute_cases(cases: list[BenchmarkCase]) -> list[BenchmarkResult]:
    results: list[BenchmarkResult] = []
    for case in cases:
        results.append(await execute_case(case))
    return results


def _secret_value(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    value = secret.get_secret_value().strip()
    return value or None


def build_eval_llm(settings: BenchmarkEvalSettings):
    provider = settings.benchmark_eval_provider.strip().lower()
    if provider == "groq":
        api_key = _secret_value(settings.groq_api_key)
        if api_key is None:
            raise RuntimeError("GROQ_API_KEY is required for groq benchmark evaluation.")
        return LangchainLLMWrapper(
            ChatGroq(model=settings.benchmark_eval_model, api_key=api_key, temperature=0, max_tokens=4096)
        )
    if provider == "gemini":
        api_key = _secret_value(settings.gemini_api_key)
        if api_key is None:
            raise RuntimeError("GEMINI_API_KEY is required for gemini benchmark evaluation.")
        return LangchainLLMWrapper(
            ChatGoogleGenerativeAI(
                model=settings.benchmark_eval_model,
                google_api_key=api_key,
                temperature=0,
                max_output_tokens=4096,
            )
        )
    raise ValueError(f"Unsupported benchmark eval provider: {settings.benchmark_eval_provider}")


def build_eval_embeddings(settings: BenchmarkEvalSettings):
    api_key = settings.jina_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise RuntimeError("JINA_API_KEY is required for answer_relevancy benchmark evaluation.")
    return LangchainEmbeddingsWrapper(
        JinaEmbeddings(
            session=requests.Session(),
            model_name=settings.jina_embedding_model,
            jina_api_key=api_key,
        )
    )


def build_metric_objects(metric_names: list[str], *, llm: Any, embeddings: Any) -> list[Any]:
    metrics: list[Any] = []
    for name in metric_names:
        if name == "faithfulness":
            metrics.append(Faithfulness(llm=llm))
        elif name == "answer_relevancy":
            metrics.append(ResponseRelevancy(llm=llm, embeddings=embeddings))
        elif name == "context_precision":
            metrics.append(ContextPrecision(llm=llm))
        elif name == "context_recall":
            metrics.append(ContextRecall(llm=llm))
        elif name == "answer_correctness":
            metrics.append(FactualCorrectness(llm=llm))
        else:
            raise ValueError(f"Unsupported metric name in benchmark dataset: {name}")
    return metrics


def score_result_with_ragas(result: BenchmarkResult, *, llm: Any, embeddings: Any) -> None:
    if not result.runtime_success:
        result.metric_errors["ragas"] = "Skipped due to runtime failure."
        return
    if not result.generated_answer.strip():
        result.metric_errors["ragas"] = "Skipped because generated_answer is empty."
        return
    if not result.retrieved_contexts:
        result.metric_errors["ragas"] = "Skipped because retrieved_contexts is empty."
        return

    requested_metrics = list(result.primary_metrics or ["faithfulness", "answer_relevancy"])
    sample = SingleTurnSample(
        user_input=result.question,
        response=result.generated_answer,
        retrieved_contexts=result.retrieved_contexts,
        reference=" ".join(result.expected_answer_points) if result.expected_answer_points else None,
    )
    metric_objects = build_metric_objects(requested_metrics, llm=llm, embeddings=embeddings)
    evaluation_result = evaluate(
        dataset=EvaluationDataset(samples=[sample]),
        metrics=metric_objects,
        llm=llm,
        embeddings=embeddings,
        show_progress=False,
        raise_exceptions=False,
    )
    records = evaluation_result.to_pandas().to_dict(orient="records")
    if not records:
        result.metric_errors["ragas"] = "RAGAS returned no result rows."
        return

    record = records[0]
    for metric_name in requested_metrics:
        column = METRIC_NAME_MAP[metric_name]
        raw_value = record.get(column)
        if raw_value is None or raw_value != raw_value:  # None or NaN check
            result.metric_scores[metric_name] = None
            result.metric_errors[metric_name] = "RAGAS returned no numeric score."
        else:
            result.metric_scores[metric_name] = round(float(raw_value), 4)


def score_results_with_ragas(results: list[BenchmarkResult]) -> None:
    settings = BenchmarkEvalSettings()
    llm = build_eval_llm(settings)
    embeddings = build_eval_embeddings(settings)
    for result in results:
        score_result_with_ragas(result, llm=llm, embeddings=embeddings)


def serialize_result(result: BenchmarkResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["average_metric_score"] = result.average_metric_score
    return payload


def render_results_markdown(results: list[BenchmarkResult]) -> str:
    lines: list[str] = []
    lines.append("# Benchmark Results")
    lines.append("")
    lines.append(f"Date: `{datetime.now(UTC).isoformat()}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| ID | Route | Runtime | Faithfulness | Answer Relevancy | Answer Correctness | Context Precision | Context Recall | Notes |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for result in results:
        lines.append(
            "| {id} | {route} | {runtime} | {faithfulness} | {answer_relevancy} | {answer_correctness} | {context_precision} | {context_recall} | {notes} |".format(
                id=result.id,
                route=result.route or "-",
                runtime="pass" if result.runtime_success else "fail",
                faithfulness=_fmt_metric(result.metric_scores.get("faithfulness")),
                answer_relevancy=_fmt_metric(result.metric_scores.get("answer_relevancy")),
                answer_correctness=_fmt_metric(result.metric_scores.get("answer_correctness")),
                context_precision=_fmt_metric(result.metric_scores.get("context_precision")),
                context_recall=_fmt_metric(result.metric_scores.get("context_recall")),
                notes=_compact_notes(result),
            )
        )
    lines.append("")
    lines.append("## Grouped Summary")
    lines.append("")
    for heading, selected in [
        ("Document-heavy cases", [item for item in results if item.route_expectation == "document"]),
        ("Data-only cases", [item for item in results if item.route_expectation == "data"]),
        ("Hybrid cases", [item for item in results if item.route_expectation == "hybrid"]),
        ("Adversarial cases", [item for item in results if item.difficulty == "Adversarial"]),
    ]:
        lines.append(f"### {heading}")
        lines.append("")
        if not selected:
            lines.append("- None")
            lines.append("")
            continue
        for item in selected:
            lines.append(f"- `{item.id}`: route `{item.route or '-'}`, avg score `{_fmt_metric(item.average_metric_score)}`, {_compact_notes(item)}")
        lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    strongest = sorted(
        [item for item in results if item.average_metric_score is not None],
        key=lambda item: item.average_metric_score or -1,
        reverse=True,
    )[:3]
    weakest = sorted(
        [item for item in results if item.average_metric_score is not None],
        key=lambda item: item.average_metric_score or 999,
    )[:3]
    lines.append("- Strongest cases: " + (", ".join(f"`{item.id}`" for item in strongest) if strongest else "No scored cases yet."))
    lines.append("- Weakest cases: " + (", ".join(f"`{item.id}`" for item in weakest) if weakest else "No scored cases yet."))
    lines.append(f"- Runtime failures: `{sum(1 for item in results if not item.runtime_success)}`")
    lines.append(f"- Route mismatches: `{sum(1 for item in results if item.runtime_success and not item.route_match)}`")
    lines.append(f"- Missing citations: `{sum(1 for item in results if item.runtime_success and not item.has_citations)}`")
    lines.append(f"- Missing retrieved contexts: `{sum(1 for item in results if item.runtime_success and not item.has_retrieved_contexts)}`")
    lines.append("")
    lines.append("## Per Case")
    lines.append("")
    for result in results:
        lines.append(f"### {result.id}")
        lines.append("")
        lines.append(f"- Difficulty: `{result.difficulty}`")
        lines.append(f"- Expected route: `{result.route_expectation}`")
        lines.append(f"- Actual route: `{result.route or '-'}`")
        lines.append(f"- Runtime success: `{str(result.runtime_success).lower()}`")
        lines.append(f"- Duration: `{result.duration_ms:.2f} ms`")
        lines.append(f"- Notes: {_compact_notes(result)}")
        if result.citations:
            lines.append("- Citation count: `{}`".format(len(result.citations)))
        if result.metric_scores:
            for key, value in result.metric_scores.items():
                lines.append(f"- {key}: `{_fmt_metric(value)}`")
        if result.metric_errors:
            lines.append(f"- Metric errors: `{json.dumps(result.metric_errors, ensure_ascii=True)}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _fmt_metric(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.4f}"


def _compact_notes(result: BenchmarkResult) -> str:
    notes = list(result.notes)
    if result.error_type:
        notes.append(f"{result.error_type}: {result.error_detail}")
    if result.runtime_success and not result.route_match:
        notes.append("route mismatch")
    if result.runtime_success and not result.has_citations:
        notes.append("missing citations")
    if result.runtime_success and not result.has_retrieved_contexts:
        notes.append("missing retrieved contexts")
    if not notes:
        return "ok"
    return "; ".join(notes)


def write_report(output_dir: Path, results: list[BenchmarkResult]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "results.json"
    md_path = output_dir / "results.md"
    json_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "results": [serialize_result(item) for item in results],
    }
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    md_path.write_text(render_results_markdown(results), encoding="utf-8")
    return json_path, md_path


def save_current_results(results: list[BenchmarkResult]) -> tuple[Path, Path]:
    json_path = Path("data/evaluation/ragas_results.json")
    md_path = Path("data/evaluation/RAGAS_RESULTS.md")
    json_payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "results": [serialize_result(item) for item in results],
    }
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    md_path.write_text(render_results_markdown(results), encoding="utf-8")
    return json_path, md_path


def run_benchmark(settings: BenchmarkRunSettings) -> list[BenchmarkResult]:
    init_db()
    cases = load_benchmark_cases(settings.dataset_path)
    if settings.case_id:
        cases = [case for case in cases if case.id == settings.case_id]
        if not cases:
            raise ValueError(f"Benchmark case not found: {settings.case_id}")
    results = asyncio.run(execute_cases(cases))
    if settings.use_ragas:
        score_results_with_ragas(results)
    return results
