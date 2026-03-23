# Decision Making

---

## 1. PDF Ingestion Decision

### Chosen approach

PDF documents are parsed using `Docling`, which converts the source PDF into structured outputs such as Markdown and document JSON. These outputs are then used to build retrieval-ready chunks with preserved metadata.

- for the current submission, default assumptions are:
  - `project_id = east-metro`
  - `package_id = v3`

### Document categories

PDF uploads are handled as two business document types:

- `project_description`
- `progress_update` -- required reporting_date field

### Why require reporting period at upload
1. Progress reports are time-sensitive documents. If reporting date metadata is wrong or inferred incorrectly, retrieval quality and downstream reasoning will be unreliable.
2. From an operational/admin perspective, uploading a monthly or progress report together with its reporting period is a natural and valid workflow.




### 1.1 Documents Chunking Method

For PDF documents, the ingestion objective is to preserve business context and structure. These documents usually contain descriptive sections, milestone tables, package details, and narrative explanations.

The chunking strategy is **structure-aware** rather than character-prefix-based. Chunks are formed around meaningful document boundaries such as:

- sections
- paragraphs
- tables

For each chunk, the system stores relevant metadata such as:

- source document
- document type
- heading path
- page span
- title
- project context
- extracted entities where applicable

This makes retrieval more reliable because the answer layer can trace evidence back to a specific section or table instead of relying on arbitrary text windows.

---

## 2. Why This PDF Method Was Chosen

### 2.1 Why not simple prefix or fixed-length chunking

A traditional prefix-based or fixed-character chunking approach is not reliable enough for this document set.

Main reasons:

1. Long paragraphs may be split at arbitrary positions, which damages coherence and weakens retrieval quality.
2. Tables are important in these PDFs, and naive chunking does not preserve row-column meaning well.
3. Questions in this domain often depend on section boundaries, milestone tables, and reporting context, so structural preservation matters more than raw text extraction simplicity.

### 2.2 Why not use VLM by default

A VLM-based ingestion path is not the choice for this submission.

Reasons:

1. The current PDFs are mostly born-digital and contain a lot of text and tables that can still be converted into structured outputs without a VLM-first pipeline.
2. Adding VLMs into the default ingestion path increases system complexity and operational cost without a clear immediate benefit for the current dataset.
3. If future PDFs contain more scanned pages, diagrams, or image-heavy content, then a VLM + OCR path can be introduced as an extension.

### Final PDF decision

The selected default is:

- `Docling` for parsing
- structure-aware chunking for retrieval preparation
- explicit upload metadata for business-critical fields such as reporting period

This gives a better balance of structure preservation, retrieval quality, and implementation clarity for the current project scope.

---

## 3. CSV / Spreadsheet Ingestion Decision

### Chosen approach

For `CSV` and `XLSX` files, the system uses a file-based ingestion approach rather than inserting every spreadsheet into relational tables.

Uploaded tabular files are normalized into analysis-ready artifacts, mainly:

- parquet datasets
- tabular profile metadata
- column/type summaries
- sample rows for inspection
- repair reports when malformed CSV rows need correction

### Why file-based instead of database table ingestion

This is a flexibility decision.

Reasons:

1. Spreadsheet schemas can vary significantly across files and over time.
2. If every new spreadsheet shape required a database schema change, ingestion would become brittle and expensive to maintain.
3. A file-based approach allows the system to support new table formats without repeated backend schema redesign.
4. Parquet is a good fit for structured analytical data because it is efficient, portable, and easy to query programmatically.

### How these artifacts are intended to be used

The purpose of tabular ingestion is not vector retrieval first. Instead:

- the system extracts schema and sample context for the LLM
- the LLM or analysis layer can inspect headers and dataset structure
- when deeper answers are needed, code can query the parquet data directly

This preserves the analytical nature of structured data.

### Why not store spreadsheet data in vector form

The current decision is to avoid using vector search as the primary retrieval mechanism for structured tabular data.

Reasons:

