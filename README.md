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

### 2. Installierte KIs prüfen
```bash
./loop.py --check
```

### 3. Eine Aufgabe ausführen
```bash
# Direkt im aktuellen Verzeichnis:
./loop.py "Erstelle eine REST-API mit FastAPI für Notizen"

# Mit Projekt-Kontext (wie in der Claude UI):
./loop.py -p projects/demo "Erstelle einen Authentifizierungs-Endpoint"
```

### 4. Optionen
| Parameter | Beschreibung |
| :--- | :--- |
| `-p`, `--project` | Zielverzeichnis des Projekts (Standard: `.`) |
| `-m`, `--max-iterations` | Maximale Runden für den autonomen Loop (Standard: `10`) |
| `--planner` | Bestimmt das Planer-Modell (z. B. `claude`) |
| `--reviewer` | Bestimmt das Prüfer-Modell (z. B. `agy` oder `gemini`) |
| `--check` | Zeigt erkannte AI-CLIs an |

---

## 🇬🇧 Quickstart (English)

### 1. Prerequisites
* Python 3.10+.
* Official CLIs authenticated in your terminal (e.g., `claude` and `agy` or `gemini`).

### 2. Verify Available AI Tools
```bash
./loop.py --check
```

### 3. Run a Task
```bash
# In the current directory:
./loop.py "Build a FastAPI notes service"

# With project context (mirroring Claude UI Projects):
./loop.py -p projects/demo "Add JWT authentication endpoints"
```

---

## 📂 Claude UI Projekte lokal gespiegelt

In der Claude Web-UI haben Projekte **Anweisungen**, **Wissen** und **Chats**. Lokal wird das 1:1 in Ordnern abgebildet:

```
projects/
└── mein-projekt/
    ├── CLAUDE.md              # 🎯 Projekt-Anweisungen (liest Claude automatisch)
    ├── knowledge/             # 📚 Projekt-Wissen (Docs, Notizen, DB-Schemas)
    │   └── api_spec.md
    └── logs/                  # 💬 Vollständige Protokolle aller Runden
```

---

## 💡 Token-Schonung

* **Artefakt-Handoff:** Es werden keine riesigen Chat-Verläufe übertragen, sondern nur präzise Markdown-Dateien (`.dual-loop/PLAN.md` und `.dual-loop/REVIEW.md`).
* **Loop-Guard:** Maximal 2 Review-Runden, um teure Endlos-Diskussionen zwischen den Modellen zu verhindern.
* **.done Marker:** Erstellt die KI die Datei `.done`, stoppt der Loop sofort.

---

## 📄 Lizenz
MIT License. Open Source für die Community.
