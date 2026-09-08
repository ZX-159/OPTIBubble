import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

/** Poll an endpoint; exposes {data, error, loading, refresh}. Pauses when
 *  hidden or `active` is false. */
export function usePoll(path, { ms = 2000, active = true, immediate = true } = {}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(immediate && !!path);
  const bus = useRef(false);
  const refresh = useCallback(async (quiet) => {
    if (!path) return;
    if (bus.current) return;
    bus.current = true;
    if (!quiet) setLoading(true);
    try {
      const d = await api(path);
      setData(d); setError(null);
    } catch (e) {
      setError(e);
    } finally {
      bus.current = false;
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    if (!path || !active) return;
    if (immediate) refresh(true);
    const iv = setInterval(() => {
      if (!document.hidden) refresh(true);
    }, ms);
    return () => clearInterval(iv);
  }, [path, active, ms, refresh, immediate]);
  return { data, error, loading, refresh, setData };
}

/** One-shot fetch with manual refresh. */
export function useFetch(path, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: !!path });
  const load = useCallback(async (quiet) => {
    if (!path) return;
    if (!quiet) setState((s) => ({ ...s, loading: true }));
    try {
      const data = await api(path);
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState((s) => ({ ...s, error, loading: false }));
    }
  }, [path]);
  useEffect(() => { load(true); /* eslint-disable-next-line */ }, [path, ...deps]);
  return { ...state, reload: load };
}
