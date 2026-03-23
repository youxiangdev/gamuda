# TC-09 to TC-14 Data and Hybrid Test Cases

## Purpose

This companion test set extends the current `TC-01` to `TC-08` benchmark, which is still weighted toward document retrieval.

The goal here is to exercise:

- `data` routing against the real tabular ingestion path
- multi-step structured analysis over the ingested parquet datasets
- `hybrid` routing where the answer needs both report narrative and dataset evidence
- controlled handling of incomplete or messy structured data

## Current Data Sources In Scope

The current data-agent path does not query raw files directly. It discovers ingested `.csv` and `.xlsx` documents from the `documents` table, reads each document's `tabular_profile.json`, and then queries the generated parquet datasets.

Based on the current repository data, the tabular sources in scope are:

| Source File | Ingested Dataset Name | Rows | Notes |
| --- | --- | --- | --- |
| `financial_summary_mar_2026.csv` | `financial_summary_mar_2026` | `8` | Work-package level March cost and progress summary |
| `risk_register_mar_2026.csv` | `risk_register_mar_2026` | `14` | March risk register with one malformed row repaired during CSV ingestion |

Important ingestion nuance:

- the risk register is intentionally messy enough to fail a naive `pandas.read_csv`
- the repo's `CsvLoader` repairs one malformed row and records that repair in `csv_repair_report.json`
- date formats are mixed and normalized during ingestion
- one `owner` field remains blank in the normalized risk dataset

## Proposed Test Cases

| ID | Route Focus | Difficulty | Query | What A Good Answer Should Do | Expected Sources |
| --- | --- | --- | --- | --- | --- |
| TC-09 | Data | Easy | Which work package had the largest pending variation order exposure in the March financial dataset, and what was the primary VO reference? | Identify `Cheras North Station Structural and Architectural` as the highest pending VO item at `RM 12 million`, and cite `VO-021`. A good answer should make clear this comes from the structured March financial dataset rather than report prose. | `financial_summary_mar_2026.csv` |
| TC-10 | Data | Medium | Which March work packages were `5.0` percentage points or more behind planned progress, ranked from worst to less severe? | Return the ranked list: `Utilities Relocation` at `-12.0%`, `Cheras North Station Structural and Architectural` at `-5.5%`, and `Systems Interface and Design Coordination` at `-5.0%`. A good answer should use filtering plus ordering, not a vague narrative summary. | `financial_summary_mar_2026.csv` |
| TC-11 | Data | Medium | Which risks were in `Escalated` status in the March risk register, and what were their risk scores and escalation levels? | Identify `R-001` at risk score `25` with escalation level `Employer`, and `R-014` at risk score `20` with escalation level `Steering Committee`. A good answer should preserve the exact row-level attributes and not confuse `status` with `response_strategy`. | `risk_register_mar_2026.csv` |
| TC-12 | Data | Hard | Which work package carries the highest total risk score in the March risk register, and does that match the work package with the worst schedule variance in the March financial summary? | Aggregate risk scores by `linked_work_package` and identify `Viaduct Civil Works` as highest on total risk score at `51`. Then compare against the finance dataset and explain that the worst schedule variance belongs to `Utilities Relocation` at `-12.0%`, so they do **not** match. | `risk_register_mar_2026.csv`, `financial_summary_mar_2026.csv` |
| TC-13 | Hybrid | Hard | The March executive update says Package V3 is under pressure because of Cheras North disruption and utility diversion complexity. Do the structured datasets support that view, and what are the strongest data points? | Answer `Yes, broadly`. Tie the narrative to specific data points such as `Cheras North Station Structural and Architectural` having the largest pending VO exposure at `RM 12 million` and the highest cost variance at `RM 17 million`, while `Utilities Relocation` shows the worst schedule variance at `-12.0%` and the highest single escalated risk `R-001` at score `25`. A good answer should connect the report claim to the actual structured evidence instead of repeating the report alone. | `executive_steering_update_mar_2026.md`, `financial_summary_mar_2026.csv`, `risk_register_mar_2026.csv` |
| TC-14 | Hybrid | Adversarial | The March executive update warns that pending VOs may harden into claims. Does the structured data show that the largest pending commercial exposure sits in exactly the same work package as the worst schedule pressure? | Answer carefully: `No, not exactly at single-work-package level`. The largest pending VO exposure is `Cheras North Station Structural and Architectural` at `RM 12 million`, but the worst schedule variance is `Utilities Relocation` at `-12.0%`. A good answer should still explain that both sit within the same broader Cheras North and utilities problem area, so the narrative is directionally supported even though the structured leaders differ. | `executive_steering_update_mar_2026.md`, `financial_summary_mar_2026.csv`, `risk_register_mar_2026.csv` |

## Why These Cases Matter

These cases cover gaps in the current benchmark:

- `TC-09` and `TC-10` test straightforward data-agent ranking and filtering
- `TC-11` tests record-level extraction from the risk register
- `TC-12` tests multi-query reasoning across two structured datasets without relying on PDFs
- `TC-13` tests whether the system can justify a narrative claim with structured evidence
- `TC-14` tests whether the system stays precise when the narrative is directionally true but the structured leaders are split across related work packages

## Recommended Evaluation Notes

- For `data` cases, review whether the router correctly avoids sending the question to the document agent.
- For `TC-12`, check whether the data agent can compare findings across separate dataset queries without inventing a join that the tool layer does not provide directly.
- For `TC-13` and `TC-14`, check whether the router chooses `hybrid` and whether the reporter keeps the distinction between narrative support and structured confirmation.
- For all cases, verify that citations reference actual `query_id` outputs for dataset claims and actual document citations for narrative claims.
