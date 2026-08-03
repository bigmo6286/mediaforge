import React, { useEffect, useState } from "react";
import { getProviders } from "./api.js";
import AvatarTab from "./tabs/AvatarTab.jsx";
import GenerateTab from "./tabs/GenerateTab.jsx";
import StyleTab from "./tabs/StyleTab.jsx";
import VideoTab from "./tabs/VideoTab.jsx";
import ImageTab from "./tabs/ImageTab.jsx";
import SettingsTab from "./tabs/SettingsTab.jsx";
import Gallery from "./components/Gallery.jsx";

const TABS = [
  { id: "avatar", label: "🎤 Talking Avatar" },
  { id: "generate", label: "✨ Motion (Wan)" },
  { id: "style", label: "🎭 Face & Wardrobe" },
  { id: "video", label: "🎬 Video Edit" },
  { id: "image", label: "🖼️ Image Edit" },
  { id: "settings", label: "⚙ Settings" },
];

export default function App() {
  const [tab, setTab] = useState("avatar");
  const [providers, setProviders] = useState(null);
  const [results, setResults] = useState([]); // {title, output, kind}

  const refreshProviders = () =>
    getProviders().then(setProviders).catch(() => setProviders(null));
  useEffect(() => {
    refreshProviders();
  }, []);

  const addResult = (r) => setResults((prev) => [r, ...prev]);

  const active = providers?.active;
  const configured =
    providers && active && providers[active] && providers[active].configured;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">▲</span> MediaForge
          <span className="tagline">open-source AI video &amp; image studio</span>
        </div>
        {providers && (
          <div className="badges">
            <div className={`provider-badge ${providers.has_gpu ? "ok" : ""}`}>
              {providers.has_gpu ? "⚡ GPU" : "🖥 CPU"}
            </div>
            <div className={`provider-badge ${active === "local" || configured ? "ok" : "warn"}`}>
              models → <b>{active}</b>
              {active === "local"
                ? " · on-device"
                : configured
                ? " · ready"
                : " · no API key"}
            </div>
          </div>
        )}
      </header>

      {providers && active !== "local" && !configured && (
        <div className="banner">
          No <b>{active}</b> API key detected. Video generation will error until you
          add one to <code>backend/.env</code>. Local editing works regardless.
        </div>
      )}

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? "tab active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="content">
        <section className="panel">
          {tab === "avatar" && (
            <AvatarTab providers={providers} onResult={addResult} />
          )}
          {tab === "generate" && (
            <GenerateTab providers={providers} onResult={addResult} />
          )}
          {tab === "style" && (
            <StyleTab providers={providers} onResult={addResult} />
          )}
          {tab === "video" && <VideoTab onResult={addResult} />}
          {tab === "image" && <ImageTab onResult={addResult} />}
          {tab === "settings" && <SettingsTab onSaved={refreshProviders} />}
        </section>

        <aside className="sidebar">
          <Gallery results={results} onClear={() => setResults([])} />
        </aside>
      </main>

      <footer className="foot">
        Runs locally · Wan is open-source (Wan-AI) · light ops on CPU, generation on
        GPU (hosted or local)
      </footer>
    </div>
  );
}
