# Schnellstart

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/schnellstart.md)

Voraussetzung: ClaudeGravity ist [installiert](installation.md) und mindestens eine KI-CLI ist angemeldet.

## 1. Einrichten

```bash
cd ~/Projekte/mein-projekt
claudegravity init
```

Die Einrichtung erkennt Betriebssystem, KI-CLIs und lokale Modelle und fragt drei Dinge, jeweils mit Vorschlag (Enter übernimmt ihn):

1. **Ziel:** Schnell (`balanced`), Günstig (`hybrid`, wenn Cloud-CLI und lokales Modell da sind, sonst `local-free` oder `eco`) oder maximale Qualität (`best-code`).
2. **Prüfbefehl:** aus dem Projekt geraten (`vendor/bin/phpunit` bei `composer.json`, `npm test` bei `package.json`, `python3 -m unittest …` bei `tests/` usw.).
3. **Speicherort:** Projekt-Profil `.dual-loop/profile.json` oder globales Profil `~/.config/claudegravity/profile.json`.

Am Ende stehen das Profil und die beiden Befehle für den Start. Alles lässt sich später im Profil ändern, siehe [Vorrang der Einstellungen](cli-referenz.md#vorrang-der-einstellungen).

Nur nachsehen, was erkannt wird, ohne etwas zu speichern:

```bash
claudegravity --info
```

Die Ausgabe zeigt Betriebssystem und Python-Version, alle erkannten CLIs und Endpunkte (z. B. `[x] Claude Code (claude / claude)`) und die Standard-Belegung der drei Rollen.

## 2. Erst ansehen, dann starten (Trockenlauf)

```bash
claudegravity --dry-run "Erstelle ein Python-Skript für Wetterabfragen mit Fehlerbehandlung"
```

Der Trockenlauf zeigt, welche CLI und welches Modell jede Rolle bekommt, schätzt den Verbrauch und gibt den fertigen Startbefehl aus. Es wird **keine Datei** angelegt.

Die **Kostenschätzung vorab** nennt einen günstigen, erwarteten und ungünstigen Fall. Grundlage sind die Kennzahlen der letzten 20 Sessions im Projekt (aus `.done` und `AUDIT.md`), bevorzugt mit derselben Strategie, sobald es davon mindestens zwei gibt. Ohne Verlauf zeigt sie nur eine Faustregel für die Bau-Runden. USD erscheinen nur, wenn Anbieter Kosten gemeldet haben; eine Preistabelle gibt es nicht. Dazu kommen Tipps, etwa ein passendes `--budget-max`, eine lokale Bau-Strategie oder `--proof` bei viel Nacharbeit.

## 3. Erste Aufgabe

```bash
cd ~/Projekte/mein-projekt
claudegravity "Erstelle ein Python-Skript für Wetterabfragen mit Fehlerbehandlung"
```

Gibt es noch kein Profil, fragt der erste Lauf im Terminal nach: Trockenlauf zeigen (Standard, danach „So starten? [j/N]“), Einrichtung starten, direkt starten oder direkt starten und nicht mehr fragen (schreibt `"guide": false` ins globale Profil; einmalig: `--no-guide`). Beim Start warnt der Loop außerdem vor riskanten Einstellungen, etwa `--yolo` ohne Git, fehlendem `--proof`, `--no-inspect` oder einem API-Key über unverschlüsseltes `http://`.

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

Nach jedem KI-Aufruf zeigt eine Statuszeile, wo der Lauf steht und was als Nächstes kommt:

```text
📍 Bau-Runde 3/10 · 🔨 Bauleiter Claude Code fertig nach 1 min 15 s · +12k Tokens (gesamt 40k Tokens, 0.25 USD gemeldet)
   Weiter: Prüfbefehl `make test` · Budget 40% von 100k Tokens
```

USD erscheinen nur, wenn der Anbieter Kosten meldet, der Budget-Anteil nur mit `--budget-max`. Endet der Lauf ohne Erfolg, nennt die letzte Zeile den **Abbruchgrund** (Rundenlimit, Abnahme-Limit, Etappe nicht grün, Budget, Limit-Menü oder Strg+C); er steht auch im Kennzahlen-Block von `AUDIT.md`. `--no-progress` schaltet die Statuszeile ab.

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
