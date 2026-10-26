"""Sprache der Terminal-Ausgaben: Deutsch (Standard) oder Englisch (`--lang en`, `CLAUDEGRAVITY_LANG=en`).

Der Code schreibt seine Meldungen weiter auf Deutsch. `translate()` übersetzt eine fertige Meldung anhand
des Katalogs `EN`: Jeder Schlüssel ist die deutsche Vorlage mit `{}` für eingesetzte Werte, der Wert die
englische Vorlage (`{0}`, `{1}` … für eine andere Reihenfolge). Eingesetzte Werte werden ihrerseits übersetzt,
etwa Rollennamen. Unbekannte Meldungen (z. B. Modellantworten) bleiben unverändert.
"""

import locale
import os
import re
import string

LANGS = ("de", "en")
MAX_TRANSLATE = 20000  # längere Texte (Modellantworten) bleiben unverändert


def detect_lang(env: dict | None = None) -> str:
    """Sprache aus CLAUDEGRAVITY_LANG; `auto` liest die Locale (de* → de, sonst en). Standard: de."""
    env = os.environ if env is None else env
    wanted = (env.get("CLAUDEGRAVITY_LANG") or "de").strip().lower()
    if wanted in LANGS:
        return wanted
    if wanted != "auto":
        return "de"
    return locale_lang(env)


def locale_lang(env: dict | None = None) -> str:
    """de, wenn die Locale deutsch ist (LC_ALL, LC_MESSAGES, LANG oder System), sonst en."""
    env = os.environ if env is None else env
    name = next((env.get(k) for k in ("LC_ALL", "LC_MESSAGES", "LANG") if env.get(k)), "") or ""
    if not name or name.split(".")[0] in ("C", "POSIX"):
        try:
            name = locale.getlocale()[0] or ""
        except ValueError:
            name = ""
    name = name.lower()
    return "de" if name.startswith("de") or name.startswith("german") else "en"


def resolve_lang(value: str | None) -> str:
    """Wert von --lang (de, en, auto oder None) in de/en auflösen."""
    if value in LANGS:
        return value
    if value == "auto":
        return locale_lang()
    return detect_lang()


# Satzbausteine, die als eingesetzte Werte vorkommen (Rollen, Statuszeile)
GLOSSARY = {
    "🏗️ Architekt (Planung & Entwurf)": "🏗️ Architect (planning & design)",
    "🧐 Prüfstatiker (Prüfung & Review)": "🧐 Reviewer (review & audit)",
    "🔨 Bauleiter (Bau & Umsetzung)": "🔨 Builder (build & implementation)",
    "🔎 Abnahme": "🔎 Acceptance",
    "🏗️ Architekt": "🏗️ Architect",
    "🧐 Prüfstatiker": "🧐 Reviewer",
    "🔨 Bauleiter": "🔨 Builder",
    "Prüfstatiker prüft den Plan": "Reviewer checks the plan",
    "Urteil auswerten: Freigabe oder Überarbeitung": "Evaluate verdict: approval or revision",
    "Urteil auswerten: fertig oder Nacharbeit": "Evaluate verdict: done or rework",
    "Fertigmeldung prüfen, sonst nächste Runde": "Check completion report, otherwise next round",
    "Architekt": "Architect",
    "Prüfstatiker": "Reviewer",
    "Bauleiter": "Builder",
    "Abnahme": "Acceptance",
    "keine": "none",
    "kein": "none",
}

