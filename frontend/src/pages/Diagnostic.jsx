import React, { useEffect, useState } from "react";
import { api } from "../api.js";

export default function Diagnostic({ onDone }) {
  const [questions, setQuestions] = useState(null);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api("/diagnostic/questions").then(q => { if (active) setQuestions(q); })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);

  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const payload = questions.map(q => ({ question_id: q.id, answer: answers[q.id] || "" }));
      await api("/diagnostic/submit", { method: "POST", body: JSON.stringify({ answers: payload }) });
      onDone();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h2>Your AI diagnostic</h2>
      <p>Answer every question. A successful submission replaces your previous diagnostic in this organization.
        If scoring fails, your previous diagnostic stays available.</p>
      <p>Open answers may be sent to the configured AI provider. Use anonymized examples; omit customer details and secrets.</p>
      {error && <p className="error" role="alert">{error}</p>}
      {!questions && !error && <p role="status">Loading questions…</p>}
      <fieldset disabled={busy}>
        {questions?.map(q => (
          <label className="question" key={q.id} htmlFor={q.id}>
            <span>{q.text}</span>
            {q.type === "mcq" ? (
              <select id={q.id} required value={answers[q.id] || ""}
                onChange={e => setAnswers(a => ({ ...a, [q.id]: e.target.value }))}>
                <option value="" disabled>Choose…</option>
                {q.options.map(o => <option key={o}>{o}</option>)}
              </select>
            ) : (
              <textarea id={q.id} required maxLength={5000} rows={4} value={answers[q.id] || ""}
                onChange={e => setAnswers(a => ({ ...a, [q.id]: e.target.value }))} />
            )}
          </label>
        ))}
      </fieldset>
      <button disabled={busy || !questions?.length}>{busy ? "Scoring and saving…" : "Submit diagnostic"}</button>
    </form>
  );
}
