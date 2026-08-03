import React from "react";

export default function ProgressBar({ state }) {
  if (state.status === "idle") return null;
  const pct = Math.round((state.progress || 0) * 100);
  const cls =
    state.status === "error" ? "error" : state.status === "done" ? "done" : "run";
  return (
    <div className={`progress ${cls}`}>
      <div className="bar">
        <div className="fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-msg">
        {state.status === "error" ? "⚠ " : ""}
        {state.message} {state.status !== "error" && `· ${pct}%`}
      </div>
    </div>
  );
}
