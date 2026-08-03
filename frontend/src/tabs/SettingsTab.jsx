import React, { useEffect, useState } from "react";
import { getSettings, saveSettings } from "../api.js";

// Add API keys and pick the hosted-GPU provider, with hints + get-key links.
export default function SettingsTab({ onSaved }) {
  const [settings, setSettings] = useState(null);
  const [values, setValues] = useState({}); // only fields the user typed
  const [provider, setProvider] = useState("fal");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = () =>
    getSettings().then((s) => {
      setSettings(s);
      setProvider(s.provider || "fal");
    });
  useEffect(() => {
    load();
  }, []);

  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      const fields = { provider, ...values };
      await saveSettings(fields);
      setValues({});
      await load();
      onSaved && (await onSaved()); // refresh header/tabs
      setMsg({ ok: true, text: "Saved. Changes are live — no restart needed." });
    } catch (e) {
      setMsg({ ok: false, text: e.message });
    } finally {
      setSaving(false);
    }
  };

  if (!settings) return <div className="tab-body">Loading settings…</div>;

  return (
    <div className="tab-body">
      <h2>Settings</h2>
      <p className="muted">
        Keys are written to <code>backend/.env</code> on this machine (git-ignored,
        never uploaded) and applied immediately.
      </p>

      <div className="settings-card">
        <div className="settings-row">
          <span>This machine</span>
          <b>
            {settings.has_gpu
              ? `⚡ ${settings.gpu_name || "GPU"} · ${settings.vram_gb} GB`
              : "🖥 CPU only"}
          </b>
        </div>
        {settings.has_gpu && settings.gpu_ok_for_heavy && (
          <p className="hint" style={{ marginTop: 0 }}>
            Enough VRAM to run everything locally (free, no keys). You can still add
            a key to offload to a hosted GPU.
          </p>
        )}
        {settings.has_gpu && !settings.gpu_ok_for_heavy && (
          <p className="hint" style={{ marginTop: 0 }}>
            Your GPU runs <b>face swap &amp; restore</b> locally, but it's too small
            for local <b>video/avatar generation</b> — those use a hosted provider
            or the free Colab GPU. Add a key below, or see <code>colab/</code>.
          </p>
        )}
        {!settings.has_gpu && (
          <p className="hint" style={{ marginTop: 0 }}>
            No GPU detected — generation uses a hosted provider (add a key below) or
            the free Colab GPU. Local voice and editing work with no key.
          </p>
        )}
      </div>

      <div className="field">
        <label>Hosted-GPU provider</label>
        <div className="seg">
          {["fal", "replicate"].map((p) => (
            <button
              key={p}
              className={provider === p ? "seg-btn active" : "seg-btn"}
              onClick={() => setProvider(p)}
            >
              {p}
            </button>
          ))}
        </div>
        <p className="hint" style={{ marginTop: 0 }}>
          Which service runs the heavy models when not using a local GPU. Applies to
          motion, avatar, face-swap, try-on and restore.
        </p>
      </div>

      {settings.fields.map((f) => {
        const cur = settings.keys[f.key];
        return (
          <div className="field" key={f.key}>
            <label>
              {f.label}
              {cur?.set ? (
                <span className="pill">saved · {cur.masked}</span>
              ) : (
                <span className="pill warn-pill">not set</span>
              )}
            </label>
            <input
              type="password"
              placeholder={cur?.set ? "•••••••• (leave blank to keep)" : "paste your key here"}
              value={values[f.key] || ""}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              autoComplete="off"
            />
            <p className="hint">
              {f.hint}{" "}
              <a href={f.link} target="_blank" rel="noreferrer" className="getkey">
                Get {f.label} ↗
              </a>
            </p>
          </div>
        );
      })}

      <button className="primary" onClick={save} disabled={saving}>
        {saving ? "Saving…" : "Save settings"}
      </button>
      {msg && (
        <p className={msg.ok ? "save-ok" : "err"} style={{ marginTop: 12 }}>
          {msg.ok ? "✓ " : "⚠ "}
          {msg.text}
        </p>
      )}

      <div className="colab-card">
        <div className="settings-row">
          <span><b>Free GPU via Google Colab</b></span>
          <a
            className="colab-btn"
            href="https://colab.research.google.com/github/bigmo6286/mediaforge/blob/main/colab/MediaForge_FreeGPU.ipynb"
            target="_blank"
            rel="noreferrer"
          >
            Open in Colab ↗
          </a>
        </div>
        <p className="hint" style={{ marginTop: 8 }}>
          No key, no local GPU needed — run motion generation on Colab's free T4:
        </p>
        <ol className="colab-steps">
          <li>Click <b>Open in Colab</b> above.</li>
          <li>Enable the GPU: <b>Runtime → Change runtime type → GPU → Save</b>.</li>
          <li>Run each cell top to bottom (Shift+Enter). The last cell prints a link.</li>
          <li>Click that link to open MediaForge, go to <b>Motion</b>, and Generate.</li>
        </ol>
        <p className="hint">
          Talking-avatar generation needs a hosted key above (or SadTalker setup);
          motion, voice and editing are free.
        </p>
      </div>

      <p className="hint" style={{ marginTop: 16 }}>
        Local voice (Piper) and all editing already work with no key.
      </p>
    </div>
  );
}
