# Benchmark Results

Date: `2026-03-23T10:51:18.852060+00:00`

## Summary

| ID | Route | Runtime | Faithfulness | Answer Relevancy | Answer Correctness | Context Precision | Context Recall | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TC-01 | document | pass | - | 1.0000 | - | - | - | ok |
| TC-02 | document | pass | 0.8571 | 0.8200 | - | - | - | ok |
| TC-03 | document | pass | 0.8889 | 0.9705 | - | 0.8875 | 1.0000 | route mismatch |
| TC-04 | document | pass | 0.3333 | 0.9774 | - | 1.0000 | - | route mismatch |
| TC-05 | document | pass | 1.0000 | - | - | - | 1.0000 | route mismatch |
| TC-06 | document | pass | 0.6154 | - | - | - | 0.0000 | ok |
| TC-07 | document | pass | 0.5000 | - | - | - | - | route mismatch |
| TC-08 | document | pass | - | 1.0000 | - | - | - | ok |
| TC-09 | data | pass | 0.7500 | 0.9804 | - | - | - | ok |
| TC-10 | data | pass | 0.6250 | 0.9123 | - | - | - | ok |
| TC-11 | document | pass | - | - | - | - | - | route mismatch; missing citations; missing retrieved contexts |
| TC-12 | hybrid | pass | 0.7778 | 0.9792 | - | - | 0.7500 | route mismatch |
| TC-13 | hybrid | pass | 0.0833 | 0.9208 | - | 0.2500 | 0.4000 | ok |
| TC-14 | hybrid | pass | - | - | - | - | - | ok |

## Grouped Summary

### Document-heavy cases

- `TC-01`: route `document`, avg score `1.0000`, ok
- `TC-02`: route `document`, avg score `0.8385`, ok
- `TC-06`: route `document`, avg score `0.3077`, ok
- `TC-08`: route `document`, avg score `1.0000`, ok

### Data-only cases

- `TC-09`: route `data`, avg score `0.8652`, ok
- `TC-10`: route `data`, avg score `0.7687`, ok
- `TC-11`: route `document`, avg score `-`, route mismatch; missing citations; missing retrieved contexts
- `TC-12`: route `hybrid`, avg score `0.8357`, route mismatch

### Hybrid cases

- `TC-03`: route `document`, avg score `0.9367`, route mismatch
- `TC-04`: route `document`, avg score `0.7702`, route mismatch
- `TC-05`: route `document`, avg score `1.0000`, route mismatch
- `TC-07`: route `document`, avg score `0.5000`, route mismatch
- `TC-13`: route `hybrid`, avg score `0.4135`, ok
- `TC-14`: route `hybrid`, avg score `-`, ok

### Adversarial cases

- `TC-07`: route `document`, avg score `0.5000`, route mismatch
- `TC-08`: route `document`, avg score `1.0000`, ok
- `TC-14`: route `hybrid`, avg score `-`, ok

## Interpretation

- Strongest cases: `TC-01`, `TC-05`, `TC-08`
- Weakest cases: `TC-06`, `TC-13`, `TC-07`
- Runtime failures: `0`
- Route mismatches: `6`
- Missing citations: `1`
- Missing retrieved contexts: `1`

## Per Case

### TC-01

- Difficulty: `Easy`
- Expected route: `document`
- Actual route: `document`
- Runtime success: `true`
- Duration: `4268.16 ms`
- Notes: ok
- Citation count: `1`
- faithfulness: `-`
- answer_relevancy: `1.0000`
- Metric errors: `{"faithfulness": "RAGAS returned no numeric score."}`

### TC-02

- Difficulty: `Easy`
- Expected route: `document`
- Actual route: `document`
- Runtime success: `true`
- Duration: `2976.75 ms`
- Notes: ok
- Citation count: `1`
- faithfulness: `0.8571`
- answer_relevancy: `0.8200`

### TC-03

- Difficulty: `Medium`
- Expected route: `hybrid`
- Actual route: `document`
- Runtime success: `true`
- Duration: `6836.76 ms`
- Notes: route mismatch
- Citation count: `5`
- faithfulness: `0.8889`
- context_precision: `0.8875`
- context_recall: `1.0000`
- answer_relevancy: `0.9705`

### TC-04

