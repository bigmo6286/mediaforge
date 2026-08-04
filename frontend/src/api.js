// Thin client for the MediaForge API. All calls go through the Vite proxy.

// Parse a JSON response defensively. An empty body (0 bytes) or non-JSON text
// used to blow up as "Failed to execute 'json' on 'Response': unexpected end of
// json input" — on Colab that empty body is usually the kernel proxy dropping
// an oversized request. Surface a real, actionable message instead.
async function parseJson(r, action) {
  const text = await r.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      /* non-JSON body (e.g. an HTML/plaintext error page) */
    }
  }
  if (!r.ok) {
    const detail = data && data.detail;
    throw new Error(
      (typeof detail === "string" && detail) ||
        text ||
        `${action} failed (HTTP ${r.status})`
    );
  }
  if (data == null) {
    throw new Error(
      `${action}: the server returned an empty response (HTTP ${r.status}). ` +
        `On Colab this usually means the file is too large for the proxy — ` +
        `try a smaller image (under ~2 MB).`
    );
  }
  return data;
}

// Large images can exceed Colab's kernel-proxy request-size limit, which makes
// the upload return an empty body. Downscale big images in the browser first;
// small files and non-images pass through untouched.
export async function maybeDownscaleImage(
  file,
  maxDim = 1600,
  maxBytes = 1.8 * 1024 * 1024
) {
  if (!file.type.startsWith("image/") || file.type === "image/gif") return file;
  if (file.size <= maxBytes) return file;
  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    return file; // unsupported — let the server/proxy deal with it
  }
  const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
  const w = Math.max(1, Math.round(bitmap.width * scale));
  const h = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  canvas.getContext("2d").drawImage(bitmap, 0, 0, w, h);
  const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.9));
  if (!blob) return file;
  const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
  return new File([blob], name, { type: "image/jpeg" });
}

export async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  return parseJson(r, "upload");
}

export async function postForm(url, fields) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  const r = await fetch(url, { method: "POST", body: fd });
  return parseJson(r, "request");
}

export async function getJob(id) {
  const r = await fetch(`/api/jobs/${id}`);
  return r.json();
}

export async function getProviders() {
  const r = await fetch("/api/generate/providers");
  return r.json();
}

export async function getSettings() {
  const r = await fetch("/api/settings");
  return r.json();
}

export async function saveSettings(fields) {
  return postForm("/api/settings", fields);
}

// Poll a job until it finishes; onTick(job) is called on each update.
export function pollJob(id, onTick) {
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const job = await getJob(id);
        onTick && onTick(job);
        if (job.status === "done") return resolve(job);
        if (job.status === "error") return reject(new Error(job.error || "job failed"));
        setTimeout(tick, 1200);
      } catch (e) {
        reject(e);
      }
    };
    tick();
  });
}

export const fileUrl = (rel) => `/files/${rel}`;
