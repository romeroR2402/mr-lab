import type { MrLabBridge, RpcErrorShape, RpcMethod, RpcMethods } from "../../shared/types";

declare global {
  interface Window {
    mrlab?: MrLabBridge;
  }
}

export class ApiError extends Error {
  constructor(public code: string, message: string, public data?: Record<string, unknown>) {
    super(message);
  }
}

export function bridge(): MrLabBridge {
  if (!window.mrlab) {
    throw new ApiError("no_bridge", "La interfaz se está ejecutando fuera de Electron: el backend no está disponible.");
  }
  return window.mrlab;
}

/** Llama al backend y lanza ApiError ante fallos. */
export async function call<M extends RpcMethod>(method: M, params?: RpcMethods[M][0]): Promise<RpcMethods[M][1]> {
  const res = await bridge().rpc(method, params);
  if (!res.ok) {
    const e: RpcErrorShape = res.error;
    throw new ApiError(e.code, e.message, e.data);
  }
  return res.result;
}
