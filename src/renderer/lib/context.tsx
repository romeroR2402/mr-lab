import { createContext, useContext } from "react";
import type { BackendStatus, ScanResult, Settings } from "../../shared/types";
import type { PageId } from "../components/Sidebar";
import type { ApiError } from "./api";

export interface LabContext {
  backend: BackendStatus;
  scan: ScanResult | null;
  scanError: ApiError | null;
  scanning: boolean;
  rescan: () => Promise<void>;
  settings: Settings | null;
  reloadSettings: () => Promise<void>;
  selectedKey: string | null;
  setSelectedKey: (k: string | null) => void;
  navigate: (p: PageId) => void;
}

export const Ctx = createContext<LabContext | null>(null);

export function useLab(): LabContext {
  const c = useContext(Ctx);
  if (!c) throw new Error("useLab fuera de proveedor");
  return c;
}
