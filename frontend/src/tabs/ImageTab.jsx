import React, { useState } from "react";
import { postForm, fileUrl } from "../api.js";
import Uploader from "../components/Uploader.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import useJobRunner from "../components/useJobRunner.js";

const OPS = [
  { id: "rembg", label: "Remove background", fields: [] },
  { id: "resize", label: "Resize", fields: [["a", "Target width", 800]] },
  { id: "convert", label: "Convert", fields: [["fmt", "Format (png/jpg/webp)", "webp"]] },
];

export default function ImageTab({ onResult }) {
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
      const result = await run(postForm(`/api/image/${op.id}`, fields));
      onResult({ title: `Image · ${op.label}`, ...result });
    } catch (e) {
      /* shown in progress bar */
    }
  };

  return (
    <div className="tab-body">
      <h2>Edit image (local)</h2>
      <Uploader accept="image/*" label="Upload an image" onUploaded={setSrc} />
      {src && <img className="preview" src={fileUrl(src.path)} alt="source" />}

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
        {busy ? "Processing…" : `Run ${op.label}`}
      </button>
      {op.id === "rembg" && (
        <p className="hint">
          Needs <code>rembg</code>: <code>pip install rembg onnxruntime</code> (first
          run downloads the model).
        </p>
      )}
      <ProgressBar state={state} />
    </div>
  );
}
