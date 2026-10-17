# ClaudeGravity Loop - Projekt-Richtlinien

## Zweck
`claudegravity-loop` ist ein leichtgewichtiger, autonomer Runner für AI-Coding-Aufgaben mit **Claude Code** und **Google Antigravity (`agy`)**.
Er basiert auf dem Prinzip des [claudex-loop](https://github.com/chaseai-yt/claudex-loop): **Das Modell, das den Plan entwirft oder baut, benotet sich niemals selbst.**

## Architektur
- `loop.py`: Haupt-CLI-Runner (benötigt nur Python 3.10+ Standardbibliothek).
- `.dual-loop/`: Git-ignorierter Arbeitsordner. Enthält ausschließlich den Unterordner `sessions/` (alle Pläne, Reviews und Logs sind aufgabenspezifisch darin isoliert).
- `projects/`: Ordner für gespiegelte Projekte (wie in der Claude UI).
  - Jedes Unterprojekt kann eine eigene `CLAUDE.md` und einen Ordner `knowledge/` besitzen.

## Richtlinien für Entwickler & Agenten
- Verwende ausschließlich Standard-Bibliotheken (`argparse`, `pathlib`, `subprocess`, `signal`, `shutil`).
- Keine externen API-Schlüssel: Cloud-Modelle werden ausschließlich über die offiziellen CLIs (`claude`, `agy`, `gemini`) mit bestehenden Abos angesprochen.
- Token-Schonung hat oberste Priorität: Übergib nur den Plan oder relevante Diffs, keine aufgeblähten Chat-Historien.
- Sobald eine autonome Aufgabe erfolgreich abgeschlossen ist, erstelle die Datei `.done` im jeweiligen Session-Ordner (`.dual-loop/sessions/<session>/.done`) und NICHT im Projekt-Hauptverzeichnis.
