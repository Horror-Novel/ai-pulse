import React, { useState } from "react";
import { api, setToken } from "../api.js";

export default function Login({ onDone }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setError("");
    try {
      const data = await api("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      setToken(data.token);
      onDone(data);
    } catch (err) {
      setError(err.message);
    } finally { setBusy(false); }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Sign in</h2>
      <label>Email<input type="email" required autoComplete="username" maxLength={200} value={email} onChange={(e) => setEmail(e.target.value)} /></label>
      <label>Password<input type="password" required autoComplete="current-password" maxLength={1024} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
      {error && <p className="error" role="alert">{error}</p>}
      <button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form>
  );
}
