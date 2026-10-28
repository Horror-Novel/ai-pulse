const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function getToken() {
  return sessionStorage.getItem("token");
}

export function setToken(t) {
  localStorage.removeItem("token"); // Remove tokens left by the inherited application.
  sessionStorage.setItem("token", t);
}

export function clearToken() {
  sessionStorage.removeItem("token");
  localStorage.removeItem("token");
}

export async function api(path, options = {}) {
  const res = await fetch(BASE + path, {
    ...options,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      ...(options.headers || {}),
    },
  });
  let data;
  try { data = await res.json(); }
  catch { throw new Error("The server returned an unreadable response. Please retry."); }
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(res.status === 401 ? "Your session is invalid or expired. Sign out and sign in again."
      : typeof detail === "string" ? detail : "The request was rejected. Check your answers and retry.");
  }
  return data;
}
