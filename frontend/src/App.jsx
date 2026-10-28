import React, { useState } from "react";
import Login from "./pages/Login.jsx";
import OrgPicker from "./pages/OrgPicker.jsx";
import Diagnostic from "./pages/Diagnostic.jsx";
import Report from "./pages/Report.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import { clearToken } from "./api.js";

export default function App() {
  const [step, setStep] = useState("login");
  const [session, setSession] = useState(null);
  const [org, setOrg] = useState(null);

  function logout() {
    clearToken();
    setSession(null);
    setOrg(null);
    setStep("login");
  }

  return (
    <div className="wrap">
      <header><h1>AI Pulse</h1>{session && <button className="secondary" onClick={logout}>Sign out</button>}</header>
      {org && <>
        <p>{org.org_name} · {org.role}</p>
        <nav aria-label="Application">
          <button className="secondary" onClick={() => { setOrg(null); setStep("org"); }}>Switch organization</button>
          <button className="secondary" onClick={() => setStep("diagnostic")}>Take diagnostic</button>
          <button className="secondary" onClick={() => setStep("report")}>My report & data</button>
          {org.role === "admin" && <button className="secondary" onClick={() => setStep("dashboard")}>Dashboard</button>}
        </nav>
      </>}
      {step === "login" && <Login onDone={(s) => { setSession(s); setStep("org"); }} />}
      {step === "org" && <OrgPicker orgs={session.organizations} onPick={(o) => {
        setOrg(o); setStep(o.role === "admin" ? "dashboard" : "diagnostic");
      }} />}
      {step === "diagnostic" && <Diagnostic key={org.org_id} onDone={() => setStep("report")} />}
      {step === "report" && <Report key={org.org_id} org={org} />}
      {step === "dashboard" && <Dashboard key={org.org_id} org={org} />}
    </div>
  );
}
