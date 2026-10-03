import React, { useRef, useState } from "react";
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
  const [viral, setViral] = useState(false);
  // "" = auto: Claude when a key is saved, otherwise acoustic scoring.
  const [picker, setPicker] = useState("");
  const [summary, setSummary] = useState(null);
  const claudeReady = !!providers?.claude?.configured;
  const claudeModel = providers?.claude?.model || "Claude";
  const effectivePicker = picker || (claudeReady ? "claude" : "acoustic");
  const { state, run, busy } = useJobRunner();
  // Tracks which shorts we've already pushed to the Results panel, so streaming
  // them live (as each renders) and the final result don't create duplicates.
  const seen = useRef(new Set());

  const emitShorts = (shorts) => {
    (shorts || []).forEach((s) => {
      if (!s?.output || seen.current.has(s.output)) return;
      seen.current.add(s.output);
      const tag = s.score != null ? `🔥 ${s.score} · ` : "";
      const label = s.title
        ? `${s.duration}s · ${s.title}`
        : `${s.duration}s · ${s.language} — ${(s.text || "").slice(0, 40)}…`;
      onResult({ title: `${tag}${label}`, output: s.output });
    });
  };

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
    seen.current = new Set();
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
          viral,
          picker: viral ? effectivePicker : "",
        }),
        // Stream each short into the Results panel the moment it's rendered, so
        // a runtime timeout can't cost you the clips already finished.
        (job) => emitShorts(job.partial?.shorts)
      );
      emitShorts(res?.shorts);
      setSummary({
        count: (res?.shorts || []).length,
        language: res?.language,
        picker: res?.picker,
        pickerError: res?.picker_error,
      });
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
        <label className="check">
          <input type="checkbox" checked={viral} onChange={(e) => setViral(e.target.checked)} />
          🔥 Pick the most viral moments
        </label>
      </div>
      {viral && (
        <div className="field" style={{ marginTop: 10 }}>
          <label>Pick moments with</label>
          <div className="seg">
            {[
              ["claude", "Claude (reads the transcript)"],
              ["acoustic", "Acoustic (energy & pace)"],
            ].map(([value, label]) => (
              <button
                key={value}
                className={effectivePicker === value ? "seg-btn active" : "seg-btn"}
                onClick={() => setPicker(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {effectivePicker === "claude" ? (
            <p className="hint" style={{ marginTop: 0 }}>
              <b>{claudeModel}</b> reads the whole transcript and picks the clips
              with the strongest hook and payoff, cutting at sentence boundaries, and
              writes a title for each. Delivery energy is passed along as a hint.
              {!claudeReady && (
                <>
                  {" "}
                  <b>No Anthropic key is saved</b> — add one in ⚙ Settings, or the
                  run will fall back to acoustic scoring.
                </>
              )}
            </p>
          ) : (
            <p className="hint" style={{ marginTop: 0 }}>
              Scores every candidate clip by energy, delivery and pace, with no
              API key needed. Works in any language but can't judge what is
              being said.
            </p>
          )}
        </div>
      )}
      <p className="hint">
        With <b>viral moments</b> on, only the strongest clips are kept — the
        number set by <b>Max shorts</b> (or the top 10 if that's 0). Each result
        shows its score. Off = sequential clips covering the whole video.
      </p>

      <button className="primary" disabled={busy || !video} onClick={submit}>
        {busy ? "Making shorts…" : "✂️ Make shorts"}
      </button>

      <p className="hint">
        Clips appear in Results as each one finishes — so if the Colab runtime
        times out mid-run, everything already rendered is kept (and saved to
        Google Drive if you ran notebook cell 3).
      </p>

      {summary && (
        <p className="hint">
          Made <b>{summary.count}</b> short{summary.count === 1 ? "" : "s"} · detected
          language: <b>{summary.language}</b>
          {summary.picker && (
            <>
              {" "}· picked by <b>{summary.picker}</b>
            </>
          )}
          . They're in the Results panel →
        </p>
      )}
      {summary?.pickerError && (
        <div className="err">
          Claude couldn't pick the moments ({summary.pickerError}) — acoustic
          scoring was used instead.
        </div>
      )}
      <ProgressBar state={state} />
    </div>
  );
}
