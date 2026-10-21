# Schnellstart

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/schnellstart.md)

Voraussetzung: ClaudeGravity ist [installiert](installation.md) und mindestens eine KI-CLI ist angemeldet.

## 1. Prüfen, was verfügbar ist

```bash
claudegravity --info
```

Die Ausgabe zeigt Betriebssystem und Python-Version, alle erkannten CLIs und Endpunkte (z. B. `[x] Claude Code (claude / claude)`) und die Standard-Belegung der drei Rollen.

## 2. Erst ansehen, dann starten (Trockenlauf)

```bash
claudegravity --dry-run "Erstelle ein Python-Skript für Wetterabfragen mit Fehlerbehandlung"
```

Der Trockenlauf zeigt, welche CLI und welches Modell jede Rolle bekommt, und gibt den fertigen Startbefehl aus. Es wird **keine Datei** angelegt.

## 3. Erste Aufgabe

```bash
cd ~/Projekte/mein-projekt
claudegravity "Erstelle ein Python-Skript für Wetterabfragen mit Fehlerbehandlung"
```

Oder mit Zielordner, ohne vorher zu wechseln:

```bash
claudegravity "Erstelle ein Python-Skript für Wetterabfragen" -p ~/Projekte/mein-projekt
```

## Was dann passiert

1. **🏗️ Architekt** schreibt `PLAN_v1.md` in einen neuen Session-Ordner unter `.dual-loop/sessions/`.
2. **🧐 Prüfstatiker** prüft den Plan und antwortet mit `VERDICT: APPROVED` oder `VERDICT: REVISE`. Bei `REVISE` überarbeitet der Architekt den Plan (bis zu 2 Review-Runden).
3. **Du entscheidest** im Menü:
   ```
   [1] Approve  -> Plan genehmigen & weiter zur Implementierung
   [2] Changes  -> Änderungen/Feedback anbringen
   [3] Swap     -> Rollen tauschen (Architekt <-> Prüfstatiker)
   [4] Anzeigen -> Plan direkt hier im Terminal lesen
   [5] Beenden  -> Abbrechen (Fortsetzen später mit --resume möglich)
   ```
   **[Enter]** genügt zum Freigeben.
4. **Rechte-Abfrage:** Ohne `--yolo` fragt ClaudeGravity, ob der Bauleiter volle Schreib- und Tool-Rechte bekommt.
5. **🔨 Bauleiter** setzt den Plan in bis zu 10 Runden um (`-m` ändert das) und legt am Ende `.dual-loop/sessions/<session>/.done` an. In diese Datei schreibt ClaudeGravity zusätzlich den Token- und Kostenbericht.

Details zu jedem Schritt: [Ablauf & Rollen](ablauf-und-rollen.md).

## Typische Kombinationen

```bash
# Rückfragen zulassen und danach ohne Nachfragen bauen
claudegravity "Baue ein Kundenportal" -i --yolo

# Sparsam: starker Plan, günstiges Modell baut
claudegravity "Füge Logging hinzu" --strategy eco

# 0 € im Bau-Loop mit lokalem Ollama
claudegravity "Baue ein REST-Interface" --strategy local-free

# Unterbrochene Sitzung fortsetzen
claudegravity -c
```

## Weiter

* [Strategien](strategien.md) – welches Preset wofür
* [Backends](backends.md) – Ollama, LM Studio, Intranet-Server
* [CLI-Referenz](cli-referenz.md) – alle Flags
