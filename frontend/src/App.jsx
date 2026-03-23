import { Fragment, useEffect, useRef, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const DEFAULT_ROUTE = "docs";
const buildApiUrl = (path) => new URL(path, API_BASE_URL).toString();

const getRouteFromPath = (pathname) => {
  if (pathname === "/chat") return "chat";
  if (pathname === "/docs" || pathname === "/") return "docs";
  return DEFAULT_ROUTE;
};

const getPathFromRoute = (route) => (route === "chat" ? "/chat" : "/docs");

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

const formatEventLabel = (eventType) =>
  eventType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

const renderInlineMarkdown = (text, keyPrefix) => {
  const inlineMarkdownPattern =
    /(`([^`]+)`)|(\[([^\]]+)\]\((https?:\/\/[^\s)]+)\))|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)/g;
  const nodes = [];
  let lastIndex = 0;
  let match;

  while ((match = inlineMarkdownPattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const nodeKey = `${keyPrefix}-${match.index}`;

    if (match[2]) {
      nodes.push(
        <code key={nodeKey} className="markdown-inline-code">
          {match[2]}
        </code>
      );
    } else if (match[4] && match[5]) {
      nodes.push(
        <a
          key={nodeKey}
          className="markdown-link"
          href={match[5]}
          target="_blank"
          rel="noreferrer"
        >
          {match[4]}
        </a>
      );
    } else if (match[7]) {
      nodes.push(
        <strong key={nodeKey} className="markdown-strong">
          {renderInlineMarkdown(match[7], `${nodeKey}-strong`)}
        </strong>
      );
    } else if (match[9]) {
      nodes.push(
        <em key={nodeKey} className="markdown-emphasis">
          {renderInlineMarkdown(match[9], `${nodeKey}-emphasis`)}
        </em>
      );
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
};

const renderInlineMarkdownWithBreaks = (text, keyPrefix) =>
  text.split("\n").flatMap((line, index, lines) => {
    const lineKey = `${keyPrefix}-line-${index}`;
    const content = renderInlineMarkdown(line, lineKey);

    if (index === lines.length - 1) {
      return content;
    }

    return [
      <Fragment key={lineKey}>
        {content}
        <br />
      </Fragment>,
    ];
  });

const parseMarkdownBlocks = (content) => {
  const lines = content.split("\n");
  const blocks = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim();
      const codeLines = [];
      index += 1;

      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }

      if (index < lines.length) {
        index += 1;
      }

      blocks.push({ type: "code", language, content: codeLines.join("\n") });
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        level: headingMatch[1].length,
        content: headingMatch[2],
      });
      index += 1;
      continue;
    }

    if (/^[-*+]\s+/.test(trimmed)) {
      const items = [];

      while (index < lines.length && /^[-*+]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*+]\s+/, ""));
        index += 1;
      }

      blocks.push({ type: "unordered-list", items });
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items = [];

      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ""));
        index += 1;
      }

      blocks.push({ type: "ordered-list", items });
      continue;
    }

    if (/^>\s?/.test(trimmed)) {
      const quoteLines = [];

      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }

      blocks.push({ type: "blockquote", content: quoteLines.join("\n") });
      continue;
    }

    const paragraphLines = [];

    while (index < lines.length) {
      const current = lines[index];
      const currentTrimmed = current.trim();

      if (
        !currentTrimmed ||
        currentTrimmed.startsWith("```") ||
        /^(#{1,6})\s+/.test(currentTrimmed) ||
        /^[-*+]\s+/.test(currentTrimmed) ||
        /^\d+\.\s+/.test(currentTrimmed) ||
        /^>\s?/.test(currentTrimmed)
      ) {
        break;
      }

      paragraphLines.push(current);
      index += 1;
    }

    blocks.push({ type: "paragraph", content: paragraphLines.join("\n") });
  }

  return blocks;
};