EN = {
    # Statuszeile nach jedem Aufruf (runner.format_progress)
    "📍 {} · {} fertig nach {} · {}": "📍 {} · {} done after {} · {}",
    "   Weiter: {}": "   Next: {}",
    "   Weiter: {} · {}": "   Next: {} · {}",
    "Bau-Runde {}/{}": "Build round {}/{}",
    "Bau-Runde {}/{} · Etappe {}/{}": "Build round {}/{} · stage {}/{}",
    "Abnahme-Runde {}": "Acceptance round {}",
    "Plan-Runde {}": "Plan round {}",
    "Prüfbefehl `{}`": "Proof command `{}`",
    "+{} (gesamt {})": "+{} (total {})",
    "+{} (gesamt {}, {} gemeldet)": "+{} (total {}, {} reported)",
    "{} min {} s": "{} min {} s",
    # backends
    "ℹ️  agy hat ohne Antworttext geendet (abgelehnter Befehl?). Frage einmal in derselben Unterhaltung nach.": "ℹ️  agy ended without an answer (rejected command?). Asking once more in the same conversation.",
    "ℹ️  agy kennt das Modell „{}“ nicht, nehme „{}“.": "ℹ️  agy does not know the model “{}”, using “{}”.",
    "⚠️  agy kennt das Modell „{}“ nicht, nutze das Standardmodell der CLI. Verfügbar: {}": "⚠️  agy does not know the model “{}”, using the CLI's default model. Available: {}",
    "⚠️  Nachfrage bei agy fehlgeschlagen: {}": "⚠️  Follow-up with agy failed: {}",
    "🛡️  Datenschutzschild: {} vor dem Versand an {} geschwärzt.": "🛡️  Privacy shield: {} redacted before sending to {}.",
    # budget
    "\n🛑 Hartes Budget erreicht, Lauf beendet. Stand gesichert.": "\n🛑 Hard budget reached, run ended. State saved.",
    "💶 Budget-Warnung: {}": "💶 Budget warning: {}",
    # build
    "⏳ Warte auf 🔨 Bauleiter ({}) ({})...": "⏳ Waiting for 🔨 Builder ({}) ({})...",
    "\n📋 Zusammenfassung von 🔨 Bauleiter ({}) [{}]:": "\n📋 Summary from 🔨 Builder ({}) [{}]:",
    "[!] Suchen/Ersetzen nicht angewendet: {}": "[!] Search/replace not applied: {}",
    "\n📝 {} Datei(en) durch 🔨 Bauleiter ({}) aktualisiert:": "\n📝 {} file(s) updated by 🔨 Builder ({}):",
    "⚠️ Bauleiter-Sitzung ließ sich nicht fortsetzen ({}), starte mit vollem Auftrag neu...": "⚠️ Could not resume the Builder session ({}), restarting with the full brief...",
    # candidates
    "🚀 Kandidat `{}` baut in {} (Log: {})": "🚀 Candidate `{}` is building in {} (log: {})",
    "\n🔨 Phase 3: {} Kandidaten bauen parallel: {}": "\n🔨 Phase 3: {} candidates build in parallel: {}",
    "\n[*] ClaudeGravity Loop beendet.": "\n[*] ClaudeGravity Loop finished.",
    "Die Kandidaten bauen parallel ohne Rückfrage und brauchen volle Schreibrechte in ihren Worktrees. Erlauben? [J/n]: ": "The candidates build in parallel without prompts and need full write access in their worktrees. Allow? [Y/n]: ",
    "🛑 --candidates braucht mindestens zwei verfügbare Bauleiter (unbekannt: {}).": "🛑 --candidates needs at least two available Builders (unknown: {}).",
    "🛑 Der Kandidaten-Modus braucht ein Git-Repository mit mindestens einem Commit (jeder Kandidat bekommt einen Worktree).": "🛑 Candidate mode needs a Git repository with at least one commit (every candidate gets a worktree).",
    "Kandidaten nicht gestartet.": "Candidates not started.",
    "⚠️ Ohne --proof entscheidet allein die Abnahme, welcher Kandidat fertig ist.": "⚠️ Without --proof only the acceptance check decides which candidate is done.",
    "\n🔎 Phase 4: Abnahme wählt aus {} grünen Kandidaten: {}": "\n🔎 Phase 4: Acceptance picks from {} green candidates: {}",
    "🏆 Gewinner: `{}` (Branch `{}`).": "🏆 Winner: `{}` (branch `{}`).",
    "\n⏹️ Abbruchgrund: {}": "\n⏹️ Reason for stopping: {}",
    "⏹️ Kandidaten abgebrochen.": "⏹️ Candidates stopped.",
    "⚠️ Jeder verfügbare Anbieter hat selbst gebaut; die Abnahme ist nicht unabhängig.": "⚠️ Every available provider built a candidate itself; the acceptance check is not independent.",
    "⚠️ Die Abnahme nannte keinen gültigen Gewinner; gewählt nach kleinstem Eingriff: `{}`.": "⚠️ The acceptance check named no valid winner; picked by smallest change: `{}`.",
    "🏁 Kandidat `{}` fertig nach {} s (Rückgabe {})": "🏁 Candidate `{}` finished after {} s (exit code {})",
    "| Kandidat | Fertig | Prüfbefehl | Testwächter | Tokens | Dauer |": "| Candidate | Done | Proof | Test guard | Tokens | Duration |",
    # cli: --check
    "🖥️  Betriebssystem: {} (Python {})": "🖥️  Operating system: {} (Python {})",
    "🔍 Erkannte KI-Systeme & Endpoints auf deinem System:": "🔍 AI systems & endpoints detected on your system:",
    "🎯 Standard-Belegung auf diesem System (wenn NICHTS explizit angegeben wird):": "🎯 Default roles on this system (when NOTHING is set explicitly):",
    "1. 🏗️ Architekt (Phase 1: Planung & Entwurf):": "1. 🏗️ Architect (phase 1: planning & design):",
    "   • CLI           : {} (`{}`)": "   • CLI           : {} (`{}`)",
    "   • Modell        : {} von {} (änderbar via --architekt-model)": "   • Model         : {} of {} (change with --architekt-model)",
    "   • Thinking-Effort: {}": "   • Thinking effort: {}",
    "   • Aufgabe       : Entwirft den Plan (Phase 1) [nur ~10-15% aller Tokens]": "   • Job           : Drafts the plan (phase 1) [only ~10-15% of all tokens]",
    "\n2. 🧐 Prüfstatiker (Phase 2: Prüfung & Review / Stresstest):": "\n2. 🧐 Reviewer (phase 2: review & stress test):",
    "   • Modell        : {} von {} (änderbar via --pruefstatiker-model)": "   • Model         : {} of {} (change with --pruefstatiker-model)",
    "   • Aufgabe       : Grillt den Plan unabhängig auf Schwachstellen (Phase 2) [nur ~5-10% aller Tokens]": "   • Job           : Grills the plan independently for weaknesses (phase 2) [only ~5-10% of all tokens]",
    "\n3. 🔨 Bauleiter (Phase 3: Bau & Umsetzung / Implementation):": "\n3. 🔨 Builder (phase 3: build & implementation):",
    "   • CLI           : {} wie der Architekt (oder separat via --bauer / --builder)": "   • CLI           : {} like the Architect (or separately with --bauer / --builder)",
    "   • Modell        : Wie der Architekt (oder Sparmodell via --bauer-model / lokaler Server)": "   • Model         : Like the Architect (or a cheaper model with --bauer-model / local server)",
    "   • Thinking-Effort: Wie der Architekt (oder steuerbar via --bauer-effort, nur für agy/codex)": "   • Thinking effort: Like the Architect (or set with --bauer-effort, agy/codex/copilot only)",
    "   • Aufgabe       : Setzt den Plan autonom im Code um [verbraucht ~80-90% aller Tokens!]": "   • Job           : Implements the plan autonomously [uses ~80-90% of all tokens!]",
    "\n💡 Spar-Strategien & Kombi-Möglichkeiten:": "\n💡 Saving strategies & combinations:",
    "  • '--strategy eco'        : Bis zu 70% Token-Ersparnis (Architekt/Prüfstatiker Effort medium,": "  • '--strategy eco'        : Up to 70% fewer tokens (Architect/Reviewer effort medium,",
    "                             Bauleiter {} mit `{}`)": "                             Builder {} with `{}`)",
    "  • '--strategy best-code'  : Effort high in allen 3 Phasen (wirkt nur bei agy)": "  • '--strategy best-code'  : Effort high in all 3 phases (only effective with agy)",
    "\n⚙️  Wichtigste Steuerungs-Flags:": "\n⚙️  Most important flags:",
    "  - Strategie-Presets      : --strategy <best-code|eco|local-free|balanced>": "  - Strategy presets       : --strategy <best-code|eco|local-free|hybrid|balanced>",
    "  - Trockenlauf            : --dry-run (zeigt Rollen, Modelle & Befehl ohne Ausführung)": "  - Dry run                : --dry-run (shows roles, models & command without running)",
    "  - Eigener Endpunkt       : --endpoint <url> (z.B. http://localhost:11434/v1 oder http://192.168.1.50:11434/v1)": "  - Own endpoint           : --endpoint <url> (e.g. http://localhost:11434/v1 or http://192.168.1.50:11434/v1)",
    "  - Bauleiter-Endpunkt     : --bauer-endpoint <url> (z.B. http://localhost:11434/v1)": "  - Builder endpoint       : --bauer-endpoint <url> (e.g. http://localhost:11434/v1)",
    "  - Bauleiter festlegen    : --bauer / --builder <claude|agy|ollama|lmstudio|endpoint|codex|copilot>": "  - Choose the Builder     : --bauer / --builder <claude|agy|ollama|lmstudio|endpoint|codex|copilot>",
    "  - Bauleiter-Modell       : --bauer-model <name> (z.B. qwen2.5-coder:32b, haiku, gemini-3.8-flash)": "  - Builder model          : --bauer-model <name> (e.g. qwen2.5-coder:32b, haiku, gemini-3.8-flash)",
    "  - Auto-Fallback bei Limit: --auto-switch / --fallback (wechselt bei Limit nahtlos zum Alternativmodell)": "  - Auto fallback on limit : --auto-switch / --fallback (switches to an alternative model on a limit)",
    "  - Fragen-Modus aktivieren: -i / --ask (Agenten stellen bei Unklarheiten gezielte Fragen an dich)": "  - Question mode          : -i / --ask (agents ask you targeted questions when unclear)",
    '  - Prüfbefehl             : --proof "python -m unittest" (Loop führt ihn nach jeder Bau-Runde selbst aus)': '  - Proof command          : --proof "python -m unittest" (the loop runs it itself after every build round)',
    "  - Abnahme                : --abnahme <cli> (prüft den fertigen Code, nie der Bauleiter; --no-inspect schaltet ab)": "  - Acceptance             : --abnahme <cli> (checks the finished code, never the Builder; --no-inspect turns it off)",
    "  - Etappen                : --etappen auto|an|aus (Plan in kleinen Stücken; auto: an bei lokalen Bauleitern)": "  - Stages                 : --etappen auto|an|aus (plan in small pieces; auto: on for local Builders)",
    "  - Ohne Freigabe-Menü     : --plan-auto (baut nur, wenn der Prüfstatiker APPROVED meldet)": "  - Without approval menu  : --plan-auto (builds only when the Reviewer reports APPROVED)",
    "  - Token & Kosten-Audit   : Automatisch aktiv (wird in .done auditiert inkl. Rolle, Modell & Effort)": "  - Token & cost audit     : Always on (recorded in .done incl. role, model & effort)",
    "  {} {} (`{}` / `{}`){}": "  {} {} (`{}` / `{}`){}",
    "  (keine) Installiere z.B. `claude` oder `agy`, oder gib --endpoint <url> an.": "  (none) Install e.g. `claude` or `agy`, or pass --endpoint <url>.",
    "   • CLI           : {} (`{}`) – kein zweites Modell gefunden, prüft sich selbst!": "   • CLI           : {} (`{}`) – no second model found, it reviews itself!",
    "  • '--strategy local-free' : 0 € Kosten im Bau-Loop! {} plant, {} baut!": "  • '--strategy local-free' : €0 in the build loop! {} plans, {} builds!",
    "  • '--strategy local-free' : 0 € Kosten im Bau-Loop – aktuell kein lokaler Server erkannt": "  • '--strategy local-free' : €0 in the build loop – no local server detected right now",
    "                             (Ollama, LM Studio oder --bauer-endpoint <url> angeben)": "                             (start Ollama or LM Studio, or pass --bauer-endpoint <url>)",
    "  • '--strategy hybrid'     : {} plant und nimmt ab, {} prüft und baut in Etappen": "  • '--strategy hybrid'     : {} plans and accepts, {} reviews and builds in stages",
    "angemeldet": "signed in",
    "nicht angemeldet (claude login)": "not signed in (claude login)",
    "nicht angemeldet (gemini auth login)": "not signed in (gemini auth login)",
    "bereit": "ready",
    "lokal": "local",
    "nicht bereit": "not ready",
    "nicht erreichbar": "not reachable",
    # cli: Trockenlauf
    "🔍 ClaudeGravity Loop — Trockenlauf (Dry Run)": "🔍 ClaudeGravity Loop — dry run",
    "📌 Aufgabe        : {}": "📌 Task           : {}",
    "🎯 Strategie      : {}": "🎯 Strategy       : {}",
    "📁 Ziel-Projekt   : {}": "📁 Target project : {}",
    "\n1. 🏗️ Architekt (Phase 1: Planung & Entwurf):": "\n1. 🏗️ Architect (phase 1: planning & design):",
    "   • CLI/Endpoint  : {} (`{}`)": "   • CLI/endpoint  : {} (`{}`)",
    "   • Modell        : {}": "   • Model         : {}",
    "   • Effort        : {}": "   • Effort        : {}",
    "   • Token-Anteil  : Leichtgewichtig (~10-15% aller Tokens)": "   • Token share   : Lightweight (~10-15% of all tokens)",
    "   • Token-Anteil  : Leichtgewichtig (~5-10% aller Tokens)": "   • Token share   : Lightweight (~5-10% of all tokens)",
    "   • Token-Anteil  : Schwergewicht (~80-90% aller Tokens!)": "   • Token share   : Heavyweight (~80-90% of all tokens!)",
    "\n4. 🔎 Abnahme (Phase 4: Prüfung des fertigen Codes):": "\n4. 🔎 Acceptance (phase 4: check of the finished code):",
    "   • Prüfbefehl    : {}": "   • Proof command : {}",
    "\n💡 Wirtschaftlichkeits- & Qualitäts-Analyse:": "\n💡 Cost & quality analysis:",
    "\n🚀 Generierter Shell-Befehl (zum Starten):": "\n🚀 Generated shell command (to start):",
    "⚠️  Konfigurationskonflikt: {}": "⚠️  Configuration conflict: {}",
    "🧩 Vorlage `{}` ({})": "🧩 Template `{}` ({})",
    "   • Abgeschaltet (--no-inspect)": "   • Turned off (--no-inspect)",
    "\n🧩 Etappen-Modus: Architekt schneidet den Plan in Etappen, der Bauleiter setzt sie einzeln um, der Loop prüft jede (--etappen aus schaltet ab).": "\n🧩 Stage mode: the Architect cuts the plan into stages, the Builder implements them one by one, the loop checks each (--etappen aus turns it off).",
    "   • Spareffekt: 100% kostenlose Bau-Iterationen (0 € API-Kosten in Phase 3)!": "   • Saving: 100% free build iterations (€0 API cost in phase 3)!",
    "   • Grund: Phase 1 & 2 planen mit {} und {}. Der rechenintensive Bau-Loop": "   • Why: phases 1 & 2 plan with {} and {}. The compute-heavy build loop",
    "     läuft komplett auf {} (Modell: {}).": "     runs entirely on {} (model: {}).",
    "\n🔔 Hinweise:": "\n🔔 Notes:",
    "Nichts ausgeführt. Tipp: `claudegravity init` speichert deine Wahl als Profil.": "Nothing was run. Tip: `claudegravity init` saves your choice as a profile.",
    "   Prüfbefehl aus dem Projekt geraten: {} (anderer mit --proof)": "   Proof command guessed from the project: {} (another one with --proof)",
    "   • Eskalation    : nach {} erfolglosen Runden einmalig zu {}{}": "   • Escalation    : after {} unsuccessful rounds, once to {}{}",
    "   • Eskalation    : nicht möglich ({})": "   • Escalation    : not possible ({})",
    "   • Kein zweiter Anbieter verfügbar: keine unabhängige Abnahme möglich!": "   • No second provider available: no independent acceptance possible!",
    "   • CLI/Endpoint  : {} (`{}`), nie der Bauleiter": "   • CLI/endpoint  : {} (`{}`), never the Builder",
    "   • Spareffekt: Bis zu ~70% Kosten- und Tokenersparnis!": "   • Saving: up to ~70% less cost and tokens!",
    "   • Grund: Phase 1 & 2 planen mit {} und {} (Effort medium). Das ressourcenintensive": "   • Why: phases 1 & 2 plan with {} and {} (effort medium). The resource-heavy",
    "     Bauen in Phase 3 übernimmt {} mit dem Spar-Modell `{}`.": "     build in phase 3 is done by {} with the cheaper model `{}`.",
    "   Hinweis abgeschaltet ({}, guide = {}).": "   Hint turned off ({}, guide = {}).",
    "   • Spareffekt: Cloud nur für Plan und Abnahme ({}); Prüfung und Bau laufen lokal für 0 €.": "   • Saving: cloud only for plan and acceptance ({}); review and build run locally for €0.",
    "   • Grund: Kleine Etappen passen in den Kontext lokaler Modelle; jede Etappe prüft der Loop mit --proof.": "   • Why: small stages fit into the context of local models; the loop checks every stage with --proof.",
    "   Konnte das globale Profil nicht schreiben: {}": "   Could not write the global profile: {}",
    "   • Fokus: Höchste Code-Qualität, tiefes Reasoning und maximale Fehlertoleranz.": "   • Focus: highest code quality, deep reasoning and maximum fault tolerance.",
    "   • Alle Phasen laufen mit Effort high: {}, {}, {}.": "   • All phases run with effort high: {}, {}, {}.",
    "   • Ausgewogenes Standard-Verhältnis zwischen starker Planung und stabiler Umsetzung.": "   • Balanced default between strong planning and stable implementation.",
    "   • Hinweis: Effort wird nur an agy übergeben; andere CLIs nutzen ihre eigene Voreinstellung.": "   • Note: effort is only passed to agy; other CLIs use their own default.",
    "\nSo starten? [j/N]: ": "\nStart like this? [y/N]: ",
    # common
    "\n[!] Abbruch empfangen. Beende aktuelle Iteration sauber...": "\n[!] Abort received. Finishing the current iteration cleanly...",
    "\n⏳ Starte Countdown ({}s bis {}). Drücke [Strg+C] zum Abbrechen...": "\n⏳ Starting countdown ({}s until {}). Press [Ctrl+C] to cancel...",
    "\n⏰ Wartezeit abgelaufen! Setze Ausführung fort...": "\n⏰ Wait is over! Continuing...",
    "\n[!] Warten durch Nutzer abgebrochen.": "\n[!] Waiting cancelled by the user.",
    # metrics
    "📊 Ressourcen-Audit erfolgreich in {} eingetragen.": "📊 Resource audit written to {}.",
    # phases
    "[*] ClaudeGravity Loop gestartet": "[*] ClaudeGravity Loop started",
    "[*] Ziel-Projekt      : {}": "[*] Target project    : {}",
    "[*] Strategie         : {}": "[*] Strategy          : {}",
    "[*] 🏗️ Architekt      : {}": "[*] 🏗️ Architect      : {}",
    "[*] 🧐 Prüfstatiker   : {}": "[*] 🧐 Reviewer       : {}",
    "[*] 🔨 Bauleiter      : {}": "[*] 🔨 Builder        : {}",
    "[*] Session-ID        : {}": "[*] Session ID        : {}",
    "[*] Git-Workspace     : {}": "[*] Git workspace     : {}",
    "🌿 eigener Worktree pro Session": "🌿 own worktree per session",
    "\n🔨 Phase 3: Starte Implementierungs-Loop in {}...": "\n🔨 Phase 3: starting the implementation loop in {}...",
    "🔨 Ausführender Bauleiter: {}": "🔨 Builder: {}",
    "🔄 Setze letzte Sitzung fort: {}": "🔄 Resuming last session: {}",
    "📌 Ursprüngliche Aufgabe: {}": "📌 Original task: {}",
    "🔓 YOLO-Modus aktiv: Bauleiter erhält volle Tool- & Schreibrechte ({}); Architekt und Prüfstatiker bleiben lesend.": "🔓 YOLO mode on: the Builder gets full tool & write access ({}); Architect and Reviewer stay read-only.",
    "[*] Modus             : ❓ Fragen-Modus aktiv (--ask)": "[*] Mode              : ❓ question mode on (--ask)",
    "[*] Fallback          : 🔄 Auto-Switch aktiv (--auto-switch)": "[*] Fallback          : 🔄 auto switch on (--auto-switch)",
    "[*] Rollen-Status     : 🔄 Rollen getauscht (--swap)": "[*] Roles             : 🔄 roles swapped (--swap)",
    "[*] Etappen-Modus     : 🧩 Plan in Etappen, Bauleiter setzt sie einzeln um (--etappen aus schaltet ab)": "[*] Stage mode        : 🧩 plan in stages, the Builder implements them one by one (--etappen aus turns it off)",
    "\n🎉 Fertigmeldung ({}) gefunden! Aufgabe erfolgreich abgeschlossen.": "\n🎉 Completion report ({}) found! Task completed successfully.",
    "\n🔎 Phase 4: Abnahme (Runde {}) durch {}...": "\n🔎 Phase 4: acceptance (round {}) by {}...",
    "⚠️ Abnahme verweigert ({}). Der Bauleiter bessert nach.": "⚠️ Acceptance refused ({}). The Builder reworks.",
    "🧩 Etappen-Modus: {} Etappen, weiter mit Etappe {}.": "🧩 Stage mode: {} stages, continuing with stage {}.",
    "⬆️ Eskalation: {} → {} nach {}.": "⬆️ Escalation: {} → {} after {}.",
    "🛡️  Aufgabe enthält mögliche Zugangsdaten ({}); sie werden vor dem Versand an Cloud-Modelle geschwärzt.": "🛡️  The task contains possible credentials ({}); they are redacted before sending to cloud models.",
    "✅ {} vom Prüfstatiker genehmigt, Freigabe ohne Rückfrage (--plan-auto).": "✅ {} approved by the Reviewer, accepted without asking (--plan-auto).",
    "Implementierung nicht gestartet.": "Implementation not started.",
    "\n⚙️  Berechtigungs-Prüfung für Phase 3 (Implementierung):": "\n⚙️  Permission check for phase 3 (implementation):",
    "Soll 🔨 Bauleiter ({}) volle Schreib-/Tool-Rechte erhalten ({})? [J/n]: ": "Give 🔨 Builder ({}) full write/tool access ({})? [Y/n]: ",
    "🔎 Abnahme des fertigen Codes durch: {}": "🔎 Acceptance of the finished code by: {}",
    "⚠️ Keine unabhängige Abnahme möglich: Es ist kein zweiter Anbieter verfügbar. Der Bauleiter prüft sich selbst.": "⚠️ No independent acceptance possible: there is no second provider. The Builder checks itself.",
    "⚠️ {} hat sich seit Baubeginn geändert. Der Bauleiter arbeitet mit der neuen Fassung weiter.": "⚠️ {} changed since the build started. The Builder continues with the new version.",
    "🧪 Führe Prüfbefehl aus: {}": "🧪 Running proof command: {}",
    "🛑 Abnahme-Limit ({}) erreicht. Offene Befunde stehen in {}/INSPECTION_round*.md.": "🛑 Acceptance limit ({}) reached. Open findings are in {}/INSPECTION_round*.md.",
    "✅ Abnahme erteilt ({}).": "✅ Accepted ({}).",
    "🛑 Abnahme-Limit ({}) erreicht. Befunde: {}/INSPECTION_round{}.md": "🛑 Acceptance limit ({}) reached. Findings: {}/INSPECTION_round{}.md",
    "ℹ️  Der Plan enthält keinen Abschnitt `## Etappen` mit mindestens zwei Etappen. Der Bauleiter baut den ganzen Plan auf einmal.": "ℹ️  The plan has no `## Etappen` section with at least two stages. The Builder builds the whole plan at once.",
    "⚠️  Ohne --proof gilt jede Etappe nach einer Bau-Runde als erledigt. Mit --proof prüft der Loop jede Etappe selbst.": "⚠️  Without --proof every stage counts as done after one build round. With --proof the loop checks every stage itself.",
    "\n==================== Iteration {}/{} · {} ====================\n{}\n": "\n==================== Iteration {}/{} · {} ====================\n{}\n",
    "🌿 Git-Workspace bleibt für die Nacharbeit erhalten: {}": "🌿 Git workspace kept for rework: {}",
    "\n🔍 Unterbrochene Sitzung gefunden: {}": "\n🔍 Interrupted session found: {}",
    "📌 Aufgabe: {}": "📌 Task: {}",
    "⚠️  Aufgabe enthält mögliche Zugangsdaten ({}) und der Datenschutzschild ist aus: sie gehen im Klartext an {}. Besser als Umgebungsvariable übergeben.": "⚠️  The task contains possible credentials ({}) and the privacy shield is off: they go to {} in plain text. Better pass them as an environment variable.",
    "✅ {}: Rundenlimit erreicht, kein HOCH-Befund offen. Gebaut wird mit den Hinweisen des Prüfstatikers.": "✅ {}: round limit reached, no HIGH finding open. Building with the Reviewer's notes.",
    "🛑 Der Prüfstatiker hat {} nicht freigegeben. Ohne Rückfrage (--plan-auto) wird nicht gebaut.": "🛑 The Reviewer did not approve {}. Without asking (--plan-auto) nothing is built.",
    "🔓 Schreibberechtigung aktiviert ({}).": "🔓 Write access granted ({}).",
    "🔒 Eingeschränkter Modus: Bestätigung bei jedem Tool-Call erforderlich.": "🔒 Restricted mode: every tool call needs confirmation.",
    "❌ Prüfbefehl ist rot. Fertigmeldung zurückgewiesen.": "❌ Proof command is red. Completion report rejected.",
    "❌ Testwächter (strict): Fertigmeldung zurückgewiesen.": "❌ Test guard (strict): completion report rejected.",
    "⚠️ Eskalation nicht möglich: {}. {} baut weiter.": "⚠️ Escalation not possible: {}. {} keeps building.",
    "❌ {} noch nicht fertig (Versuch {}/{}).": "❌ {} not done yet (attempt {}/{}).",
    "[!] Fehler bei Iteration {}: {}": "[!] Error in iteration {}: {}",
    "Möchtest du diese Sitzung fortsetzen? [J/n]: ": "Resume this session? [Y/n]: ",
    "🔁 Nacharbeit als Etappe {} angehängt.": "🔁 Rework added as stage {}.",
    "🛑 {} ist nach {} Versuchen nicht grün. Stand gesichert; weiter mit 'claudegravity -c'.": "🛑 {} is not green after {} attempts. State saved; continue with 'claudegravity -c'.",
    "🌿 Git-Workspace bleibt für die Fortsetzung erhalten: {}": "🌿 Git workspace kept for resuming: {}",
    "\n[+] Abgebrochen. Stand gesichert, weiter mit 'claudegravity -c'.": "\n[+] Stopped. State saved, continue with 'claudegravity -c'.",
    "\n[+] Maximale Rundenanzahl ({}) erreicht. Stand gesichert.": "\n[+] Maximum number of rounds ({}) reached. State saved.",
    "Etappe {}/{}": "Stage {}/{}",
    "Etappe {}": "Stage {}",
    # planning
    "\n📁 Session-Ordner: {}": "\n📁 Session folder: {}",
    "🚀 Phase 1: Plan-Entwurf durch 🏗️ Architekt ({}) im Kontext von {}...": "🚀 Phase 1: plan draft by 🏗️ Architect ({}) in the context of {}...",
    "⏳ Warte auf 🏗️ Architekt ({})...": "⏳ Waiting for 🏗️ Architect ({})...",
    "📄 Plan v1 gespeichert in {}": "📄 Plan v1 saved to {}",
    "🔄 Wiederaufnahme: Geladen {}": "🔄 Resuming: loaded {}",
    "\n🔍 Phase 2: Unabhängiges Review (Runde {}/{}) durch 🧐 Prüfstatiker ({})...": "\n🔍 Phase 2: independent review (round {}/{}) by 🧐 Reviewer ({})...",
    "⏳ Warte auf Review von 🧐 Prüfstatiker ({})...": "⏳ Waiting for the review by 🧐 Reviewer ({})...",
    "📋 Review gespeichert in {}": "📋 Review saved to {}",
    "📋 PLAN-STATUS: Fertiggestellt & Geprüft": "📋 PLAN STATUS: finished & reviewed",
    "📄 Aktuelle Plan-Datei             : {}": "📄 Current plan file               : {}",
    "🏗️ Architekt (Planung & Bau)       : {}": "🏗️ Architect (planning & build)    : {}",
    "🧐 Prüfstatiker (Prüfung & Review) : {}": "🧐 Reviewer (review & audit)       : {}",
    "Möchtest du den Plan freigeben, Rollen tauschen oder Änderungen vornehmen?": "Do you want to approve the plan, swap roles or make changes?",
    "  [1] Approve  -> Plan genehmigen & weiter zur Implementierung": "  [1] Approve  -> approve the plan & go on to implementation",
    "  [2] Changes  -> Änderungen/Feedback anbringen": "  [2] Changes  -> add changes/feedback",
    "  [3] Swap     -> Rollen tauschen (Architekt <-> Prüfstatiker)": "  [3] Swap     -> swap roles (Architect <-> Reviewer)",
    "  [4] Anzeigen -> Plan direkt hier im Terminal lesen": "  [4] Show     -> read the plan here in the terminal",
    "  [5] Beenden  -> Abbrechen (Fortsetzen später mit --resume möglich)": "  [5] Quit     -> stop (resume later with --resume)",
    "⚠️ Modell versuchte eine Datei anzulegen. Erzwinge reine Textausgabe...": "⚠️ The model tried to create a file. Forcing plain text output...",
    "⚠️ {} enthielt einen Berechtigungsfehler. Nutze Vorgängerversion.": "⚠️ {} contained a permission error. Using the previous version.",
    "⚠️ {} wurde nach der Freigabe geändert. Die Freigabe gilt nicht mehr, Review startet neu.": "⚠️ {} was changed after approval. The approval no longer holds, the review starts again.",
    "🎉 Plan wurde in einer früheren Sitzung bereits genehmigt!": "🎉 The plan was already approved in an earlier session!",
    "ℹ️  Urteil: {}": "ℹ️  Verdict: {}",
    "🎉 Plan von 🧐 Prüfstatiker ({}) genehmigt!": "🎉 Plan approved by 🧐 Reviewer ({})!",
    "❓ 🏗️ Architekt ({}) hat Rückfragen an dich:": "❓ 🏗️ Architect ({}) has questions for you:",
    "⚠️ Prüfer-Sitzung ließ sich nicht fortsetzen, prüfe den vollständigen Plan neu...": "⚠️ Could not resume the Reviewer session, reviewing the full plan again...",
    "⚠️ Kritikpunkte von 🧐 Prüfstatiker ({}). 🏗️ Architekt ({}) bessert den Plan nach...": "⚠️ Findings from 🧐 Reviewer ({}). 🏗️ Architect ({}) revises the plan...",
    "⏳ Warte auf Überarbeitung durch 🏗️ Architekt ({})...": "⏳ Waiting for the revision by 🏗️ Architect ({})...",
    "📄 Plan v{} gespeichert in {}": "📄 Plan v{} saved to {}",
    "🛑 Maximale Review-Runden erreicht.": "🛑 Maximum review rounds reached.",
    "\n🔄 Rollen erfolgreich getauscht:": "\n🔄 Roles swapped:",
    "   🏗️ Neuer Architekt (Planung & Entwurf): {}": "   🏗️ New Architect (planning & design): {}",
    "   🧐 Neuer Prüfstatiker (Prüfung & Review): {}": "   🧐 New Reviewer (review & audit): {}",
    "⏳ 🏗️ Architekt ({}) bezieht deine Vorgaben in Plan v1 ein...": "⏳ 🏗️ Architect ({}) is including your input in plan v1...",
    "⚠️ Modell versuchte erneut eine Datei anzulegen. Erzwinge reinen Text...": "⚠️ The model tried again to create a file. Forcing plain text...",
    "Auswahl [1/2/3/4/5] (Standard: 1): ": "Choice [1/2/3/4/5] (default: 1): ",
    "❓ 🧐 Prüfstatiker ({}) hat Rückfragen an dich:": "❓ 🧐 Reviewer ({}) has questions for you:",
    "Abgebrochen. Du kannst diesen Stand jederzeit mit 'claudegravity --resume' fortsetzen.": "Stopped. You can resume this state any time with 'claudegravity --resume'.",
    "📝 Deine Antwort / Klärung (oder [Enter] zum Überspringen): ": "📝 Your answer / clarification (or [Enter] to skip): ",
    "💬 WO / WIE MÖCHTEST DU DIE ÄNDERUNGEN VORNEHMEN?": "💬 WHERE / HOW DO YOU WANT TO MAKE THE CHANGES?",
    "[UI-Varianten (Graphische Oberfläche)]:": "[UI options (graphical)]:",
    "  [1] Im Editor öffnen (VS Code / Antigravity / Cursor / System)": "  [1] Open in the editor (VS Code / Antigravity / Cursor / system)",
    "      -> Öffnet die Plan-Datei direkt zum Bearbeiten": "      -> opens the plan file for editing",
    "  [2] Claude UI (Web / Desktop)": "  [2] Claude UI (web / desktop)",
    "      -> Zeigt den Plan-Pfad zum einfachen Kopieren in die Claude Web-UI": "      -> shows the plan path to copy into the Claude web UI",
    "\n[CLI-Varianten (Terminal)]:": "\n[CLI options (terminal)]:",
    "  [3] Feedback direkt hier eintippen": "  [3] Type feedback right here",
    "      -> KI überarbeitet den Plan anhand deiner Anweisung automatisch": "      -> the AI revises the plan from your instruction",
    "  [4] Interaktive {} CLI-Session (Architekt) starten": "  [4] Start an interactive {} CLI session (Architect)",
    "  [5] Interaktive {} CLI-Session (Prüfstatiker) starten": "  [5] Start an interactive {} CLI session (Reviewer)",
    "  [6] Zurück zum Hauptmenü": "  [6] Back to the main menu",
    "🚀 Öffne {} mit {}...": "🚀 Opening {} with {}...",
    "\nDrücke [Enter], sobald du mit dem Bearbeiten im Editor fertig bist...": "\nPress [Enter] once you are done editing...",
    "💾 Manuell bearbeiteter Plan gesichert als {}": "💾 Manually edited plan saved as {}",
    "\n📋 Plan-Pfad für Claude UI:": "\n📋 Plan path for the Claude UI:",
    "   Pfad: {}": "   Path: {}",
    "   Kopiere den Inhalt der Datei in deine Claude UI / Web-Chat.": "   Copy the file content into your Claude UI / web chat.",
    "\nDrücke [Enter], wenn du die Änderungen vorgenommen und in {} gespeichert hast...": "\nPress [Enter] when you have made the changes and saved them in {}...",
    "Auswahl [1-6]: ": "Choice [1-6]: ",
    "⏳ {} überarbeitet den Plan basierend auf deinem Feedback...": "⏳ {} revises the plan based on your feedback...",
    "✅ Plan aktualisiert und als {} gesichert!": "✅ Plan updated and saved as {}!",
    "🚀 Starte interaktive {}-Sitzung (Architekt) in {}...": "🚀 Starting interactive {} session (Architect) in {}...",
    "Zurück im Loop.": "Back in the loop.",
    "\n📝 Gib deine Änderungswünsche ein: ": "\n📝 Enter your changes: ",
    "🚀 Starte interaktive {}-Sitzung (Prüfstatiker) in {}...": "🚀 Starting interactive {} session (Reviewer) in {}...",
    # runner
    "   Grund: {}": "   Reason: {}",
    "Wie möchtest du fortfahren?": "How do you want to continue?",
    "  [2] ⏳ Warten         -> Countdown starten{} und automatisch wiederholen": "  [2] ⏳ Wait           -> start a countdown{} and retry automatically",
    "  [3] 💾 Beenden        -> Stand sichern und beenden (Fortsetzen später mit 'claudegravity -c')": "  [3] 💾 Quit           -> save state and quit (resume later with 'claudegravity -c')",
    "\n🔄 Auto-Switch aktiv: Wechsle automatisch von {} zu {}...": "\n🔄 Auto switch on: switching from {} to {}...",
    "🚨 [CG-1302] STÖRUNG: {} antwortet auch nach automatischen Neuversuchen nicht!": "🚨 [CG-1302] OUTAGE: {} does not answer even after automatic retries!",
    "🚨 [CG-1301] AI-LIMIT ERREICHT: {} meldet Sitzungs- / Ratenlimit!": "🚨 [CG-1301] AI LIMIT REACHED: {} reports a session / rate limit!",
    "   Reset erwartet: {}": "   Reset expected: {}",
    "  [1] 🔄 Modell-Wechsel -> Zu {} wechseln und sofort weiterarbeiten": "  [1] 🔄 Switch model   -> switch to {} and continue right away",
    "  [1] 🔄 Modell-Wechsel -> (Keine Alternative, die nicht schon die Gegenrolle hat)": "  [1] 🔄 Switch model   -> (no alternative that does not already hold the counter role)",
    "Auswahl [1/2/3] (Standard: 1): ": "Choice [1/2/3] (default: 1): ",
    "🔄 Rolle '{}' wechselt zu {}!": "🔄 Role '{}' switches to {}!",
    "🔁 Vorübergehender Fehler bei {}: {}": "🔁 Temporary error with {}: {}",
    "   Neuversuch {}/{} in {} s ...": "   Retry {}/{} in {} s ...",
    "💾 Sitzung gesichert. Setze jederzeit fort mit 'claudegravity -c'.": "💾 Session saved. Resume any time with 'claudegravity -c'.",
    "Wieviele Minuten soll gewartet werden? [Standard: 15]: ": "How many minutes should it wait? [default: 15]: ",
    # safety
    "[!] Blockiert: {} liegt außerhalb des Projektordners oder ist eine Geheimnis-Datei und wird nicht geschrieben.": "[!] Blocked: {} is outside the project folder or a secrets file and is not written.",
    "[!] Blockiert: {} liegt außerhalb des Projektordners oder ist eine Geheimnis-Datei und wird nicht geändert.": "[!] Blocked: {} is outside the project folder or a secrets file and is not changed.",
    "[!] Fehler beim Schreiben von {}: {}": "[!] Error writing {}: {}",
    # session
    "[!] {} Datei(en) im Workspace ließen sich nicht löschen (gehören vermutlich einem anderen Benutzer, z. B. root nach Docker).": "[!] {} file(s) in the workspace could not be deleted (probably owned by another user, e.g. root after Docker).",
    "🌿 Git-Workspace angelegt: {} (Branch `{}` von `{}`)": "🌿 Git workspace created: {} (branch `{}` from `{}`)",
    "🧹 Git-Workspace freigegeben.": "🧹 Git workspace released.",
    '   👉 Programme schließen, die dort Dateien offen halten, dann: rmdir /s /q "{}"': '   👉 Close programs that keep files open there, then: rmdir /s /q "{}"',
    '   👉 Von Hand aufräumen: sudo rm -rf "{}" && git -C "{}" worktree prune': '   👉 Clean up by hand: sudo rm -rf "{}" && git -C "{}" worktree prune',
    "[!] Git-Workspace {} ist beschädigt und wird neu angelegt (Commits auf dem Branch bleiben erhalten).": "[!] Git workspace {} is damaged and is recreated (commits on the branch are kept).",
    "[!] Git-Workspace konnte nicht angelegt werden, arbeite direkt im Projekt: {}": "[!] Could not create the Git workspace, working directly in the project: {}",
    "[!] Git-Workspace {} ist kein gültiger Worktree mehr, räume nur noch den Ordner auf.": "[!] Git workspace {} is no longer a valid worktree, only cleaning up the folder.",
    "💡 Ergebnis liegt auf Branch `{}` (übernehmen mit: git merge {})": "💡 The result is on branch `{}` (take it with: git merge {})",
    "[!] Merge übersprungen: Projekt steht auf `{}`, nicht auf `{}`.": "[!] Merge skipped: the project is on `{}`, not on `{}`.",
    "💾 Änderungen auf Branch `{}` committet.": "💾 Changes committed on branch `{}`.",
    "[!] Im Workspace liegen noch nicht committete Änderungen, er bleibt bestehen: {}": "[!] The workspace has uncommitted changes, it is kept: {}",
    "[!] git konnte den Workspace nicht vollständig entfernen: {}": "[!] git could not fully remove the workspace: {}",
    "🔀 Branch `{}` in `{}` gemerged und gelöscht.": "🔀 Branch `{}` merged into `{}` and deleted.",
    "[!] Merge von `{}` fehlgeschlagen (Konflikt?), Branch bleibt erhalten: {}": "[!] Merge of `{}` failed (conflict?), the branch is kept: {}",
    "⚠️  {} ist beschädigt und wird übersprungen.": "⚠️  {} is damaged and is skipped.",
    "♻️  Stand aus {} wiederhergestellt (letzte Runde wird ggf. wiederholt).": "♻️  State restored from {} (the last round may be repeated).",
    "[!] Änderungen im Workspace konnten nicht committet werden, Workspace bleibt bestehen: {}": "[!] Changes in the workspace could not be committed, the workspace is kept: {}",
    "🛑 Audit [{}]: {}: {}": "🛑 Audit [{}]: {}: {}",
    "🛑 Audit: {}: {}": "🛑 Audit: {}: {}",
    "Blockierter Schreibversuch": "Blocked write attempt",
    "Änderung durch lesende Rolle": "Change by a read-only role",
    "Mögliche Zugangsdaten in Modellantwort": "Possible credentials in a model answer",
    "Tests abgeschwächt oder entfernt": "Tests weakened or removed",
    "✅ {} erledigt (`{}` grün).": "✅ {} done (`{}` green).",
    "✅ {} erledigt.": "✅ {} done.",
    "⚙️  Aus Umgebung/Profil: {}": "⚙️  From environment/profile: {}",
    # Trockenlauf: Kostenschätzung, Hinweise, automatische Rollen
    "{} (nur für agy/codex/copilot wirksam)": "{} (only effective for agy/codex/copilot)",
    "Voreinstellung der CLI (via --effort nur für agy/codex steuerbar)": "CLI default (set with --effort only for agy/codex)",
    "CLI-Default": "CLI default",
    "Standard": "default",
    "keiner (--proof <befehl>)": "none (--proof <command>)",
    "{} (braucht Schreibrechte: --yolo oder Ja bei der Rechte-Abfrage)": "{} (needs write access: --yolo or yes at the permission prompt)",
    "Architekt Endpoint ({})": "Architect endpoint ({})",
    "Prüfstatiker Endpoint ({})": "Reviewer endpoint ({})",
    "Bauleiter Endpoint ({})": "Builder endpoint ({})",
    "\n💰 Kostenschätzung vorab:": "\n💰 Cost estimate up front:",
    "   • Bau-Runden    : {} (Faustregel, noch kein Verlauf)": "   • Build rounds  : {} (rule of thumb, no history yet)",
    "   • Bau-Runden    : {}": "   • Build rounds  : {}",
    "günstig {} · erwartet {} · ungünstig {}": "best {} · expected {} · worst {}",
    "   • Tokens/Kosten : noch keine Kennzahlen in diesem Projekt. Nach dem ersten Lauf schätzt der": "   • Tokens/cost   : no metrics in this project yet. After the first run the dry run estimates",
    "     Trockenlauf aus deinen eigenen Sessions; USD nur, wenn Anbieter Kosten melden.": "     from your own sessions; USD only if providers report cost.",
    "   • Grundlage     : {}, Erfolgsquote {}": "   • Basis         : {}, success rate {}",
    "{} frühere Session(s) mit gleicher Strategie": "{} earlier session(s) with the same strategy",
    "{} frühere Session(s) (alle Strategien)": "{} earlier session(s) (all strategies)",
    "   • Tokens        : {}": "   • Tokens        : {}",
    "   • Kosten        : {} (gemeldet in {} von {} Sessions)": "   • Cost          : {} (reported in {} of {} sessions)",
    "   • Kosten        : keine gemeldet (Abo-CLIs und lokale Modelle melden keine; Tokens oben zum Nachrechnen)": "   • Cost          : none reported (subscription CLIs and local models report none; see tokens above)",
    "   • Tipp: {}": "   • Tip: {}",
    "Im ungünstigsten Fall reicht --budget-max {} nicht (bisher bis {}); der Lauf bricht dann mit gesichertem Stand ab.": "In the worst case --budget-max {} is not enough (so far up to {}); the run then stops with the state saved.",
    "--budget-max {} begrenzt den ungünstigsten Fall mit etwas Luft.": "--budget-max {} caps the worst case with some headroom.",
    "Mit --strategy hybrid oder local-free baut ein lokales Modell; Bau-Runden kosten dann 0 USD.": "With --strategy hybrid or local-free a local model builds; build rounds then cost 0 USD.",
    "Mit --strategy eco baut ein Spar-Modell; ein lokales Modell (Ollama, LM Studio) spart den Bau ganz.": "With --strategy eco a cheaper model builds; a local model (Ollama, LM Studio) saves the build cost entirely.",
    "Viel Nacharbeit bisher (Median {}): ein --proof-Befehl gibt dem Bauleiter früh ein klares Signal.": "A lot of rework so far (median {}): a --proof command gives the Builder a clear signal early.",
    "Viel Nacharbeit bisher (Median {}): kleinere Aufgaben oder --etappen an senken die Runden.": "A lot of rework so far (median {}): smaller tasks or --etappen an cut the rounds.",
    "⚠️  --yolo ohne Git: Der Bauleiter schreibt mit vollen Rechten, Änderungen lassen sich nicht per Git zurückholen.": "⚠️  --yolo without Git: the Builder writes with full access, changes cannot be undone with Git.",
    "⚠️  --yolo mit --no-worktree: Der Bauleiter schreibt mit vollen Rechten direkt in deinen Arbeitsstand.": "⚠️  --yolo with --no-worktree: the Builder writes with full access straight into your working tree.",
    "ℹ️  Kein --proof: Der Loop führt keine Tests aus; über „fertig“ entscheidet nur die Abnahme.": "ℹ️  No --proof: the loop runs no tests; only the acceptance check decides “done”.",
    "⚠️  --no-inspect: Kein zweiter Anbieter prüft den fertigen Code.": "⚠️  --no-inspect: no second provider checks the finished code.",
    "⚠️  --no-shield: Zugangsdaten in Prompts gehen ungeschwärzt an Cloud-Modelle.": "⚠️  --no-shield: credentials in prompts go unredacted to cloud models.",
    "⚠️  API-Key wird unverschlüsselt (http://) an {} geschickt. Besser https:// verwenden.": "⚠️  The API key is sent unencrypted (http://) to {}. Better use https://.",
    "⚠️ Strategie hybrid braucht eine Cloud-CLI (codex, claude, agy oder gemini) und ein lokales Modell (Ollama, LM Studio oder --endpoint). Es fehlt: {}.": "⚠️ Strategy hybrid needs a cloud CLI (codex, claude, agy or gemini) and a local model (Ollama, LM Studio or --endpoint). Missing: {}.",
    "Cloud-CLI": "cloud CLI",
    "lokales Modell": "local model",
    "🧭 Strategie hybrid: Architekt {}, Prüfstatiker {}, Bauleiter {}, Abnahme {}.": "🧭 Strategy hybrid: Architect {}, Reviewer {}, Builder {}, Acceptance {}.",
    "⚠️ Keine Ollama-Modelle gefunden (/api/tags). Es gelten die Standardmodelle; installiere eins mit `ollama pull`.": "⚠️ No Ollama models found (/api/tags). The default models apply; install one with `ollama pull`.",
    "⚠️ Nur ein passendes Ollama-Modell installiert: {} nutzt {} wie eine andere Rolle und ist damit nicht unabhängig.": "⚠️ Only one suitable Ollama model installed: {} uses {} like another role and is therefore not independent.",
    "🤖 {}: Ollama-Modell {} automatisch gewählt (ändern mit --{}).": "🤖 {}: Ollama model {} picked automatically (change with --{}).",
    # Konfiguration
    "❌ Unbekannte Vorlage `{}`. Verfügbar: {}.": "❌ Unknown template `{}`. Available: {}.",
    "{}: {} {} überschreibt {}": "{}: {} {} overrides {}",
    "❌ [{}] {}: {}": "❌ [{}] {}: {}",
    "Budget {} nicht lesbar (Beispiele: 500k, 1.5m, 80000, 2.50usd, $2.50)": "Budget {} is not readable (examples: 500k, 1.5m, 80000, 2.50usd, $2.50)",
    "⚙️  Wirksame Konfiguration (Kommandozeile > Session > Vorlage > Umgebung > Projekt-Profil > globales Profil > Standard)": "⚙️  Effective configuration (command line > session > template > environment > project profile > global profile > default)",
    "geladen": "loaded",
    "nicht vorhanden": "not found",
    "{}<EINSTELLUNG>, z. B. {}STRATEGY=hybrid": "{}<SETTING>, e.g. {}STRATEGY=hybrid",
    ", Pflicht: {}": ", required: {}",
    "  ⚠️ Konflikt": "  ⚠️ conflict",
    "Konflikte:": "Conflicts:",
    "10 (Etappen: 2 je Etappe + 2)": "10 (stages: 2 per stage + 2)",
    "Kommandozeile": "command line",
    "Session (Fortsetzen)": "session (resume)",
    "Vorlage": "template",
    "Umgebung": "environment",
    "Projekt-Profil": "project profile",
    "Globales Profil": "global profile",
    # Kennzahlen und Verbrauchsbericht (.done, AUDIT.md)
    "### 📈 Kennzahlen (ClaudeGravity KPI v1)": "### 📈 Metrics (ClaudeGravity KPI v1)",
    "* **Ergebnis:** {} · Strategie `{}` · Dauer {}": "* **Result:** {} · strategy `{}` · duration {}",
    "erfolgreich": "successful",
    "offen ({})": "open ({})",
    "unbekannt": "unknown",
    "* **Kosten je Aufgabe:** {} · **davon Abnahme:** {} (gemeldet von: {})": "* **Cost per task:** {} · **of which acceptance:** {} (reported by: {})",
    "kein Anbieter (Abo-CLIs und lokale Modelle melden keine Kosten)": "no provider (subscription CLIs and local models report no cost)",
    "* **Runden:** Plan-Review {} · Bau {} (bis Erfolg: {}) · Etappen {} · Abnahme {}": "* **Rounds:** plan review {} · build {} (until success: {}) · stages {} · acceptance {}",
    "* **Runden:** Plan-Review {} · Bau {} (bis Erfolg: {}) · Abnahme {}": "* **Rounds:** plan review {} · build {} (until success: {}) · acceptance {}",
    "* **Runden:** Plan-Review {} · Bau {} · Etappen {} · Abnahme {}": "* **Rounds:** plan review {} · build {} · stages {} · acceptance {}",
    "* **Runden:** Plan-Review {} · Bau {} · Abnahme {}": "* **Rounds:** plan review {} · build {} · acceptance {}",
    "* **Nacharbeit:** {} von {} Bau-Runden (Quote {}); Prüfbefehl rot {}/{}, Abnahme verweigert {}": "* **Rework:** {} of {} build rounds (rate {}); proof red {}/{}, acceptance refused {}",
    "* **Eskalation:** Bau-Runde {}: {} → {} ({})": "* **Escalation:** build round {}: {} → {} ({})",
    "* **Abbruchgrund:** {}": "* **Reason for stopping:** {}",
    "### 📊 Ressourcen-Verbrauch & Kosten (ClaudeGravity Audit)": "### 📊 Resource usage & cost (ClaudeGravity Audit)",
    "* **Gesamt-Tokens:** {} Tokens": "* **Total tokens:** {} tokens",
    "  * **Input-Tokens:** {}": "  * **Input tokens:** {}",
    "  * **Output-Tokens:** {}": "  * **Output tokens:** {}",
    "* **Entstandene Kosten (geschätzt):** ~${} USD": "* **Cost incurred (estimated):** ~${} USD",
    "* **Aufschlüsselung nach Rolle, Agent, Modell & Effort:**": "* **Breakdown by role, agent, model & effort:**",
    "    * **Modell:** `{}`": "    * **Model:** `{}`",
    "    * **Reasoning-Effort:** `{}`": "    * **Reasoning effort:** `{}`",
    "    * **Verbrauch:** {} Tokens (Input: {}, Output: {})": "    * **Usage:** {} tokens (input: {}, output: {})",
    "    * **Kosten:** {}": "    * **Cost:** {}",
    "Abo-Inklusivkontingent": "included in subscription",
    "  * Keine detaillierte Modell-Aufschlüsselung verfügbar.": "  * No detailed model breakdown available.",
    "* **Automatische Neuversuche:** {} (danach erfolgreich: {}, aufgegeben: {})": "* **Automatic retries:** {} (then successful: {}, given up: {})",
    "* **Sicherheitsereignisse** (Details in `LOG.md` und `audit-events.jsonl`):": "* **Security events** (details in `LOG.md` and `audit-events.jsonl`):",
    "* **Audit-Zeitstempel:** {}": "* **Audit timestamp:** {}",
    "# Aufgabe abgeschlossen\n": "# Task completed\n",
    "führt genehmigten Plan aus": "runs the approved plan",
    # wizard
    "🧭 ClaudeGravity einrichten\n": "🧭 Set up ClaudeGravity\n",
    "🖥️  System : {} {}, Python {}": "🖥️  System : {} {}, Python {}",
    "📁 Projekt: {}": "📁 Project: {}",
    "🔍 Gefunden:": "🔍 Found:",
    "\nWas ist dir am wichtigsten?": "\nWhat matters most to you?",
    "   → Strategie `{}`: {}": "   → Strategy `{}`: {}",
    "\nMit welchem Befehl prüft der Loop jede Bau-Runde selbst (Tests)? Ohne Prüfbefehl entscheidet nur die Abnahme.": "\nWhich command should the loop run itself after every build round (tests)? Without one only the acceptance check decides.",
    "Prüfbefehl (- für keinen)": "Proof command (- for none)",
    "\nWo speichern? Das Projekt-Profil gilt nur hier und schlägt das globale.": "\nWhere to save? The project profile only applies here and beats the global one.",
    "  [1] Projekt: {}": "  [1] Project: {}",
    "  [2] Global : {}": "  [2] Global : {}",
    "Auswahl": "Choice",
    "Auswahl [1]: ": "Choice [1]: ",
    "✅ Profil gespeichert: {}": "✅ Profile saved: {}",
    "\nSo geht es weiter:": "\nNext steps:",
    "  1. Erst ansehen, was passieren würde (legt nichts an):": "  1. First see what would happen (creates nothing):",
    '     claudegravity --dry-run "Deine Aufgabe"': '     claudegravity --dry-run "Your task"',
    "  2. Dann starten:": "  2. Then start:",
    '     claudegravity "Deine Aufgabe"': '     claudegravity "Your task"',
    "  Wirksame Einstellungen und ihre Herkunft: claudegravity --print-effective-config": "  Effective settings and where they come from: claudegravity --print-effective-config",
    "\n👋 Erster Lauf ohne Profil. Empfohlen: erst ansehen, welche Modelle welche Rolle bekommen.": "\n👋 First run without a profile. Recommended: first see which models get which role.",
    "  [1] Trockenlauf zeigen, nichts ausführen (Standard)": "  [1] Show a dry run, run nothing (default)",
    "  [2] Einrichtung starten (claudegravity init)": "  [2] Start the setup (claudegravity init)",
    "  [3] Jetzt starten": "  [3] Start now",
    "  [4] Jetzt starten und diesen Hinweis nicht mehr zeigen": "  [4] Start now and don't show this hint again",
    "ClaudeGravity Loop: Ein Modell plant, ein anderes prüft, eines baut, ein anderer Anbieter nimmt ab.\n": "ClaudeGravity Loop: one model plans, another reviews, one builds, a different provider accepts.\n",
    "  claudegravity init                       Einrichtung (erkennt KIs, speichert ein Profil)": "  claudegravity init                       Setup (detects AIs, saves a profile)",
    '  claudegravity "Deine Aufgabe"            Loop starten': '  claudegravity "Your task"                Start the loop',
    '  claudegravity --dry-run "Deine Aufgabe"  Nur zeigen, wer welche Rolle bekommt': '  claudegravity --dry-run "Your task"      Only show who gets which role',
    "  claudegravity --resume                   Unterbrochene Sitzung fortsetzen": "  claudegravity --resume                   Resume an interrupted session",
    "  claudegravity --help                     Wichtigste Optionen (alle: --help-all)": "  claudegravity --help                     Most important options (all: --help-all)",
    "   (nichts) Installiere zuerst eine KI-CLI (z. B. `claude`, `codex`, `agy`) oder starte Ollama.": "   (nothing) First install an AI CLI (e.g. `claude`, `codex`, `agy`) or start Ollama.",
    "⚠️  Nur ein Anbieter gefunden: Architekt und Prüfstatiker wären dasselbe Modell, das sich selbst prüft.": "⚠️  Only one provider found: Architect and Reviewer would be the same model reviewing itself.",
    "   Besser: eine zweite CLI installieren oder Ollama/LM Studio starten.": "   Better: install a second CLI or start Ollama/LM Studio.",
    "   Bitte eine der Möglichkeiten wählen: {}": "   Please pick one of the options: {}",
    "❌ Profil nicht gespeichert: {}": "❌ Profile not saved: {}",
    "Schnell: Standard-Belegung, ein Lauf ohne Umwege": "Fast: default roles, one run without detours",
    "Günstig: Cloud nur für Plan und Abnahme, Bau lokal (falls vorhanden)": "Cheap: cloud only for plan and acceptance, build locally (if available)",
    "Maximale Qualität: alle Rollen mit hohem Effort": "Maximum quality: all roles with high effort",
    "alle Phasen mit Effort high": "all phases with effort high",
    "{} plant und nimmt ab, {} prüft und baut": "{} plans and accepts, {} reviews and builds",
    "Bau-Loop lokal mit {}": "build loop locally with {}",
    "kein lokales Modell gefunden, daher Sparmodelle und Effort medium": "no local model found, so cheaper models and effort medium",
    "ausgewogene Standard-Belegung": "balanced default roles",
    "\nEinrichtung abgebrochen, nichts gespeichert.": "\nSetup cancelled, nothing saved.",
    "Cloud": "cloud",
    # Testwächter
    "⚠️ Testwächter des Loops: Seit Baubeginn wurden Tests abgeschwächt oder entfernt:\n{}\nDas ist nur zulässig, wenn der Plan es ausdrücklich verlangt (z. B. ein veralteter Test). Sonst gilt die Umsetzung als nicht fertig: Tests wiederherstellen und den Code reparieren.": "⚠️ Loop test guard: tests were weakened or removed since the build started:\n{}\nThis is only allowed if the plan explicitly asks for it (e.g. an outdated test). Otherwise the work is not done: restore the tests and fix the code.",
    # GitHub: Issue als Aufgabe, Pull Request
    "🐙 GitHub-Issue #{}: {} ({})": "🐙 GitHub issue #{}: {} ({})",
    "⚠️  Das Issue ist bereits geschlossen.": "⚠️  The issue is already closed.",
    "## Zusammenfassung": "## Summary",
    "Umgesetzt mit [ClaudeGravity Loop]({}): ein Modell plant, ein anderes prüft, eines baut, ein anderer Anbieter nimmt ab.": "Implemented with [ClaudeGravity Loop]({}): one model plans, another reviews, one builds, a different provider accepts.",
    "**Aufgabe:**": "**Task:**",
    "* **Prüfbefehl:** `{}`, vom Loop selbst ausgeführt und grün": "* **Proof command:** `{}`, run by the loop itself and green",
    "* **Prüfbefehl:** keiner; über „fertig“ entschied die Abnahme": "* **Proof command:** none; the acceptance check decided “done”",
    "Freigegebener Plan": "Approved plan",
    "🤖 Erstellt mit ClaudeGravity Loop {}, Sitzung `{}`": "🤖 Created with ClaudeGravity Loop {}, session `{}`",
    "🔗 Pull Request gibt es schon: {}": "🔗 Pull request already exists: {}",
    "[!] Kein Pull Request: --open-pr braucht den Git-Workspace der Sitzung (nicht mit --no-worktree).": "[!] No pull request: --open-pr needs the session's Git workspace (not with --no-worktree).",
    "[!] Kein Pull Request: Branch `{}` ist schon gemerged.": "[!] No pull request: branch `{}` is already merged.",
    "ℹ️  Kein Pull Request: Branch `{}` hat keine neuen Commits gegenüber `{}`.": "ℹ️  No pull request: branch `{}` has no new commits compared to `{}`.",
    "⬆️  Branch `{}` nach origin gepusht.": "⬆️  Pushed branch `{}` to origin.",
    "🔗 Pull Request geöffnet{}: {}": "🔗 Pull request opened{}: {}",
    " (Entwurf)": " (draft)",
    "kein GitHub-Repository erkannt (git remote origin)": "no GitHub repository found (git remote origin)",
    "„{}“ ist keine Issue-Nummer (#12), kein owner/repo#12 und keine Issue-URL": "“{}” is not an issue number (#12), owner/repo#12 or issue URL",
    "#{} ({}): {}": "#{} ({}): {}",
    "Repository unbekannt": "repository unknown",
    "gh nicht installiert": "gh not installed",
    "kein GH_TOKEN/GITHUB_TOKEN für die API": "no GH_TOKEN/GITHUB_TOKEN for the API",
    "git push fehlgeschlagen": "git push failed",
    "⚠️  --open-pr und --merge zusammen: es wird nicht gemerged, der Branch geht als Pull Request raus.": "⚠️  --open-pr and --merge together: nothing is merged, the branch goes out as a pull request.",
    "⚠️  --open-pr braucht den Git-Workspace der Sitzung; ohne ihn (--no-worktree oder kein Git) gibt es keinen Pull Request.": "⚠️  --open-pr needs the session's Git workspace; without it (--no-worktree or no Git) there is no pull request.",
    "[*] Pull Request      : {}": "[*] Pull request      : {}",
    "🔗 nach Abschluss pushen und öffnen": "🔗 push and open after completion",
    "🔗 nach Abschluss pushen und öffnen (Entwurf)": "🔗 push and open after completion (draft)",
    "⚠️ {}: `{}` wird ignoriert. Schreib- und Veröffentlichungsrechte nur per Kommandozeile, Umgebung oder globalem Profil.": "⚠️ {}: `{}` is ignored. Write and publish rights only via the command line, environment or global profile.",
}


