// Thin client for the MediaForge API. All calls go through the Vite proxy.

export async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/upload", { method: "POST", body: fd });
  if (!r.ok) throw new Error((await r.json()).detail || "upload failed");
  return r.json();
}

export async function postForm(url, fields) {
  const fd = new FormData();
  for (const [k, v] of Object.entries(fields)) fd.append(k, v);
  const r = await fetch(url, { method: "POST", body: fd });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `request failed (${r.status})`);
  return data;
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
