# Decision: Data Preparation And Ingestion Logic

## Overview

The current submission focuses on building a reliable data preparation and ingestion layer for project documents. The goal is to transform uploaded files into retrieval-ready and analysis-ready artifacts while preserving traceability, structure, and business context.

The ingestion strategy is split by document type:

- `PDF` documents are treated as unstructured or semi-structured project knowledge and prepared for retrieval.
- `CSV` / `XLSX` documents are treated as structured analytical data and prepared for code-based querying and analysis.

This separation is intentional because narrative documents and tabular datasets have different retrieval and reasoning needs.

---

## 1. PDF Ingestion Decision

### Chosen approach

PDF documents are parsed using `Docling`, which converts the source PDF into structured outputs such as Markdown and document JSON. These outputs are then used to build retrieval-ready chunks with preserved metadata.

### Document categories

PDF uploads are handled as two business document types:

- `project_description`
- `progress_update`

### 1.1 Project Description Documents

For `project_description` documents, the ingestion objective is to preserve business context and structure. These documents usually contain descriptive sections, milestone tables, package details, and narrative explanations.

The chunking strategy is structure-aware rather than character-prefix-based. Chunks are formed around meaningful document boundaries such as:

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

### 1.2 Progress Update Documents

For `progress_update` documents, time is a critical business dimension. Because of that, the system requires the user to provide the reporting period during upload.

Current assumptions:

- `reporting_period` is mandatory for `progress_update`
- the format is normalized as `YYYY-MM`
- optional project-specific fields such as `project_id` and `package_id` can be supported
- for the current submission, default assumptions are:
  - `project_id = east-metro`
  - `package_id = v3`

### Why require reporting period at upload

This is a deliberate business-level decision.

Reasons:

1. Progress reports are time-sensitive documents. If reporting date metadata is wrong or inferred incorrectly, retrieval quality and downstream reasoning will be unreliable.
2. Requiring the reporting period during upload reduces ambiguity and avoids weak heuristics.
3. From an operational/admin perspective, uploading a monthly or progress report together with its reporting period is a natural and valid workflow.
4. This design makes cross-period comparison more dependable, which is important for milestone tracking, status reconciliation, and trend analysis.

---

## 2. Why This PDF Method Was Chosen

### 2.1 Why not simple prefix or fixed-length chunking

A traditional prefix-based or fixed-character chunking approach is not reliable enough for this document set.

Main reasons:

1. Long paragraphs may be split at arbitrary positions, which damages coherence and weakens retrieval quality.
2. Tables are important in these PDFs, and naive chunking does not preserve row-column meaning well.
3. Questions in this domain often depend on section boundaries, milestone tables, and reporting context, so structural preservation matters more than raw text extraction simplicity.

### 2.2 Why not use VLM by default

A VLM-based ingestion path is not the default choice for this submission.

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

## Final Summary

The ingestion and preparation strategy is based on one core principle:

- preserve structure where structure matters
- preserve analytical capability where data is structured
- attach business metadata early when it is critical for correctness

Therefore:

- `PDF` documents are parsed with `Docling` and chunked in a structure-aware way for retrieval
- `progress_update` documents require explicit reporting-period metadata at upload time
- `CSV/XLSX` files are normalized into parquet for analysis instead of being forced into relational tables or vector chunks
- `PostgreSQL + pgvector` is used as the simplest practical storage and retrieval foundation for the current project phase
