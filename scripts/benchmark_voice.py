"""Report measured client milestones from the runtime's voice_metrics.json.

Run Antonella, complete voice turns, then run:
python scripts/benchmark_voice.py --input voice_metrics.json
No file proves physical validation. End-of-speech and audible playback
latency remain unmeasured: first_response_audio marks receipt, not playback.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.voice_runtime import percentile


# -.-.-.-
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="voice_metrics.json")
    args = parser.parse_args()
    path = Path(args.input)
    if not path.exists():
        print("NOT PHYSICALLY TESTED — no runtime metrics file")
        return 0
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(document, dict) or document.get("schema_version") != 1
                or document.get("source") != "antonella.voice_runtime"
                or not isinstance(document.get("turns"), list)):
            raise ValueError("Expected version 1 runtime metrics")
        samples = []
        for turn in document["turns"]:
            if not isinstance(turn, dict) or not isinstance(turn.get("metrics"), dict):
                raise ValueError("Invalid turn record")
            if turn.get("interrupted") is False:
                samples.append(turn["metrics"])
    except (OSError, ValueError) as error:
        print(f"Invalid runtime metrics: {type(error).__name__}")
        return 1

    print("Voice client milestones (runtime export; physical provenance not verified)")
    print("| Metric | Valid turns | p50 (ms) | p95 (ms) |")
    print("|---|---|---|---|")
    for metric in ("route_to_agent_ms", "agent_to_first_action_ms",
                   "input_transcription_to_first_audio_ms"):
        values = [s[metric] for s in samples if type(s.get(metric)) in (int, float)
                  and math.isfinite(s[metric]) and s[metric] >= 0]
        print(f"| {metric} | {len(values)} | {percentile(values, 50)} | {percentile(values, 95)} |")
    print(f"Completed, non-interrupted turns: {len(samples)}")
    print("True end-of-speech p95: NOT MEASURED (no trustworthy VAD/end-of-turn timestamp)")
    print("Physical barge-in: NOT MEASURED BY THIS BENCHMARK (validar via run_user_acceptance.py)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
