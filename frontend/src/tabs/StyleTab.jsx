import React, { useState } from "react";
import { postForm, fileUrl } from "../api.js";
import Uploader from "../components/Uploader.jsx";
import ProgressBar from "../components/ProgressBar.jsx";
import useJobRunner from "../components/useJobRunner.js";

// Face swap (change the face in a photo) + virtual try-on (change the outfit).
export default function StyleTab({ providers, onResult }) {
  const [mode, setMode] = useState("face"); // face | dress
  return (
    <div className="tab-body">
      <h2>Face &amp; wardrobe</h2>
      <div className="seg">
        <button className={mode === "face" ? "seg-btn active" : "seg-btn"} onClick={() => setMode("face")}>
          Face swap
        </button>
        <button className={mode === "dress" ? "seg-btn active" : "seg-btn"} onClick={() => setMode("dress")}>
          Dress change
        </button>
      </div>
      {mode === "face" ? (
        <FaceSwap providers={providers} onResult={onResult} />
      ) : (
        <DressChange providers={providers} onResult={onResult} />
      )}
    </div>
  );
}

const isVideoPath = (p) => /\.(mp4|mov|mkv|webm|avi)$/i.test(p || "");

function FaceSwap({ providers, onResult }) {
  const [target, setTarget] = useState(null); // photo OR video whose face is replaced
  const [face, setFace] = useState(null); // face to insert
  const { state, run, busy } = useJobRunner();

  const targetIsVideo = isVideoPath(target?.path);

  const submit = async () => {
    if (!target || !face) return;
    try {
      const result = await run(
        postForm("/api/edit/faceswap", { target: target.path, source_face: face.path })
      );
      onResult({ title: targetIsVideo ? "Face swap (video)" : "Face swap", ...result });
    } catch (e) {
      /* shown in progress bar */
    }
  };

  return (
    <>
      <p className="muted">
        Replace the face in a <b>photo or video</b> with another face — swapped
        across every frame for video. Use it only on people who have consented.
      </p>
      <div className="row wrap">
        <div className="field">
          <label>Target photo or video (face gets replaced)</label>
          <Uploader accept="image/*,video/*" label="Upload a photo or video" onUploaded={setTarget} />
          {target &&
            (targetIsVideo ? (
              <video className="preview" src={fileUrl(target.path)} controls />
            ) : (
              <img className="preview" src={fileUrl(target.path)} alt="target" />
            ))}
        </div>
        <div className="field">
          <label>Face photo (identity to insert)</label>
          <Uploader accept="image/*" label="Upload the face" onUploaded={setFace} />
          {face && <img className="preview" src={fileUrl(face.path)} alt="face" />}
        </div>
      </div>
      <button className="primary" disabled={busy || !target || !face} onClick={submit}>
        {busy ? "Swapping…" : targetIsVideo ? "Swap face in video" : "Swap face"}
      </button>
      <p className="hint">
        Runs on <b>{providers?.faceswap?.provider}</b>
        {providers?.faceswap?.provider === "local" && !providers?.faceswap?.local_ready
          ? " · set INSWAPPER_MODEL to enable local"
          : ""}
        {targetIsVideo && providers?.faceswap?.provider === "local"
          ? " · video is processed frame-by-frame (slow on CPU)"
          : ""}
      </p>
      <ProgressBar state={state} />
    </>
  );
}

const CATEGORIES = [
  ["upper_body", "Top / upper body"],
  ["lower_body", "Bottoms / lower body"],
  ["dresses", "Dress / full outfit"],
];

function DressChange({ providers, onResult }) {
  const [person, setPerson] = useState(null);
  const [garment, setGarment] = useState(null);
  const [category, setCategory] = useState("upper_body");
  const [description, setDescription] = useState("");
  const { state, run, busy } = useJobRunner();

  const submit = async () => {
    if (!person || !garment) return;
    try {
      const result = await run(
        postForm("/api/edit/tryon", {
          person: person.path,
          garment: garment.path,
          category,
          description,
        })
      );
      onResult({ title: "Dress change", ...result });
    } catch (e) {
      /* shown in progress bar */
    }
  };

  return (
    <>
      <p className="muted">
        Virtual try-on: render a person wearing a different garment (open-source
        IDM-VTON). Needs a GPU — hosted by default on this machine.
      </p>
      <div className="row wrap">
        <div className="field">
          <label>Person photo</label>
          <Uploader accept="image/*" label="Upload the person" onUploaded={setPerson} />
          {person && <img className="preview" src={fileUrl(person.path)} alt="person" />}
        </div>
        <div className="field">
          <label>Garment photo</label>
          <Uploader accept="image/*" label="Upload the clothing item" onUploaded={setGarment} />
          {garment && <img className="preview" src={fileUrl(garment.path)} alt="garment" />}
        </div>
      </div>
      <div className="row wrap">
        <div className="field">
          <label>Garment type</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map(([id, label]) => (
              <option key={id} value={id}>{label}</option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Description (optional)</label>
          <input value={description} onChange={(e) => setDescription(e.target.value)}
                 placeholder="e.g. red floral summer dress" />
        </div>
      </div>
      <button className="primary" disabled={busy || !person || !garment} onClick={submit}>
        {busy ? "Rendering…" : "Change outfit"}
      </button>
      <p className="hint">Runs on <b>{providers?.tryon?.provider}</b></p>
      <ProgressBar state={state} />
    </>
  );
}
