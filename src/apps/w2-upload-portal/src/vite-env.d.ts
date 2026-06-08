/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_W2_INTAKE_API_URL?: string;
  readonly VITE_W2_PROCESSING_API_URL?: string;
  readonly VITE_W2_STATUS_API_URL?: string;
  readonly VITE_W2_AGENT_API_URL?: string;
  readonly VITE_W2_EXECUTION_MODE?: "direct" | "foundry-agent" | "selectable";
  readonly VITE_AUTH_ENABLED?: string;
  readonly VITE_AUTH_TENANT_ID?: string;
  readonly VITE_AUTH_CLIENT_ID?: string;
  readonly VITE_AUTH_SCOPE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
