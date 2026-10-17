# Tests

[← Zurück zur Übersicht](../README.md) · [Dokumentations-Index](README.md)

Tests ziehen sich durch alle drei Phasen. Diese Seite beschreibt, wie ClaudeGravity mit Tests in deinem Projekt umgeht und wie du ClaudeGravity selbst prüfst.

## Tests im Ablauf

| Phase | Was mit Tests passiert |
| :--- | :--- |
| 🏗️ **Architekt** | Der Plan muss **Testkriterien** enthalten (neben betroffenen Dateien, Architektur und Randfällen). |
| 🧐 **Prüfstatiker** | Prüft den Plan ausdrücklich auf **fehlende Tests** und fordert sie per `VERDICT: REVISE` nach. |
| 🔨 **Bauleiter** | Soll in jeder Runde Tests ausführen und `.done` erst anlegen, wenn alles getestet ist. |

ClaudeGravity führt selbst **keine** Tests aus und prüft nicht, ob sie grün sind. Es verlässt sich auf den Bauleiter und auf den freigegebenen Plan.

## Tests zuverlässig machen

* **Testbefehl in die `CLAUDE.md` des Projekts schreiben**, z. B. `Tests: python -m pytest -q`. Die Datei geht als Kontext an den Architekten, der den Befehl in den Plan übernimmt (siehe [Sessions & Dateien](sessions-und-dateien.md#projektkontext-claudemd--knowledge)).
* **Abschlusskriterium festlegen**, z. B. „Erstelle `.done` erst, wenn `pytest` ohne Fehler durchläuft.“
* **Im Freigabe-Menü prüfen** ([4] Anzeigen), ob der Plan konkrete Tests nennt. Falls nicht: [2] Changes → [3] Feedback, z. B. „Ergänze Unit-Tests für alle Randfälle.“
* **Mit `--strategy best-code`** bekommen alle Phasen hohen Effort, was sich bei testintensiven Aufgaben auszahlt.
* **Nach dem Lauf selbst nachprüfen**: Testsuite einmal lokal ausführen, bevor du committest.

### Endpunkt-Bauleiter und Tests

Ollama-, LM-Studio- und eigene Server-Bauleiter können **keine Befehle ausführen**. Sie schreiben nur Dateien über `filepath:`-Blöcke. Tests laufen in diesem Fall nicht automatisch. Für Aufgaben, bei denen Tests im Loop laufen müssen, eine CLI als Bauleiter wählen (`claude`, `agy`, `gemini`), oder die Tests nach dem Lauf selbst starten.

## ClaudeGravity selbst prüfen

Ohne KI-Aufrufe und ohne Dateien zu ändern:

```bash
# Erkennung von CLIs und Endpunkten
claudegravity --info

# Rollen- und Modellbelegung für ein Preset
claudegravity --dry-run "Testaufgabe" --strategy local-free

# Optimizer
claudegravity-mcp --optimize "Fixe den Login-Bug" --priority lowest-cost

# MCP-Server antwortet auf tools/list
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 mcp_server.py
```

Einen echten Durchlauf ohne Risiko machst du am besten im Demo-Projekt:

```bash
claudegravity "Ergänze eine Begrüßungsfunktion mit Test" -p projects/demo -m 3
```
