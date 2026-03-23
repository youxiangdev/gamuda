# Senior AI Engineer Take-Home Review

## Review basis

This review compares the current repository against the assessment brief in `Senior AI Engineer - Take Home Assessment.pdf`.

Focus:

- requirement coverage
- senior-level implementation quality
- architecture and system design readiness
- submission readiness

Non-focus:

- judging whether the current retrieved answers are good or bad in content quality

## Check performed

I checked the current implementation, not just the earlier review draft.

Reviewed areas:

- `app/ai/graph.py`
- `app/ai/document_tools.py`
- `app/ai/data_tools.py`
- `app/ai/prompt.py`
- `app/services/embedding_service.py`
- `app/services/ingestion_service.py`
- `app/services/chat_service.py`
- `app/api/v1/routes/documents.py`
- `frontend/src/App.jsx`
- `README.md`
- `architecture.md`
- `decision.md`

Sanity checks:

- `uv run python -m compileall app` passed
- `uv run pytest` could not run because `pytest` is not installed in the project and there is no test suite in the repo

## Overall verdict

The current submission is no longer just an ingestion prototype. It now has a real end-to-end multi-agent path:

- router
- document specialist
- data specialist
- reporter

It also has real retrieval/query tools behind the specialist agents.

The strongest area is still **data ingestion and preparation**.
The weakest area is now **retrieval quality hardening, evaluation evidence, and submission packaging**.

If this were graded today, I think the main risk is no longer "the RAG path is fake." The main risk is that the RAG path is still **baseline-quality and insufficiently validated** for a strong senior-level submission.

## What is already solid

- The ingestion foundation is well split across upload, storage, ingestion jobs, PDF parsing, chunk persistence, and tabular normalization.
- The PDF path is meaningfully structured: Docling output, chunk metadata, page spans, heading paths, and stored chunk records are all there.
- PDF chunk embeddings are actually written to `document_chunks.embedding` when `JINA_API_KEY` is configured.
- The document agent is no longer placeholder-only. It can call:
  - `search_documents`
  - `keyword_search_documents`
- The data agent is also real now. It can call:
  - `list_datasets`
  - `describe_dataset`
  - `query_parquet`
- The graph is a real LangGraph workflow with `direct_response`, `clarify`, `document`, `data`, and `hybrid` routing.
- Specialist outputs are validated before promotion into shared state, which is a strong design choice:
  - document findings must cite chunk IDs returned in the run
  - data findings must cite query IDs returned in the run
- The frontend already supports the right demo flow:
  - upload documents
  - inspect docs
  - run chat
  - stream events
  - render citations/evidence
- There is useful observability groundwork:
  - per-agent model/provider logging
  - token usage
  - estimated cost
  - run events

## Main gaps

These are the parts that are still lacking after checking the current codebase.

### 1. Retrieval quality is real and directionally thoughtful, but still not convincingly senior-level yet

This is the biggest implementation gap now.

What is implemented today:

- vector similarity search over `document_chunks.embedding`
- simple keyword search over chunk text/metadata fields
- agent-driven tool selection through prompting
- iterative query reformulation at the agent level instead of a single-shot retrieval pass
- mixed retrieval behavior where the document agent can try semantic search first, then retry with rephrased searches and keyword lookups

Important nuance:

- The current document retrieval design is not just "naive vector search only".
- A fairer description is:
  - iterative query reformulation
  - semantic search
  - keyword search
  - bounded multi-step evidence gathering inside the specialist agent
- This is a valid retrieval-improvement strategy and can be defended as an alternative to "retrieve a large pool and rerank".

What is still missing:

- deterministic hybrid retrieval logic at the tool/runtime layer
- candidate fusion
- reranking
- explicit metadata filtering by reporting period, package, or document type
- retrieval evaluation showing the chosen strategy is actually better than naive similarity

Why this matters:

- The brief asks for at least one technique beyond naive similarity search.
- The current code likely does satisfy that requirement in spirit because it uses iterative query reformulation plus a semantic/keyword combination rather than relying on a single vector lookup.
- However, the improvement is still mostly expressed through prompt-guided agent behavior rather than through an explicit retrieval policy that is easy to inspect, benchmark, and explain.
- Because of that, an evaluator may still read it as "baseline retrieval with smart prompting" unless the approach is documented and measured more clearly.

Current code evidence:

- `app/ai/document_tools.py` does cosine-distance retrieval plus a simple `ILIKE` keyword path
- `app/ai/prompt.py` instructs the document agent to retry weak searches with rephrased queries and to combine semantic and keyword retrieval
- `app/ai/graph.py` gives the specialist a bounded multi-step tool loop, which supports the iterative retrieval pattern
- `architecture.md` still talks about reranking, but the runtime does not implement a reranker

Assessment:

- the justification for not using reranking is valid if positioned as `iterative query reformulation` or `multi-query retrieval`
- the current implementation still needs clearer retrieval policy, structured filters, and evaluation evidence to make that justification strong in a senior-level submission

### 2. The architecture document still overstates the current implementation

This is now a credibility issue more than a coding issue.

`architecture.md` describes a richer document retrieval path than what the code actually does today, including:

- generated search queries
- retrieve from vector store
- rerank and select evidence

The current runtime does not have:

- a separate retrieval orchestration layer
- a reranker
- deterministic candidate fusion logic
- explicit entity / metadata filtering in the document tool layer, even though useful fields already exist in stored chunks

