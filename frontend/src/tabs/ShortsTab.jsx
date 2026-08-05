import React, { useState } from "react";
import { postForm, importServerFile } from "../api.js";
import Uploader from "../components/Uploader.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import useJobRunner from "../components/useJobRunner.js";

// Each option carries its ASR engine + language code. Whisper (large-v3) auto-
// detects and covers many languages; MMS (Meta, 1000+ langs, ISO-639-3 codes)
// is the better choice for Igbo / Nigerian Pidgin, which vanilla Whisper botches.
// Shape: [value, label, engine, code].
const LANGUAGES = [
  ["auto", "Auto-detect (Whisper)", "whisper", ""],
  ["w:en", "English (Whisper)", "whisper", "en"],
  ["w:yo", "Yoruba (Whisper)", "whisper", "yo"],
  ["w:ha", "Hausa (Whisper)", "whisper", "ha"],
  ["w:sw", "Swahili (Whisper)", "whisper", "sw"],
  ["w:am", "Amharic (Whisper)", "whisper", "am"],
  ["w:so", "Somali (Whisper)", "whisper", "so"],
  ["w:sn", "Shona (Whisper)", "whisper", "sn"],
  ["w:af", "Afrikaans (Whisper)", "whisper", "af"],
  // MMS — best for Nigerian languages Whisper struggles with.
  ["m:ibo", "Igbo (MMS)", "mms", "ibo"],
  ["m:pcm", "Nigerian Pidgin (MMS)", "mms", "pcm"],
  ["m:yor", "Yoruba (MMS)", "mms", "yor"],
  ["m:hau", "Hausa (MMS)", "mms", "hau"],
  ["m:swh", "Swahili (MMS)", "mms", "swh"],
  ["m:eng", "English (MMS)", "mms", "eng"],
];

// Turn a long uploaded video into captioned vertical shorts. Main use:
// Nigerian / African-language content.
export default function ShortsTab({ providers, onResult }) {
  const [video, setVideo] = useState(null);
  const [serverPath, setServerPath] = useState("");
  const [importErr, setImportErr] = useState(null);
  const [importing, setImporting] = useState(false);
  const [clipSeconds, setClipSeconds] = useState(45);
  const [langValue, setLangValue] = useState("auto");
  const [vertical, setVertical] = useState(true);
  const [captions, setCaptions] = useState(true);
  const [maxShorts, setMaxShorts] = useState(0);
  const [summary, setSummary] = useState(null);
  const { state, run, busy } = useJobRunner();

  const useServerFile = async () => {
    const p = serverPath.trim();
    if (!p) return;
    setImporting(true);
    setImportErr(null);
    try {
      const res = await importServerFile(p);
      setVideo(res);
    } catch (e) {
      setImportErr(e.message);
    } finally {
      setImporting(false);
    }
  };

  const submit = async () => {
    if (!video) return;
    setSummary(null);
    const opt = LANGUAGES.find((l) => l[0] === langValue) || LANGUAGES[0];
    const [, , engine, code] = opt;
    try {
      const res = await run(
        postForm("/api/generate/shorts", {
          path: video.path,
          clip_seconds: clipSeconds,
          vertical,
          captions,
          language: code,
          engine,
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

        <div className="muted" style={{ margin: "10px 0 6px", fontSize: 13 }}>
          — or, for a <b>large / multi-GB video</b>, point to a file already on
          the server —
        </div>
        <div className="row" style={{ alignItems: "stretch" }}>
          <input
            type="text"
            value={serverPath}
            placeholder="/content/drive/MyDrive/MediaForge/uploads/my-video.mp4"
            onChange={(e) => setServerPath(e.target.value)}
            style={{ flex: 1 }}
          />
          <button className="ghost" disabled={importing || !serverPath.trim()} onClick={useServerFile}>
            {importing ? "Loading…" : "Use file"}
          </button>
        </div>
        <p className="hint">
          Browser upload can't reliably move a multi-GB file through Colab.
          Instead put the video on your <b>mounted Google Drive</b> (run notebook
          cell 3) or anywhere on the Colab VM, then paste its full path here.
        </p>
        {importErr && <div className="err">{importErr}</div>}
        {video && <div className="ok">✓ {video.name}</div>}
      </div>

      <div className="field">
        <label>2 · Spoken language</label>
        <select value={langValue} onChange={(e) => setLangValue(e.target.value)}>
          {LANGUAGES.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <p className="hint">
          Forcing the language beats auto-detect. Whisper handles Yoruba, Hausa,
          Swahili &amp; more; for <b>Igbo and Nigerian Pidgin</b> pick an
          <b> (MMS)</b> option — Meta MMS covers those far better. First MMS run
          downloads the model (~3 GB) and the language adapter.
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
