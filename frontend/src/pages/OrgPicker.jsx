import React, { useState } from "react";
import { api, setToken } from "../api.js";

export default function OrgPicker({ orgs, onPick }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function pick(o) {
    setBusy(true); setError("");
    try {
      const data = await api("/auth/select-org", { method: "POST", body: JSON.stringify({ org_id: o.org_id }) });
      setToken(data.token); onPick(o);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return (
    <div className="card">
      <h2>Choose an organization</h2>
      {error && <p className="error" role="alert">{error}</p>}
      {orgs.map(o => <p key={o.org_id}>
        <button disabled={busy} onClick={() => pick(o)}>{o.org_name}</button> <small>({o.role})</small>
      </p>)}
    </div>
  );
}