function MarkdownPreview({ content }) {
  const blocks = parseMarkdownBlocks(content);

  return (
    <div className="markdown-preview">
      {blocks.map((block, index) => {
        const blockKey = `markdown-block-${index}`;

        if (block.type === "heading") {
          const HeadingTag = `h${block.level}`;
          return (
            <HeadingTag key={blockKey} className="markdown-heading">
              {renderInlineMarkdown(block.content, `${blockKey}-heading`)}
            </HeadingTag>
          );
        }

        if (block.type === "code") {
          return (
            <pre key={blockKey} className="markdown-code-block">
              <code>{block.content}</code>
            </pre>
          );
        }

        if (block.type === "unordered-list") {
          return (
            <ul key={blockKey} className="markdown-list">
              {block.items.map((item, itemIndex) => (
                <li key={`${blockKey}-item-${itemIndex}`}>
                  {renderInlineMarkdownWithBreaks(item, `${blockKey}-item-${itemIndex}`)}
                </li>
              ))}
            </ul>
          );
        }

        if (block.type === "ordered-list") {
          return (
            <ol key={blockKey} className="markdown-list markdown-list-ordered">
              {block.items.map((item, itemIndex) => (
                <li key={`${blockKey}-item-${itemIndex}`}>
                  {renderInlineMarkdownWithBreaks(item, `${blockKey}-item-${itemIndex}`)}
                </li>
              ))}
            </ol>
          );
        }

        if (block.type === "blockquote") {
          return (
            <blockquote key={blockKey} className="markdown-blockquote">
              {renderInlineMarkdownWithBreaks(block.content, `${blockKey}-quote`)}
            </blockquote>
          );
        }

        return (
          <p key={blockKey} className="markdown-paragraph">
            {renderInlineMarkdownWithBreaks(block.content, `${blockKey}-paragraph`)}
          </p>
        );
      })}
    </div>
  );
}

const EVENT_CONTENT = {
  run_started: {
    title: "Run started",
    description: "Your question was received and a new analysis run was created.",
  },
  route_selected: {
    title: "Route selected",
    description: "The router chose the best evidence path for this question.",
  },
  document_agent_started: {
    title: "Checking documents",
    description: "Searching the embedded project reports and briefs for relevant evidence.",
  },
  document_findings: {
    title: "Document evidence ready",
    description: "The document retriever returned cited report and brief evidence.",
  },
  data_agent_started: {
    title: "Checking datasets",
    description: "Inspecting structured datasets and preparing bounded analysis queries.",
  },
  data_findings: {
    title: "Data evidence ready",
    description: "The data analyst returned cited evidence from the structured artifacts.",
  },
  direct_response_started: {
    title: "Answering directly",
    description: "Using the current conversation context without starting retrieval or data analysis.",
  },
  clarify_started: {
    title: "Asking for clarification",
    description: "The request needs one more detail before a grounded answer can continue.",
  },
  reporter_started: {
    title: "Drafting response",
    description: "Synthesizing all findings into a grounded answer.",
  },
  answer_streaming: {
    title: "Streaming answer",
    description: "The assistant is now sending the final response.",
  },
  completed: {
    title: "Answer ready",
    description: "The run completed and the response is ready to read.",
  },
  error: {
    title: "Run failed",
    description: "Something interrupted the run before the answer was completed.",
  },
};

const getTimelineEntries = (events) => {
  const entries = [];
  let sawAnswerStream = false;

  events.forEach((entry) => {
    if (entry.type === "answer_chunk") {
      if (!sawAnswerStream) {
        entries.push({
          id: "answer-streaming",
          type: "answer_streaming",
          payload: entry.payload,
        });
        sawAnswerStream = true;
      }
      return;
    }

    entries.push(entry);
  });

  return entries;
};

