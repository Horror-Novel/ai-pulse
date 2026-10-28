import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Dashboard({ org }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let active = true;
    let latestRequest = 0;
    async function load() {
      const requestId = ++latestRequest;
      try {
        const result = await api(`/dashboard?org_id=${org.org_id}`);
        if (active && requestId === latestRequest) { setData(result); setError(""); }
      } catch (e) {
        // Remove old performance data when current authorization/refresh fails.
        if (active && requestId === latestRequest) { setData(null); setError(e.message); }
      }
    }
    load();
    const timer = setInterval(load, 5000);
    window.addEventListener("focus", load);
    return () => { active = false; clearInterval(timer); window.removeEventListener("focus", load); };
  }, [org.org_id, refresh]);

  return (
    <section className="card">
      <h2>Leadership dashboard</h2>
      <p>{org.org_name}</p>
      <button className="secondary" onClick={() => setRefresh(v => v + 1)}>Refresh dashboard</button>
      <p>Recalculated on every request. This view refreshes every five seconds and when focused.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {!data && !error && <p role="status">Loading dashboard…</p>}
      {data && <>
        <p className="notice">{data.privacy_notice}</p>
        {data.departments.length === 0 ? <p>No departments meet the privacy threshold yet.</p> : <>
          <div className="table-scroll"><table>
            <thead><tr><th>Department</th><th>Completed employees</th><th>Average / 5</th><th>Maturity</th></tr></thead>
            <tbody>{data.departments.map(d => <tr key={d.department}>
              <td>{d.department}</td><td>{d.completed_employees}</td><td>{d.average_score}</td><td>{d.level}</td>
            </tr>)}</tbody>
          </table></div>
          <h3>Reported risks in eligible departments</h3>
          {data.top_risks.length ? <ul>{data.top_risks.map(([flag, count]) =>
            <li key={flag}>{flag.replaceAll("_", " ")}: {count} employees</li>)}</ul>
            : <p>No risk labels meet the reporting threshold. This does not establish an absence of risk.</p>}
        </>}
        <p>Self-reported diagnostic feedback is advisory. Mock-mode results are simulated; this dashboard
          must not be used to rank employees or make employment decisions.</p>
      </>}
    </section>
  );
}
