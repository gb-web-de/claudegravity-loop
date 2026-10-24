# AGENTS.md

Leitfaden für Mitwirkende und KI-Agenten (siehe auch `CLAUDE.md` und `.github/copilot-instructions.md`).

## Lokal testen
```sh
python -m unittest discover -s tests -v
python tests/smoke/run_smoke.py --strategy balanced --out /tmp/smoke
pip install ruff==0.16.9 && ruff check . && ruff format --check .
```

## Wo liegt was
- Plugin-Manifeste: `plugin.json`, `mcp.json`, `mcp_config.json`, `gemini-extension.json`, `.claude-plugin/`, `.cursor-plugin/`, `.vscode/mcp.json`.
- Befehlsvorlagen: `commands/*.md` (Claude/Cursor/Copilot) und gleichlautend `commands/claudegravity/*.toml` (Gemini CLI).

## Erwartungen
- Befehlstexte in Markdown und TOML bleiben deckungsgleich; Versionen der Manifeste gemeinsam erhöhen.
- Neue Funktionen bekommen einen Test in `tests/`; Doku in `docs/de/` und `docs/en/` nachziehen.
- Nur Standardbibliothek zur Laufzeit; Windows, macOS und Linux unterstützen.

## Sicherheit und Umfang
- Keine Geheimnisse committen; Modell-Ausgaben nie vertrauen; Prozesse ohne `shell=True`.
- Kleine, gezielte Änderungen; Produktverhalten nicht nebenbei ändern.
