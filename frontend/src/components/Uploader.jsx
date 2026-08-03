import React, { useRef, useState } from "react";
import { uploadFile } from "../api.js";

// Drag/drop or click-to-pick a file, uploads it, and reports {path,name,info}
// back to the parent via onUploaded.
export default function Uploader({ accept, label, onUploaded }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState(null);
  const [err, setErr] = useState(null);

  const handle = async (file) => {
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await uploadFile(file);
      setName(res.name);
      onUploaded(res);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="uploader"
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        handle(e.dataTransfer.files[0]);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        hidden
        onChange={(e) => handle(e.target.files[0])}
      />
      {busy ? (
        <span>Uploading…</span>
      ) : name ? (
        <span className="ok">✓ {name}</span>
      ) : (
        <span>{label || "Drop a file or click to upload"}</span>
      )}
      {err && <div className="err">{err}</div>}
    </div>
  );
}