# Wortgruppen, die eingebettet in sonst unbekannten Texten vorkommen (Namen von Endpunkten, Effort-Hinweise)
PHRASES = {
    "🏗️ Architekt Endpoint": "🏗️ Architect endpoint",
    "🧐 Prüfstatiker Endpoint": "🧐 Reviewer endpoint",
    "🔨 Bauleiter Endpoint": "🔨 Builder endpoint",
    "Lokal/Intranet": "local/intranet",
    "🏗️ Architekt (Planung & Entwurf)": "🏗️ Architect (planning & design)",
    "🧐 Prüfstatiker (Prüfung & Review)": "🧐 Reviewer (review & audit)",
    "🔨 Bauleiter (Bau & Umsetzung)": "🔨 Builder (build & implementation)",
    "Architekt Endpoint": "Architect endpoint",
    "Prüfstatiker Endpoint": "Reviewer endpoint",
    "Bauleiter Endpoint": "Builder endpoint",
    "Netzwerk-Server": "Network server",
    "KI-Server": "AI server",
    "(Lokal:": "(local:",
    "(Netzwerk:": "(network:",
    "nur für agy/codex/copilot wirksam": "only effective for agy/codex/copilot",
    "(Modell:": "(model:",
    "Sitzung fortgesetzt": "session resumed",
    "🏗️ Architekt": "🏗️ Architect",
    "🧐 Prüfstatiker": "🧐 Reviewer",
    "🔨 Bauleiter": "🔨 Builder",
    "🔎 Abnahme": "🔎 Acceptance",
    "Etappe": "Stage",
}
_PHRASE_RE = re.compile("|".join(re.escape(k) for k in sorted(PHRASES, key=len, reverse=True)))


