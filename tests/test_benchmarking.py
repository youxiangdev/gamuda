from pathlib import Path

from app.evaluation.benchmarking import (
    BenchmarkResult,
    dedupe_preserve_order,
    extract_contexts_and_citations,
    load_benchmark_cases,
    render_results_markdown,
)


def test_load_benchmark_cases_reads_tc01_to_tc14_dataset():
    cases = load_benchmark_cases(Path("data/evaluation/ragas_dataset.json"))
    case_ids = [case.id for case in cases]
    assert len(cases) == 14
    assert case_ids[0] == "TC-01"
    assert case_ids[-1] == "TC-14"


def test_dedupe_preserve_order_keeps_first_non_empty_values():
    assert dedupe_preserve_order(["alpha", "", "alpha", "beta", " beta "]) == ["alpha", "beta"]


def test_extract_contexts_and_citations_merges_document_and_data_evidence():
    state = {
        "document_findings": {
            "findings": [
                {
                    "claim": "Doc claim",
                    "evidence": [
                        {"snippet": "doc snippet", "citation": "doc citation"},
                        {"snippet": "doc snippet", "citation": "doc citation"},
                    ],
                }
            ]
        },
        "data_findings": {
            "findings": [
                {
                    "claim": "Data claim",
                    "evidence": [
                        {"snippet": "data snippet", "citation": "data citation"},
                    ],
                }
            ]
        },
    }
    contexts, citations = extract_contexts_and_citations(state)
    assert contexts == ["doc snippet", "data snippet"]
    assert citations == ["doc citation", "data citation"]


def test_render_results_markdown_includes_grouped_sections_and_case_rows():
    results = [
        BenchmarkResult(
            id="TC-01",
            difficulty="Easy",
            question="Q1",
            route_expectation="document",
            route="document",
            runtime_success=True,
            generated_answer="A1",
            retrieved_contexts=["context"],
            citations=["citation"],
            route_match=True,
            has_citations=True,
            has_retrieved_contexts=True,
            primary_metrics=["faithfulness", "answer_relevancy"],
            metric_scores={"faithfulness": 0.9, "answer_relevancy": 0.8},
        ),
        BenchmarkResult(
            id="TC-09",
            difficulty="Easy",
            question="Q2",
            route_expectation="data",
            route="data",
            runtime_success=False,
            error_type="RuntimeError",
            error_detail="boom",
            primary_metrics=["faithfulness", "answer_relevancy"],
        ),
    ]
    content = render_results_markdown(results)
    assert "## Grouped Summary" in content
    assert "### Document-heavy cases" in content
    assert "### Data-only cases" in content
    assert "## Per Case" in content
    assert "| TC-01 | document | pass | 0.9000 | 0.8000 | - | - | - | ok |" in content
    assert "RuntimeError: boom" in content