1. These files are inherently structured and analytical.
2. Converting them into vector chunks risks losing filtering, aggregation, and computation ability.
3. For tabular questions, code-based querying over parquet is more faithful than semantic retrieval over flattened text.
4. Vectorization may still be useful later for metadata discovery or hybrid routing, but it should not replace analytical access to the table itself.

NOTES (AFTER COMPLETING THE AGENT DEVELOPMENT, My Small conclusion on this mistake):
1. after completing the whole process, I have changed my mind.
2. I would like to try store the spreadsheet data into vector form and current data analysis approach
3. Reason: 
3.1: we could not make the assumption everyone using csv to store meaningful analytics data, some of them mix and use csv for documentation purpose, therefore loading the row into vector does enhance the reliability of the system.
3.2: We could not make the assumption risk must use csv while progress only can use pdf, as real world situation this is depend on the admin/operation team but not us developer, so what we need to do is ensure the retrieving quality only.

### Final CSV / spreadsheet decision

The selected default is:

- file-backed storage
- parquet as the normalized format
- tabular profile generation for schema awareness
- direct analytical access rather than vector-first retrieval

---

## 4. Storage Decision

### Chosen approach

The system uses:

- `PostgreSQL` for application metadata
- `pgvector` for vector similarity search over retrieval chunks

### Why PostgreSQL + pgvector

For the current phase of the project, `PostgreSQL + pgvector` is sufficient.

Reasons:

1. It keeps metadata and vector search in the same system, which simplifies development and operations.
2. The expected data volume for the take-home scope does not justify introducing a second dedicated vector database.
3. This approach is easier to explain, maintain, and deploy in an early-stage system.

### Why not Qdrant or Pinecone for now

Dedicated vector databases may provide better performance or operational features at larger scale, but they are not the default choice here.

Reasons:

1. The current project phase does not yet require that level of specialization.
2. Adding a separate vector database increases infrastructure complexity.
3. For the current use case, `PostgreSQL + pgvector` provides a simpler and more than sufficient baseline.

### Final storage decision

The selected default is:

- `PostgreSQL + pgvector`

This is the most practical choice for the current scope, complexity, and expected workload.

---

## Final Summary for ingestion

The ingestion and preparation strategy is based on one core principle:

- preserve structure where structure matters
- preserve analytical capability where data is structured
- attach business metadata early when it is critical for correctness

Therefore:

- `PDF` documents are parsed with `Docling` and chunked in a structure-aware way for retrieval
- `progress_update` documents require explicit reporting-period metadata at upload time
- `CSV/XLSX` files are normalized into parquet for analysis instead of being forced into relational tables or vector chunks
- `PostgreSQL + pgvector` is used as the simplest practical storage and retrieval foundation for the current project phase

## 5. Agent designing

For agent design, I am referencing codex/claude code while maintaining the current requirement to avoid overengineering. 

For data agent, my main idea is we provide the context of the current db and the tools for llm to perform the query search on the current db, this approach ensure scalability on the db become larger. 
The flow:

`check current dataset(list dataset and describe dataset)`  --> `Identify which dataset to perform query` --> `use query dataset tools` --> `allow rerun the query to search the best answer` --> `complete the step or continue the looping`


Also, I might introduce skill if the table become more and more, this approach allow reduce the noise in the context while maintaining the performance and retrieving quality.

For document agent, my main idea here is let the agent get the correct answer by providing the tools and context as well. The main capability of the agent in my plan is 

`agent perform rephrase`  --> `agent search using keyword/sentence` --> `identify the gap` --> `check if still needed to search` --> `complete the step or continue the looping`

To make the current implementation lightweighting, I concatenate the agent into this current one agent.

The reason I am not employing the reranking approach
1. based on my own experience, most of the time, the retrieval not good is because of the query, reranking might not be solving the problem as reranking idea is 

`query/rephrase query`  --> `search top k =50 based on query` --> `reranking` --> `final answer`

If the root cause is the query, this method might still not provide the accurate answer.

For overall agent design, I get the idea from multi-agent concept.
The sub agent will have its own workspace to workaround, and only provide the final output to the reporter, to ensure the context is clean and manageable prompt length. This approach allow the subagent to try and error on the finding.
