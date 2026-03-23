# RAGAS Dataset Specification

## Purpose

This file defines the RAGAS evaluation dataset and reporting structure for this take-home submission.

The goal is not to build a large evaluation platform.
The goal is to demonstrate that the current multi-agent RAG system can answer the required `8` benchmark questions, plus the companion `6` data and hybrid questions, in a grounded way using retrieved evidence.

## Minimum Requirement

The evaluation set should contain:

- the required `8` benchmark questions defined in [RAGAS_TEST_CASES.md](/Users/peanut/gamuda%20take%20home/data/evaluation/RAGAS_TEST_CASES.md)
- the companion `6` benchmark questions defined in [TC09_TC14_DATA_HYBRID_TEST_CASES.md](/Users/peanut/gamuda%20take%20home/data/evaluation/TC09_TC14_DATA_HYBRID_TEST_CASES.md)

For each test case, capture:

- `id`
- `difficulty`
- `question`
- `ground_truth`
- `generated_answer`
- `retrieved_contexts`

Minimum metrics to report:

- `faithfulness`
- `answer_relevancy`

Recommended additional metrics:

- `context_precision`
- `context_recall`
- `answer_correctness`

## Dataset Shape

Recommended file:

- `data/evaluation/ragas_dataset.json`

Recommended top-level structure:

```json
{
  "dataset_name": "gamuda_take_home_ragas_eval",
  "created_at": "2026-03-23T00:00:00Z",
  "samples": [
    {
      "id": "TC-01",
      "difficulty": "Easy",
      "question": "What was the overall actual progress for Package V3 in January 2026?",
      "ground_truth": "The overall actual progress for Package V3 in January 2026 was 31.5% against a planned 32.0%.",
      "expected_sources": [
        "monthly_status_report_jan_2026.md"
      ],
      "primary_metrics": [
        "faithfulness",
        "answer_relevancy"
      ],
      "generated_answer": "",
      "retrieved_contexts": [],
      "reference_contexts": [],
      "route": "",
      "citations": [],
      "notes": ""
    }
  ]
}
```

## Field Definitions

### Core fields

- `id`
  Stable benchmark identifier such as `TC-01`.

- `difficulty`
  One of:
  - `Easy`
  - `Medium`
  - `Hard`
  - `Adversarial`

- `question`
  The benchmark question sent into the system.

- `ground_truth`
  A concise reference answer written in evaluator-friendly prose.
  This should be fact-focused, not overly long.

- `generated_answer`
  The final user-facing answer returned by the current graph run.

- `retrieved_contexts`
  The actual evidence snippets used by the system for that run.
  This is the most important context field for RAGAS.

### Supporting fields

- `expected_sources`
  The logical source list already defined in [RAGAS_TEST_CASES.md](/Users/peanut/gamuda%20take%20home/data/evaluation/RAGAS_TEST_CASES.md).
  Useful for debugging and manual review.

- `reference_contexts`
  Optional reference snippets manually curated from the expected sources.
  Useful for `context_recall` or more controlled evaluation.

- `route`
  The chosen route for the run:
  - `document`
  - `data`
  - `hybrid`
  - `direct_response`
  - `clarify`

- `citations`
  Structured citations returned to the reporter, for example:
  - document chunk citations
  - query citations

- `notes`
  Free text for evaluator observations or runtime notes.

## Mapping From Current System

For each benchmark run, map the current graph output into the RAGAS dataset as follows.

### `question`

Take the benchmark question directly from [RAGAS_TEST_CASES.md](/Users/peanut/gamuda%20take%20home/data/evaluation/RAGAS_TEST_CASES.md).

### `generated_answer`

Use the graph final answer:

- `state["final_answer"]`

### `route`

Use:

- `state["route"]`

### `retrieved_contexts`

Build this from the evidence already passed into the reporter.

Document side:

- `state["document_findings"]["findings"][*]["evidence"][*]["snippet"]`

Data side:

- `state["data_findings"]["findings"][*]["evidence"][*]["snippet"]`