def _phrases(text: str) -> str:
    return _PHRASE_RE.sub(lambda m: PHRASES[m.group(0)], text)


def _compile(template: str) -> re.Pattern:
    """Deutsche Vorlage → Regex: Text wörtlich, `{}` als Gruppe, `{{`/`}}` als Klammern.
    Einzeilige Vorlagen passen nur auf eine Zeile; mehrzeilige Meldungen werden dann zeilenweise übersetzt."""
    parts = template.replace("{{", "\x00").replace("}}", "\x01").split("{}")
    escaped = [re.escape(p.replace("\x00", "{").replace("\x01", "}")) for p in parts]
    group = "(.*?)" if "\n" in template else "([^\n]*?)"
    return re.compile(group.join(escaped), re.DOTALL)


def _anchor(template: str) -> str:
    """Längstes wörtliches Stück der Vorlage: Nur Meldungen, die es enthalten, werden per Regex geprüft."""
    pieces = template.replace("{{", "{").replace("}}", "}").split("{}")
    return max(pieces, key=len)


_PATTERNS: list[tuple[str, re.Pattern, str]] | None = None


def _patterns() -> list[tuple[str, re.Pattern, str]]:
    global _PATTERNS
    if _PATTERNS is None:
        # Längere Vorlagen zuerst, damit allgemeine wie "   {}" nicht vor genaueren greifen
        # Vorlagen mit führendem Zeilenumbruch passen auch auf die einzelne Zeile einer mehrzeiligen Meldung
        variants = {de.lstrip("\n"): en.lstrip("\n") for de, en in EN.items() if de.startswith("\n") and de.strip()}
        items = sorted({**variants, **EN}.items(), key=lambda kv: -len(kv[0].replace("{}", "")))
        _PATTERNS = [(_anchor(de), _compile(de), en) for de, en in items]
    return _PATTERNS


