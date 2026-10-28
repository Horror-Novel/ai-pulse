import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Report({ org }) {
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api("/reports/me").then(r => { if (active) setReport(r); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  async function remove() {
    setBusy(true); setError(""); setMessage("");
    try {
      await api("/diagnostic/me", { method: "DELETE" });
      // Clear the sensitive UI immediately after deletion, even if reloading fails.
      setReport({ name: report.name, status: "empty", answered: 0, risks: [], next_steps: [] });
      setConfirming(false);
      setMessage("Your answers and report were deleted in this organization. Dashboard eligibility has been recalculated.");
      setReport(await api("/reports/me"));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function download() {
    setBusy(true); setError("");
    try {
      const data = await api("/diagnostic/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "ai-pulse-diagnostic.json";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setMessage(data.responses.length ? "Your export was downloaded. It contains personal data; store it safely."
        : "Your export was downloaded. There are no diagnostic answers in this organization.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <section className="card">
      <h2>My report & data</h2>
      <p>{org.org_name}</p>
      {error && <p className="error" role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {!report && !error && <p>Loading report…</p>}
      {report && <>
        {report.status === "completed" ? <>
          <h3>{report.name}: {report.level}</h3>
          {report.scoring_mode === "mock" && <p className="notice">Demo mode: AI scores and explanations are simulated.</p>}
          <p>Average score: {report.average_score} / 5 · {report.answered} questions</p>
          <p>AI feedback is advisory and may be wrong. It is not a validated measure of job performance.</p>
          <h3>Risks</h3>
          {report.risks.length ? <ul>{report.risks.map(r => <li key={r}>{r.replaceAll("_", " ")}</li>)}</ul>
            : <p>No risks were flagged; this does not establish that usage is safe.</p>}
          <h3>Next steps</h3>
          <ul>{report.next_steps.map(s => <li key={s}>{s}</li>)}</ul>
        </> : <p>{report.status === "incomplete"
          ? "Only incomplete inherited answers exist. Take the diagnostic to receive a validated report. You can export or delete those answers."
          : "No diagnostic data. Take the diagnostic when you are ready."}</p>}
        <div className="actions">
          <button onClick={download} disabled={busy}>Export my data (JSON)</button>
          <button className="danger" onClick={() => setConfirming(true)} disabled={busy || report.answered === 0}>
            Delete my diagnostic data
          </button>
        </div>
        {confirming && <div className="confirmation" role="group" aria-label="Confirm deletion">
          <p>Delete all your diagnostic answers and report in {org.org_name}? This cannot be undone.
            Your account and data in other organizations stay available. This does not delete external provider records,
            backups or files you already exported.</p>
          <button className="danger" disabled={busy} onClick={remove}>Confirm deletion</button>
          <button className="secondary" disabled={busy} onClick={() => setConfirming(false)}>Cancel</button>
        </div>}
      </>}
    </section>
  );
}
