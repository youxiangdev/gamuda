# RAGAS Test Cases

## Overview

This evaluation set contains `8` test queries across `4` difficulty levels in line with the assessment requirement:

- `Easy` x 2
- `Medium` x 2
- `Hard` x 2
- `Adversarial` x 2

The primary evaluation focus is:

- `Faithfulness`
- `Answer Relevancy`

Optional bonus metrics:

- `Context Precision`
- `Context Recall`
- `Answer Correctness`

## Evaluation Design Principles

- Each query is grounded in the current project document set
- Each query has a clear expected answer direction
- Cross-document questions are included intentionally
- Conflict-heavy questions are reserved for `Adversarial` and `Hard` cases
- Source expectations are listed so citation quality can also be reviewed

## Test Cases

| ID | Difficulty | Query | Primary Metrics | What A Good Answer Should Do | Expected Sources |
| --- | --- | --- | --- | --- | --- |
| TC-01 | Easy | What was the overall actual progress for Package V3 in January 2026? | Faithfulness, Answer Relevancy | State that actual progress was `31.5%` against planned `32.0%`, without adding unsupported explanation | `monthly_status_report_jan_2026.md` |
| TC-02 | Easy | Which station package showed worse schedule slippage in February 2026, Pandan Gateway or Cheras North, and what was the evidence? | Faithfulness, Answer Relevancy | Answer that `Cheras North` was worse, and support it with the February progress snapshot showing Pandan Gateway at `33.0% planned vs 32.0% actual` and Cheras North at `29.0% planned vs 25.0% actual` | `monthly_status_report_feb_2026.md` |
| TC-03 | Medium | What were the principal causes of delay at Cheras North by February 2026, and were they fully resolved by March 2026? | Faithfulness, Context Precision, Context Recall, Answer Relevancy | Identify the key causes: utility conflict, unresolved authority clearance, additional underground services, and redesign/sequence impacts. Then explain they were not fully resolved by March because the executive update still shows the utility diversion slipping into April | `monthly_status_report_jan_2026.md`, `monthly_status_report_feb_2026.md`, `executive_steering_update_mar_2026.md`, `risk_register_mar_2026.csv` |
| TC-04 | Medium | Which commercial issues most threatened Package V3 by March 2026, and which references support that view? | Faithfulness, Context Precision, Answer Relevancy | Cite the strongest commercial pressure points such as Cheras North redesign and sequence disruption, utility-related changes and protection measures, extended preliminaries from recovery working windows, and prolonged interface coordination. A good answer should reference `VO-019`, `VO-020`, `VO-021`, the finance sheet, and the March executive update | `executive_steering_update_mar_2026.md`, `financial_summary_mar_2026.csv`, `risk_register_mar_2026.csv` |
| TC-05 | Hard | How did the outlook for Cheras North utility diversion change between February and March 2026? | Faithfulness, Context Recall, Answer Correctness | Explain that in February the team still expected completion in March subject to authority clearance, but by the March executive update the forecast had slipped to `18 Apr 2026` | `monthly_status_report_feb_2026.md`, `executive_steering_update_mar_2026.md`, `risk_register_mar_2026.csv` |
| TC-06 | Hard | Why is Package V3 considered delivery-sensitive within the East Metro programme, and which downstream programme activities are most exposed if it slips further? | Faithfulness, Answer Relevancy, Context Recall | Explain that V3 combines high-visibility station works, constrained traffic and utility interfaces, and systems access dependencies. Then connect that to downstream exposure such as systems design freeze, access handover, installation readiness, and later integration activities | `PROGRAMME_BRIEF.md`, `PACKAGE_V3_BRIEF.md`, `executive_steering_update_mar_2026.md` |
| TC-07 | Adversarial | Has NCR-014 been fully closed? | Faithfulness, Answer Correctness | Answer carefully: `No, not fully verified/closed at project controls level.` It should mention that site reported it closed, but independent QA verification remained pending and later records were still being reconciled | `monthly_status_report_jan_2026.md`, `monthly_status_report_feb_2026.md`, `risk_register_mar_2026.csv`, `executive_steering_update_mar_2026.md` |
| TC-08 | Adversarial | Was the systems interface design freeze achieved by the end of March 2026? | Faithfulness, Answer Correctness, Answer Relevancy | Answer `No`. It should distinguish baseline target vs actual status, noting the baseline date was `31 Mar 2026` but the March executive update moved the forecast to `22 Apr 2026` | `PACKAGE_V3_BRIEF.md`, `monthly_status_report_jan_2026.md`, `monthly_status_report_feb_2026.md`, `executive_steering_update_mar_2026.md` |

## Notes Per Difficulty Level

### Easy

These questions check whether the system can retrieve and restate a single fact cleanly.

### Medium

These questions check whether the system can synthesize a small number of related facts without drifting into unsupported narrative.

### Hard

These questions require cross-document reasoning and timeline comparison.

### Adversarial

These questions are intentionally phrased to trigger overconfident answers if the system ignores document conflicts or timeline nuance.

## Recommended Ground Truth Style

For implementation, each test case should eventually store:

- `question`
- `difficulty`
- `ground_truth`
- `expected_sources`
- `primary_metrics`
- `notes`

This can later be converted into JSON or CSV for automated RAGAS runs.