def _fill(template: str, values: list[str]) -> str:
    """Englische Vorlage füllen; `{0}`, `{1}` erlauben eine andere Reihenfolge."""
    out, auto = [], 0
    for literal, field, _spec, _conv in string.Formatter().parse(template):
        out.append(literal)
        if field is None:
            continue
        if field == "":
            out.append(values[auto] if auto < len(values) else "")
            auto += 1
        else:
            index = int(field)
            out.append(values[index] if index < len(values) else "")
    return "".join(out)


def to_english(text: str, depth: int = 0) -> str:
    """Eine deutsche Meldung ins Englische; eingesetzte Werte werden mitübersetzt, Unbekanntes bleibt."""
    if not text or depth > 3 or len(text) > MAX_TRANSLATE:
        return text
    if text in GLOSSARY:
        return GLOSSARY[text]
    if text in EN and "{}" not in text:
        return EN[text].replace("{{", "{").replace("}}", "}")
    for anchor, pattern, english in _patterns():
        if anchor not in text:
            continue
        m = pattern.fullmatch(text)
        if m:
            return _fill(english, [to_english(v, depth + 1) for v in m.groups()])
    if "\n" in text and depth == 0:
        return "\n".join(to_english(line, depth + 1) for line in text.split("\n"))
    # Eingerückte Meldungen (z. B. Hinweise unter einer Überschrift): Einrückung behalten, Rest übersetzen
    body = text.lstrip(" ")
    if body != text and body:
        english = to_english(body, depth + 1)
        if english != body:
            return text[: len(text) - len(body)] + english
    return _phrases(text)