The data-agent part of the architecture is much closer to reality now.
The document-agent part is still described as more mature than the implementation.

What should happen before submission:

- either implement the missing retrieval steps
- or rewrite the architecture doc into:
  - implemented now
  - designed next
  - omitted due to time

### 3. RAGAS evaluation is still missing

This remains a major blocker.

Current status:

- `data/evaluation/RAGAS_TEST_CASES.md` exists
- there is no executable evaluation script or notebook
- there are no recorded RAGAS outputs in the repo
- there is no results table or interpretation

What is still lacking:

- at least 8 executed evaluation queries
- published scores
- short analysis of what performed well vs poorly

Without this, a core deliverable in the brief is still incomplete.

### 4. There is still no automated test coverage on the critical path

Current status:

- no `tests/` directory
- `pytest` is not installed in the environment defined by this repo
- I could not run automated tests because none appear to be set up

Why this matters:

- The repository now contains enough real logic that testing matters:
  - routing behavior
  - retrieval tool behavior
  - query-tool validation
  - finding-schema enforcement
  - failure paths

Minimum test bar for a senior-level submission:

- route selection tests
- document-tool retrieval tests
- data-tool query tests
- finding validation tests
- insufficient-evidence tests
- chat run / SSE happy-path smoke tests

### 5. Submission packaging is still incomplete

The repo has improved implementation-wise, but the evaluator package is still not complete.

Still lacking or not yet evident:

- public deployed application URL in `README.md`
- screen recording walkthrough link in `README.md`
- `DECISIONS.md` in the requested submission-ready form
- a clear evaluator-facing summary of what is implemented vs intentionally deferred

Current state:

- `README.md` is mainly local setup documentation
- `decision.md` is thoughtful, but it reads as one narrative decision memo, not a discrete decision log with at least 6 entries
- filenames are not yet submission-polished (`decision.md` vs `DECISIONS.md`)

### 6. Security and production-readiness treatment is still thin

The code shows good instincts, but the repo still lacks explicit hardening in areas the brief is likely to care about.

Examples of what I do not yet see clearly implemented or documented:

- upload file size limits
- content sniffing beyond file extension checks
- duplicate upload handling / idempotency
- prompt-injection handling strategy for retrieved text
- malicious document containment / quarantine hook
- explicit API key validation and degraded-mode reporting
- privacy and retention posture

Concrete example:

- `app/api/v1/routes/documents.py` and `app/services/document_service.py` validate extensions and metadata, but they do not appear to enforce stronger upload safety controls

Related retrieval note:

- chunk records already store useful structured fields such as `reporting_period`, `heading_path`, and `contains_entities`
- `contains_entities` is currently populated from deterministic regex extraction such as `MS-*`, `VO-*`, `NCR-*`, and `R-*`
- this is a good start for business-aware retrieval, but the document search tools do not yet use `contains_entities` or metadata fields as explicit first-class filters

### 7. Operational readiness is still uneven

The system is good enough for demoing, but some runtime behavior is still fragile.

Examples:

- semantic retrieval depends on embeddings being present, which in turn depends on `JINA_API_KEY`
- if embeddings are unavailable, `search_documents` returns no semantic results rather than exposing a clearer retrieval-readiness status
- live run transport is kept in-memory inside `ChatService._runs`, so active run state is not durable across process restarts

These are not assessment blockers by themselves, but they do matter for senior-level polish.

## Good to have

These are not the first blockers, but they would raise the submission quality meaningfully.

### 1. Make retrieval behavior explicit and measurable

Best improvement path:

- add metadata-aware filtering
- add hybrid candidate fusion
- add reranking
- publish a small retrieval benchmark or ablation note

### 2. Add clearer evidence UX in the frontend

The current frontend is already useful, but better evaluator-facing UX would help.

Examples:

- clickable evidence cards
- page/deep-link targets for document evidence
- clearer no-evidence / degraded-retrieval states
- grouped evidence by agent

### 3. Improve run durability and replay

Current run messages are persisted, but live run state is not.

Higher-mark improvement:

- persist run events
- allow SSE replay
- survive restart during an active run
- preserve specialist evidence and metrics for later inspection

### 4. Add benchmark numbers for the architecture section

Helpful additions:

- PDF ingestion latency
- average embedding time per document
- query latency by route
- average cost per chat run
- artifact size growth

This would make the scalability/cost discussion stronger and more concrete.

## Recommended priority order

If time is limited, this is the highest-value sequence now:

1. Add a clearly non-naive retrieval strategy and make it explicit in code and docs.
2. Run RAGAS and publish the results table.
3. Add a focused automated test suite for routing, tools, and evidence validation.
4. Rewrite `architecture.md`, `decision.md`, and `README.md` to match current reality and submission requirements.
5. Add deployment URL and walkthrough link.
6. Add basic security and degraded-mode documentation.

## Bottom line

Current state:

- strong ingestion and preparation layer
- real multi-agent RAG workflow
- still light on retrieval sophistication, evaluation proof, and submission polish

This repository now looks like a **working prototype with real end-to-end behavior**, not a fake agent demo.
What still keeps it from feeling fully submission-ready is the lack of:

- a clearly stronger-than-baseline retrieval strategy
- RAGAS evidence
- automated tests
- submission-complete docs and artifacts

That is the gap I would close next.
