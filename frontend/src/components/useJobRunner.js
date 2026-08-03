import { useState } from "react";
import { pollJob } from "../api.js";

// Encapsulates: submit -> poll -> surface progress/error. Returns a `run`
// function you hand a promise that resolves to {job_id}.
export default function useJobRunner() {
  const [state, setState] = useState({ status: "idle", progress: 0, message: "" });

  const run = async (submitPromise) => {
    setState({ status: "submitting", progress: 0, message: "submitting…" });
    try {
      const { job_id } = await submitPromise;
      if (!job_id) throw new Error("no job id returned");
      const job = await pollJob(job_id, (j) =>
        setState({ status: j.status, progress: j.progress, message: j.message })
      );
      setState({ status: "done", progress: 1, message: "complete" });
      return job.result;
    } catch (e) {
      setState({ status: "error", progress: 0, message: e.message });
      throw e;
    }
  };

  const busy = state.status === "submitting" || state.status === "running";
  return { state, run, busy };
}
