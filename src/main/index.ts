import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { BackendBridge } from "./backend";

const isDev = process.env.MRLAB_DEV === "1";
const RPC_METHOD = /^[a-z]+\.[a-zA-Z]+$/;

const appRoot = app.isPackaged ? process.resourcesPath : resolve(__dirname, "..", "..", "..");
const dataDir = join(app.getPath("userData"), "data");
mkdirSync(dataDir, { recursive: true });

const backend = new BackendBridge({
  appRoot,
  packaged: app.isPackaged,
  dataDir,
  toolsDir: join(resourcesDir(), "tools"),
  resourcesDir: resourcesDir(),
});

/** Carpeta con los componentes integrados (motores Android/Apple y controladores). */
function resourcesDir(): string {
  return app.isPackaged ? process.resourcesPath : join(appRoot, "resources");
}

let win: BrowserWindow | null = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: "#070b10",
    title: "Mobile Recovery Lab",
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, "..", "preload", "index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  // Bloquear navegación y ventanas emergentes externas.
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (e, url) => {
    if (!url.startsWith("http://localhost:5173") && !url.startsWith("file://")) e.preventDefault();
  });
  if (isDev) win.loadURL("http://localhost:5173");
  else win.loadFile(join(__dirname, "..", "..", "renderer", "index.html"));
}

ipcMain.handle("rpc", async (_e, method: unknown, params: unknown) => {
  if (typeof method !== "string" || !RPC_METHOD.test(method)) {
    return { ok: false, error: { code: "invalid_method", message: "Nombre de método inválido" } };
  }
  try {
    const result = await backend.call(method, (params as Record<string, unknown>) ?? {});
    return { ok: true, result };
  } catch (err: any) {
    return { ok: false, error: { code: err?.code ?? "unknown", message: err?.message ?? String(err), data: err?.data } };
  }
});
ipcMain.handle("backend:status", () => backend.status);
ipcMain.handle("app:info", () => ({ version: app.getVersion(), platform: process.platform, packaged: app.isPackaged }));
// Selector nativo de carpeta o .zip para importar datos.
ipcMain.handle("dialog:pickSource", async (_e, kind: unknown) => {
  if (!win) return null;
  const folder = kind === "folder";
  const r = await dialog.showOpenDialog(win, {
    title: folder ? "Seleccionar carpeta a importar" : "Seleccionar archivo .zip a importar",
    properties: folder ? ["openDirectory"] : ["openFile"],
    filters: folder ? undefined : [{ name: "Archivo ZIP", extensions: ["zip"] }],
  });
  return r.canceled ? null : r.filePaths[0] ?? null;
});

// Convierte un reporte HTML generado por el backend en PDF (A4) con el motor de Chromium.
ipcMain.handle("report:toPdf", async (_e, htmlPath: unknown) => {
  const exportsDir = resolve(dataDir, "exports");
  if (typeof htmlPath !== "string" || !resolve(htmlPath).startsWith(exportsDir) || !htmlPath.toLowerCase().endsWith(".html")) {
    throw new Error("Ruta de reporte no permitida");
  }
  const pdfWin = new BrowserWindow({
    show: false,
    webPreferences: { javascript: false, sandbox: true, contextIsolation: true, nodeIntegration: false },
  });
  try {
    await pdfWin.loadFile(htmlPath);
    const pdf = await pdfWin.webContents.printToPDF({
      pageSize: "A4",
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: "<span></span>",
      footerTemplate:
        '<div style="font-size:8px;color:#64748b;width:100%;padding:0 14mm;display:flex;justify-content:space-between">' +
        '<span>Mobile Recovery Lab</span><span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>',
      margins: { top: 0.6, bottom: 0.7, left: 0.55, right: 0.55 },
    });
    const pdfPath = htmlPath.replace(/\.html$/i, ".pdf");
    writeFileSync(pdfPath, pdf);
    return pdfPath;
  } finally {
    pdfWin.destroy();
  }
});

// Única URL externa permitida: la ficha oficial de Apple Devices en Microsoft Store.
ipcMain.handle("shell:openAppleStore", async () => {
  if (process.platform !== "win32") return false;
  await shell.openExternal("ms-windows-store://pdp/?productid=9NP83LWLPZ9K");
  return true;
});
ipcMain.handle("shell:openPath", (_e, p: unknown) => {
  // Solo se permiten rutas dentro del directorio de datos de la aplicación.
  if (typeof p !== "string" || !resolve(p).startsWith(resolve(dataDir))) return "Ruta no permitida";
  return shell.openPath(p);
});

backend.on("status", (s) => win?.webContents.send("backend:status", s));

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });
  app.whenReady().then(() => {
    backend.start().catch((e) => console.error("[backend]", e?.message ?? e));
    createWindow();
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
}

app.on("before-quit", () => backend.stop());
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
