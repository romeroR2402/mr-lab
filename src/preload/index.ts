import { contextBridge, ipcRenderer } from "electron";
import type { BackendStatus, MrLabBridge } from "../shared/types";

const bridge: MrLabBridge = {
  rpc: (method, params) => ipcRenderer.invoke("rpc", method, params ?? {}),
  backendStatus: () => ipcRenderer.invoke("backend:status"),
  onBackendStatus: (cb) => {
    const listener = (_: unknown, s: BackendStatus) => cb(s);
    ipcRenderer.on("backend:status", listener);
    return () => ipcRenderer.removeListener("backend:status", listener);
  },
  openPath: (p) => ipcRenderer.invoke("shell:openPath", p),
  openAppleDevicesStore: () => ipcRenderer.invoke("shell:openAppleStore"),
  pickSource: (kind) => ipcRenderer.invoke("dialog:pickSource", kind),
  reportToPdf: (htmlPath) => ipcRenderer.invoke("report:toPdf", htmlPath),
  appInfo: () => ipcRenderer.invoke("app:info"),
};

contextBridge.exposeInMainWorld("mrlab", bridge);
