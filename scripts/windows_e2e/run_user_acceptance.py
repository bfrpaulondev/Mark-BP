"""One-command Windows validation runner (ANT-275 E4/E5/E6).

Physical usage from the repository root::

    $env:ANTONELLA_E2E_PHYSICAL="1"
    python scripts/windows_e2e/run_user_acceptance.py

The runner performs the capability-gated automated suite, launches Antonella
for the interactive voice checks (unless ``--use-existing-antonella`` is
supplied), records only PASS/FAIL/SKIPPED status for the user's voice verdicts,
and writes the final reports to ``windows_e2e_reports/``.

Without the explicit physical gate, automated cases remain NOT PHYSICALLY
TESTED and interactive hardware checks are not started.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.windows_e2e.capability_probe import probe  # noqa: E402
from scripts.windows_e2e.run_physical import run as run_automated  # noqa: E402


def _ask(prompt: str, *, skippable: bool = False) -> str:
    while True:
        suffix = "[p]assou / [f]alhou"
        if skippable:
            suffix += " / [s]altar"
        answer = input(f"{prompt} {suffix}: ").strip().lower()
        if answer in ("p", "passou"):
            return "PASS"
        if answer in ("f", "falhou"):
            return "FAIL"
        if skippable and answer in ("s", "saltar", "skip"):
            return "SKIPPED"
        expected = "p (passou) ou f (falhou)"
        if skippable:
            expected += " ou s (saltar)"
        print(f"Responde {expected}.")


INTERACTIVE_STEPS = (
    {
        "id": "voice-capture",
        "title": "[VOICE 1/4] Captura de microfone",
        "instruction": 'Diz: "Antonella, que horas são?" — espera pela resposta falada.',
        "pass_criteria": "Ouves a resposta da Antonella.",
    },
    {
        "id": "assistant-speech",
        "title": "[VOICE 2/4] Fala da assistente",
        "instruction": "Pede uma resposta longa e observa a fala contínua.",
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
        "skippable": True,
        "skip_reason": "barge_in não foi executado",
    },
)


# -.-.-.-
def _physical_gate(
    environ: Mapping[str, str] | None = None,
    platform: str | None = None,
) -> bool:
    values = os.environ if environ is None else environ
    current_platform = sys.platform if platform is None else platform
    return values.get("ANTONELLA_E2E_PHYSICAL") == "1" and current_platform == "win32"


# -.-.-.-
def _launch_antonella(root: Path) -> subprocess.Popen:
    """Launch the canonical desktop entrypoint and retain stderr only for early-failure diagnosis."""
    return subprocess.Popen(
        [sys.executable, str(root / "antonella.py")],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


# -.-.-.-
def _sanitize_diagnostic(text: str, root: Path) -> str:
    value = str(text or "")
    for raw, replacement in ((str(root), "<repo>"), (str(Path.home()), "<home>")):
        if raw:
            value = value.replace(raw, replacement)
            value = value.replace(raw.replace("\\", "/"), replacement)
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    value = " · ".join(lines[-3:]) if lines else ""
    value = re.sub(r"\s+", " ", value).replace("|", "/").strip()
    return value[:320]


# -.-.-.-
def _early_exit_detail(process: subprocess.Popen, root: Path) -> str:
    if process.poll() is None:
        return ""
    try:
        _stdout, stderr = process.communicate(timeout=2)
    except Exception:
        return f"exit_code={process.returncode}"
    detail = _sanitize_diagnostic(stderr or "", root)
    prefix = f"exit_code={process.returncode}"
    return f"{prefix} · {detail}" if detail else prefix


# -.-.-.-
def _stop_launched(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


# -.-.-.-
def run_interactive() -> list[dict]:
    records: list[dict] = []
    print("\n=== VALIDAÇÃO INTERACTIVA (o teu veredicto é o resultado) ===")
    for index, step in enumerate(INTERACTIVE_STEPS, start=1):
        print(f"\n{step['title']}")
        print(f"  Instrução: {step['instruction']}")
        print(f"  Critério:  {step['pass_criteria']}")
        status = _ask(
            "  Resultado?",
            skippable=bool(step.get("skippable")),
        )
        row = {
            "case_id": step["id"],
            "status": status,
            "timestamp": time.time(),
        }
        if status == "SKIPPED":
            row["reason"] = step.get("skip_reason", "skipped by user")
        records.append(row)
        if index < len(INTERACTIVE_STEPS):
            print()
    return records


# -.-.-.-
def _voice_metrics_row(root: Path) -> dict:
    metrics_path = root / "voice_metrics.json"
    exists = metrics_path.is_file() and metrics_path.stat().st_size > 0
    return {
        "case_id": "voice-runtime-metrics",
        "status": "PASS" if exists else "FAIL",
        "timestamp": time.time(),
        **({} if exists else {"reason": "voice_metrics.json was not produced"}),
    }


# -.-.-.-
def _write_voice_benchmark(root: Path, out_dir: Path) -> None:
    """Persist only the content-free benchmark stdout produced by A8."""
    destination = out_dir / "voice_benchmark.txt"
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts" / "benchmark_voice.py"),
                "--input",
                str(root / "voice_metrics.json"),
            ],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if completed.returncode == 0:
            destination.write_text(completed.stdout, encoding="utf-8")
        else:
            destination.write_text(
                f"benchmark failed: returncode={completed.returncode}\n",
                encoding="utf-8",
            )
    except Exception as exc:
        destination.write_text(
            f"benchmark unavailable: {type(exc).__name__}\n",
            encoding="utf-8",
        )


# -.-.-.-
def _write_acceptance(out_dir: Path, rows: list[dict], note: str | None = None) -> None:
    acceptance_path = out_dir / "user_acceptance.md"
    lines = [
        "# Windows User Acceptance",
        "",
        "| Passo | Resultado |",
        "|---|---|",
    ]
    for row in rows:
        label = row["status"]
        if row.get("reason"):
            reason = " ".join(str(row["reason"]).replace("|", "/").split())[:360]
            label += f" — {reason}"
        lines.append(f"| {row['case_id']} | {label} |")
    if not rows:
        lines.append("| (sem passos interactivos executados) | SKIPPED |")
    lines.extend(
        [
            "",
            note or "Passos interactivos são veredictos do utilizador; nunca inferidos.",
        ]
    )
    acceptance_path.write_text("\n".join(lines), encoding="utf-8")


# -.-.-.-
def _write_environment(out_dir: Path, capabilities: dict) -> None:
    """Persist only the capability probe's technical, PII-free environment data."""
    (out_dir / "environment.json").write_text(
        json.dumps(capabilities, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# -.-.-.-
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-interactive",
        action="store_true",
        help="automated suite only",
    )
    parser.add_argument(
        "--use-existing-antonella",
        action="store_true",
        help="do not launch a second Antonella process for interactive voice checks",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    out_dir = root / "windows_e2e_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    capabilities = probe()
    _write_environment(out_dir, capabilities)

    print("=== CAPABILITIES (sem PII) ===")
    print(
        f"monitores: {capabilities['monitor_count']} · "
        f"negativos: {capabilities['negative_coordinates']}"
    )
    print(
        f"chrome: {capabilities['chrome_available']} · "
        f"edge: {capabilities['edge_available']}"
    )
    optional = capabilities.get("optional_dependencies") or {}
    print(
        "opcional: "
        + (", ".join(key for key, value in optional.items() if value) or "(nenhuma)")
    )

    physical_gate = _physical_gate()
    if not physical_gate:
        print(
            "\nNOT PHYSICALLY TESTED — para executar os casos físicos no Windows, "
            "define ANTONELLA_E2E_PHYSICAL=1 antes deste comando."
        )

    bundle = run_automated(out_dir, capabilities=capabilities)
    print("\n=== E2E AUTOMATIZADO CONCLUÍDO (report.md/report.json) ===")

    user_rows: list[dict] = []
    acceptance_note: str | None = None
    launched: subprocess.Popen | None = None

    if args.skip_interactive:
        acceptance_note = "Passos interactivos ignorados explicitamente por --skip-interactive."
    elif not physical_gate:
        acceptance_note = (
            "NOT PHYSICALLY TESTED — passos interactivos não foram iniciados sem o gate físico."
        )
    else:
        try:
            if args.use_existing_antonella:
                print(
                    "\nUsando uma instância Antonella já aberta. "
                    "Confirma que está pronta e com microfone/áudio disponíveis."
                )
            else:
                launched = _launch_antonella(root)
                print("\nAntonella iniciada pelo runner para a validação de voz.")

            input("Quando a janela estiver pronta para voz, carrega ENTER para continuar: ")
            if launched is not None and launched.poll() is not None:
                diagnostic = _early_exit_detail(launched, root)
                reason = "Antonella process exited before interactive validation"
                if diagnostic:
                    reason += f" · {diagnostic}"
                user_rows.append(
                    {
                        "case_id": "antonella-launch",
                        "status": "FAIL",
                        "timestamp": time.time(),
                        "reason": reason,
                    }
                )
            else:
                user_rows.extend(run_interactive())
                user_rows.append(_voice_metrics_row(root))
                _write_voice_benchmark(root, out_dir)
        finally:
            _stop_launched(launched)

    _write_acceptance(out_dir, user_rows, acceptance_note)

    automated_failed = any(record.status == "FAIL" for record in bundle.records)
    interactive_failed = any(row["status"] == "FAIL" for row in user_rows)
    print(f"\nrelatórios em: {out_dir}")
    return 1 if automated_failed or interactive_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
