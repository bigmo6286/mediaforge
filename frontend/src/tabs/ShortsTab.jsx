import React, { useState } from "react";
import { postForm } from "../api.js";
import Uploader from "../components/Uploader.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import useJobRunner from "../components/useJobRunner.js";

// Languages faster-whisper (large-v3) supports well enough to force. "auto"
// lets Whisper detect. Igbo / Nigerian Pidgin aren't reliably supported by
// vanilla Whisper — see the hint below.
const LANGUAGES = [
  ["", "Auto-detect"],
  ["en", "English"],
  ["yo", "Yoruba"],
  ["ha", "Hausa"],
  ["sw", "Swahili"],
  ["am", "Amharic"],
  ["so", "Somali"],
  ["sn", "Shona"],
  ["af", "Afrikaans"],
];

// Turn a long uploaded video into captioned vertical shorts. Main use:
// Nigerian / African-language content.
export default function ShortsTab({ providers, onResult }) {
  const [video, setVideo] = useState(null);
  const [clipSeconds, setClipSeconds] = useState(45);
  const [language, setLanguage] = useState("");
  const [vertical, setVertical] = useState(true);
  const [captions, setCaptions] = useState(true);
  const [maxShorts, setMaxShorts] = useState(0);
  const [summary, setSummary] = useState(null);
  const { state, run, busy } = useJobRunner();

  const submit = async () => {
    if (!video) return;
    setSummary(null);
    try {
      const res = await run(
        postForm("/api/generate/shorts", {
          path: video.path,
          clip_seconds: clipSeconds,
          vertical,
          captions,
          language,
          max_shorts: maxShorts,
        })
      );
      const shorts = res?.shorts || [];
      shorts.forEach((s, i) =>
        onResult({
          title: `Short ${i + 1} · ${s.duration}s · ${s.language} — ${(s.text || "").slice(0, 40)}…`,
          output: s.output,
        })
      );
      setSummary({ count: shorts.length, language: res?.language });
    } catch (e) {
      /* surfaced in progress bar */
    }
  };

  return (
    <div className="tab-body">
      <h2>Video → captioned shorts</h2>
      <p className="muted">
        Upload a long video and get vertical, captioned short clips — built for
        Nigerian &amp; African-language content. Speech is transcribed on the GPU
        with Whisper; the transcript is split into clips at sentence boundaries.
      </p>

      <div className="field">
        <label>1 · Source video</label>
        <Uploader accept="video/*" label="Upload a video (mp4/mov/webm)" onUploaded={setVideo} />
        {video && <div className="ok">✓ {video.name}</div>}
      </div>

      <div className="field">
        <label>2 · Spoken language</label>
        <select value={language} onChange={(e) => setLanguage(e.target.value)}>
          {LANGUAGES.map(([id, label]) => (
            <option key={id || "auto"} value={id}>
              {label}
            </option>
          ))}
        </select>
        <p className="hint">
          Forcing the language is more accurate than auto-detect. Whisper handles
          Yoruba, Hausa, Swahili &amp; more, but <b>Igbo and Nigerian Pidgin are
          weak</b> — for those, set <code>WHISPER_MODEL</code> to a fine-tuned
          model or Meta MMS.
        </p>
      </div>

      <div className="row">
        <div className="field" style={{ marginBottom: 0 }}>
          <label>3 · Clip length: {clipSeconds}s</label>
          <input
            type="range"
            min={15}
            max={90}
            step={5}
            value={clipSeconds}
            onChange={(e) => setClipSeconds(Number(e.target.value))}
          />
        </div>
        <div className="field" style={{ marginBottom: 0, flex: "0 0 auto" }}>
          <label>Max shorts (0 = all)</label>
          <input
            type="number"
            min={0}
            max={50}
            value={maxShorts}
            onChange={(e) => setMaxShorts(Number(e.target.value))}
            style={{ width: 90 }}
          />
        </div>
      </div>

      <div className="row" style={{ marginTop: 10 }}>
        <label className="check">
          <input type="checkbox" checked={vertical} onChange={(e) => setVertical(e.target.checked)} />
          Reframe to 9:16 vertical
        </label>
        <label className="check">
          <input type="checkbox" checked={captions} onChange={(e) => setCaptions(e.target.checked)} />
          Burn in captions
        </label>
      </div>

      <button className="primary" disabled={busy || !video} onClick={submit}>
        {busy ? "Making shorts…" : "✂️ Make shorts"}
      </button>

      {summary && (
        <p className="hint">
          Made <b>{summary.count}</b> short{summary.count === 1 ? "" : "s"} · detected
          language: <b>{summary.language}</b>. They're in the Results panel →
        </p>
      )}
      <ProgressBar state={state} />
    </div>
  );
}
