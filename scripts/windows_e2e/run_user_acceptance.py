"""One-command Windows validation runner (ANT-275 E4/E5/E6).

Single entry point for a physical session:
  python scripts/windows_e2e/run_user_acceptance.py

1. machine capability probe;
2. automated E2E suite (capability-gated executors);
3. minimal INTERACTIVE steps — the user is shown a clear instruction and
   only answers PASS/FAIL (no technical analysis required);
4. final reports in windows_e2e_reports/: report.md, report.json,
   user_acceptance.md.

Interactive results are the USER's verdict, recorded verbatim as
PASS/FAIL/SKIPPED — never inferred. No voice content is recorded or
written to reports: statuses and reason codes only.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.windows_e2e.capability_probe import probe  # noqa: E402
from scripts.windows_e2e.run_physical import run as run_automated  # noqa: E402


def _ask(prompt: str) -> bool:
    while True:
        answer = input(f"{prompt} [p]assou / [f]alhou: ").strip().lower()
        if answer in ("p", "passou"):
            return True
        if answer in ("f", "falhou"):
            return False
        print("Responde 'p' (passou) ou 'f' (falhou).")


INTERACTIVE_STEPS = (
    {
        "id": "voice-capture",
        "title": "[VOICE 1/4] Captura de microfone",
        "instruction": 'Diz: "Antonella, que horas são?" — espera pela resposta falada.',
        "pass_criteria": "Ouvis a resposta da Antonella.",
    },
    {
        "id": "assistant-speech",
        "title": "[VOICE 2/4] Fala da assistente",
        "instruction": "Pede qualquer resposta longa e observa a fala contínua.",
        "pass_criteria": "A fala é contínua, sem cortes nem áudio repetido.",
    },
    {
        "id": "barge-in",
        "title": "[VOICE 3/4] Barge-in (se activo em config)",
        "instruction": 'Enquanto a Antonella fala, diz: "Antonella, para."',
        "pass_criteria": "A fala para e o mic abre sem reproduzir áudio antigo.",
        "skippable": True,
        "skip_reason": "barge_in desactivado na configuração",
    },
    {
        "id": "second-command-after-interrupt",
        "title": "[VOICE 4/4] Comando após interrupção",
        "instruction": 'Logo após interromper, diz: "Abre o Bloco de notas."',
        "pass_criteria": "O novo comando é respondido sem áudio velho.",
    },
)


def run_interactive(out_dir: Path, *, quiet_hours_note: str = "") -> list[dict]:
    from scripts.windows_e2e.evidence import EvidenceRecord

    records: list[dict] = []
    print("\n=== VALIDAÇÃO INTERACTIVA (o teu veredicto é o resultado) ===")
    for index, step in enumerate(INTERACTIVE_STEPS, start=1):
        print(f"\n{step['title']}")
        print(f"  Instrução: {step['instruction']}")
        print(f"  Critério:  {step['pass_criteria']}")
        answer = _ask("  Resultado?")
        records.append(
            {
                "case_id": step["id"],
                "status": "PASS" if answer else "FAIL",
                "timestamp": time.time(),
            }
        )
        if index < len(INTERACTIVE_STEPS):
            print()
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-interactive", action="store_true", help="automated suite only")
    args = parser.parse_args()

    out_dir = Path(__file__).resolve().parents[2] / "windows_e2e_reports"
    capabilities = probe()

    print("=== CAPABILITIES (sem PII) ===")
    print(f"monitores: {capabilities['monitor_count']} · negativos: {capabilities['negative_coordinates']}")
    print(f"chrome: {capabilities['chrome_available']} · edge: {capabilities['edge_available']}")
    optional = capabilities.get("optional_dependencies") or {}
    print(f"opcional: {', '.join(k for k, v in optional.items() if v) or '(nenhuma)'}")

    bundle = run_automated(out_dir, capabilities=capabilities)
    print("\n=== E2E AUTOMATIZADO CONCLUÍDO (report.md/report.json) ===")

    user_rows: list[dict] = []
    if not args.skip_interactive:
        user_rows = run_interactive(out_dir)

    acceptance_path = out_dir / "user_acceptance.md"
    lines = [
        "# Windows User Acceptance",
        "",
        "| Passo | Resultado |",
        "|---|---|",
    ]
    for row in user_rows:
        lines.append(f"| {row['case_id']} | {row['status']} |")
    if not user_rows:
        lines.append("| (interactivos ignorados — --skip-interactive) | SKIPPED |")
    lines.append("")
    lines.append("Passos interactivos são veredictos do utilizador; nunca inferidos.")
    acceptance_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nrelatórios em: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
