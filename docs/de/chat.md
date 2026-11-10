# Chat-Oberfläche

[← Zurück zur Übersicht](../../README.md) · [Dokumentations-Index](README.md) · 🇬🇧 [English](../en/chat.md)

Der einfachste Weg, den Loop zu benutzen: ein Chat im Browser. Du schreibst die Aufgabe, liest Plan und Review, gibst mit einem Knopf frei oder schreibst, was anders sein soll, und siehst dem Bau zu. Flags brauchst du dafür nicht.

```bash
claudegravity chat                      # im Projektordner
claudegravity chat -p ~/projekte/shop   # anderes Projekt
```

Der Befehl startet einen kleinen Server auf deinem Rechner, zeigt die Adresse und öffnet sie im Browser. Mit Strg+C im Terminal beendest du den Chat; laufende Aufgaben werden dabei angehalten und lassen sich später fortsetzen.

## So läuft ein Gespräch

1. **Aufgabe schreiben** und senden. Der Loop besetzt die Rollen wie im Terminal (Profil, Strategie, erkannte KIs).
2. **Plan und Review lesen.** Der Plan des Architekten und das Urteil des Prüfstatikers erscheinen als Nachrichten.
3. **Freigeben oder ändern.** „Plan freigeben und bauen“ startet den Bau. Schreibst du stattdessen einen Satz, überarbeitet der Architekt den Plan danach, und der Prüfstatiker prüft die neue Fassung, bevor du wieder gefragt wirst.
4. **Zusehen.** Jede Bau-Runde, jeder Prüfbefehl (rot mit Ausgabe) und die Abnahme erscheinen im Verlauf. Oben steht, wer gerade arbeitet.
5. **Ergebnis.** Am Ende zeigt „Änderungen zeigen“ die geänderten Dateien und den Diff, neue Dateien mit Inhalt.

Stellt der Loop eine Rückfrage (Schreibrechte, Limit eines Anbieters, Rückfragen der KI mit „KI darf vorab Rückfragen stellen“), erscheint sie mit Knöpfen über dem Eingabefeld. Der Titel des Browser-Tabs bekommt dann einen Punkt.

## Was die Seite sonst kann

| Bereich | Funktion |
| :--- | :--- |
| Linke Spalte | „Neue Aufgabe“, Projekt wechseln (Ordnerauswahl, zuletzt benutzte Projekte), alle Sitzungen des Projekts, auch die aus dem Terminal. |
| **Stopp** | Hält den Lauf an; der Loop sichert seinen Stand. Ein zweiter Klick nach acht Sekunden beendet hart. Unter Windows beendet Stopp sofort hart; der Stand bis zum letzten Schritt bleibt erhalten. |
| **Fortsetzen** | Setzt eine angehaltene oder abgebrochene Sitzung an derselben Stelle fort, mit denselben Rollen, Modellen und Endpunkten. |
| **Details** | Phase, Runde, Tokens, Kosten, geänderte Dateien, Diff, Rollen, `LOG.md`, die Konsolen-Ausgabe des Laufs und der Abschlussbericht. |
| **Optionen** | Strategie, Art der Aufgabe (Vorlage), Prüfbefehl, „Bauleiter darf schreiben“ (`--yolo`, im Chat vorbelegt), „Plan ohne Rückfrage freigeben“ (`--plan-auto`), „KI darf vorab Rückfragen stellen“ (`--ask`), „in den Ausgangs-Branch mergen“ (`--merge`). „Weitere Optionen“ nimmt jedes Flag aus der [CLI-Referenz](cli-referenz.md), z. B. `--builder codex --max-iterations 5`. |

Sitzungen, die im Terminal laufen, zeigt der Chat zum Mitlesen; Rückfragen beantwortest du dort, wo der Lauf gestartet wurde. Die Seite gibt es auf Deutsch und Englisch (`--lang en`), hell und dunkel nach Systemeinstellung, und sie passt auf ein Handy-Display.

## Flags

| Flag | Beschreibung | Standard |
| :--- | :--- | :--- |
| `chat` | Als Aufgabe geschrieben: Chat-Oberfläche starten. | |
| `--chat-port <port>` | Port der Chat-Oberfläche; ist er belegt, ein freier. | `8766` |
| `-p <ordner>` | Projekt, mit dem der Chat startet; in der Seite umschaltbar. | aktueller Ordner |

`CLAUDEGRAVITY_NO_BROWSER=1` verhindert, dass der Browser von selbst öffnet (z. B. über SSH). Für den Zugriff von einem anderen Gerät die Adresse per SSH weiterleiten: `ssh -L 8766:127.0.0.1:8766 rechner`.

## Technik und Sicherheit

* Der Chat startet den Loop als eigenen Prozess; Antworten gehen als Zeilen an dessen Standardeingabe. Alles, was das Terminal kann, gilt unverändert: Rollen-Trennung, Lesemodus für Architekt, Prüfstatiker und Abnahme, Prüfbefehl, Testwächter, Sandbox.
* Das Gespräch entsteht aus `timeline.jsonl` im Session-Ordner (siehe [Sessions & Dateien](sessions-und-dateien.md)); die Konsolen-Ausgabe eines Chat-Laufs steht in `.dual-loop/sessions/<zeit>_chat.log`.
* Der Server hört nur auf `127.0.0.1`. Jede Anfrage braucht den Zufallstoken aus der Adresse, der `Host`-Kopf wird geprüft, es gibt keine CORS-Freigabe und eine strenge Content-Security-Policy. Schreibende Aufrufe verlangen zusätzlich `Content-Type: application/json` und, falls der Browser eine Herkunft mitschickt, die eigene. Eine fremde Webseite kann so weder lesen noch einen Lauf starten.
* Texte aus Modellen und Dateien setzt die Seite nur als Text ein, nie als HTML; Links öffnet sie nur zu `http(s)`-Adressen.
* Wer die Adresse samt Token hat, kann auf deinem Rechner Aufgaben starten. Teile sie nicht und zeige sie nicht in Bildschirmaufnahmen. Mehr im [Bedrohungsmodell](sicherheit.md).