Merge both into a flat list of strings.

Recommended rule:

- deduplicate exact duplicate snippets
- keep ordering stable
- preserve only the evidence actually used in that run

### `citations`

Build this from:

Document side:

- `state["document_findings"]["findings"][*]["evidence"][*]["citation"]`

Data side:

- `state["data_findings"]["findings"][*]["evidence"][*]["citation"]`

### `ground_truth`

Write one short reference answer per case using the expected-answer direction already documented in [RAGAS_TEST_CASES.md](/Users/peanut/gamuda%20take%20home/data/evaluation/RAGAS_TEST_CASES.md).

This is sufficient for the take-home.
It does not need to be overly long or literary.

## Recommended Sample Structure

Use this exact per-sample structure:

```json
{
  "id": "TC-04",
  "difficulty": "Medium",
  "question": "Which commercial issues most threatened Package V3 by March 2026, and which references support that view?",
  "ground_truth": "The strongest commercial threats to Package V3 by March 2026 were Cheras North redesign and sequence disruption, utility-related changes and protection measures, extended preliminaries from recovery working windows, and prolonged interface coordination. Supporting references should include VO-019, VO-020, VO-021, the March finance sheet, and the March executive update.",
  "expected_sources": [
    "executive_steering_update_mar_2026.md",
    "financial_summary_mar_2026.csv",
    "risk_register_mar_2026.csv"
  ],
  "primary_metrics": [
    "faithfulness",
    "context_precision",
    "answer_relevancy"
  ],
  "generated_answer": "",
  "retrieved_contexts": [],
  "reference_contexts": [],
  "route": "",
  "citations": [],
  "notes": ""
}
```

## Expected Output Artifacts

The submission should ideally contain these three files.

### 1. Dataset file

- `data/evaluation/ragas_dataset.json`

Purpose:

- stores the structured evaluation inputs and run outputs

### 2. Results file

- `data/evaluation/RAGAS_RESULTS.md`

Purpose:

- reports the metric table for the `14` benchmark cases

Recommended table:

| ID | Route | Faithfulness | Answer Relevancy | Context Precision | Context Recall | Answer Correctness | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |

### 3. Summary file

- `data/evaluation/RAGAS_SUMMARY.md`

Purpose:

- explains the results in plain English

Recommended sections:

- strongest cases
- weakest cases
- common failure pattern
- retrieval observations
- next improvement step

## Expected Outcome For This Assessment

The expected outcome is not "perfect scores".

The expected outcome is:

- all `14` benchmark cases are executed, with `TC01-TC08` treated as the required core set
- the system produces a final answer and retrieved evidence for each case
- RAGAS scores are published for at least:
  - `faithfulness`
  - `answer_relevancy`
- the results are interpretable and tied back to the system design

For this take-home, a strong outcome would look like:

- most easy and medium questions scoring clearly well
- hard and adversarial questions showing lower but still defensible scores
- weak cases explained honestly
- failure patterns linked to retrieval, routing, or synthesis limitations

## Practical Success Criteria

I would consider the requirement satisfied if the repo shows:

1. A reproducible dataset for the `14` benchmark questions.
2. A metric table with at least `faithfulness` and `answer_relevancy`.
3. Clear mapping between generated answers and retrieved contexts.
4. A short written interpretation of the results.

I would consider it strong if the repo also shows:

1. Route information for each test case.
2. Saved citations for each run.
3. Optional `context_precision`, `context_recall`, and `answer_correctness`.
4. A short explanation of why some cases underperform.

## Notes On Current Repo State

The current file [TC01_TC08_BENCHMARK_REVIEW.md](/Users/peanut/gamuda%20take%20home/data/evaluation/TC01_TC08_BENCHMARK_REVIEW.md) is a useful manual benchmark review.

However, it is not yet a structured RAGAS output because it does not store:

- `ground_truth`
- `generated_answer`
- `retrieved_contexts`
- computed metric fields in a machine-readable dataset

That file should be kept as a qualitative review companion, while the new RAGAS files provide the formal benchmark evidence.
