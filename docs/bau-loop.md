# Bau-Loop (Phase 3)

[← Zurück zur Übersicht](../README.md) · [Dokumentations-Index](README.md)

Der Bau-Loop startet erst, wenn du den Plan im Freigabe-Menü bestätigt hast (siehe [Ablauf & Rollen](ablauf-und-rollen.md)). Hier verbraucht ClaudeGravity rund 80–90 % aller Tokens, deshalb lohnt sich hier ein günstigeres oder lokales Modell (siehe [Strategien](strategien.md)).

## Wer baut?

* Standard: dieselbe CLI wie der Architekt, der den freigegebenen Plan geschrieben hat (nach einem Swap also der neue Architekt).
* Mit `--bauer <key>` (Alias `--builder`) ein beliebiges anderes Backend, z. B. `--bauer ollama` oder `--bauer bauer_ep`.
* Modell und Effort: `--bauer-model`, `--bauer-effort` oder die Standardwerte des Presets.

## Rechte-Abfrage vor dem Start

Ohne `--yolo` fragt ClaudeGravity:

```
Soll 🔨 Bauleiter (Claude Code) volle Schreib-/Tool-Rechte erhalten (--dangerously-skip-permissions)? [J/n]:
```

* **[Enter] / J:** Die Rechte-Flags werden gesetzt und in `state.json` gemerkt (siehe [Backends](backends.md#rechte--yolo)).
* **n:** Eingeschränkter Modus. Die CLI fragt dann selbst bei jedem Tool-Aufruf nach. Da ClaudeGravity die CLIs nicht interaktiv startet, kommt der Bauleiter in diesem Modus oft nicht weiter.

## Ablauf einer Runde

1. ClaudeGravity prüft, ob `.dual-loop/sessions/<session>/.done` schon existiert. Falls ja, ist die Aufgabe fertig.
2. `last_iteration` und Metriken werden in `state.json` gespeichert. So kann nach einem Abbruch genau hier fortgesetzt werden.
3. Der Bauleiter bekommt einen kurzen Prompt: Pfad zur freigegebenen Planversion, die Aufgabe, den Auftrag „Dateien erstellen/ändern, Tests durchführen“ und den genauen Pfad für die Fertigmeldung. Es wird **keine Chat-Historie** mitgeschickt, nur der Plan (Token-Schonung).
4. Die Antwort wird im Terminal ausgegeben und an `logs/loop_<session>.log` angehängt.
5. Bei **Endpunkt-Bauleitern** (Ollama-Server, LM Studio, eigene Server, Copilot) liest ClaudeGravity die `filepath:`-Codeblöcke aus der Antwort und schreibt die Dateien selbst (Format siehe [Backends](backends.md#wie-endpunkt-bauleiter-dateien-schreiben)). Geschriebene Dateien werden aufgelistet.
6. Erneute Prüfung auf `.done`, dann `--delay` Sekunden Pause (Standard 3) und die nächste Runde.

Ein Fehler in einer Runde (z. B. Absturz der CLI) beendet den Loop nicht: Er wird gemeldet, und die nächste Runde startet.

## Ende des Loops

| Auslöser | Ergebnis |
| :--- | :--- |
| `.done` im Session-Ordner gefunden | `phase = completed`, Audit-Bericht wird in `.done` geschrieben und angezeigt. |
| `.done` im Projekt-Hauptordner | Wird in den Session-Ordner verschoben und wie oben behandelt. |
| `--max-iterations` erreicht (Standard 10) | Stand gesichert, Audit-Bericht geschrieben. Weiter mit `claudegravity -c -m <neues Maximum>`. |
| `Strg+C` | Aktuelle Runde wird sauber beendet, Stand bleibt erhalten. |
| Ratenlimit | Menü Wechseln / Warten / Beenden oder automatischer Wechsel mit `--auto-switch` (siehe [Ablauf & Rollen](ablauf-und-rollen.md#limits--auto-switch)). |

## Wann ist der Bauleiter „fertig“?

Der Bauleiter entscheidet selbst, wann er `.done` anlegt. Der Prompt verlangt, dass vorher **alle Anforderungen erfüllt und getestet** sind. Wie du das absicherst, steht in [Tests](tests.md).

## Nützliche Flags für Phase 3

| Flag | Wirkung |
| :--- | :--- |
| `-m`, `--max-iterations <n>` | Maximale Runden |
| `-d`, `--delay <s>` | Pause zwischen Runden, `0` für keine Pause |
| `--yolo` | Rechte-Abfrage überspringen |
| `--auto-switch` | Bei Limit automatisch Backend wechseln |
| `--bauer`, `--bauer-model`, `--bauer-effort`, `--bauer-endpoint` | Bauleiter festlegen |

Vollständige Liste: [CLI-Referenz](cli-referenz.md).
