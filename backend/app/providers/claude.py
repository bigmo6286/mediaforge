"""Claude (Anthropic) provider — language-level judgment for MediaForge.

Claude does not render pixels or audio; the GPU providers do that. What it
adds is reading: given a transcript it decides which moments would make the
strongest shorts, and names them. Each feature here is one Messages API call
with a JSON schema on the output, so the rest of the pipeline gets typed data
back rather than prose to parse.
"""
from __future__ import annotations

import json

from .. import config
from ..jobs import JobProgress
from ._hosted import ProviderError

MIN_CLIP_SECONDS = 5.0

_SYSTEM = """You are a short-form video editor who cuts long videos into viral shorts for YouTube Shorts, TikTok and Instagram Reels. The channel's audience is largely Nigerian and African; transcripts may be in English, Nigerian Pidgin, Yoruba, Igbo, Hausa, Swahili or other languages, sometimes with transcription errors.

You receive a numbered transcript. Each line is one sentence-level segment with its start and end time in seconds and, when available, an energy score (0-100: how loud and expressive the delivery was).

Choose the moments most likely to be watched to the end and shared. A good short:
- opens on a hook in its first sentence (a bold claim, a question, a confession, a punchline, a number);
- is self-contained: it makes sense without the rest of the video and does not start mid-thought;
- delivers one clear idea, story beat or payoff;
- ends on a complete sentence, ideally a strong line or a call to action.

Rules:
- A clip is a contiguous run of segments, start_segment to end_segment inclusive.
- Clips must not overlap.
- Respect the duration limits in the request. Prefer clips near the target length; never exceed the maximum.
- Score each clip from 0 to 100 for viral potential. Be discriminating: reserve 85 and above for genuinely strong moments.
- Write the title in English, under 60 characters, as a hook rather than a summary. No hashtags, no emoji.
- 'why' is one short sentence on what makes the moment work.
- Return clips in order of start time. If the transcript has fewer strong moments than requested, return fewer."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_segment": {"type": "integer"},
                    "end_segment": {"type": "integer"},
                    "title": {"type": "string"},
                    "why": {"type": "string"},
                    "score": {"type": "integer"},
                },
                "required": ["start_segment", "end_segment", "title", "why", "score"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}


def _client():
    if not config.ANTHROPIC_API_KEY:
        raise ProviderError(
            "ANTHROPIC_API_KEY is not set. Add it in the Settings tab (or backend/.env).")
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise ProviderError("The anthropic package is missing. Run: pip install anthropic") from exc
    # The key is passed explicitly so one saved from the Settings tab applies
    # at once, without restarting the server.
    return anthropic, anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY,
                                          timeout=300.0, max_retries=2)


def _format_transcript(segs: list[dict], energy: list[float] | None) -> str:
    lines = []
    for i, s in enumerate(segs):
        e = f" energy={energy[i]:.0f}" if energy else ""
        text = " ".join(s["text"].split())
        lines.append(f"[{i}] {s['start']:.1f}-{s['end']:.1f}s{e}: {text}")
    return "\n".join(lines)


def pick_moments(segs: list[dict], *, target: float, max_len: float, keep: int,
                 language: str = "", energy: list[float] | None = None,
                 progress: JobProgress | None = None) -> list[dict]:
    """Ask Claude which transcript segments to cut into shorts.

    Returns a time-ordered list of {start_segment, end_segment, title, why,
    score}, validated against the transcript: indices in range, clips within
    the length limits, no overlaps, at most `keep` entries.
    """
    anthropic, client = _client()
    lang = f" The spoken language was detected as '{language}'." if language else ""
    user = (
        f"Pick up to {keep} clips. Target length about {target:.0f} seconds; "
        f"minimum {MIN_CLIP_SECONDS:.0f} seconds; maximum {max_len:.0f} seconds.{lang}\n\n"
        f"Transcript ({len(segs)} segments):\n{_format_transcript(segs, energy)}"
    )
    if progress:
        progress.update(0.18, f"asking {config.CLAUDE_MODEL} to pick the best moments")
    try:
        resp = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=16000,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "medium",
                           "format": {"type": "json_schema", "schema": _SCHEMA}},
        )
    except anthropic.AuthenticationError as exc:
        raise ProviderError(
            "Anthropic rejected the API key. Check ANTHROPIC_API_KEY in Settings.") from exc
    except anthropic.RateLimitError as exc:
        raise ProviderError("Anthropic rate limit reached. Wait a moment and retry.") from exc
    except anthropic.APIStatusError as exc:
        raise ProviderError(f"Anthropic API error ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise ProviderError(f"Could not reach the Anthropic API: {exc}") from exc

    if resp.stop_reason == "refusal":
        details = getattr(resp, "stop_details", None)
        why = getattr(details, "explanation", "") or "no reason given"
        raise ProviderError(f"Claude declined to process this transcript: {why}")
    if resp.stop_reason == "max_tokens":
        raise ProviderError("Claude's answer was cut off (max_tokens). Ask for fewer clips.")
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"Claude returned malformed JSON: {text[:200]}") from exc
    return _validate(data.get("clips") or [], segs, max_len=max_len, keep=keep)


def _validate(clips: list, segs: list[dict], *, max_len: float, keep: int) -> list[dict]:
    n = len(segs)
    out = []
    for c in clips:
        if not isinstance(c, dict):
            continue
        try:
            a, b = int(c["start_segment"]), int(c["end_segment"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= a < n and 0 <= b < n and a <= b):
            continue
        # Trim segments off the end until the clip fits the hard cap.
        while b > a and segs[b]["end"] - segs[a]["start"] > max_len:
            b -= 1
        dur = segs[b]["end"] - segs[a]["start"]
        if dur < MIN_CLIP_SECONDS or dur > max_len:
            continue
        try:
            score = max(0, min(100, int(c.get("score", 0))))
        except (TypeError, ValueError):
            score = 0
        out.append({"start_segment": a, "end_segment": b,
                    "title": str(c.get("title") or "").strip()[:80],
                    "why": str(c.get("why") or "").strip()[:200],
                    "score": score})
    # Highest score wins any overlap; then back into time order.
    out.sort(key=lambda c: c["score"], reverse=True)
    chosen: list[dict] = []
    for c in out:
        overlaps = any(c["start_segment"] <= k["end_segment"]
                       and k["start_segment"] <= c["end_segment"] for k in chosen)
        if overlaps:
            continue
        chosen.append(c)
        if len(chosen) >= keep:
            break
    chosen.sort(key=lambda c: c["start_segment"])
    return chosen