def translate(text: str, lang: str) -> str:
    """Meldung in der gewählten Sprache (de: unverändert)."""
    return to_english(text) if lang == "en" else text


def prescan_lang(argv: list[str], env: dict | None = None) -> str:
    """Sprache schon vor dem Einlesen der Kommandozeile (für --help): --lang X / --lang=X, sonst Umgebung."""
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv):
            return resolve_lang(argv[i + 1]) if argv[i + 1] in LANGS + ("auto",) else detect_lang(env)
        if arg.startswith("--lang="):
            value = arg.split("=", 1)[1]
            return resolve_lang(value) if value in LANGS + ("auto",) else detect_lang(env)
    return detect_lang(env)


def help_text(text: str, lang: str) -> str:
    """Hilfetext einer Option (argparse) in der gewählten Sprache."""
    if lang != "en" or not isinstance(text, str):
        return text
    return HELP.get(text, text)


# Modellantworten in der Sprache der Ausgabe; Formatmarken bleiben, weil der Loop sie liest.
MODEL_DIRECTIVE = (
    "\n\nLANGUAGE: Write all prose (plan, review, findings, questions, summaries) in English. "
    "Keep the required markers exactly as specified, e.g. `VERDICT:`, `## Etappen`, `### FRAGEN AN DEN NUTZER:`, "
    "`filepath:` and `edit:` blocks, `HIGH`/`MEDIUM`/`LOW`."
)

