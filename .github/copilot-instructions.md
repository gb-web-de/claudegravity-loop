# Copilot-Anweisungen für ClaudeGravity Loop

- **Zweck:** ClaudeGravity ist ein Dual-Loop-Orchestrator: Architekt, Prüfstatiker, Bauleiter und Abnahme laufen auf getrennten Anbietern; das Modell, das baut, benotet sich nie selbst.
- **Python:** Laufzeit ab Python 3.10; CI testet 3.10 und 3.13.
- **Keine Laufzeit-Abhängigkeiten:** Nur die Standardbibliothek. Endnutzer müssen nichts per `pip` installieren. Ruff ist reines Entwicklungswerkzeug.
- **Tests vor jedem Commit:**
  - `python -m unittest discover -s tests -v`
  - `python tests/smoke/run_smoke.py --strategy balanced --out /tmp/smoke`
  - `ruff check .` und `ruff format --check .`
- **Plattformen:** Windows, macOS und Linux. Prozesse mit Argumentlisten, nie `shell=True`; Pfade mit `pathlib`; UTF-8 erzwingen (`PYTHONIOENCODING=utf-8`).
- **Plugins/MCP:** Manifeste (`plugin.json`, `mcp.json`, `mcp_config.json`, `gemini-extension.json`, `.claude-plugin/`, `.cursor-plugin/`, `.vscode/mcp.json`) und Befehle (`commands/*.md` samt `commands/claudegravity/*.toml`) bleiben konsistent. Versionen gemeinsam erhöhen; `tests/test_plugins.py` prüft das.
- **Doku:** `docs/de/` und `docs/en/` immer beide anpassen.
- **Änderungen:** klein und gezielt halten, keine Geheimnisse committen.
