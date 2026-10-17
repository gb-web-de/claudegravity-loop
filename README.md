# ClaudeGravity Loop

> **Cross-Model Adversarial & Autonomous Execution Loop** for **Claude Code** and **Google Antigravity (`agy` / `gemini`)**.  
> Inspired by [claudex-loop](https://github.com/chaseai-yt/claudex-loop), adapted for official CLI subscriptions with zero extra API costs.

---

## 🌟 Kernprinzip / Core Principle

> **„Wer den Code schreibt, darf ihn nicht selbst benoten.“**  
> **"The model that writes the plan or code never grades it."**

Ein einzelnes KI-Modell (z. B. Claude) übersieht beim Überprüfen eigener Entwürfe typischerweise eigene Denkfehler (Confirmation Bias). `claudegravity-loop` löst das durch ein unabhängiges 4-Augen-Prinzip:
* **Planer & Builder:** Claude Code entwirft die Architektur und setzt sie um.
* **Adversarial Reviewer:** Antigravity (`agy` / `gemini`) prüft den Plan gnadenlos auf Schwachstellen, Race Conditions und Lücken, bevor eine Zeile Code gebaut wird.

---

## 🇩🇪 Schnellstart (Deutsch)

### 1. Voraussetzungen
* Python 3.10 oder neuer.
* Die offiziellen CLIs im Terminal angemeldet (z. B. `claude` und `agy` oder `gemini`).

### 2. Eine Aufgabe ausführen
```bash
# Im aktuellen Verzeichnis (fragt vor Phase 3 nach Rechten):
claudegravity "Refaktoriere das Spielplan-Modul"

# Automatisch mit vollen Schreibrechten ausführen (--yolo):
claudegravity --yolo "Refaktoriere das Spielplan-Modul"

# In einem anderen Projektordner:
claudegravity -p /home/gordon/Projekte/handball --yolo "Füge Unit-Tests hinzu"
```

### 3. Sitzung fortsetzen (Crash-Recovery / Resume)
Wurde der Rechner neu gestartet, der Prozess unterbrochen oder soll eine alte Aufgabe weitergeführt werden?
```bash
# Setzt die letzte unterbrochene Sitzung exakt an der Stelle fort:
claudegravity --resume

# Kurzform:
claudegravity -c
```

### 4. Parameter & Optionen
| Parameter | Beschreibung |
| :--- | :--- |
| `-p`, `--project` | Zielverzeichnis des Projekts (Standard: `.`) |
| `-c`, `--resume` | Unterbrochene Sitzung an exakt derselben Iteration fortsetzen |
| `-m`, `--max-iterations` | Maximale Runden für den autonomen Loop (Standard: `10`) |
| `--yolo`, `--auto-approve`| Erteilt in Phase 3 automatisch Schreibrechte (`--dangerously-skip-permissions`) |
| `--planner` | Bestimmt das Planer-Modell (z. B. `claude`) |
| `--reviewer` | Bestimmt das Prüfer-Modell (z. B. `agy` oder `gemini`) |
| `--check` | Zeigt erkannte AI-CLIs an |

---

## 🎯 Interaktive Plan-Freigabe & Change-Routing

Sobald der Plan fertiggestellt und von Antigravity geprüft wurde, wirst du gefragt:
```text
Möchtest du den Plan freigeben oder Änderungen vornehmen?
  [1] Approve  -> Plan genehmigen & weiter zur Implementierung
  [2] Changes  -> Änderungen/Feedback anbringen
  [3] Anzeigen -> Plan direkt hier im Terminal lesen
  [4] Beenden  -> Abbrechen (Fortsetzen später mit --resume)
```

Wählst du **[2] Changes**, erscheint das übersichtliche Routing-Menü:

```text
[UI-Varianten (Graphische Oberfläche)]:
  [1] Im Editor öffnen (VS Code / Antigravity / Cursor / System)
      -> Öffnet die Plan-Datei direkt zum Bearbeiten
  [2] Claude UI (Web / Desktop)
      -> Zeigt den Plan-Pfad zum einfachen Kopieren in die Claude Web-UI

[CLI-Varianten (Terminal)]:
  [3] Feedback direkt hier eintippen
      -> KI überarbeitet den Plan anhand deiner Anweisung automatisch
  [4] Interaktive Claude Code CLI-Session starten
  [5] Interaktive Antigravity CLI-Session starten
  [6] Zurück zum Hauptmenü
```

---

## 📂 Plan-Versionierung & Audit-Log

Nichts geht verloren! Jeder Durchlauf legt automatisch ein eigenes Session-Archiv an:

```
.dual-loop/
├── PLAN.md                                    # 🎯 Immer die aktuellste Version
├── REVIEW.md                                  # 📋 Das aktuellste Review
├── PLAN-REVIEW-LOG.md                         # 📜 Fortlaufendes Audit-Logbuch
└── sessions/
    └── 20261017_102220_refaktoriere_.../      # 📦 Revisionssicheres Session-Archiv
        ├── state.json                         # 💾 Sitzungsstatus für --resume
        ├── PLAN_v1.md                         # Erster Entwurf
        ├── REVIEW_round1.md                   # Review von Modell B
        ├── PLAN_v2.md                         # Überarbeiteter Plan
        └── REVIEW_round2.md                   # Zweites Review
```

---

## 🇬🇧 Quickstart (English)

### 1. Run a Task
```bash
claudegravity --yolo "Refactor tournament module"
```

### 2. Resume Interrupted Session
```bash
claudegravity --resume
```

---

## 💡 Token-Schonung

* **Artefakt-Handoff:** Es werden keine riesigen Chat-Verläufe übertragen, sondern nur präzise Markdown-Dateien (`PLAN_v1.md`, `REVIEW_round1.md`).
* **Loop-Guard:** Maximal 2 Review-Runden, um teure Endlos-Diskussionen zwischen den Modellen zu verhindern.
* **.done Marker:** Erstellt die KI die Datei `.done`, stoppt der Loop sofort.

---

## 📄 Lizenz
MIT License. Open Source für die Community.
