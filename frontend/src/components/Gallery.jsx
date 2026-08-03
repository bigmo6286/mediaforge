import React from "react";
import { fileUrl } from "../api.js";

function isVideo(p) {
  return /\.(mp4|mov|mkv|webm|avi)$/i.test(p);
}
function isImage(p) {
  return /\.(png|jpe?g|webp|gif)$/i.test(p);
}
function isAudio(p) {
  return /\.(mp3|wav)$/i.test(p);
}

export default function Gallery({ results, onClear }) {
  return (
    <div className="gallery">
      <div className="gallery-head">
        <h3>Results</h3>
        {results.length > 0 && (
          <button className="link" onClick={onClear}>
            clear
          </button>
        )}
      </div>
      {results.length === 0 && (
        <p className="muted">Your rendered clips and images appear here.</p>
      )}
      {results.map((r, i) => {
        const out = r.output || r.result?.output;
        if (!out) {
          // e.g. extract-frames returns a folder listing
          return (
            <div className="result" key={i}>
              <div className="result-title">{r.title}</div>
              <div className="muted">{JSON.stringify(r.result || r)}</div>
            </div>
          );
        }
        const url = fileUrl(out);
        return (
          <div className="result" key={i}>
            <div className="result-title">{r.title}</div>
            {isVideo(out) && <video src={url} controls />}
            {isImage(out) && <img src={url} alt={r.title} />}
            {isAudio(out) && <audio src={url} controls />}
            <a className="download" href={url} download>
              ⬇ download
            </a>
          </div>
        );
      })}
    </div>
  );
}
