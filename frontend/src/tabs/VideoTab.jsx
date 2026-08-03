import React, { useState } from "react";
import { postForm, fileUrl } from "../api.js";
import Uploader from "../components/Uploader.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import useJobRunner from "../components/useJobRunner.js";

// Local ffmpeg-based video editing. Runs on CPU — fine on modest hardware.
const OPS = [
  { id: "trim", label: "Trim", fields: [["a", "Start (s)", 0], ["b", "End (s)", 3]] },
  {
    id: "crop",
    label: "Crop",
    fields: [["a", "Width", 320], ["b", "Height", 240], ["c", "X", 0], ["d", "Y", 0]],
  },
  { id: "resize", label: "Resize", fields: [["a", "Target width", 640]] },
  { id: "speed", label: "Speed", fields: [["a", "Factor (2=2x, 0.5=half)", 2]] },
  { id: "gif", label: "To GIF", fields: [["a", "FPS", 12], ["b", "Width", 480]] },
  { id: "convert", label: "Convert", fields: [["fmt", "Format (mp4/webm/mov)", "webm"]] },
  { id: "frames", label: "Extract frames", fields: [["a", "FPS", 1]] },
  { id: "audio", label: "Extract audio", fields: [] },
];

export default function VideoTab({ onResult }) {
  const [src, setSrc] = useState(null);
  const [op, setOp] = useState(OPS[0]);
  const [vals, setVals] = useState({});
  const { state, run, busy } = useJobRunner();

  const setVal = (k, v) => setVals((p) => ({ ...p, [k]: v }));

  const submit = async () => {
    if (!src) return;
    const fields = { path: src.path };
    for (const [k, , def] of op.fields) fields[k] = vals[k] ?? def;
    try {
      const result = await run(postForm(`/api/video/${op.id}`, fields));
      onResult({ title: `Video · ${op.label}`, ...result });
    } catch (e) {
      /* shown in progress bar */
    }
  };

  return (
    <div className="tab-body">
      <h2>Edit video (local · ffmpeg)</h2>
      <Uploader accept="video/*" label="Upload a video" onUploaded={setSrc} />
      {src && (
        <video className="preview" src={fileUrl(src.path)} controls />
      )}

      <div className="op-grid">
        {OPS.map((o) => (
          <button
            key={o.id}
            className={op.id === o.id ? "op active" : "op"}
            onClick={() => {
              setOp(o);
              setVals({});
            }}
          >
            {o.label}
          </button>
        ))}
      </div>

      {op.fields.length > 0 && (
        <div className="row wrap">
          {op.fields.map(([k, label, def]) => (
            <div className="field" key={k}>
              <label>{label}</label>
              <input
                value={vals[k] ?? def}
                onChange={(e) => setVal(k, e.target.value)}
              />
            </div>
          ))}
        </div>
      )}

      <button className="primary" disabled={busy || !src} onClick={submit}>
        {busy ? "Rendering…" : `Run ${op.label}`}
      </button>
      <ProgressBar state={state} />
    </div>
  );
}