# Hilfe der Kommandozeile (--help, --help-all): Gruppen, Beschreibung und Hilfetexte der Optionen
HELP = {
    'claudegravity [Optionen] "Aufgabe"': 'claudegravity [options] "task"',
    "ClaudeGravity Loop: Ein Modell plant, ein anderes prüft, eines baut, ein anderer Anbieter nimmt ab.": "ClaudeGravity Loop: one model plans, another reviews, one builds, a different provider accepts.",
    'Erste Schritte: claudegravity init · Trockenlauf: claudegravity --dry-run "Aufgabe" · Alle Optionen mit Aliasen: claudegravity --help-all': 'Getting started: claudegravity init · Dry run: claudegravity --dry-run "task" · All options with aliases: claudegravity --help-all',
    "Start": "Start",
    "Strategie und Kosten": "Strategy and cost",
    "Rollen und Modelle": "Roles and models",
    "Ablauf": "Flow",
    "Rechte und Arbeitsbereich": "Permissions and workspace",
    "Ausgabe": "Output",
    "GitHub-Issue als Aufgabe: Nummer (12, #12), owner/repo#12 oder URL; liest Titel, Text und Kommentare über gh oder GH_TOKEN": "GitHub issue as the task: number (12, #12), owner/repo#12 or URL; reads title, body and comments via gh or GH_TOKEN",
    "Nach erfolgreichem Abschluss den Session-Branch pushen und einen Pull Request öffnen (mit „Closes #n“ bei --from-issue)": "After a successful finish, push the session branch and open a pull request (with “Closes #n” for --from-issue)",
    "Pull Request als Entwurf öffnen (schließt --open-pr ein)": "Open the pull request as a draft (implies --open-pr)",
    "Die Aufgabe für den Loop": "The task for the loop",
    "Pfad zum Ziel-Projekt (absolut oder relativ, Standard: .)": "Path to the target project (absolute or relative, default: .)",
    "Einrichtung: erkennt System und KI-CLIs, fragt Ziel und Prüfbefehl, speichert ein Profil (auch: claudegravity init)": "Setup: detects system and AI CLIs, asks for goal and proof command, saves a profile (also: claudegravity init)",
    "Trockenlauf: Zeigt Rollen, Modelle, Kosten-Analyse und generierten Befehl ohne Ausführung": "Dry run: shows roles, models, cost analysis and the generated command without running anything",
    "Unterbrochene Sitzung fortsetzen": "Resume an interrupted session",
    'Aufgaben-Vorlage: bugfix, feature, refactor oder eigene aus dem Profil ("templates"); einzelne Flags überschreiben sie': 'Task template: bugfix, feature, refactor or your own from the profile ("templates"); single flags override it',
    "Installierte AI-CLIs, Standard-Modelle und Rollenkonfiguration anzeigen": "Show installed AI CLIs, default models and role setup",
    "Wirksame Konfiguration mit Quelle je Einstellung (Kommandozeile, Session, Umgebung, Profil, Standard) anzeigen und beenden": "Show the effective configuration with the source of each setting (command line, session, environment, profile, default) and exit",
    "Diese Hilfe (wichtigste Optionen)": "This help (most important options)",
    "Alle Optionen mit Aliasen zeigen": "Show all options with aliases",
    "Version anzeigen": "Show the version",
    "Sprache der Ausgaben und Modellantworten: de, en oder auto (Locale); auch CLAUDEGRAVITY_LANG": "Language of output and model answers: de, en or auto (locale); also CLAUDEGRAVITY_LANG",
    "Optimierungs-Strategie: best-code (beste Qualität), eco (bis zu 70%% Ersparnis), local-free (0€ Kosten in Phase 3 via Lokal/Intranet-Modell), hybrid (Cloud-CLI plant und nimmt ab, lokales Modell prüft und baut in Etappen), balanced (Standard). Aliase: quality, economy, cost, free, local, mixed": "Strategy: best-code (best quality), eco (up to 70%% savings), local-free (€0 in phase 3 via a local/intranet model), hybrid (cloud CLI plans and accepts, a local model reviews and builds in stages), balanced (default). Aliases: quality, economy, cost, free, local, mixed",
    "Harte Grenze für die Session: Tokens (500k, 1.5m) oder gemeldete Kosten (2.50usd); der Lauf endet nach dem Aufruf, der sie erreicht": "Hard limit for the session: tokens (500k, 1.5m) or reported cost (2.50usd); the run ends after the call that reaches it",
    "Weiche Grenze: nur Warnung (Standard: 80 %% von --budget-max)": "Soft limit: warning only (default: 80 %% of --budget-max)",
    'Harte Grenzen je Rolle, z. B. "bauleiter=300k,abnahme=0.50usd"': 'Hard limits per role, e.g. "bauleiter=300k,abnahme=0.50usd"',
    "Lokaler Bauleiter scheitert wiederholt: auf eine Cloud-CLI wechseln (auto oder z. B. claude, codex); einmal pro Session, steht in .done": "A local Builder fails repeatedly: switch to a cloud CLI (auto or e.g. claude, codex); once per session, recorded in .done",
    "Erfolglose Bau-Runden in Folge bis zur Eskalation (Standard: 2)": "Unsuccessful build rounds in a row before escalating (default: 2)",
    "Explizite CLI für Architekt / Planung (z.B. claude oder agy)": "CLI for the Architect / planning (e.g. claude or agy)",
    "Explizite CLI für Prüfstatiker / Review (z.B. agy oder claude)": "CLI for the Reviewer / review (e.g. agy or claude)",
    "Explizite CLI für Bauleiter / Umsetzung (Phase 3, z.B. claude oder agy, Standard: folgt Architekt)": "CLI for the Builder / implementation (phase 3, e.g. claude or agy, default: follows the Architect)",
    'Best-of-N: mehrere Bauleiter bauen den Plan parallel in eigenen Worktrees, die Abnahme wählt den besten, z. B. "claude,codex" oder "codex,ollama=qwen3-coder:30b"': 'Best-of-N: several Builders build the plan in parallel in their own worktrees, the acceptance check picks the best, e.g. "claude,codex" or "codex,ollama=qwen3-coder:30b"',
    "CLI für die Abnahme des fertigen Codes (Standard: Prüfstatiker, nie der Bauleiter)": "CLI for the acceptance check of the finished code (default: Reviewer, never the Builder)",
    "OpenAI-kompatibler Endpunkt (z.B. http://localhost:11434/v1 oder http://192.168.1.50:11434/v1)": "OpenAI-compatible endpoint (e.g. http://localhost:11434/v1 or http://192.168.1.50:11434/v1)",
    "Rollen tauschen: Antigravity wird Architekt (Planung), Claude wird Prüfstatiker (Review)": "Swap roles: Antigravity becomes Architect (planning), Claude becomes Reviewer (review)",
    "Modell für den Architekten (z.B. sonnet, gemini-4-argon, opus)": "Model for the Architect (e.g. sonnet, gemini-4-argon, opus)",
    "Modell für den Prüfstatiker (z.B. gemini-4-argon, sonnet, opus)": "Model for the Reviewer (e.g. gemini-4-argon, sonnet, opus)",
    "Modell für den Bauleiter in Phase 3 (z.B. haiku, gemini-3.8-flash, sonnet)": "Model for the Builder in phase 3 (e.g. haiku, gemini-3.8-flash, sonnet)",
    "Modell für die Abnahme": "Model for the acceptance check",
    "Reasoning-Intensität / Thinking Effort (für agy)": "Reasoning effort (for agy)",
    "Spezifische Reasoning-Intensität für den Architekten (falls agy)": "Reasoning effort for the Architect (if agy)",
    "Spezifische Reasoning-Intensität für den Prüfstatiker (für agy)": "Reasoning effort for the Reviewer (for agy)",
    "Reasoning-Intensität für den Bauleiter in Phase 3 (für agy)": "Reasoning effort for the Builder in phase 3 (for agy)",
    "Reasoning-Intensität für die Abnahme": "Reasoning effort for the acceptance check",
    "Spezifischer Endpunkt für den Architekten": "Endpoint for the Architect",
    "Spezifischer Endpunkt für den Prüfstatiker": "Endpoint for the Reviewer",
    "Spezifischer Endpunkt für den Bauleiter (Phase 3)": "Endpoint for the Builder (phase 3)",
    "Optionaler API-Key für geschützte KI-Endpunkte": "Optional API key for protected AI endpoints",
    "Sekunden pro Runde für Endpunkte (Standard: 900 im Heimnetz, 180 sonst; auch CLAUDEGRAVITY_TIMEOUT)": "Seconds per round for endpoints (default: 900 on the home network, 180 otherwise; also CLAUDEGRAVITY_TIMEOUT)",
    'Prüfbefehl, den der Loop nach jeder Bau-Runde selbst ausführt (z.B. "python -m unittest discover -s tests")': 'Proof command the loop runs itself after every build round (e.g. "python -m unittest discover -s tests")',
    "Fragen-Modus: Beide Agenten stellen bei Unklarheiten gezielte Fragen an dich, bevor der Plan finalisiert wird": "Question mode: both agents ask you targeted questions when something is unclear, before the plan is final",
    "Plan ohne Rückfrage freigeben, sobald der Prüfstatiker APPROVED meldet (sonst kein Bau); für Läufe ohne Terminal": "Approve the plan without asking once the Reviewer reports APPROVED (otherwise no build); for runs without a terminal",
    "Bauleiter jede Runde in neuer Sitzung starten; Standard: claude und codex setzen ihre Sitzung fort und bekommen nur Rückmeldung und nächsten Schritt": "Start the Builder in a new session every round; default: claude and codex resume their session and only get feedback and the next step",
    "Etappen-Modus: Architekt plant Etappen, Bauleiter setzt sie einzeln um, Loop prüft jede mit --proof (auto: an bei lokalen/Endpunkt-Bauleitern)": "Stage mode: the Architect plans stages, the Builder implements them one by one, the loop checks each with --proof (auto: on for local/endpoint Builders)",
    "Repo-Karte (Dateien mit Klassen und Funktionen) im Prompt: auto nur für Endpunkte ohne Dateizugriff, an für alle Rollen, aus nie": "Repo map (files with classes and functions) in the prompt: auto only for endpoints without file access, an for all roles, aus never",
    "Maximale autonome Iterationen (Standard: 10, im Etappen-Modus 2 pro Etappe + 2)": "Maximum autonomous iterations (default: 10, in stage mode 2 per stage + 2)",
    "Maximale Review-Runden für den Plan (Standard: 2)": "Maximum review rounds for the plan (default: 2)",
    "Maximale Abnahme-Runden pro Lauf (Standard: 2)": "Maximum acceptance rounds per run (default: 2)",
    "Geschönte Tests erkennen (gelöscht, Skip/Only, weniger Prüfungen): warn meldet es der Abnahme, strict weist die Fertigmeldung zurück, off schaltet ab (Standard: warn)": "Detect weakened tests (deleted, skip/only, fewer assertions): warn tells the acceptance check, strict rejects the completion report, off turns it off (default: warn)",
    "Abnahme durch einen anderen Anbieter auslassen (wird im LOG.md vermerkt)": "Skip the acceptance check by another provider (noted in LOG.md)",
    "Bei Erreichen eines AI-Limits automatisch zum alternativen Modell wechseln": "Switch to the alternative model automatically when an AI limit is reached",
    "Automatische Neuversuche bei vorübergehenden Fehlern (Überlastung, 5xx, Verbindungsabbruch) mit Backoff und Jitter (Standard: 3, 0 schaltet ab)": "Automatic retries on temporary errors (overload, 5xx, dropped connection) with backoff and jitter (default: 3, 0 turns it off)",
    "Pause zwischen Runden in Sekunden": "Pause between rounds in seconds",
    "Automatisch volle Schreib- und Toolrechte erteilen (keine Nachfrage)": "Grant full write and tool access automatically (no prompt)",
    "Keinen eigenen Git-Workspace pro Session anlegen, sondern direkt im Projektverzeichnis bauen": "Do not create a Git workspace per session, build directly in the project folder",
    "Session-Branch nach erfolgreichem Abschluss (.done) in den Ausgangs-Branch mergen": "Merge the session branch into the starting branch after success (.done)",
    "Datenschutzschild aus: Zugangsdaten in Prompts an Cloud-Modelle nicht schwärzen": "Privacy shield off: do not redact credentials in prompts to cloud models",
    "json: zusätzlich events.jsonl im Session-Ordner, eine JSON-Zeile pro Ereignis (Aufruf, Prüfbefehl, Audit, Eskalation, Ende)": "json: also write events.jsonl in the session folder, one JSON line per event (call, proof command, audit, escalation, end)",
    'Keine Statuszeile nach jedem KI-Aufruf (im Profil: "progress": false)': 'No status line after each AI call (in the profile: "progress": false)',
    'Hinweis beim ersten Lauf ohne Profil nicht zeigen (im Profil: "guide": false)': 'Do not show the hint on the first run without a profile (in the profile: "guide": false)',
}
