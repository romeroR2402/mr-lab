// Contratos compartidos entre main, preload y renderer.

export type Platform = "android" | "apple";
export type CheckStatus = "ok" | "warning" | "error" | "info" | "unavailable";

export interface DeviceInfo {
  key: string;
  label: string;
  platform: Platform;
  serial: string;
  connection: "usb" | "network" | "emulator" | "unknown";
  commState: string;
  authState: string;
  mode: string;
  manufacturer: string | null;
  model: string | null;
  modelCode: string | null;
  osName: string | null;
  osVersion: string | null;
  connector: string;
  diagnostics: string[];
  notes: string[];
}

export interface ScanResult {
  devices: DeviceInfo[];
  errors: string[];
  scannedAt: string | null;
  connectors: Record<string, { available: boolean; count: number }>;
}

export interface ToolInfo {
  id: string;
  name: string;
  path: string | null;
  installed: boolean;
  version: string | null;
  purpose: string;
  requiredFor: string[];
}

export interface ToolsReport {
  tools: ToolInfo[];
  appleService: { name: string; installed: boolean; running: boolean; detail: string };
  encryption: { available: boolean; version: string | null };
  platform: string;
}

export interface DiagnosticCheck {
  id: string;
  category: string;
  label: string;
  status: CheckStatus;
  value: string | null;
  detail: string | null;
  data: Record<string, string | number | null>;
}

export interface RecoveryChannel {
  id: string;
  label: string;
  module: string;
  implemented: boolean;
}

export interface DiagnosticReport {
  id: number;
  device: DeviceInfo;
  timestamp: string;
  summaryStatus: CheckStatus;
  checks: DiagnosticCheck[];
  recoveryChannels: RecoveryChannel[];
  caseId: number | null;
}

export interface DiagnosticHistoryItem {
  id: number;
  timestamp: string;
  platform: Platform;
  deviceSerial: string;
  deviceLabel: string | null;
  caseId: number | null;
  summaryStatus: CheckStatus;
}

export interface CaseRecord {
  id: number;
  folio: string;
  createdAt: string;
  updatedAt: string;
  technician: string;
  deviceType: "android" | "ios" | "ipados" | "other";
  deviceModel: string | null;
  deviceSerial: string | null;
  reason: string;
  authorizationType: string;
  authorizedBy: string;
  authorizationRef: string | null;
  status: string;
  results: string | null;
  operations?: { id: number; timestamp: string; operation: string; method: string | null; result: string; details: string | null }[];
  files?: { id: number; createdAt: string; path: string; sha256: string | null; sizeBytes: number | null; description: string | null }[];
}

export interface EvidenceEntry {
  id: number;
  timestamp: string;
  technician: string;
  caseId: number | null;
  deviceSerial: string | null;
  deviceLabel: string | null;
  operation: string;
  result: string;
  details: string | null;
  files: string[];
  error: string | null;
  confirmation: string | null;
  entryHash: string;
}

export interface ModuleInfo {
  id: string;
  name: string;
  stage: number;
  status: "implemented" | "partial" | "planned";
  description: string;
  scope?: string[];
}

export interface Settings {
  technicianName: string;
  labName: string;
  adbPath: string;
  fastbootPath: string;
  libimobiledeviceDir: string;
  autoScanSeconds: number;
  maskIdentifiers: boolean;
}

export interface DashboardSummary {
  primaryDevice: DeviceInfo | null;
  deviceCount: number;
  scannedAt: string | null;
  scanErrors: string[];
  lastDiagnostic: DiagnosticReport | null;
  screen: { display: DiagnosticCheck | null; touch: DiagnosticCheck | null } | null;
  recoveryChannels: RecoveryChannel[];
  recentCases: CaseRecord[];
  caseStats: { total: number; byStatus: Record<string, number> };
  evidenceCount: number;
  tools: Record<string, boolean>;
  appleService: ToolsReport["appleService"];
  encryption: ToolsReport["encryption"];
}

export interface HealthInfo {
  version: string;
  dataDir: string;
  db: string;
  schemaVersion: number;
  python: string;
}

/** Mapa método RPC -> [params, resultado]. */
export interface RpcMethods {
  "system.health": [Record<string, never>, HealthInfo];
  "system.modules": [Record<string, never>, ModuleInfo[]];
  "tools.detect": [{ force?: boolean }, ToolsReport];
  "settings.get": [Record<string, never>, Settings];
  "settings.update": [{ values: Partial<Settings> }, Settings];
  "devices.scan": [Record<string, never>, ScanResult];
  "devices.last": [Record<string, never>, ScanResult];
  "diagnostics.run": [{ deviceKey: string; caseId?: number | null }, DiagnosticReport];
  "diagnostics.history": [{ deviceSerial?: string }, DiagnosticHistoryItem[]];
  "diagnostics.get": [{ id: number }, DiagnosticReport];
  "dashboard.summary": [Record<string, never>, DashboardSummary];
  "cases.list": [{ status?: string; search?: string }, CaseRecord[]];
  "cases.get": [{ id: number }, CaseRecord];
  "cases.create": [Record<string, unknown>, CaseRecord];
  "cases.updateStatus": [{ id: number; status: string; results?: string }, CaseRecord];
  "evidence.list": [{ limit?: number; offset?: number; caseId?: number }, { total: number; entries: EvidenceEntry[] }];
  "evidence.verify": [Record<string, never>, { valid: boolean; checked: number; brokenAtId: number | null }];
}

export type RpcMethod = keyof RpcMethods;

export interface RpcErrorShape {
  code: string;
  message: string;
  data?: Record<string, unknown>;
}

export type RpcResponse<T> = { ok: true; result: T } | { ok: false; error: RpcErrorShape };

export type BackendState = "starting" | "ready" | "crashed" | "stopped";

export interface BackendStatus {
  state: BackendState;
  detail?: string;
  restarts: number;
}

export interface MrLabBridge {
  rpc<M extends RpcMethod>(method: M, params?: RpcMethods[M][0]): Promise<RpcResponse<RpcMethods[M][1]>>;
  backendStatus(): Promise<BackendStatus>;
  onBackendStatus(cb: (s: BackendStatus) => void): () => void;
  openPath(path: string): Promise<string>;
  appInfo(): Promise<{ version: string; platform: string; packaged: boolean }>;
}