- Difficulty: `Medium`
- Expected route: `hybrid`
- Actual route: `document`
- Runtime success: `true`
- Duration: `6635.62 ms`
- Notes: route mismatch
- Citation count: `3`
- faithfulness: `0.3333`
- context_precision: `1.0000`
- answer_relevancy: `0.9774`

### TC-05

- Difficulty: `Hard`
- Expected route: `hybrid`
- Actual route: `document`
- Runtime success: `true`
- Duration: `15555.70 ms`
- Notes: route mismatch
- Citation count: `3`
- faithfulness: `1.0000`
- context_recall: `1.0000`
- answer_correctness: `-`
- Metric errors: `{"answer_correctness": "RAGAS returned no numeric score."}`

### TC-06

- Difficulty: `Hard`
- Expected route: `document`
- Actual route: `document`
- Runtime success: `true`
- Duration: `13901.88 ms`
- Notes: ok
- Citation count: `3`
- faithfulness: `0.6154`
- answer_relevancy: `-`
- context_recall: `0.0000`
- Metric errors: `{"answer_relevancy": "RAGAS returned no numeric score."}`

### TC-07

- Difficulty: `Adversarial`
- Expected route: `hybrid`
- Actual route: `document`
- Runtime success: `true`
- Duration: `5470.78 ms`
- Notes: route mismatch
- Citation count: `4`
- faithfulness: `0.5000`
- answer_correctness: `-`
- Metric errors: `{"answer_correctness": "RAGAS returned no numeric score."}`

### TC-08

- Difficulty: `Adversarial`
- Expected route: `document`
- Actual route: `document`
- Runtime success: `true`
- Duration: `5221.89 ms`
- Notes: ok
- Citation count: `2`
- faithfulness: `-`
- answer_correctness: `-`
- answer_relevancy: `1.0000`
- Metric errors: `{"faithfulness": "RAGAS returned no numeric score.", "answer_correctness": "RAGAS returned no numeric score."}`

### TC-09

- Difficulty: `Easy`
- Expected route: `data`
- Actual route: `data`
- Runtime success: `true`
- Duration: `3397.69 ms`
- Notes: ok
- Citation count: `1`
- faithfulness: `0.7500`
- answer_relevancy: `0.9804`
- answer_correctness: `-`
- Metric errors: `{"answer_correctness": "RAGAS returned no numeric score."}`

### TC-10

- Difficulty: `Medium`
- Expected route: `data`
- Actual route: `data`
- Runtime success: `true`
- Duration: `4810.84 ms`
- Notes: ok
- Citation count: `1`
- faithfulness: `0.6250`
- answer_relevancy: `0.9123`
- answer_correctness: `-`
- Metric errors: `{"answer_correctness": "RAGAS returned no numeric score."}`

### TC-11

- Difficulty: `Medium`
- Expected route: `data`
- Actual route: `document`
- Runtime success: `true`
- Duration: `8745.57 ms`
- Notes: route mismatch; missing citations; missing retrieved contexts
- Metric errors: `{"ragas": "Skipped because retrieved_contexts is empty."}`

### TC-12

- Difficulty: `Hard`
- Expected route: `data`
- Actual route: `hybrid`
- Runtime success: `true`
- Duration: `10949.44 ms`
- Notes: route mismatch
- Citation count: `2`
- faithfulness: `0.7778`
- answer_relevancy: `0.9792`
- answer_correctness: `-`
- context_recall: `0.7500`
- Metric errors: `{"answer_correctness": "RAGAS returned no numeric score."}`

### TC-13

- Difficulty: `Hard`
- Expected route: `hybrid`
- Actual route: `hybrid`
- Runtime success: `true`
- Duration: `7723.44 ms`
- Notes: ok
- Citation count: `5`
- faithfulness: `0.0833`
- answer_relevancy: `0.9208`
- context_precision: `0.2500`
- context_recall: `0.4000`

### TC-14

- Difficulty: `Adversarial`
- Expected route: `hybrid`
- Actual route: `hybrid`
- Runtime success: `true`
- Duration: `15870.44 ms`
- Notes: ok
- Citation count: `2`
- faithfulness: `-`
- answer_correctness: `-`
- answer_relevancy: `-`
- Metric errors: `{"faithfulness": "RAGAS returned no numeric score.", "answer_correctness": "RAGAS returned no numeric score.", "answer_relevancy": "RAGAS returned no numeric score."}`
