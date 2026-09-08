/** Tiny API layer with typed errors + polling hook. */
export class ApiError extends Error {
  constructor(msg, status, data) { super(msg); this.status = status; this.data = data; }
}
export async function api(path, opts = {}) {
  let r;
  try {
    r = await fetch(path, {
      headers: opts.body && !(opts.body instanceof FormData)
        ? { "Content-Type": "application/json", ...(opts.headers || {}) }
        : opts.headers,
      ...opts,
    });
  } catch (e) {
    throw new ApiError("Cannot reach the engine — is it running?", 0, null);
  }
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json().catch(() => null) : await r.text();
  if (!r.ok) {
    const msg = (data && (data.error?.message || data.error || data.message ||
      (Array.isArray(data.errors) && data.errors.join(" · ")))) || `Request failed (${r.status})`;
    throw new ApiError(msg, r.status, data);
  }
  return data;
}