const getCurrentStep = (timelineEntries, status) => {
  if (!timelineEntries.length) {
    return {
      title: "Waiting to start",
      description: "Submit a question to begin a new run.",
    };
  }

  if (status === "failed") {
    return EVENT_CONTENT.error;
  }

  if (status === "completed") {
    return EVENT_CONTENT.completed;
  }

  const latest = timelineEntries[timelineEntries.length - 1];
  return EVENT_CONTENT[latest.type] || { title: formatEventLabel(latest.type), description: "" };
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
  const [screen, setScreen] = useState(() => getRouteFromPath(window.location.pathname));
  const [documents, setDocuments] = useState([]);
  const [apiHealthy, setApiHealthy] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [chunkOpen, setChunkOpen] = useState(false);
  const [dataOpen, setDataOpen] = useState(false);
  const [fileOpen, setFileOpen] = useState(false);
  const [activeDocument, setActiveDocument] = useState(null);
  const [activeChunks, setActiveChunks] = useState([]);
  const [activeTabularProfile, setActiveTabularProfile] = useState(null);
  const [activeFileView, setActiveFileView] = useState(null);
  const [activeFileSheet, setActiveFileSheet] = useState("");
  const [fileViewerLoading, setFileViewerLoading] = useState(false);
  const [fileViewerError, setFileViewerError] = useState("");
  const [feedback, setFeedback] = useState("No upload in progress.");
  const [feedbackError, setFeedbackError] = useState(false);
  const [chatQuestion, setChatQuestion] = useState("");
  const [currentThreadId, setCurrentThreadId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatRun, setChatRun] = useState(null);
  const [chatEvents, setChatEvents] = useState([]);
  const [chatError, setChatError] = useState("");
  const [formState, setFormState] = useState({
    file: null,
    document_type: "project_description",
    reporting_period: "",
  });
  const eventSourceRef = useRef(null);
  const completionCheckTimeoutRef = useRef(null);

  useEffect(() => {
    void checkHealth();
    void loadDocuments();
  }, []);

  useEffect(() => {
    const normalizedRoute = getRouteFromPath(window.location.pathname);
    const normalizedPath = getPathFromRoute(normalizedRoute);

    if (window.location.pathname !== normalizedPath) {
      window.history.replaceState({}, "", normalizedPath);
    }

    setScreen(normalizedRoute);

    const handlePopState = () => {
      setScreen(getRouteFromPath(window.location.pathname));
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(
    () => () => {
      eventSourceRef.current?.close();
      if (completionCheckTimeoutRef.current) {
        window.clearTimeout(completionCheckTimeoutRef.current);
      }
    },
    []
  );

  const clearCompletionCheck = () => {
    if (completionCheckTimeoutRef.current) {
      window.clearTimeout(completionCheckTimeoutRef.current);
      completionCheckTimeoutRef.current = null;
    }
  };

  const reconcileRunState = async (threadId, assistantMessageId) => {
    if (!threadId || !assistantMessageId) {
      return false;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/chat/threads/${threadId}`);
      if (!response.ok) {
        return false;
      }

      const thread = await response.json();
      const assistantMessage = thread.messages?.find((message) => message.id === assistantMessageId);
      if (!assistantMessage || !["completed", "failed"].includes(assistantMessage.status)) {
        return false;
      }

      setChatRun((current) =>
        current
          ? {
              ...current,
              status: assistantMessage.status,
            }
          : current
      );
      setChatMessages((current) =>
        current.map((message) =>
          message.id === assistantMessageId
            ? {
                ...message,
                content: assistantMessage.content || message.content,
                status: assistantMessage.status,
              }
            : message
        )
      );

      if (assistantMessage.status === "failed") {
        setChatError(assistantMessage.content || "Chat run failed.");
      }

      eventSourceRef.current?.close();
      eventSourceRef.current = null;
      clearCompletionCheck();
      return true;
    } catch {
      return false;
    }
  };

  const scheduleCompletionCheck = (threadId, assistantMessageId) => {
    clearCompletionCheck();
    completionCheckTimeoutRef.current = window.setTimeout(() => {
      void reconcileRunState(threadId, assistantMessageId);
    }, 1500);
  };

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

  const openFileViewer = async (documentRecord) => {
    setActiveDocument(documentRecord);
    setActiveFileView(null);
    setActiveFileSheet("");
    setFileViewerError("");
    setFileViewerLoading(true);
    setFileOpen(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/documents/${documentRecord.id}/viewer`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to load file viewer.");
      }

      setActiveFileView(payload);
      if (payload.viewer_type === "tabular" && payload.sheets?.length) {
        setActiveFileSheet(payload.sheets[0].sheet_name);
      }
    } catch (error) {
      setFileViewerError(error.message || "Failed to load file viewer.");
    } finally {
      setFileViewerLoading(false);
    }
  };

  const closeFileViewer = () => {
    setFileOpen(false);
    setActiveFileView(null);
    setActiveFileSheet("");
    setFileViewerError("");
    setFileViewerLoading(false);
  };

  const handleChatSubmit = async (event) => {
    event.preventDefault();
    const question = chatQuestion.trim();
    if (!question) {
      setChatError("Enter a question to start a chat run.");
      return;
    }

    eventSourceRef.current?.close();
    clearCompletionCheck();
    setChatError("");
    setChatEvents([]);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/chat/runs`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question, thread_id: currentThreadId }),
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "Failed to start chat run.");
      }

      setCurrentThreadId(payload.thread_id);
      setChatRun(payload);
      setChatQuestion("");
      setChatMessages((current) => [
        ...current,
        {
          id: payload.user_message_id,
          role: "user",
          content: question,
          status: "completed",
        },
        {
          id: payload.assistant_message_id,
          role: "assistant",
          content: "",
          status: "pending",
        },
      ]);

      const source = new EventSource(`${API_BASE_URL}/api/v1/chat/runs/${payload.run_id}/events`);
      eventSourceRef.current = source;

      const appendEvent = (eventType, rawEvent) => {
        const eventPayload = JSON.parse(rawEvent.data);
        setChatEvents((current) => [
          ...current,
          {
            id: `${eventType}-${eventPayload.event_id}`,
            type: eventType,
            payload: eventPayload,
          },
        ]);

        if (eventType === "run_started") {
          setChatRun((current) => (current ? { ...current, status: eventPayload.status } : current));
          setChatMessages((current) =>
            current.map((message) =>
              message.id === payload.assistant_message_id
                ? { ...message, status: eventPayload.status }
                : message
            )
          );
        }

        if (eventType === "route_selected") {
          setChatRun((current) => (current ? { ...current, route: eventPayload.route } : current));
        }

        if (eventType === "answer_chunk") {
          setChatMessages((current) =>
            current.map((message) =>
              message.id === payload.assistant_message_id
                ? { ...message, content: `${message.content}${eventPayload.delta || ""}`, status: "streaming" }
                : message
            )
          );
          scheduleCompletionCheck(payload.thread_id, payload.assistant_message_id);
        }

        if (eventType === "completed") {
          clearCompletionCheck();
          setChatRun((current) => (current ? { ...current, status: eventPayload.status } : current));
          setChatMessages((current) =>
            current.map((message) =>
              message.id === payload.assistant_message_id
                ? { ...message, content: eventPayload.final_answer || message.content, status: "completed" }
                : message
            )
          );
          source.close();
          eventSourceRef.current = null;
        }

        if (eventType === "error") {
          clearCompletionCheck();
          setChatRun((current) => (current ? { ...current, status: eventPayload.status } : current));
          setChatError(eventPayload.detail || "Chat run failed.");
          setChatMessages((current) =>
            current.map((message) =>
              message.id === payload.assistant_message_id
                ? { ...message, content: eventPayload.detail || "Chat run failed.", status: "failed" }
                : message
            )
          );
          source.close();
          eventSourceRef.current = null;
        }
      };

      [
        "run_started",
        "route_selected",
        "document_agent_started",
        "document_findings",
        "data_agent_started",
        "data_findings",
        "direct_response_started",
        "clarify_started",
        "reporter_started",
        "answer_chunk",
        "completed",
        "error",
      ].forEach((eventType) => {
        source.addEventListener(eventType, (rawEvent) => appendEvent(eventType, rawEvent));
      });

      source.onerror = () => {
        void reconcileRunState(payload.thread_id, payload.assistant_message_id);
        if (source.readyState === EventSource.CLOSED) {
          eventSourceRef.current = null;
        }
      };
    } catch (error) {
      setChatError(error.message || "Failed to start chat run.");
    }
  };

  const handleChatKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  const navigateTo = (route) => {
    const nextPath = getPathFromRoute(route);
    if (window.location.pathname !== nextPath) {
      window.history.pushState({}, "", nextPath);
    }
    setScreen(route);
  };

  const handleNewChat = () => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    clearCompletionCheck();
    setCurrentThreadId(null);
    setChatMessages([]);
    setChatRun(null);
    setChatEvents([]);
    setChatError("");
    setChatQuestion("");
  };

  const timelineEntries = getTimelineEntries(chatEvents);
  const currentStep = getCurrentStep(timelineEntries, chatRun?.status);
  const chatIsRunning = Boolean(chatRun && !["completed", "failed"].includes(chatRun.status));
  const currentFileSheet =
    activeFileView?.sheets?.find((sheet) => sheet.sheet_name === activeFileSheet) ||
    activeFileView?.sheets?.[0] ||
    null;

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
            className={`nav-link ${screen === "docs" ? "active" : ""}`}
            onClick={() => navigateTo("docs")}
          >
            Data Ingestion
          </button>
          <button
            className={`nav-link ${screen === "chat" ? "active" : ""}`}
            onClick={() => navigateTo("chat")}
          >
            Chat With Docs
          </button>
        </nav>
      </aside>

      <main className="content">
        {screen === "docs" ? (
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
                            <div className="action-stack">
                              <button className="secondary-btn" onClick={() => openFileViewer(document)}>
                                View File
                              </button>
                              {document.extension === ".pdf" ? (
                                <button className="secondary-btn" onClick={() => openChunkPreview(document)}>
                                  Preview Chunks
                                </button>
                              ) : (
                                <button className="secondary-btn" onClick={() => openDataPreview(document)}>
                                  Preview Data
                                </button>
                              )}
                            </div>
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
          <>
            <header className="screen-header">
              <div>
                <span className="eyebrow">Conversation View</span>
                <h2>Chat With Docs</h2>
                <p>Ask a question, follow the current processing step, and expand the runtime timeline only when you need it.</p>
              </div>

              <div className="header-actions">
                <div className="status-chip">{chatRun?.status || "idle"}</div>
                <div className="status-chip">{chatRun?.route || "route pending"}</div>
                <button className="secondary-btn" onClick={handleNewChat}>
                  New Chat
                </button>
              </div>
            </header>

            <section className="panel chat-room-panel">
              <div className="chat-room-header">
                <div>
                  <h3>Project Intelligence Assistant</h3>
                </div>
              </div>

              <div className="chat-thread">
                {!chatMessages.length ? (
                  <div className="chat-empty-state">
                    <span className="eyebrow">Ready</span>
                    <h3>Start a conversation</h3>
                    <p>Ask about Package V3 progress, milestones, risks, or commercial signals to begin a run.</p>
                  </div>
                ) : (
                  chatMessages.map((message) => {
                    const isUser = message.role === "user";
                    const isActiveAssistantMessage = message.id === chatRun?.assistant_message_id;

                    return (
                      <article
                        className={`message-row ${isUser ? "message-row-user" : "message-row-bot"}`}
                        key={message.id}
                      >
                        {!isUser ? <div className="assistant-avatar">AI</div> : null}
                        <div className="message-stack">
                          <div
                            className={`message-bubble ${
                              isUser ? "message-bubble-user" : "message-bubble-bot"
                            }`}
                          >
                            <div className="message-label">
                              {isUser ? "You" : "Project Intelligence Assistant"}
                            </div>

                            {message.content ? (
                              <div
                                className={`message-body ${
                                  isUser ? "message-body-user" : "assistant-answer"
                                }`}
                              >
                                {isUser ? (
                                  message.content
                                ) : (
                                  <MarkdownPreview content={message.content} />
                                )}
                              </div>
                            ) : !isUser && isActiveAssistantMessage && !chatError ? (
                              <div className="runtime-status-card">
                                <div className="runtime-status-head">
                                  <span className="loading-indicator" aria-hidden="true" />
                                  <div>
                                    <strong>{currentStep.title}</strong>
                                    <div className="subtle-text">{currentStep.description}</div>
                                  </div>
                                </div>
                              </div>
                            ) : null}
                          </div>

                          {!isUser && isActiveAssistantMessage && timelineEntries.length ? (
                            <details className="timeline-details">
                              <summary>
                                <span>Runtime timeline</span>
                                <span className="subtle-text">{timelineEntries.length} step(s)</span>
                              </summary>

                              <div className="timeline-list">
                                {timelineEntries.map((entry) => {
                                  const content =
                                    EVENT_CONTENT[entry.type] || {
                                      title: formatEventLabel(entry.type),
                                      description: "",
                                    };

                                  return (
                                    <article className="timeline-item" key={entry.id}>
                                      <div className="timeline-marker" aria-hidden="true" />
                                      <div className="timeline-copy">
                                        <div className="timeline-title-row">
                                          <strong>{content.title}</strong>
                                          <span className="subtle-text">
                                            {entry.payload.timestamp
                                              ? formatDate(entry.payload.timestamp)
                                              : "No timestamp"}
                                          </span>
                                        </div>
                                        <div className="subtle-text">{content.description}</div>

                                        {entry.payload.route ? (
                                          <div className="meta-pill-wrap">
                                            <span className="meta-pill">route: {entry.payload.route}</span>
                                          </div>
                                        ) : null}

                                        {entry.payload.findings?.length ? (
                                          <div className="timeline-findings">
                                            {entry.payload.findings.map((finding, index) => (
                                              <div className="timeline-finding" key={`${entry.id}-finding-${index}`}>
                                                <strong>{finding.claim}</strong>
                                                <ul className="event-evidence-list">
                                                  {finding.evidence?.map((evidence, evidenceIndex) => (
                                                    <li key={`${entry.id}-evidence-${evidenceIndex}`}>
                                                      <span>{evidence.source}</span>
                                                      <span className="subtle-text">
                                                        {evidence.citation} · {evidence.snippet}
                                                      </span>
                                                    </li>
                                                  ))}
                                                </ul>
                                              </div>
                                            ))}
                                          </div>
                                        ) : null}

                                        {entry.payload.detail ? (
                                          <div className="subtle-text">{entry.payload.detail}</div>
                                        ) : null}
                                      </div>
                                    </article>
                                  );
                                })}
                              </div>
                            </details>
                          ) : null}
                        </div>
                      </article>
                    );
                  })
                )}
              </div>

              <form className="chat-composer" onSubmit={handleChatSubmit}>
                <label className="chat-composer-field">
                  <span>Question</span>
                  <textarea
                    value={chatQuestion}
                    onChange={(event) => setChatQuestion(event.target.value)}
                    onKeyDown={handleChatKeyDown}
                    placeholder="Ask about Package V3 progress, risks, milestones, or commercial signals..."
                    rows={3}
                    disabled={chatIsRunning}
                  />
                </label>

                <div className="chat-composer-footer">
                  <div className={`feedback ${chatError ? "error" : ""}`}>
                    {chatError ||
                      (chatIsRunning
                        ? "A run is in progress. The latest step is shown inside the assistant reply."
                        : currentThreadId
                          ? "Continue the current conversation, or start over with New Chat."
                          : "Your message will appear on the right, and the assistant answer will appear on the left.")}
                  </div>
                  <button type="submit" className="primary-btn" disabled={chatIsRunning}>
                    {chatIsRunning ? "Working..." : "Send Question"}
                  </button>
                </div>
              </form>
            </section>
          </>
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
        open={fileOpen}
        onClose={closeFileViewer}
        title={activeDocument?.original_filename || "View File"}
        subtitle="Original File"
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
                <strong>Format</strong>
                <div>{activeDocument.extension || "n/a"}</div>
              </div>
              <div className="meta-card">
                <strong>Size</strong>
                <div>{formatFileSize(activeDocument.file_size)}</div>
              </div>
              <div className="meta-card">
                <strong>Status</strong>
                <div>{activeDocument.latest_ingestion_status || "pending"}</div>
              </div>
            </div>

            {fileViewerLoading ? (
              <div className="note-box">Loading the full file view...</div>
            ) : fileViewerError ? (
              <div className="note-box">{fileViewerError}</div>
            ) : activeFileView?.viewer_type === "pdf" && activeFileView.file_url ? (
              <div className="file-viewer-shell">
                <div className="file-viewer-toolbar">
                  <a
                    className="secondary-btn file-open-link"
                    href={buildApiUrl(activeFileView.file_url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open In New Tab
                  </a>
                </div>
                <iframe
                  className="file-viewer-frame"
                  src={buildApiUrl(activeFileView.file_url)}
                  title={activeDocument.original_filename}
                />
              </div>
            ) : currentFileSheet ? (
              <div className="file-viewer-shell">
                {activeFileView.sheets.length > 1 ? (
                  <div className="sheet-tab-row">
                    {activeFileView.sheets.map((sheet) => (
                      <button
                        key={sheet.sheet_name}
                        className={`sheet-tab ${sheet.sheet_name === currentFileSheet.sheet_name ? "active" : ""}`}
                        onClick={() => setActiveFileSheet(sheet.sheet_name)}
                        type="button"
                      >
                        {sheet.sheet_name}
                      </button>
                    ))}
                  </div>
                ) : null}

                <article className="chunk-card">
                  <div className="chunk-card-header">
                    <div>
                      <strong>{currentFileSheet.sheet_name}</strong>
                      <div className="subtle-text">
                        {currentFileSheet.row_count} row(s) · {currentFileSheet.columns.length} column(s)
                      </div>
                    </div>
                    <span className="meta-pill">full file</span>
                  </div>

                  <div className="table-wrap file-table-wrap">
                    <table className="sample-table viewer-table">
                      <thead>
                        <tr>
                          {currentFileSheet.columns.map((column) => (
                            <th key={`${currentFileSheet.sheet_name}-column-${column}`}>{column}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {currentFileSheet.rows.length ? (
                          currentFileSheet.rows.map((row, rowIndex) => (
                            <tr key={`${currentFileSheet.sheet_name}-row-${rowIndex}`}>
                              {currentFileSheet.columns.map((column) => (
                                <td key={`${currentFileSheet.sheet_name}-row-${rowIndex}-${column}`}>
                                  {row[column] ?? "null"}
                                </td>
                              ))}
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={currentFileSheet.columns.length || 1}>No rows available.</td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </article>
              </div>
            ) : (
              <div className="note-box">This file does not have a direct viewer yet.</div>
            )}
          </>
        ) : null}
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
