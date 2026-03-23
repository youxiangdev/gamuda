# TC-01 to TC-08 Benchmark Review

Date: `2026-03-23`

Update:

- This file now reflects the post-fix rerun after adding specialist retry-and-repair handling for provider generation failures.

## Method

This review was produced by executing the current LangGraph chat flow against the `8` benchmark questions in [RAGAS_TEST_CASES.md](/Users/peanut/gamuda%20take%20home/data/evaluation/RAGAS_TEST_CASES.md) and comparing each final answer to the expected answer direction in that file.

Execution notes:

- run path: current `router -> document/data -> reporter` graph
- environment: running app container with current database contents
- assessment basis: final user-facing answer quality first, runtime stability second

## Summary

| ID | Verdict | Score | Notes |
| --- | --- | --- | --- |
| TC-01 | Pass | 9.5/10 | Correct fact and cleanly scoped answer. |
| TC-02 | Pass | 9.5/10 | Correct comparison and exact evidence values. |
| TC-03 | Partial | 7.5/10 | Mostly correct, but adds weaker cause framing and misses some expected nuance. |
| TC-04 | Partial | 5.5/10 | Runtime issue fixed, but answer still misses the strongest expected commercial-driver framing. |
| TC-05 | Pass | 9.0/10 | Correct February-to-March outlook change and slipped forecast. |
| TC-06 | Partial | 8.5/10 | Better downstream framing, but still not fully anchored in wider programme significance. |
| TC-07 | Pass | 9.5/10 | Correctly cautious: not fully closed, verification still pending. |
| TC-08 | Pass | 9.5/10 | Correctly answers no, with baseline-vs-forecast distinction. |

Overall:

- Pass: `5/8`
- Partial: `3/8`
- Runtime fail: `0/8`

## Per Test Case

### TC-01

Verdict: `Pass`

Why:

- Correctly states `31.5%` actual progress for January 2026.
- Includes the planned `32.0%` comparator without drifting into unsupported explanation.

Expected-answer fit:

- Very strong on faithfulness.
- Very strong on answer relevancy.

### TC-02

Verdict: `Pass`

Why:

- Correctly identifies `Cheras North` as worse.
- Uses the exact expected evidence:
  - `Pandan Gateway`: `33.0% planned / 32.0% actual`
  - `Cheras North`: `29.0% planned / 25.0% actual`

Expected-answer fit:

- Very strong on faithfulness.
- Very strong on evidence use.

### TC-03

Verdict: `Partial`

Why:

- Correctly identifies utility conflicts, additional underground services, and unresolved authority / method-statement issues.
- Correctly concludes these issues were not fully resolved by March.
- But it also foregrounds `heavy rainfall`, which is true in the report but not one of the main expected causes for Cheras North in the benchmark framing.
- It underplays the expected `redesign / sequence impact` wording.

Expected-answer fit:

- Strong enough on answer relevancy.
- Slightly weaker on context precision than desired.

### TC-04

Verdict: `Partial`

Why:

- The runtime failure has been fixed and the case now completes.
- The answer does identify real commercial pressure around utility diversion and interface design.
- But it does not align tightly with the benchmark expectation, which wants the strongest commercial issues framed as:
  - Cheras North redesign and sequence disruption
  - utility-related changes and protection measures
  - extended preliminaries from recovery windows
  - prolonged interface coordination
- It also underuses the expected reference pattern around `VO-019`, `VO-020`, `VO-021`, the finance sheet, and the March executive update.

Assessment:

- Runtime: fixed
- Answer quality: still weaker than expected

### TC-05

Verdict: `Pass`

Why:

- Correctly says that in February the team still expected completion in `March 2026`.
- Correctly says that by March the forecast slipped to `18 Apr 2026`.
- Correctly ties the deterioration to unresolved approvals / service conflict and increased risk severity.

Expected-answer fit:

- Strong on correctness.
- Strong on timeline comparison.

### TC-06

Verdict: `Partial`

Why:

- The answer now uses better downstream activities and is closer to the benchmark target.
- It identifies:
  - `systems-interface design freeze`
  - `partial access handover`
  - testing / commissioning readiness exposure
- But it still explains delivery sensitivity mainly through local constraints and baseline risks.
- The benchmark still expects a stronger statement that V3 matters because it affects wider programme interface dates, systems access, handover, installation readiness, and later integration activity.

Expected-answer fit:

- Good on faithfulness.
- Improved on answer relevancy.
- Still not fully aligned with the benchmark’s strongest “programme significance” framing.

### TC-07

Verdict: `Pass`

Why:

- Correctly answers `No`.
- Correctly distinguishes:
  - site reported it closed
  - independent QA verification remained pending
  - later records were still being reconciled

Expected-answer fit:

- Very strong on adversarial caution.
- Very strong on answer correctness.

### TC-08

Verdict: `Pass`

Why:

- The runtime failure has been fixed and the case now completes successfully.
- The answer correctly says `No`.
- It clearly distinguishes:
  - baseline target: `31 Mar 2026`
  - latest forecast: `22 Apr 2026`
  - actual status: not achieved in full by end-March, with partial approvals only

Expected-answer fit:

- Strong on faithfulness
- Strong on answer correctness
- Strong on answer relevancy

## Main Patterns

What is working:

- Straight factual retrieval and comparison questions are strong.
- Cross-document timeline questions are generally good when the model completes successfully.
- Adversarial caution on conflicting closure status is good.
- The retry-and-repair specialist harness removed the previous runtime failures in `TC-04` and `TC-08`.

What is still weak:

- Question-shape alignment for broader synthesis questions like `TC-06`.
- Commercial-issue framing and evidence selection for `TC-04`.
- Provider hardening when the model emits malformed non-JSON or fake `json` tool calls.

## Priority Fixes

1. Continue improving prompt guidance for “programme significance” and “downstream activities” style questions.
2. Improve commercial-issue framing and evidence prioritization for questions like `TC-04`.
3. Add an evaluation harness that records these `8` benchmark results automatically instead of relying on manual reruns.
