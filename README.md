# ClaudeGravity Loop 🚀

> **Cross-Model Dual-Loop für Claude Code & Google Antigravity (`agy` / `gemini`).**  
> Verhindert KI-Betriebsblindheit durch ein unabhängiges 4-Augen-Prinzip: *Wer den Plan entwirft oder Code baut, darf ihn niemals selbst benoten.*

---

## 📑 Inhaltsverzeichnis / Table of Contents
* [🇩🇪 Deutsche Dokumentation (Für Einsteiger & Anfänger)](#-deutsche-dokumentation-für-einsteiger)
  * [1. Was ist ClaudeGravity Loop? (Einfach erklärt)](#1-was-ist-claudegravity-loop-einfach-erklärt)
  * [2. Architektur: Single-File Konzept (Kein Installer!)](#2-architektur-single-file-konzept-kein-installer)
  * [3. Installation & Globaler Befehl (`~/.local/bin/claudegravity`)](#3-installation--globaler-befehl-localbinclaudegravity)
  * [4. Voraussetzungen & KI-Prüfung (`--check`)](#4-voraussetzungen--ki-prüfung---check)
  * [5. Die wichtigsten Befehle auf einen Blick (Spickzettel)](#5-die-wichtigsten-befehle-auf-einen-blick-spickzettel)
  * [6. Schritt-für-Schritt: Dein erster Durchlauf](#6-schritt-für-schritt-dein-erster-durchlauf)
  * [7. Das Menü: Plan freigeben oder ändern (Approve & Changes)](#7-das-menü-plan-freigeben-oder-ändern-approve--changes)
  * [8. Fragen-Modus: KIs stellen Fragen an dich (`-i` / `--ask`)](#8-fragen-modus-kis-stellen-fragen-an-dich--i----ask)
  * [9. Modelle & Intensität anpassen (`--model`, `--effort`)](#9-modelle--intensität-anpassen---model---effort)
  * [10. Weitermachen nach Pause oder Absturz (`--resume`)](#10-weitermachen-nach-pause-oder-absturz---resume)
  * [11. Schreibrechte & der Autopilot (`--yolo`)](#11-schreibrechte--der-autopilot---yolo)
  * [12. Was passiert bei AI-Sitzungslimits? (Token-Limits)](#12-was-passiert-bei-ai-sitzungslimits-token-limits)
  * [13. Wo liegen meine Dateien? (Saubere Ordnerstruktur)](#13-wo-liegen-meine-dateien-saubere-ordnerstruktur)
  * [14. Häufige Fragen & Fehlerbehebung (FAQ)](#14-häufige-fragen--fehlerbehebung-faq)
* [🇬🇧 English Documentation (Beginner's Guide)](#-english-documentation-for-beginners)
  * [1. What is ClaudeGravity Loop? (Explained Simply)](#1-what-is-claudegravity-loop-explained-simply)
  * [2. Architecture: Single-File Concept (Not an Installer!)](#2-architecture-single-file-concept-not-an-installer)
  * [3. Installation & Global Command Setup (`~/.local/bin/claudegravity`)](#3-installation--global-command-setup-localbinclaudegravity)
  * [4. Prerequisites & Verification (`--check`)](#4-prerequisites--verification---check)
  * [5. Quick Command Cheatsheet](#5-quick-command-cheatsheet)
  * [6. Step-by-Step: Your First Run](#6-step-by-step-your-first-run)
  * [7. Plan Approval & Changes Menu](#7-plan-approval--changes-menu)
  * [8. Interview Mode: AIs Ask You Questions (`-i` / `--ask`)](#8-interview-mode-ais-ask-you-questions--i----ask)
  * [9. Model Selection & Reasoning Effort (`--model`, `--effort`)](#9-model-selection--reasoning-effort---model---effort)
  * [10. Crash Recovery & Resuming (`--resume`)](#10-crash-recovery--resuming---resume)
  * [11. File Permissions & Autopilot (`--yolo`)](#11-file-permissions--autopilot---yolo)
  * [12. What Happens When AI Limits Are Hit? (Session Limits)](#12-what-happens-when-ai-limits-are-hit-session-limits)
  * [13. Directory Structure & File Storage](#13-directory-structure--file-storage)
  * [14. Frequently Asked Questions (FAQ)](#14-frequently-asked-questions-faq)

---

# 🇩🇪 Deutsche Dokumentation (Für Einsteiger)

---

### 1. Was ist ClaudeGravity Loop? (Einfach erklärt)

Stell dir eine Baustelle vor:
* **Der Architekt (z. B. Claude Code):** Zeichnet den Bauplan und baut das Haus.
* **Der Prüfstatiker (z. B. Antigravity / Gemini):** Prüft den Plan völlig unabhängig auf Einsturzgefahr, Sicherheitslücken und vergessene Details.

Wenn eine Programmier-KI ihre eigenen Pläne prüft, übersieht sie eigene Denkfehler (*Confirmation Bias*). **ClaudeGravity Loop** lässt zwei KIs als eingespieltes Team arbeiten:
1. **Claude** schreibt den Plan.
2. **Antigravity** grillt und prüft den Plan schonungslos.
3. Erst wenn der Plan wasserdicht ist (oder du ihn freigibst), wird der Code geschrieben und getestet.
4. **Keine Zusatzkosten:** Nutzt deine vorhandenen Terminal-CLIs mit deinen normalen Abos – keine teuren API-Keys nötig!

```mermaid
flowchart TD
    A["1. Aufgabe stellen"] --> B["2. Plan-Entwurf (Claude)"]
    B --> C["3. Unabhängige Prüfung (Antigravity)"]
    C -->|Kritikpunkte| B
    C -->|Freigabe / Genehmigung| D["4. Dein Menü: Approve oder Changes?"]
    D -->|Approve| E["5. Code wird geschrieben (Build)"]
    D -->|Changes| F["6. Änderungen (Editor, Web-UI oder Chat)"]
    F --> B
```

---

### 2. Architektur: Single-File Konzept (Kein Installer!)

**`loop.py` ist das gesamte Programm – es ist KEIN Installer!**

* **Alles in einer Datei:** Die gesamte Logik (Erkennung der KIs, Planung, Prüfung, Menüs, Tests, Wiederaufnahme) steckt komplett in `loop.py`.
* **Keine extra Pakete:** Es wird kein `pip install` oder virtuelles Environment benötigt. Es nutzt ausschließlich die Standardbibliothek von Python 3.10+.
* **Sofortige Updates:** Jede Änderung an `loop.py` ist im gesamten System sofort live aktiv.

---

### 3. Installation & Globaler Befehl (`~/.local/bin/claudegravity`)

Damit du den Befehl `claudegravity` bequem in **jedem beliebigen Ordner** deines Computers aufrufen kannst, wird eine Verknüpfung (Symlink) in deinem Benutzer-Befehlsverzeichnis angelegt:

```bash
# 1. In das geklonte Repository wechseln:
cd ~/Projekte/claudegravity-loop

# 2. Datei als ausführbar markieren:
chmod +x loop.py

# 3. Globalen Symlink anlegen:
mkdir -p ~/.local/bin
ln -sf ~/Projekte/claudegravity-loop/loop.py ~/.local/bin/claudegravity
ln -sf ~/Projekte/claudegravity-loop/loop.py ~/.local/bin/claudegravity-loop
```

*(Hinweis: `~/.local/bin` ist unter modernen Linux- und Mac-Systemen standardmäßig im Suchpfad `$PATH` enthalten. Falls der Befehl nicht sofort gefunden wird, öffne ein neues Terminalfenster).*

---

### 4. Voraussetzungen & KI-Prüfung (`--check`)

Du benötigst lediglich:
1. **Python 3.10 oder neuer** (auf fast jedem Linux/Mac bereits vorinstalliert).
2. Mindestens zwei dieser KIs im Terminal angemeldet:
   * **Claude Code** (`claude`)
   * **Google Antigravity** (`agy`) oder **Gemini CLI** (`gemini`)

Prüfe deine Installation mit einem einzigen Befehl:
```bash
claudegravity --check
```

---

### 5. Die wichtigsten Befehle auf einen Blick (Spickzettel)

| Befehl | Wofür wird er benutzt? |
| :--- | :--- |
| `claudegravity --check` | Prüft installierte KIs, Standard-Modelle und Optionen |
| `claudegravity "Aufgabe"` | Startet den Loop im aktuellen Ordner |
| `claudegravity -i "Aufgabe"` | **Fragen-Modus:** KIs stellen dir Rückfragen bei Unklarheiten |
| `claudegravity --yolo "Aufgabe"` | **Autopilot:** Startet direkt mit vollen Schreibrechten (keine Nachfragen) |
| `claudegravity -p /pfad/zum/projekt "Aufgabe"` | Führt die Aufgabe in einem anderen Projektordner aus |
| `claudegravity --resume` oder `claudegravity -c` | Setzt eine unterbrochene Sitzung exakt an gleicher Stelle fort |
| `claudegravity --reviewer-effort high "Aufgabe"` | Maximale Prüf-Intensität / Thinking Effort für Antigravity |

---

### 6. Schritt-für-Schritt: Dein erster Durchlauf

1. **Öffne dein Terminal** und wechsle in dein Wunsch-Projekt:
   ```bash
   cd ~/Projekte/mein-projekt
   ```

2. **Starte den Loop mit deiner Aufgabe:**
   ```bash
   claudegravity "Refaktoriere das Spielplan-Modul und erstelle Unit-Tests"
   ```

3. **Was jetzt automatisch passiert:**
   * **Phase 1 (Plan):** Claude liest dein Projekt und schreibt einen Schritt-für-Schritt-Plan.
   * **Phase 2 (Review):** Antigravity liest den Plan, sucht nach Fehlern und gibt sein Urteil ab (`APPROVED` oder `REVISE`). Bei Kritik bessert Claude den Plan automatisch nach (maximal 2 Runden, um Tokens zu schonen).
   * **Plan-Freigabe:** Sobald der Plan fertig ist, stoppt das Tool und zeigt dir das Menü.

---

### 7. Das Menü: Plan freigeben oder ändern (Approve & Changes)

Sobald Phase 2 abgeschlossen ist, erscheint dieses Menü:

```text
============================================================
📋 PLAN-STATUS: Fertiggestellt & Geprüft
📄 Aktuelle Plan-Datei: .dual-loop/sessions/<session>/PLAN_v2.md
============================================================
Möchtest du den Plan freigeben oder Änderungen vornehmen?
  [1] Approve  -> Plan genehmigen & weiter zur Implementierung
  [2] Changes  -> Änderungen/Feedback anbringen
  [3] Anzeigen -> Plan direkt hier im Terminal lesen
  [4] Beenden  -> Abbrechen (Fortsetzen später mit --resume möglich)
------------------------------------------------------------
Auswahl [1/2/3/4] (Standard: 1):
```

#### Wenn du `[2] Changes` wählst:
Es öffnet sich das Change-Routing-Menü:

```text
[UI-Varianten (Graphische Oberfläche)]:
  [1] Im Editor öffnen (VS Code / Antigravity / Cursor / System)
      -> Öffnet die Plan-Datei direkt im Editor zum manuellen Anpassen
  [2] Claude UI (Web / Desktop)
      -> Zeigt dir den Pfad zum Kopieren in deine Claude Web-UI

[CLI-Varianten (Terminal)]:
  [3] Feedback direkt hier eintippen
      -> Tippe z. B.: "Nimm PostgreSQL statt SQLite". Die KI baut den Plan um!
  [4] Interaktive Claude Code CLI-Session starten
  [5] Interaktive Antigravity CLI-Session starten
  [6] Zurück zum Hauptmenü
```

---

### 8. Fragen-Modus: KIs stellen Fragen an dich (`-i` / `--ask`)

Wenn du eine Aufgabe hast, bei der wichtige Entscheidungen oder Annahmen nötig sind, aktiviere den Fragen-Modus mit `-i` (oder `--ask`):

```bash
claudegravity -i "Baue ein Benachrichtigungssystem"
```

Beide KIs binden dich gezielt ein:
1. **Planer (Claude):** Stellt dir bis zu 3 konkrete Rückfragen (z.B. Mail vs. Push, Datenformat), bevor der Entwurf finalisiert wird. Du antwortest direkt im Terminal.
2. **Prüfer (Antigravity):** Prüft den Plan und stellt bei Zielkonflikten oder Sicherheitsrisiken Rückfragen an dich. Deine Antworten fließen direkt in Runde 2 des Plans ein.

---

### 9. Modelle & Intensität anpassen (`--model`, `--effort`)

Standardmäßig nutzen beide Tools (`claude`, `agy`) ihre in der CLI hinterlegten Standard-Modelle. Du kannst dies pro Aufgabe frei anpassen:

* `--planner-model <name>`: Modell für Planung/Bau (z.B. `sonnet`, `opus`, `gemini-4-argon-high`)
* `--reviewer-model <name>`: Modell für den Prüfer (z.B. `gemini-4-argon-high`, `gemini-3.8-flash-high`)
* `--effort <low|medium|high|xhigh|max>`: Thinking/Reasoning-Intensität für Antigravity (`agy`)
* `--reviewer-effort <effort>`: Spezifische Prüf-Intensität (z.B. `high` oder `max` für gründliche Adversarial Reviews)

**Beispiel mit maximaler Prüf-Schärfe und Fragen-Modus:**
```bash
claudegravity --reviewer-effort max -i "Refaktoriere das Spielplan-Modul"
```

---

### 10. Weitermachen nach Pause oder Absturz (`--resume`)

Wurde der PC ausgeschaltet, das Terminal geschlossen oder hast du mit `Ctrl+C` abgebrochen? **Keine Sorge, nichts geht verloren!**

Tippe einfach:
```bash
claudegravity --resume
# oder kurz:
claudegravity -c
```
Das Skript liest die gespeicherte `state.json` aus dem Session-Ordner ein und macht **an genau der Stelle weiter**, an der gestoppt wurde.

---

### 11. Schreibrechte & der Autopilot (`--yolo`)

KIs laufen im Hintergrund ohne Fenster. Damit eine KI nicht unbemerkt Dateien verändert, verlangt das System normalerweise eine Bestätigung.

* **Standard:** Vor Phase 3 fragt dich das Skript:  
  *„Soll Claude Code volle Schreib-/Tool-Rechte erhalten? [J/n]“* (Drücke einfach `Enter`).
* **Autopilot (`--yolo`):** Wenn du gar nicht gefragt werden möchtest:
  ```bash
  claudegravity --yolo "Erstelle eine neue Funktion"
  ```
  Das Flag `--yolo` schaltet die Schreibrechte für den gesamten Durchlauf automatisch frei.

---

### 12. Was passiert bei AI-Sitzungslimits? (Token-Limits)

Wenn Claude Code oder Antigravity an das persönliche Abonnements-Limit stößt (`You've hit your session limit · resets 3:20pm`), stürzt `claudegravity` **nicht** ab. Es sichert den Stand sofort in `state.json` und gibt dir die Wahl:
1. **Modell-Wechsel:** Das andere installierte Modell (z. B. `agy` statt `claude`) übernimmt sofort die Rolle und führt den Schritt nahtlos zu Ende.
2. **Warten per Countdown:** Wartet per Timer bis zur angegebenen Reset-Uhrzeit und setzt danach automatisch fort.
3. **Sauber beenden:** Sichert den Stand – du kannst später mit `claudegravity -c` weitermachen.

Mit `--auto-switch` wechselt das System bei Limits sogar vollautomatisch auf das Alternativ-Modell!

---

### 13. Wo liegen meine Dateien? (Saubere Ordnerstruktur)

In jedem Projekt, in dem du `claudegravity` ausführst, wird ein sauberer Ordner namens `.dual-loop/` angelegt. **Alle** Pläne, Reviews und Logs liegen isoliert im jeweiligen Session-Ordner:

```
mein-projekt/
├── .dual-loop/
│   └── sessions/                   # 📦 Revisionssicheres Archiv aller Aufgaben
│       └── 20261017_102220_task/
│           ├── state.json          # Sitzungs-Speicher für --resume
│           ├── .done               # 🏁 Fertigmeldung der Aufgabe (isoliert im Session-Ordner!)
│           ├── LOG.md              # 📜 Audit-Log der Review-Runden dieser Aufgabe
│           ├── PLAN_v1.md          # Erster Entwurf
│           ├── REVIEW_round1.md    # Kritik von Antigravity
│           ├── PLAN_v2.md          # Überarbeiteter Entwurf
│           └── REVIEW_round2.md
└── logs/                           # 💬 Ausführliche Terminal-Ausgaben
```

---

### 14. Häufige Fragen & Fehlerbehebung (FAQ)

**Kostet mich der Loop extra Geld?**  
Nein! Es werden ausschließlich deine bestehenden Abos deiner Terminal-Tools (`claude`, `agy`) genutzt. Es fallen keine API-Gebühren pro Token an.

**Was bedeutet `Maximale Review-Runden erreicht`?**  
Wenn sich die KIs nach 2 Runden nicht einig sind, bricht das Tool ab und fragt dich um Rat. Das spart Tokens und verhindert Endlosschleifen.

**Wie beende ich den Loop sicher?**  
Drücke einfach einmal `Ctrl+C`. Das Programm beendet die aktuelle Runde sauber und sichert den Zwischenstand ab.

---
---

# 🇬🇧 English Documentation (For Beginners)

---

### 1. What is ClaudeGravity Loop? (Explained Simply)

Imagine a building construction site:
* **The Architect (e.g., Claude Code):** Drafts the blueprints and builds the house.
* **The Independent Inspector (e.g., Antigravity / Gemini):** Scrutinizes the blueprint for structural flaws, security issues, and missing details.

When an AI evaluates its own plans, it suffers from *confirmation bias*. **ClaudeGravity Loop** pairs two independent AIs:
1. **Claude** writes the plan.
2. **Antigravity** ruthlessly stress-tests and reviews the plan.
3. Once approved, the code is implemented and verified.
4. **Zero API Fees:** Runs through your existing terminal subscriptions—no expensive per-token API keys required!

---

### 2. Architecture: Single-File Concept (Not an Installer!)

**`loop.py` is the entire application—it is NOT an installer!**

* **Everything in one file:** All orchestration logic (AI CLI detection, planning, adversarial review, approval menus, autonomous build loop, crash recovery) lives directly inside `loop.py`.
* **Zero dependencies:** No `pip install` or virtual environments required. It uses standard Python 3.10+ libraries only.
* **Instant updates:** Any change made to `loop.py` is immediately live across your entire system.

---

### 3. Installation & Global Command Setup (`~/.local/bin/claudegravity`)

To run `claudegravity` conveniently from **any directory** on your machine, create a symlink in your user binaries folder:

```bash
# 1. Navigate to the repository:
cd ~/Projekte/claudegravity-loop

# 2. Make the script executable:
chmod +x loop.py

# 3. Create global symlinks:
mkdir -p ~/.local/bin
ln -sf ~/Projekte/claudegravity-loop/loop.py ~/.local/bin/claudegravity
ln -sf ~/Projekte/claudegravity-loop/loop.py ~/.local/bin/claudegravity-loop
```

*(Note: `~/.local/bin` is already part of `$PATH` on most Linux and macOS systems. If the command is not immediately recognized, open a fresh terminal).*

---

### 4. Prerequisites & Verification (`--check`)

You only need:
1. **Python 3.10+** (preinstalled on Linux and macOS).
2. At least two AI CLIs logged in on your system:
   * **Claude Code** (`claude`)
   * **Google Antigravity** (`agy`) or **Gemini CLI** (`gemini`)

Verify your installation with:
```bash
claudegravity --check
```

---

### 5. Quick Command Cheatsheet

| Command | Description |
| :--- | :--- |
| `claudegravity --check` | Verify installed AIs, default models, and available options |
| `claudegravity "Task"` | Run task in the current folder (asks for permission before building) |
| `claudegravity -i "Task"` | **Interview Mode:** Both AIs ask clarifying questions if anything is ambiguous |
| `claudegravity --yolo "Task"` | **Autopilot:** Run hands-free with full tool permissions granted automatically |
| `claudegravity -p /path/to/project "Task"` | Run the task in an external project directory |
| `claudegravity --resume` or `claudegravity -c` | Resume an interrupted session exactly where it stopped |
| `claudegravity --reviewer-effort high "Task"` | Set maximum reasoning effort for Antigravity review |

---

### 6. Step-by-Step: Your First Run

1. Open your terminal and navigate to your project:
   ```bash
   cd ~/Projekte/my-project
   ```

2. Run your task:
   ```bash
   claudegravity "Refactor tournament module and add unit tests"
   ```

3. **What happens automatically:**
   * **Phase 1 (Plan):** Claude inspects the codebase and drafts a step-by-step roadmap.
   * **Phase 2 (Review):** Antigravity reviews the plan and flags risks. Claude refines the plan if needed (max 2 rounds to conserve tokens).
   * **Plan Approval:** Once ready, the tool pauses and displays the interactive approval menu.

---

### 7. Plan Approval & Changes Menu

When Phase 2 finishes, you will see this menu:

```text
============================================================
📋 PLAN STATUS: Completed & Reviewed
📄 Current Plan File: .dual-loop/sessions/<session>/PLAN_v2.md
============================================================
What would you like to do?
  [1] Approve  -> Approve plan & proceed to implementation
  [2] Changes  -> Request modifications/feedback
  [3] View     -> Read plan directly in terminal
  [4] Exit     -> Cancel (can be resumed later with --resume)
------------------------------------------------------------
Choice [1/2/3/4] (Default: 1):
```

#### If you choose `[2] Changes`:
The change routing menu puts comfortable graphical UI options on top and terminal CLI options at the bottom:

```text
[UI Options (Graphical Interfaces)]:
  [1] Open in Editor (VS Code / Antigravity / Cursor / System)
      -> Opens the plan file directly in your editor for quick manual edits
  [2] Claude UI (Web / Desktop)
      -> Displays file path to copy/paste into Claude Web UI

[CLI Options (Terminal)]:
  [3] Type feedback directly here
      -> E.g. "Use PostgreSQL instead of SQLite". The AI rewrites the plan!
  [4] Launch interactive Claude Code CLI session
  [5] Launch interactive Antigravity CLI session
  [6] Return to main menu
```

---

### 8. Interview Mode: AIs Ask You Questions (`-i` / `--ask`)

When working on complex tasks with trade-offs or architectural decisions, activate Interview Mode:

```bash
claudegravity -i "Build an authentication service"
```

Both agents will interact with you directly:
1. **Planner (Claude):** Asks up to 3 specific clarifying questions before finalizing the roadmap. You answer in the terminal.
2. **Reviewer (Antigravity):** Highlights critical edge cases or trade-offs and asks for your guidance. Your answers are passed into Plan Round 2.

---

### 9. Model Selection & Reasoning Effort (`--model`, `--effort`)

By default, the CLIs use their configured default models and effort. You can customize them per task:

* `--planner-model <name>`: Model for planning/coding (e.g., `sonnet`, `opus`, `gemini-4-argon-high`)
* `--reviewer-model <name>`: Model for review (e.g., `gemini-4-argon-high`, `gemini-3.8-flash-high`)
* `--effort <low|medium|high|xhigh|max>`: Reasoning effort for Antigravity (`agy`)
* `--reviewer-effort <effort>`: Specific effort for the review stage (e.g., `high` or `max` for deeper critique)

**Example with high reviewer reasoning effort and interview mode:**
```bash
claudegravity --reviewer-effort max -i "Refactor payment module"
```

---

### 10. Crash Recovery & Resuming (`--resume`)

If your terminal closes, your computer restarts, or you pressed `Ctrl+C`, **no progress is lost!**

Simply run:
```bash
claudegravity --resume
# or:
claudegravity -c
```
It reads the session state from `state.json` and resumes execution right where it stopped.

---

### 11. File Permissions & Autopilot (`--yolo`)

Headless AI tools require permissions to modify files on disk.

* **Interactive:** Before Phase 3, you are asked: *„Grant full write permissions? [J/n]“* (simply press `Enter`).
* **Autopilot (`--yolo`):** Skip the question completely:
  ```bash
  claudegravity --yolo "Refactor module"
  ```

---

### 12. What Happens When AI Limits Are Hit? (Session Limits)

If Claude Code or Antigravity hits a personal subscription limit (`You've hit your session limit · resets 3:20pm`), `claudegravity` does **not** crash. It safely saves state and offers 3 options:
1. **Model Switch:** The alternative installed model (e.g. `agy` taking over for `claude`) seamlessly finishes the task.
2. **Wait Timer:** Waits with a countdown until the reset time and resumes automatically.
3. **Safe Exit:** Cleanly saves progress so you can resume later with `claudegravity -c`.

With `--auto-switch`, the tool will automatically failover to the alternative model without asking!

---

### 13. Directory Structure & File Storage

All plans, audits, and sessions are safely stored in `.dual-loop/`. Every file belongs strictly to its task session:

```
my-project/
├── .dual-loop/
│   └── sessions/                   # 📦 Clean, versioned task archive
│       └── 20261017_102220_task/
│           ├── state.json          # Session state for --resume
│           ├── .done               # 🏁 Task completion marker (isolated in session!)
│           ├── LOG.md              # 📜 Audit log of review rounds
│           ├── PLAN_v1.md          # Initial roadmap
│           ├── REVIEW_round1.md    # Critique by reviewer
│           ├── PLAN_v2.md          # Revised roadmap
│           └── REVIEW_round2.md
└── logs/                           # 💬 Detailed terminal execution logs
```

---

### 14. Frequently Asked Questions (FAQ)

**Does this cost extra API fees?**  
No! It runs through your official terminal CLIs (`claude`, `agy`) using your active personal subscriptions.

**What happens if models disagree?**  
To prevent token waste, reviews are capped at 2 rounds. If disagreement persists, the tool pauses and asks you for guidance.

**How do I safely stop a running loop?**  
Press `Ctrl+C` once. The runner cleanly wraps up the current step and saves the state so you can resume later.

---

## 📄 License
MIT License. Free and Open Source.
