import { useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const formatDate = (value) =>
  new Date(value).toLocaleString("en-MY", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

const formatFileSize = (bytes) => {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(size >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
};

function Modal({ open, onClose, title, subtitle, children, wide = false }) {
  if (!open) return null;

  return (
    <div className="modal">
      <div className="modal-backdrop" onClick={onClose} />
      <div className={`modal-dialog ${wide ? "chunk-modal-dialog" : ""}`}>
        <div className="modal-header">
          <div>
            <span className="eyebrow">{subtitle}</span>
            <h3>{title}</h3>
          </div>
          <button className="icon-btn" onClick={onClose}>
            Close
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default function App() {
  const [screen, setScreen] = useState("ingestion");
  const [documents, setDocuments] = useState([]);
  const [apiHealthy, setApiHealthy] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [chunkOpen, setChunkOpen] = useState(false);
  const [dataOpen, setDataOpen] = useState(false);
  const [activeDocument, setActiveDocument] = useState(null);
  const [activeChunks, setActiveChunks] = useState([]);
  const [activeTabularProfile, setActiveTabularProfile] = useState(null);
  const [feedback, setFeedback] = useState("No upload in progress.");
  const [feedbackError, setFeedbackError] = useState(false);
  const [formState, setFormState] = useState({
    file: null,
    document_type: "project_description",
    reporting_period: "",
  });

  useEffect(() => {
    void checkHealth();
    void loadDocuments();
  }, []);

  const checkHealth = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/health`);
      setApiHealthy(response.ok);
    } catch {
      setApiHealthy(false);
    }
  };

  const loadDocuments = async () => {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/overview`);
    const payload = await response.json();
    setDocuments(payload);
  };

  const handleUpload = async (event) => {
    event.preventDefault();
    if (!formState.file) {
      setFeedbackError(true);
      setFeedback("Please choose a file.");
      return;
    }
    if (formState.document_type === "progress_update" && !formState.reporting_period) {
      setFeedbackError(true);
      setFeedback("Reporting period is required for progress_update.");
      return;
    }

    const formData = new FormData();
    formData.append("file", formState.file);
    formData.append("document_type", formState.document_type);
    if (formState.reporting_period) {
      formData.append("reporting_period", formState.reporting_period);
    }

    try {
      setFeedbackError(false);
      setFeedback("Uploading document and triggering ingestion...");
      const response = await fetch(`${API_BASE_URL}/api/v1/documents/upload`, {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Upload failed.");
      }

      setFeedback(
        `Accepted ${payload.document.original_filename}. Job ${payload.ingestion_job_id} is ${payload.ingestion_status}.`
      );
      setFormState({ file: null, document_type: "project_description", reporting_period: "" });
      setUploadOpen(false);
      await loadDocuments();
    } catch (error) {
      setFeedbackError(true);
      setFeedback(error.message || "Upload failed.");
    }
  };

  const openChunkPreview = async (documentRecord) => {
    const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentRecord.id}/chunks`);
    const chunks = await response.json();
    setActiveDocument(documentRecord);
    setActiveChunks(chunks);
    setChunkOpen(true);
  };

  const openDataPreview = async (documentRecord) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentRecord.id}/tabular-profile`);
      const profile = await response.json();
      if (!response.ok) {
        throw new Error(profile.detail || "Failed to load tabular profile.");
      }

      setActiveDocument(documentRecord);
      setActiveTabularProfile(profile);
      setDataOpen(true);
    } catch (error) {
      setFeedbackError(true);
      setFeedback(error.message || "Failed to load tabular profile.");
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-kicker">Gamuda</span>
          <h1>Document Workspace</h1>
          <p>Upload, inspect, and prepare project documents for retrieval.</p>
        </div>

        <nav className="nav">
          <button
            className={`nav-link ${screen === "ingestion" ? "active" : ""}`}
            onClick={() => setScreen("ingestion")}
          >
            Data Ingestion
          </button>
          <button
            className={`nav-link ${screen === "chat" ? "active" : ""}`}
            onClick={() => setScreen("chat")}
          >
            Chat With Docs
          </button>
        </nav>
      </aside>

      <main className="content">
        {screen === "ingestion" ? (
          <>
            <header className="screen-header">
              <div>
                <span className="eyebrow">Operational View</span>
                <h2>Data Ingestion</h2>
                <p>Inspect uploaded files, ingestion status, and chunked output in one place.</p>
              </div>

              <div className="header-actions">
                <div className="status-chip">{apiHealthy ? "API healthy" : "API unavailable"}</div>
                <button className="primary-btn header-btn" onClick={() => setUploadOpen(true)}>
                  Upload Data
                </button>
              </div>
            </header>

            <section className="panel info-banner">
              <strong>Default routing:</strong>
              <span>
                all uploaded files are currently stored under the <code>east-metro</code> project and
                <code>v3</code> package.
              </span>
            </section>

            <section className="panel table-panel">
              <div className="panel-header">
                <div>
                  <h3>Uploaded Files</h3>
                  <p>Review ingestion status and open full chunk previews from the action column.</p>
                </div>
              </div>

              <div className="table-wrap">
                <table className="documents-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Type</th>
                      <th>Reporting Period</th>
                      <th>Uploaded</th>
                      <th>Size</th>
                      <th>Status</th>
                      <th>Chunks</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.length ? (
                      documents.map((document) => (
                        <tr key={document.id}>
                          <td className="filename-cell">
                            <strong>{document.original_filename}</strong>
                            <div className="subtle-text">{document.extension}</div>
                          </td>
                          <td>{document.document_type || "n/a"}</td>
                          <td>{document.reporting_period || "n/a"}</td>
                          <td>{formatDate(document.created_at)}</td>
                          <td>{formatFileSize(document.file_size)}</td>
                          <td>
                            <span className={`status-pill ${document.latest_ingestion_status || "pending"}`}>
                              {document.latest_ingestion_status || "pending"}
                            </span>
                            {document.latest_ingestion_error ? (
                              <div className="subtle-text">{document.latest_ingestion_error}</div>
                            ) : null}
                          </td>
                          <td>{document.chunk_count}</td>
                          <td className="action-cell">
                            {document.extension === ".pdf" ? (
                              <button className="secondary-btn" onClick={() => openChunkPreview(document)}>
                                Preview Chunks
                              </button>
                            ) : (
                              <button className="secondary-btn" onClick={() => openDataPreview(document)}>
                                Preview Data
                              </button>
                            )}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="8">
                          <div className="subtle-text">
                            No uploaded files yet. Click Upload Data to start ingestion.
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        ) : (
          <section className="panel placeholder-panel">
            <span className="eyebrow">Next Step</span>
            <h3>Chat With Docs</h3>
            <p>This workspace will host retrieval and grounded responses over embedded chunks.</p>
          </section>
        )}
      </main>

      <Modal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title="Upload Data"
        subtitle="New Upload"
      >
        <form className="upload-form" onSubmit={handleUpload}>
          <label>
            <span>File</span>
            <input
              type="file"
              onChange={(event) =>
                setFormState((current) => ({ ...current, file: event.target.files?.[0] || null }))
              }
              required
            />
          </label>

          <label>
            <span>Document Type</span>
            <select
              value={formState.document_type}
              onChange={(event) =>
                setFormState((current) => ({ ...current, document_type: event.target.value }))
              }
            >
              <option value="project_description">project_description</option>
              <option value="progress_update">progress_update</option>
            </select>
          </label>

          <label>
            <span>Reporting Period</span>
            <input
              type="month"
              value={formState.reporting_period}
              onChange={(event) =>
                setFormState((current) => ({ ...current, reporting_period: event.target.value }))
              }
            />
          </label>

          <div className="note-box">
            The backend currently defaults all uploads to project <strong>east-metro</strong> and
            package <strong>v3</strong>.
          </div>

          <div className="modal-footer">
            <div className={`feedback ${feedbackError ? "error" : ""}`}>{feedback}</div>
            <button type="submit" className="primary-btn">
              Start Ingestion
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        open={chunkOpen}
        onClose={() => setChunkOpen(false)}
        title={activeDocument?.original_filename || "Document Chunks"}
        subtitle="Chunk Preview"
        wide
      >
        {activeDocument ? (
          <>
            <div className="modal-meta">
              <div className="meta-card">
                <strong>Type</strong>
                <div>{activeDocument.document_type || "n/a"}</div>
              </div>
              <div className="meta-card">
                <strong>Reporting Period</strong>
                <div>{activeDocument.reporting_period || "n/a"}</div>
              </div>
              <div className="meta-card">
                <strong>Ingestion Status</strong>
                <div>{activeDocument.latest_ingestion_status || "pending"}</div>
              </div>
              <div className="meta-card">
                <strong>Chunks</strong>
                <div>{activeDocument.chunk_count}</div>
              </div>
            </div>

            <div className="modal-list">
              {activeChunks.length ? (
                activeChunks.map((chunk) => (
                  <article className="chunk-card" key={chunk.id}>
                    <div className="chunk-card-header">
                      <div>
                        <strong>Chunk {chunk.chunk_index}</strong>
                        <div className="subtle-text">
                          {chunk.heading_path?.length ? chunk.heading_path.join(" / ") : "No heading"}
                        </div>
                      </div>
                      <span className="meta-pill">{chunk.chunk_kind}</span>
                    </div>
                    <div className="subtle-text">
                      Pages: {chunk.page_span?.join(", ") || "n/a"} · Embedding:{" "}
                      {chunk.embedding_model || "not embedded yet"}
                    </div>
                    <div className="meta-pill-wrap">
                      {chunk.contains_entities?.length ? (
                        chunk.contains_entities.map((entity) => (
                          <span className="meta-pill" key={entity}>
                            {entity}
                          </span>
                        ))
                      ) : (
                        <span className="meta-pill">No entities</span>
                      )}
                    </div>
                    <div className="chunk-card-body">{chunk.contextualized_text}</div>
                  </article>
                ))
              ) : (
                <div className="note-box">No chunks available for this document yet.</div>
              )}
            </div>
          </>
        ) : null}
      </Modal>

      <Modal
        open={dataOpen}
        onClose={() => setDataOpen(false)}
        title={activeDocument?.original_filename || "Tabular Preview"}
        subtitle="Data Preview"
        wide
      >
        {activeDocument && activeTabularProfile ? (
          <>
            {(() => {
              const datasets = Array.isArray(activeTabularProfile.datasets)
                ? activeTabularProfile.datasets
                : [];
              const repairSummary = activeTabularProfile.repair_summary || null;
              const repairLog = Array.isArray(activeTabularProfile.repair_log)
                ? activeTabularProfile.repair_log
                : [];

              return (
                <>
            <div className="modal-meta">
              <div className="meta-card">
                <strong>Type</strong>
                <div>{activeDocument.document_type || "n/a"}</div>
              </div>
              <div className="meta-card">
                <strong>Reporting Period</strong>
                <div>{activeDocument.reporting_period || "n/a"}</div>
              </div>
              <div className="meta-card">
                <strong>Datasets</strong>
                <div>{datasets.length}</div>
              </div>
              <div className="meta-card">
                <strong>Ingestion Status</strong>
                <div>{activeDocument.latest_ingestion_status || "pending"}</div>
              </div>
              <div className="meta-card">
                <strong>Repaired Rows</strong>
                <div>{repairSummary?.rows_repaired || 0}</div>
              </div>
            </div>

            <div className="modal-list">
              {repairSummary?.rows_repaired ? (
                <article className="chunk-card">
                  <div className="chunk-card-header">
                    <div>
                      <strong>CSV Repair Report</strong>
                      <div className="subtle-text">
                        Malformed rows were normalized during ingestion. Review the strategies below.
                      </div>
                    </div>
                    <span className="meta-pill">repair log</span>
                  </div>

                  <div className="meta-pill-wrap">
                    <span className="meta-pill">rows_repaired: {repairSummary.rows_repaired}</span>
                    <span className="meta-pill">rows_padded: {repairSummary.rows_padded}</span>
                    <span className="meta-pill">
                      merged_date: {repairSummary.rows_merged_into_date_column}
                    </span>
                    <span className="meta-pill">
                      merged_tail: {repairSummary.rows_merged_into_tail_column}
                    </span>
                    <span className="meta-pill">
                      tail_fallback: {repairSummary.rows_truncated_with_tail_merge}
                    </span>
                  </div>

                  <div className="table-wrap">
                    <table className="sample-table">
                      <thead>
                        <tr>
                          <th>Row</th>
                          <th>Issue</th>
                          <th>Strategy</th>
                          <th>Expected Columns</th>
                          <th>Actual Columns</th>
                        </tr>
                      </thead>
                      <tbody>
                        {repairLog.map((entry) => (
                          <tr key={`repair-row-${entry.row_number}`}>
                            <td>{entry.row_number}</td>
                            <td>{entry.issue}</td>
                            <td>{entry.strategy}</td>
                            <td>{entry.expected_columns}</td>
                            <td>{entry.actual_columns}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </article>
              ) : null}

              {datasets.length ? (
                datasets.map((dataset) => {
                  const columns = Array.isArray(dataset.columns) ? dataset.columns : [];
                  const sampleRows = Array.isArray(dataset.sample_rows) ? dataset.sample_rows : [];

                  return (
                <article className="chunk-card" key={dataset.dataset_name}>
                  <div className="chunk-card-header">
                    <div>
                      <strong>{dataset.dataset_name}</strong>
                      <div className="subtle-text">
                        {dataset.row_count} row(s) · {dataset.column_count} column(s)
                      </div>
                    </div>
                    <span className="meta-pill">dataset</span>
                  </div>

                  <div className="subtle-text">Parquet: {dataset.parquet_path}</div>

                  <div className="meta-pill-wrap">
                    {columns.map((column) => (
                      <span className="meta-pill" key={`${dataset.dataset_name}-${column.name}`}>
                        {column.name}: {column.dtype}
                      </span>
                    ))}
                  </div>

                  <div className="table-wrap">
                    <table className="sample-table">
                      <thead>
                        <tr>
                          {columns.map((column) => (
                            <th key={`${dataset.dataset_name}-head-${column.name}`}>{column.name}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sampleRows.length ? (
                          sampleRows.map((row, rowIndex) => (
                            <tr key={`${dataset.dataset_name}-row-${rowIndex}`}>
                              {columns.map((column) => (
                                <td key={`${dataset.dataset_name}-row-${rowIndex}-${column.name}`}>
                                  {row[column.name] ?? "null"}
                                </td>
                              ))}
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={columns.length || 1}>No sample rows available.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </article>
                  );
                })
              ) : (
                <div className="note-box">No tabular datasets available for this document yet.</div>
              )}
            </div>
                </>
              );
            })()}
          </>
        ) : null}
      </Modal>
    </div>
  );
}
