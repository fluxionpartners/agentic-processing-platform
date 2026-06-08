import React, { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AccountInfo,
  PublicClientApplication,
  type AuthenticationResult
} from "@azure/msal-browser";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  LockKeyhole,
  Loader2,
  Radio,
  ShieldCheck,
  Sparkles,
  Workflow,
  UploadCloud
} from "lucide-react";
import "./styles.css";

type IntakeResponse = {
  status?: string;
  blobUri?: string;
  messageId?: string;
  correlationId?: string;
  executionMode?: string;
  threadId?: string;
  runId?: string;
};

type PipelineResponse = {
  status?: string;
  recordFound?: boolean;
  checkpointStage?: string;
  extraction?: Record<string, unknown>;
  validation?: Record<string, unknown>;
  humanReview?: Record<string, unknown>;
  taxPlanning?: Record<string, unknown>;
  form1040Document?: Record<string, unknown>;
  compliance?: Record<string, unknown>;
  governance?: Record<string, unknown>;
  message?: string;
};

type UploadState = "idle" | "uploading" | "processing" | "success" | "error";
type ExecutionMode = "direct" | "foundry-agent";

const intakeApiUrl = import.meta.env.VITE_W2_INTAKE_API_URL as string | undefined;
const statusApiUrl = import.meta.env.VITE_W2_STATUS_API_URL as string | undefined;
const agentApiUrl = import.meta.env.VITE_W2_AGENT_API_URL as string | undefined;
const configuredExecutionMode = (import.meta.env.VITE_W2_EXECUTION_MODE ?? "direct") as string;
const authEnabled = import.meta.env.VITE_AUTH_ENABLED === "true";
const authTenantId = import.meta.env.VITE_AUTH_TENANT_ID as string | undefined;
const authClientId = import.meta.env.VITE_AUTH_CLIENT_ID as string | undefined;
const authScope = import.meta.env.VITE_AUTH_SCOPE as string | undefined;

const msalInstance =
  authEnabled && authTenantId && authClientId
    ? new PublicClientApplication({
        auth: {
          clientId: authClientId,
          authority: `https://login.microsoftonline.com/${authTenantId}`,
          redirectUri: window.location.origin
        },
        cache: {
          cacheLocation: "sessionStorage"
        }
      })
    : null;

let msalInitPromise: Promise<void> | null = null;

function syntheticW2Text(): string {
  return [
    "Synthetic W-2 Document",
    "Employer: Contoso Payroll Services",
    "Employer EIN: 12-3456789",
    "Employee: Alex Demo",
    "Employee SSN: XXX-XX-1234",
    "Tax Year: 2024",
    "Box 1 Wages: 85000.00",
    "Box 2 Federal Income Tax Withheld: 11250.00",
    "Box 3 Social Security Wages: 85000.00",
    "Box 4 Social Security Tax Withheld: 5270.00",
    "Box 5 Medicare Wages: 85000.00",
    "Box 6 Medicare Tax Withheld: 1232.50"
  ].join("\n");
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== "string") {
        reject(new Error("Unable to read file."));
        return;
      }
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = () => reject(new Error("Unable to read file."));
    reader.readAsDataURL(file);
  });
}

function stringToBase64(value: string): string {
  return window.btoa(unescape(encodeURIComponent(value)));
}

async function initializeMsal() {
  if (!msalInstance) {
    return;
  }
  if (!msalInitPromise) {
    msalInitPromise = msalInstance.initialize();
  }
  await msalInitPromise;
}

async function getAccessToken(): Promise<{ token: string; account: AccountInfo | null }> {
  if (!msalInstance || !authScope) {
    return { token: "", account: null };
  }

  await initializeMsal();
  const account =
    msalInstance.getActiveAccount() ??
    msalInstance.getAllAccounts()[0] ??
    (
      await msalInstance.loginPopup({
        scopes: [authScope]
      })
    ).account;

  if (!account) {
    throw new Error("Unable to complete sign-in.");
  }

  msalInstance.setActiveAccount(account);

  let tokenResult: AuthenticationResult;
  try {
    tokenResult = await msalInstance.acquireTokenSilent({
      account,
      scopes: [authScope]
    });
  } catch {
    tokenResult = await msalInstance.acquireTokenPopup({
      account,
      scopes: [authScope]
    });
  }

  return { token: tokenResult.accessToken, account };
}

function nestedRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function App() {
  const [tenantId, setTenantId] = useState("tenant-demo");
  const [taxpayerId, setTaxpayerId] = useState("taxpayer-demo-001");
  const [taxYear, setTaxYear] = useState("2024");
  const [documentName, setDocumentName] = useState("synthetic-w2-2024.txt");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [status, setStatus] = useState<UploadState>("idle");
  const [response, setResponse] = useState<IntakeResponse | null>(null);
  const [pipelineResponse, setPipelineResponse] = useState<PipelineResponse | null>(null);
  const [error, setError] = useState("");
  const [signedInAccount, setSignedInAccount] = useState<AccountInfo | null>(null);
  const [executionMode, setExecutionMode] = useState<ExecutionMode>(
    configuredExecutionMode === "foundry-agent" ? "foundry-agent" : "direct"
  );

  const correlationId = useMemo(() => {
    const suffix = crypto.randomUUID?.() ?? `${Date.now()}`;
    return `portal-w2-${suffix}`;
  }, []);

  const formGenerationResult = nestedRecord(pipelineResponse?.form1040Document);
  const form1040Artifact = nestedRecord(formGenerationResult?.artifact);
  const allowExecutionModeChoice = configuredExecutionMode === "selectable";
  const isAgentMode = executionMode === "foundry-agent";
  const canSubmit = Boolean(
    intakeApiUrl &&
      statusApiUrl &&
      (!isAgentMode || agentApiUrl) &&
      tenantId &&
      taxpayerId &&
      taxYear &&
      documentName
  );

  async function pollPipelineStatus(
    correlationIdToPoll: string,
    headers: Record<string, string>
  ): Promise<PipelineResponse> {
    if (!statusApiUrl) {
      throw new Error("Portal status API configuration is incomplete.");
    }

    const baseUrl = statusApiUrl.replace(/\/$/, "");
    const url = new URL(`${baseUrl}/${encodeURIComponent(correlationIdToPoll)}`);
    url.searchParams.set("tenantId", tenantId);

    const maxAttempts = 30;
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const statusResponse = await fetch(url.toString(), {
        method: "GET",
        headers
      });
      const statusText = await statusResponse.text();
      let statusPayload;
      try {
        statusPayload = statusText ? JSON.parse(statusText) : {};
      } catch {
        statusPayload = statusText;
      }

      if (!statusResponse.ok && statusResponse.status !== 202) {
        throw new Error(
          typeof statusPayload === "string"
            ? statusPayload
            : statusPayload.message ?? statusText
        );
      }

      setPipelineResponse(statusPayload);
      if (statusResponse.status === 200 && statusPayload.status === "complete") {
        return statusPayload;
      }

      await new Promise((resolve) => window.setTimeout(resolve, Math.min(1000 + attempt * 500, 5000)));
    }

    throw new Error("Pipeline did not complete before the portal polling timeout.");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!intakeApiUrl || !statusApiUrl) {
      setStatus("error");
      setError("Portal API configuration is incomplete. Configure intake and status URLs.");
      return;
    }

    setStatus("uploading");
    setResponse(null);
    setPipelineResponse(null);
    setError("");

    try {
      const documentBase64 = selectedFile
        ? await fileToBase64(selectedFile)
        : stringToBase64(syntheticW2Text());

      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "correlation-id": correlationId
      };

      if (authEnabled) {
        const auth = await getAccessToken();
        headers.Authorization = `Bearer ${auth.token}`;
        setSignedInAccount(auth.account);
      }

      const uploadResponse = await fetch(intakeApiUrl, {
        method: "POST",
        headers,
        body: JSON.stringify({
          correlationId,
          tenantId,
          taxpayerId,
          documentName,
          taxYear: Number(taxYear),
          documentBase64,
          executionMode
        })
      });

      const text = await uploadResponse.text();
      let parsed;
      try {
        parsed = text ? JSON.parse(text) : {};
      } catch {
        parsed = text;
      }

      if (!uploadResponse.ok) {
        throw new Error(typeof parsed === "string" ? parsed : parsed.message ?? text);
      }

      let acceptedResponse = parsed;
      setResponse(acceptedResponse);
      setStatus("processing");

      if (isAgentMode) {
        if (!agentApiUrl) {
          throw new Error("Portal agent API configuration is incomplete.");
        }
        const agentResponse = await fetch(agentApiUrl, {
          method: "POST",
          headers,
          body: JSON.stringify({
            correlationId: parsed.correlationId ?? correlationId,
            tenantId,
            taxpayerId,
            documentName,
            taxYear: Number(taxYear),
            blobUri: parsed.blobUri,
            executionMode
          })
        });
        const agentText = await agentResponse.text();
        let agentPayload;
        try {
          agentPayload = agentText ? JSON.parse(agentText) : {};
        } catch {
          agentPayload = agentText;
        }
        if (!agentResponse.ok) {
          throw new Error(
            typeof agentPayload === "string"
              ? agentPayload
              : agentPayload.message ?? agentText
          );
        }
        acceptedResponse = {
          ...acceptedResponse,
          ...agentPayload,
          status: parsed.status ?? agentPayload.status,
          messageId: agentPayload.messageId ?? parsed.messageId
        };
        setResponse(acceptedResponse);
      }

      await pollPipelineStatus(acceptedResponse.correlationId ?? correlationId, headers);
      setStatus("success");
    } catch (caught) {
      setStatus("error");
      setError(caught instanceof Error ? caught.message : "Upload failed.");
    }
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    if (file) {
      setDocumentName(file.name);
    }
  }

  return (
    <main className="shell">
      <header className="site-header">
        <a className="brand-lockup" href="https://fluxionpartners.com/" target="_blank" rel="noreferrer">
          <span className="logo-bracket">FP</span>
          <div>
            <strong>
              FLUXION <em>Partners</em>
            </strong>
            <span>INTELLIGENT AUTOMATION. DELIVERED IN WEEKS.</span>
          </div>
        </a>
        <nav className="nav-pill" aria-label="Fluxion navigation">
          <a href="https://fluxionpartners.com/#services" target="_blank" rel="noreferrer">
            Services
          </a>
          <a href="https://fluxionpartners.com/#process" target="_blank" rel="noreferrer">
            Process
          </a>
          <a href="https://fluxionpartners.com/#solutions" target="_blank" rel="noreferrer">
            Solutions
          </a>
          <a href="https://fluxionpartners.com/#contact" target="_blank" rel="noreferrer" className="nav-cta">
            Contact
          </a>
        </nav>
      </header>

      <section className="hero">
        <p className="eyebrow">Secure Document Automation</p>
        <h1>
          W-2 Intake Workbench
        </h1>
        <p className="subhead">
          Upload synthetic W-2 documents through a governed Azure ingress pattern with API
          Management, Entra-ready access control, Azure Functions, and observable processing.
        </p>
        <div className="hero-actions" aria-label="Platform qualities">
          <span>
            <CheckCircle2 size={16} />
            Production-ready pattern
          </span>
          <span>
            <ShieldCheck size={16} />
            Security-first ingress
          </span>
          <span>
            <Radio size={16} />
            Observable workflow
          </span>
        </div>
      </section>

      <section className="layout">
        <form className="panel upload-panel" onSubmit={onSubmit}>
          <div className="panel-heading split-heading">
            <div>
              <p className="section-kicker">Step 01</p>
              <h2>Submit a W-2 document</h2>
            </div>
            <div className="status-chip">
              <LockKeyhole size={15} />
              APIM secured
            </div>
          </div>

          <div className="mode-row" aria-label="Execution mode">
            <span>
              <Workflow size={16} />
              Execution path
            </span>
            {allowExecutionModeChoice ? (
              <div className="segmented-control">
                <button
                  type="button"
                  className={executionMode === "direct" ? "active" : ""}
                  onClick={() => setExecutionMode("direct")}
                >
                  Backend
                </button>
                <button
                  type="button"
                  className={executionMode === "foundry-agent" ? "active" : ""}
                  onClick={() => setExecutionMode("foundry-agent")}
                >
                  Foundry Agent
                </button>
              </div>
            ) : (
              <strong>{isAgentMode ? "Foundry Agent" : "Backend"}</strong>
            )}
          </div>

          <div className="field-grid">
            <label>
              Tenant ID
              <input value={tenantId} onChange={(event) => setTenantId(event.target.value)} />
            </label>
            <label>
              Taxpayer ID
              <input value={taxpayerId} onChange={(event) => setTaxpayerId(event.target.value)} />
            </label>
            <label>
              Tax Year
              <input
                inputMode="numeric"
                value={taxYear}
                onChange={(event) => setTaxYear(event.target.value)}
              />
            </label>
            <label>
              Document Name
              <input
                value={documentName}
                onChange={(event) => setDocumentName(event.target.value)}
              />
            </label>
          </div>

          <label className="drop-zone">
            <div className="drop-icon">
              <FileText size={24} />
            </div>
            <span>
              <strong>{selectedFile ? selectedFile.name : "Synthetic W-2 ready"}</strong>
              <small>Choose PDF, image, or text file to replace the built-in sample.</small>
            </span>
            <input type="file" accept=".pdf,.txt,.png,.jpg,.jpeg" onChange={onFileChange} />
          </label>

          <button type="submit" disabled={!canSubmit || status === "uploading" || status === "processing"}>
            {status === "uploading" || status === "processing" ? (
              <Loader2 className="spin" size={18} />
            ) : (
              <UploadCloud size={18} />
            )}
            {status === "processing" ? "Running Pipeline" : "Submit to Intake"}
          </button>

          {(!intakeApiUrl || !statusApiUrl || (isAgentMode && !agentApiUrl)) && (
            <p className="warning">
              <AlertCircle size={16} />
              Configure intake, status, and agent API URLs before submitting to Azure.
            </p>
          )}

          {authEnabled && (
            <p className="auth-note">
              <ShieldCheck size={16} />
              Entra authentication enabled
              {signedInAccount?.username ? `: ${signedInAccount.username}` : ""}
            </p>
          )}
        </form>

        <section className="panel status-panel">
          <div className="panel-heading split-heading">
            <div>
              <p className="section-kicker">Step 02</p>
              <h2>Processing command center</h2>
            </div>
            <Sparkles size={22} />
          </div>

          <ol className="timeline">
            <li className="done">Portal request prepared</li>
            <li
              className={
                status === "uploading" || status === "processing" || status === "success"
                  ? "done"
                  : ""
              }
            >
              Submitted through API Management
            </li>
            <li className={response ? "done" : ""}>Accepted by W-2 intake Function</li>
            <li className={response ? "done" : ""}>
              {isAgentMode ? "Blob staged for agent orchestration" : "Blob + Service Bus event created"}
            </li>
            {isAgentMode && (
              <li className={response?.runId ? "done" : ""}>
                Foundry supervisor agent run created
              </li>
            )}
            <li className={pipelineResponse?.extraction?.status ? "done" : ""}>
              W-2 facts extracted
            </li>
            <li className={pipelineResponse?.validation?.status ? "done" : ""}>
              Validation and review controls evaluated
            </li>
            <li className={pipelineResponse?.taxPlanning?.mappingStatus ? "done" : ""}>
              Tax facts mapped to Form 1040
            </li>
            <li className={formGenerationResult?.status ? "done" : ""}>
              Draft Form 1040 artifact generated
            </li>
            <li className={pipelineResponse?.status === "complete" ? "done" : ""}>
              Compliance and persistence completed
            </li>
          </ol>

          {status === "success" && response && (
            <div className="response-card success">
              <p>Status: {response.status}</p>
              <p>Execution: {isAgentMode ? "Foundry Agent" : "Backend"}</p>
              <p>Correlation: {response.correlationId}</p>
              <p>Message ID: {response.messageId}</p>
              {response.threadId && <p>Foundry Thread: {response.threadId}</p>}
              {response.runId && <p>Foundry Run: {response.runId}</p>}
              <p className="wrap">Blob: {response.blobUri}</p>
              {pipelineResponse?.status && <p>Pipeline: {String(pipelineResponse.status)}</p>}
              {form1040Artifact?.blobName && (
                <p className="wrap">Draft 1040: {String(form1040Artifact.blobName)}</p>
              )}
            </div>
          )}

          {status === "error" && (
            <div className="response-card error">
              <p>{error}</p>
            </div>
          )}
        </section>
      </section>

      <section className="delivery-band" aria-label="Delivery pattern">
        <div>
          <p className="section-kicker">Fluxion delivery pattern</p>
          <h2>From upload to operational signal</h2>
        </div>
        <div className="delivery-steps">
          <span>Portal</span>
          <span>API Management</span>
          {isAgentMode && <span>Foundry Agent</span>}
          <span>Function App</span>
          <span>Service Bus</span>
          <span>Foundry tools</span>
          <span>Draft 1040</span>
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
