import { useCallback, useEffect, useRef, useState } from "react";
import type { RpcMethod, RpcMethods } from "../../shared/types";
import { ApiError, call } from "./api";

export function useRpc<M extends RpcMethod>(
  method: M,
  params?: RpcMethods[M][0],
  opts: { intervalMs?: number; enabled?: boolean } = {},
) {
  const [data, setData] = useState<RpcMethods[M][1] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const paramsKey = JSON.stringify(params ?? {});
  const busy = useRef(false);
  const enabled = opts.enabled ?? true;

  const reload = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setLoading(true);
    try {
      setData(await call(method, JSON.parse(paramsKey)));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError("unknown", String(e)));
    } finally {
      busy.current = false;
      setLoading(false);
    }
  }, [method, paramsKey]);

  useEffect(() => {
    if (!enabled) return;
    reload();
    if (!opts.intervalMs) return;
    const t = setInterval(reload, opts.intervalMs);
    return () => clearInterval(t);
  }, [reload, enabled, opts.intervalMs]);

  return { data, error, loading, reload, setData };
}
