import React, { useEffect, useState } from "react";
import { postForm, fileUrl, pollJob } from "../api.js";
import Uploader from "../components/Uploader.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import useJobRunner from "../components/useJobRunner.js";

// Friendly labels for known Piper voice ids; unknown ids show their raw name.
const PIPER_LABELS = {
  "en_US-amy-medium": "Amy — US female",
  "en_US-ryan-high": "Ryan — US male",
  "en_US-lessac-medium": "Lessac — US neutral",
  "en_GB-alba-medium": "Alba — British female",
};

// Hosted (Kokoro) voices, used when TTS runs on fal/replicate.
const KOKORO_VOICES = [
  ["af_heart", "Warm female (af_heart)"],
  ["af_bella", "Bright female (af_bella)"],
  ["am_michael", "Male (am_michael)"],
  ["am_adam", "Deep male (am_adam)"],
  ["bf_emma", "British female (bf_emma)"],
];

// The headline feature: one photo -> a talking presenter video for UGC ads,
// tutorials, and virtual-presenter clips. Voice comes from a typed script
// (TTS) or an uploaded audio file.
export default function AvatarTab({ providers, onResult }) {
  const [portrait, setPortrait] = useState(null);
  const [voiceMode, setVoiceMode] = useState("script"); // script | audio
  const [script, setScript] = useState(
    "Hey everyone! Welcome back to the channel. Today I'll show you exactly how to get started — it only takes a couple of minutes."
  );
  const [audio, setAudio] = useState(null);
  const [voice, setVoice] = useState("");
  const { state, run, busy } = useJobRunner();

  const av = providers?.avatar;
  const tts = providers?.tts;
  const usingPiper = tts?.provider === "piper" && tts?.voices?.length > 0;

  // Build the voice options for whichever TTS backend is active.
  const voiceOptions = usingPiper
    ? tts.voices.map((v) => [v, PIPER_LABELS[v] || v])
    : KOKORO_VOICES;

  // Default the selection to the first available voice once providers load.
  useEffect(() => {
    if (!voice && voiceOptions.length) setVoice(voiceOptions[0][0]);
  }, [voiceOptions, voice]);

  // --- Preview voice: synthesize the script and play it before rendering ---
  const [preview, setPreview] = useState(null); // audio url
  const [previewing, setPreviewing] = useState(false);
  const [previewErr, setPreviewErr] = useState(null);

  const previewVoice = async () => {
    if (!script.trim()) return;
    setPreviewing(true);
    setPreviewErr(null);
    setPreview(null);
    try {
      const { job_id } = await postForm("/api/generate/tts", { text: script, voice });
      const job = await pollJob(job_id);
      setPreview(fileUrl(job.result.output));
    } catch (e) {
      setPreviewErr(e.message);
    } finally {
      setPreviewing(false);
    }
  };

  const submit = async () => {
    if (!portrait) return;
    const fields = { image: portrait.path, voice };
    if (voiceMode === "audio") {
      if (!audio) return;
      fields.audio = audio.path;
    } else {
      if (!script.trim()) return;
      fields.script = script;
    }
    try {
      const result = await run(postForm("/api/generate/avatar", fields));
      onResult({ title: `Talking avatar: ${(script || audio?.name || "").slice(0, 36)}…`, ...result });
    } catch (e) {
      /* surfaced in progress bar */
    }
  };

  const canSubmit =
    portrait && (voiceMode === "audio" ? !!audio : !!script.trim());

  return (
    <div className="tab-body">
      <h2>Photo → talking video</h2>
      <p className="muted">
        Turn a single portrait into a lip-synced presenter — perfect for UGC ads,
        video tutorials, and virtual-presenter clips. Powered by open-source avatar
        models (SadTalker / Hallo / Wan2.2-S2V).
      </p>

      <div className="field">
        <label>1 · Portrait photo (front-facing works best)</label>
        <Uploader accept="image/*" label="Upload a face photo" onUploaded={setPortrait} />
        {portrait && <img className="preview" src={fileUrl(portrait.path)} alt="portrait" />}
      </div>

      <div className="field">
        <label>2 · Voice</label>
        <div className="seg">
          <button
            className={voiceMode === "script" ? "seg-btn active" : "seg-btn"}
            onClick={() => setVoiceMode("script")}
          >
            Write a script
          </button>
          <button
            className={voiceMode === "audio" ? "seg-btn active" : "seg-btn"}
            onClick={() => setVoiceMode("audio")}
          >
            Upload audio
          </button>
        </div>

        {voiceMode === "script" ? (
          <>
            <textarea
              rows={4}
              value={script}
              onChange={(e) => setScript(e.target.value)}
              placeholder="What should the avatar say?"
            />
            <div className="row" style={{ marginTop: 10 }}>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>
                  Voice
                  {usingPiper && <span className="pill">local · free</span>}
                </label>
                <select value={voice} onChange={(e) => setVoice(e.target.value)}>
                  {voiceOptions.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field" style={{ marginBottom: 0, flex: "0 0 auto" }}>
                <label>&nbsp;</label>
                <button className="secondary" onClick={previewVoice} disabled={previewing || !script.trim()}>
                  {previewing ? "…" : "▶ Preview voice"}
                </button>
              </div>
            </div>
            {preview && (
              <audio controls autoPlay src={preview} style={{ width: "100%", marginTop: 10 }} />
            )}
            {previewErr && <div className="err">{previewErr}</div>}
          </>
        ) : (
          <>
            <Uploader
              accept="audio/*"
              label="Upload a voice recording (mp3/wav)"
              onUploaded={setAudio}
            />
            {audio && <audio controls src={fileUrl(audio.path)} style={{ width: "100%" }} />}
          </>
        )}
      </div>

      <button className="primary" disabled={busy || !canSubmit} onClick={submit}>
        {busy ? "Rendering avatar…" : "🎬 Create talking video"}
      </button>

      {av && (
        <p className="hint">
          Avatar model: <code>{av[av.provider] || av.provider}</code> via{" "}
          <b>{av.provider}</b>
          {providers?.tts && (
            <>
              {" · "}TTS: <b>{providers.tts.provider}</b>
              {providers.tts.provider === "piper" && !providers.tts.piper_configured
                ? " (set PIPER_MODEL)"
                : ""}
            </>
          )}
        </p>
      )}
      <ProgressBar state={state} />
    </div>
  );
}
