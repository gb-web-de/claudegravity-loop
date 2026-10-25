#!/usr/bin/env python3
"""
ClaudeGravity Loop - Cross-Model Adversarial & Autonomous Execution Loop
Auto-detects available CLIs (Claude Code, Google Antigravity agy, Gemini CLI, Codex, Copilot, Ollama)
and OpenAI-compatible REST endpoints (Ollama, LM Studio, vLLM, LiteLLM, own servers in the local network).
Supports:
- Cross-platform operation on Windows, macOS, and Linux
- Read-only planning, review and acceptance; write permissions (YOLO) only for the builder
- Multi-role architecture: 🏗️ Architekt, 🧐 Prüfstatiker, 🔨 Bauleiter, 🔎 Abnahme (never the builder's own model)
- Zero-cost build loops via local/intranet models (--strategy local-free)
- Interactive Plan Approval & Change Routing
- Versioned plan archives, token/cost audits, and rate-limit recovery
"""

# Der Code liegt im Paket claudegravity/ (ein Modul je Aufgabe, siehe CLAUDE.md). Diese Datei bleibt der
# Einstieg für `claudegravity`, die Windows-Starter und `import loop` in Tests und Werkzeugen.
import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from claudegravity import (  # noqa: E402
    backends,
    budget,
    build,
    candidates,
    cli,
    common,
    config,
    errors,
    i18n,
    metrics,
    phases,
    planning,
    roles,
    runner,
    safety,
    session,
    wizard,
)

# Alle Namen der Module auch unter `loop.<name>` anbieten, wie vor der Aufteilung.
for _module in (
    i18n,
    common,
    safety,
    errors,
    metrics,
    backends,
    session,
    budget,
    runner,
    planning,
    roles,
    build,
    config,
    wizard,
    phases,
    candidates,
    cli,
):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})

if __name__ == "__main__":
    cli.run_cli()
