import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { EventEmitter } from "node:events";
import { existsSync } from "node:fs";
import { join } from "node:path";
import * as readline from "node:readline";
import type { BackendStatus, RpcErrorShape } from "../shared/types";

interface Pending {
  resolve: (v: unknown) => void;
  reject: (e: RpcErrorShape) => void;
  timer: NodeJS.Timeout;
}

export interface BackendOptions {
  appRoot: string;        // raíz del proyecto (dev) o resources (prod)
  packaged: boolean;
  dataDir: string;
  toolsDir: string;
  resourcesDir: string;
}

const TIMEOUTS: Record<string, number> = {
  "diagnostics.run": 120_000,
  "devices.scan": 60_000,
  "tools.detect": 45_000,
  "dashboard.summary": 45_000,
};

/** Puente con el backend Python: proceso hijo que habla JSON por líneas en stdio. */
export class BackendBridge extends EventEmitter {
  private proc: ChildProcessWithoutNullStreams | null = null;
  private pending = new Map<number, Pending>();
  private nextId = 1;
  private stopping = false;
  private readyPromise: Promise<void> | null = null;
  status: BackendStatus = { state: "stopped", restarts: 0 };

  constructor(private opts: BackendOptions) {
    super();
  }

  private command(): { cmd: string; args: string[]; cwd: string } {
    if (this.opts.packaged) {
      const exe = join(this.opts.appRoot, "backend", process.platform === "win32" ? "mrlab-backend.exe" : "mrlab-backend");
      return { cmd: exe, args: [], cwd: join(this.opts.appRoot, "backend") };
    }
    const python = process.env.MRLAB_PYTHON || (process.platform === "win32" ? "python" : "python3");
    return { cmd: python, args: ["-u", "-m", "mrlab"], cwd: join(this.opts.appRoot, "backend") };
  }

  private setStatus(s: Partial<BackendStatus>) {
    this.status = { ...this.status, ...s };
    this.emit("status", this.status);
  }

  start(): Promise<void> {
    if (this.readyPromise && this.proc) return this.readyPromise;
    const { cmd, args, cwd } = this.command();
    this.setStatus({ state: "starting", detail: `${cmd} ${args.join(" ")}` });
    if (this.opts.packaged && !existsSync(cmd)) {
      this.setStatus({ state: "crashed", detail: `No se encontró el backend empaquetado: ${cmd}` });
      return Promise.reject(new Error(this.status.detail));
    }
    this.readyPromise = new Promise<void>((resolve, reject) => {
      const proc = spawn(cmd, args, {
        cwd,
        env: {
          ...process.env,
          MRLAB_DATA_DIR: this.opts.dataDir,
          MRLAB_TOOLS_DIR: this.opts.toolsDir,
          MRLAB_RESOURCES_DIR: this.opts.resourcesDir,
          PYTHONIOENCODING: "utf-8",
          PYTHONUTF8: "1",
        },
        windowsHide: true,
      });
      this.proc = proc;
      let ready = false;
      let stderrTail = "";
      const startTimer = setTimeout(() => {
        if (!ready) {
          this.setStatus({ state: "crashed", detail: "El backend no respondió al iniciar (20 s)." });
          reject(new Error("timeout"));
          proc.kill();
        }
      }, 20_000);

      readline.createInterface({ input: proc.stdout }).on("line", (line) => {
        let msg: any;
        try {
          msg = JSON.parse(line);
        } catch {
          return; // salida no JSON: se ignora
        }
        if (msg.event === "ready") {
          ready = true;
          clearTimeout(startTimer);
          this.setStatus({ state: "ready", detail: `Backend v${msg.data?.version}` });
          resolve();
          return;
        }
        const p = this.pending.get(msg.id);
        if (!p) return;
        this.pending.delete(msg.id);
        clearTimeout(p.timer);
        if (msg.error) p.reject(msg.error);
        else p.resolve(msg.result);
      });
      proc.stderr.on("data", (d: Buffer) => {
        stderrTail = (stderrTail + d.toString()).slice(-4000);
        process.stderr.write(`[backend] ${d}`);
      });
      proc.on("error", (err) => {
        clearTimeout(startTimer);
        this.setStatus({ state: "crashed", detail: `No se pudo iniciar el backend: ${err.message}` });
        reject(err);
      });
      proc.on("exit", (code) => {
        clearTimeout(startTimer);
        this.proc = null;
        this.readyPromise = null;
        for (const [, p] of this.pending) {
          clearTimeout(p.timer);
          p.reject({ code: "backend_exited", message: "El backend se detuvo durante la operación." });
        }
        this.pending.clear();
        if (this.stopping) {
          this.setStatus({ state: "stopped" });
          return;
        }
        const tail = stderrTail.trim().split("\n").slice(-3).join(" | ");
        this.setStatus({ state: "crashed", detail: `Backend finalizó (código ${code}). ${tail}` });
        if (!ready) reject(new Error("exit"));
        // reinicio automático limitado
        if (this.status.restarts < 5) {
          this.status.restarts += 1;
          setTimeout(() => this.start().catch(() => undefined), 1500);
        }
      });
    });
    return this.readyPromise;
  }

  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (!this.proc || this.status.state !== "ready") {
      try {
        await this.start();
      } catch {
        throw { code: "backend_unavailable", message: this.status.detail || "Backend no disponible" } as RpcErrorShape;
      }
    }
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject({ code: "timeout", message: `La operación ${method} excedió el tiempo de espera.` });
      }, TIMEOUTS[method] ?? 30_000);
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, timer });
      this.proc!.stdin.write(JSON.stringify({ id, method, params }) + "\n");
    });
  }

  stop() {
    this.stopping = true;
    if (this.proc) {
      try {
        this.proc.stdin.write(JSON.stringify({ id: 0, method: "system.shutdown" }) + "\n");
      } catch {
        /* ignorado */
      }
      const p = this.proc;
      setTimeout(() => p.kill(), 2000);
    }
  }
}
