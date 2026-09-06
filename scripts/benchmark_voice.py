"""Voice latency benchmark report (ANT-271 A8/V5).

Consumes a ``voice_metrics.json`` file produced by a physical session
(the runtime dumps ``VoiceLatency`` snapshots) and reports the honest
percentiles against the roadmap targets. Without a real session file it
prints NOT PHYSICALLY TESTED — it never invents numbers.

Usage: python scripts/benchmark_voice.py [--input voice_metrics.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.voice_runtime import percentile  # noqa: E402

# V5: "last_mic_frame" is NOT a proven end-of-speech (no local VAD) —
# treat its p95 as a LOWER BOUND proxy for the audible-response target.
TARGETS = {
    "route_to_agent_ms": 1000.0,          # deterministic dispatch p95 < 1s após transcrição
    "last_mic_frame_to_first_audio_ms": 3000.0,  # proxy (lower bound) para resposta audível p95 < 3s
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="voice_metrics.json")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print("NOT PHYSICALLY TESTED — no voice_metrics.json from a real session")
        print("Expected format: [{\"route_to_agent_ms\": 812.0, ...}, ...]")
        return 0

    samples = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(samples, list) or not samples:
        print("NOT PHYSICALLY TESTED — empty metrics file")
        return 0

    print("# Voice Latency Report (physical session)")
    print()
    print("| Metric | p50 (ms) | p95 (ms) | Target p95 | Met |")
    print("|---|---|---|---|---|")
    all_met = True
    for metric, target in TARGETS.items():
        values = [s[metric] for s in samples if isinstance(s.get(metric), (int, float))]
        p50 = percentile(values, 50)
        p95 = percentile(values, 95)
        met = p95 is not None and p95 < target
        all_met = all_met and met
        print(f"| {metric} | {p50} | {p95} | <{target:.0f} | {'yes' if met else 'NO'} |")

    print()
    print(f"samples: {len(samples)} · todas as metas cumpridas: {all_met}")
    print("Valores medidos numa sessão física — nunca inferidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
