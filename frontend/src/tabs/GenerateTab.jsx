import React, { useState } from "react";
import { postForm } from "../api.js";
import Uploader from "../components/Uploader.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import useJobRunner from "../components/useJobRunner.js";

// Motion generation: text/image -> video, with a choice of base model and a
// target duration. Above ~6s the backend auto-chains segments to reach length.
export default function GenerateTab({ providers, onResult }) {
  const [mode, setMode] = useState("t2v"); // t2v | i2v
  const [prompt, setPrompt] = useState(
    "a cinematic drone shot flying over misty mountains at sunrise, 4k"
  );
  const [negative, setNegative] = useState("blurry, low quality, distorted");
  const [model, setModel] = useState("ltx");
  const [seconds, setSeconds] = useState(15);
  const [image, setImage] = useState(null);
  const { state, run, busy } = useJobRunner();

  const chained = seconds > 6;

  const submit = async () => {
    try {
      let result;
      if (mode === "t2v") {
        result = await run(
          postForm("/api/generate/t2v", {
            prompt,
            negative_prompt: negative,
            model,
            target_seconds: seconds,
          })
        );
      } else {
        if (!image) return;
        result = await run(
          postForm("/api/generate/i2v", {
            prompt,
            path: image.path,
            model,
            target_seconds: seconds,
          })
        );
      }
      onResult({ title: `${model.toUpperCase()} ${mode} · ${seconds}s`, ...result });
    } catch (e) {
      /* surfaced via progress bar */
    }
  };

  const motion = providers?.motion;

  return (
    <div className="tab-body">
      <h2>Generate motion video</h2>
      <p className="muted">
        Text→Video or Image→Video with open-source models. <b>LTX-Video</b> is
        efficient enough to run on a free GPU; longer clips are built by chaining
        segments automatically.
      </p>

      <div className="seg">
        <button className={mode === "t2v" ? "seg-btn active" : "seg-btn"} onClick={() => setMode("t2v")}>
          Text → Video
        </button>
        <button className={mode === "i2v" ? "seg-btn active" : "seg-btn"} onClick={() => setMode("i2v")}>
          Image → Video
        </button>
      </div>

      {mode === "i2v" && (
        <div className="field">
          <label>Source image</label>
          <Uploader accept="image/*" label="Upload a starting image" onUploaded={setImage} />
        </div>
      )}

      <div className="field">
        <label>Prompt</label>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} />
      </div>
      <div className="field">
        <label>Negative prompt</label>
        <input value={negative} onChange={(e) => setNegative(e.target.value)} />
      </div>

      <div className="row wrap">
        <div className="field">
          <label>Base model</label>
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="ltx">LTX-Video (efficient · free-GPU)</option>
            <option value="wan">Wan 2.1/2.2</option>
          </select>
        </div>
        <div className="field">
          <label>Duration: <b>{seconds}s</b>{chained && <span className="pill">chained</span>}</label>
          <input
            type="range"
            min={3}
            max={30}
            step={1}
            value={seconds}
            onChange={(e) => setSeconds(Number(e.target.value))}
          />
        </div>
      </div>

      <button className="primary" disabled={busy || (mode === "i2v" && !image)} onClick={submit}>
        {busy ? "Generating…" : `Generate ${seconds}s video`}
      </button>

      {chained && (
        <p className="hint">
          {seconds}s is built from {Math.ceil(seconds / (motion?.segment_seconds || 5))} chained
          segments (last frame of each seeds the next), then trimmed to length.
        </p>
      )}
      {motion && (
        <p className="hint">
          Model: <code>{motion.model}</code> · provider <b>{motion.provider}</b>
        </p>
      )}
      <ProgressBar state={state} />
    </div>
  );
}
