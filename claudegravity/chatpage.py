"""Die Seite der Chat-Oberfläche (`claudegravity chat`) als eine HTML-Datei ohne fremde Quellen.

Alles, was von Modellen oder aus dem Projekt stammt, wird als Text eingesetzt (textContent), nie als HTML:
Der kleine Markdown-Leser baut nur bekannte Elemente und lässt Verweise nur auf http(s) zu.
"""

CHAT_PAGE = r"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ClaudeGravity Chat</title>
<style>
:root { --bg:#f7f7f5; --card:#ffffff; --fg:#1d1d1b; --muted:#6b6b66; --line:#e3e2dd; --accent:#3d5afe; --accentfg:#ffffff;
  --ok:#1b7f3b; --bad:#b3261e; --warn:#8a5a00; --warnbg:#fff4d6; --add:#e6f4ea; --del:#fdecea; --user:#e8ecff; --soft:#f0efea;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
@media (prefers-color-scheme: dark) { :root { --bg:#151514; --card:#1f1f1d; --fg:#ecebe6; --muted:#a3a29b; --line:#33332f;
  --accent:#8c9eff; --accentfg:#10112a; --ok:#6fcf8f; --bad:#f28b82; --warn:#f6c26b; --warnbg:#3a2f12; --add:#1d3324; --del:#3b1f1d;
  --user:#262b4d; --soft:#262623; } }
* { box-sizing: border-box; }
html, body { height:100%; }
body { margin:0; background:var(--bg); color:var(--fg); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
button, select, input, textarea { font:inherit; color:var(--fg); }
button { cursor:pointer; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:6px 12px; }
button:hover { border-color:var(--muted); }
button:disabled { opacity:.5; cursor:default; }
button.primary { background:var(--accent); color:var(--accentfg); border-color:var(--accent); font-weight:600; }
button.danger { color:var(--bad); border-color:var(--bad); }
button.ghost { background:transparent; border-color:transparent; padding:4px 8px; }
button.ghost:hover { background:var(--soft); }
:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
a { color:var(--accent); }
.muted { color:var(--muted); }
.err { color:var(--bad); }
#app { display:grid; grid-template-columns: 280px minmax(0, 1fr); height:100vh; height:100dvh; }
#side { background:var(--card); border-right:1px solid var(--line); display:flex; flex-direction:column; min-height:0; }
.brand { font-weight:700; font-size:16px; padding:16px 16px 10px; letter-spacing:.2px; }
.brand span { color:var(--accent); }
.sidepad { padding:0 12px 10px; display:grid; gap:8px; }
#new { width:100%; text-align:left; font-weight:600; }
#projbtn { width:100%; text-align:left; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
#projbtn b { display:block; font-size:11px; font-weight:500; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
#sessions { flex:1; overflow:auto; padding:4px 8px 12px; min-height:0; }
.sess { display:block; width:100%; text-align:left; border:0; background:transparent; border-radius:8px; padding:8px 10px; margin-bottom:2px; }
.sess:hover { background:var(--soft); }
.sess.on { background:var(--user); }
.sess .t { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.sess .s { display:block; font-size:12px; color:var(--muted); }
.dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; background:var(--line); vertical-align:1px; }
.dot.run { background:var(--accent); animation:pulse 1.4s ease-in-out infinite; } .dot.ok { background:var(--ok); } .dot.open { background:var(--warn); }
@keyframes pulse { 50% { opacity:.35; } }
@media (prefers-reduced-motion: reduce) { .dot.run, .typing i { animation:none !important; } }
.sidefoot { padding:10px 16px; border-top:1px solid var(--line); font-size:12px; color:var(--muted); }
#main { display:flex; flex-direction:column; min-width:0; min-height:0; }
#top { display:flex; gap:10px; align-items:center; padding:10px 16px; border-bottom:1px solid var(--line); background:var(--card); }
#menu { display:none; }
.title { flex:1; min-width:0; }
#task { font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.badge:empty { display:none; }
.badge { display:inline-block; padding:1px 9px; border-radius:999px; font-size:12.5px; border:1px solid var(--line); white-space:nowrap; }
.badge.ok { color:var(--ok); border-color:var(--ok); } .badge.bad { color:var(--bad); border-color:var(--bad); }
.badge.run { color:var(--accent); border-color:var(--accent); } .badge.warn { color:var(--warn); border-color:var(--warn); }
#activity { font-size:13px; color:var(--muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0; }
.actions { display:flex; gap:6px; flex-shrink:0; }
#scroll { flex:1; overflow:auto; min-height:0; }
#thread { max-width:860px; margin:0 auto; padding:18px 16px 8px; display:flex; flex-direction:column; gap:10px; }
.welcome { max-width:700px; margin:6vh auto 0; text-align:center; }
.welcome h1 { font-size:24px; margin:0 0 8px; }
.steps { display:grid; grid-template-columns:repeat(auto-fit, minmax(112px, 1fr)); gap:8px; margin:18px 0; text-align:left; }
.step { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; font-size:13.5px; }
.step b { display:block; }
.chips { display:flex; gap:6px; flex-wrap:wrap; justify-content:center; }
.chip { font-size:12.5px; border:1px solid var(--line); border-radius:999px; padding:2px 10px; background:var(--card); }
.chip.ok { border-color:var(--ok); } .chip.off { color:var(--muted); }
.note { background:var(--warnbg); color:var(--warn); border-radius:10px; padding:8px 12px; font-size:14px; text-align:left; margin-top:10px; overflow-wrap:anywhere; }
.msg { border:1px solid var(--line); background:var(--card); border-radius:12px; max-width:100%; }
.msg.user { align-self:flex-end; background:var(--user); border-color:transparent; padding:8px 12px; max-width:86%; white-space:pre-wrap; overflow-wrap:anywhere; }
.msg.user .lbl { display:block; font-size:12px; color:var(--muted); }
details.msg > summary { list-style:none; cursor:pointer; padding:9px 12px; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
details.msg > summary::-webkit-details-marker { display:none; }
details.msg > summary::after { content:"▸"; color:var(--muted); margin-left:auto; }
details.msg[open] > summary::after { content:"▾"; }
details.msg > summary .who { font-weight:600; }
details.msg > summary .meta { font-size:12.5px; color:var(--muted); }
.body { padding:0 14px 12px; border-top:1px solid var(--line); overflow-wrap:anywhere; }
.body > :first-child { margin-top:10px; }
.body h3 { font-size:17px; margin:14px 0 6px; } .body h4 { font-size:15.5px; margin:12px 0 4px; } .body h5, .body h6 { font-size:14.5px; margin:10px 0 4px; }
.body p { margin:8px 0; white-space:pre-wrap; } .body ul, .body ol { margin:6px 0; padding-left:22px; } .body li { margin:2px 0; white-space:pre-wrap; } .body li.sub { margin-left:18px; }
.body blockquote { margin:8px 0; padding:2px 12px; border-left:3px solid var(--line); color:var(--muted); white-space:pre-wrap; }
.body hr { border:0; border-top:1px solid var(--line); margin:12px 0; }
.body table { border-collapse:collapse; margin:8px 0; font-size:14px; display:block; overflow-x:auto; }
.body th, .body td { border:1px solid var(--line); padding:4px 8px; text-align:left; vertical-align:top; }
code { font: 13px/1.4 var(--mono); background:var(--soft); border-radius:4px; padding:1px 4px; }
pre { margin:8px 0; font: 12.5px/1.45 var(--mono); background:var(--soft); border-radius:8px; padding:10px; overflow:auto; max-height:420px; white-space:pre; }
pre code { background:transparent; padding:0; font:inherit; }
pre .lang { display:block; color:var(--muted); font-size:11.5px; margin-bottom:4px; }
pre.wrap { white-space:pre-wrap; overflow-wrap:anywhere; }
pre .a { background:var(--add); display:block; } pre .d { background:var(--del); display:block; } pre .h { color:var(--muted); display:block; }
.sys { align-self:center; font-size:13px; color:var(--muted); text-align:center; max-width:100%; overflow-wrap:anywhere; }
.sys.ok { color:var(--ok); } .sys.bad { color:var(--bad); } .sys.warn { color:var(--warn); }
.sys pre { text-align:left; margin-top:6px; }
.endcard { border:1px solid var(--line); background:var(--card); border-radius:12px; padding:12px 14px; }
.endcard.ok { border-color:var(--ok); } .endcard.bad { border-color:var(--bad); }
.endcard h3 { margin:0 0 4px; font-size:16px; }
.typing { align-self:flex-start; color:var(--muted); font-size:14px; padding:4px 2px; }
.typing i { display:inline-block; width:6px; height:6px; border-radius:50%; background:var(--muted); margin-right:3px; animation:pulse 1.2s infinite; }
.typing i:nth-child(2) { animation-delay:.2s; } .typing i:nth-child(3) { animation-delay:.4s; margin-right:8px; }
#question { max-width:860px; width:100%; margin:0 auto; padding:0 16px; }
.qcard { border:1px solid var(--accent); background:var(--card); border-radius:12px; padding:12px 14px; margin-bottom:8px; }
.qcard h3 { margin:0 0 6px; font-size:15.5px; }
.qcard .btns { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
.qcard .hint { font-size:13px; color:var(--muted); margin-top:8px; }
#composer { border-top:1px solid var(--line); background:var(--card); padding:10px 16px 12px; }
.cwrap { max-width:828px; margin:0 auto; }
.inputrow { display:flex; gap:8px; align-items:flex-end; }
#input { flex:1; resize:none; border:1px solid var(--line); border-radius:10px; padding:9px 12px; background:var(--bg); max-height:200px; min-height:42px; line-height:1.4; }
#send { height:42px; }
#hint { font-size:12.5px; margin-top:6px; min-height:18px; }
#options { margin-bottom:8px; font-size:14px; }
#options > summary { cursor:pointer; color:var(--muted); }
.optgrid { display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); gap:8px 14px; margin-top:8px; }
.optgrid label { display:grid; gap:2px; font-size:12.5px; color:var(--muted); }
.optgrid select, .optgrid input[type=text] { border:1px solid var(--line); border-radius:8px; padding:6px 8px; background:var(--bg); width:100%; }
.checks { display:flex; gap:6px 16px; flex-wrap:wrap; margin-top:8px; }
.checks label { display:flex; gap:6px; align-items:center; }
#panel { position:fixed; top:0; right:0; bottom:0; width:min(560px, 100vw); background:var(--bg); border-left:1px solid var(--line); box-shadow:-8px 0 24px rgba(0,0,0,.12); overflow:auto; padding:14px 16px 32px; z-index:20; }
#panel h2 { font-size:13px; text-transform:uppercase; letter-spacing:.6px; color:var(--muted); margin:16px 0 6px; }
.grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap:8px; }
.kv { border:1px solid var(--line); border-radius:10px; padding:6px 10px; background:var(--card); }
.kv b { display:block; font-size:12px; color:var(--muted); font-weight:500; }
.kv span { font-variant-numeric: tabular-nums; overflow-wrap:anywhere; }
table.t { width:100%; border-collapse:collapse; font-size:13.5px; background:var(--card); border:1px solid var(--line); border-radius:10px; }
table.t th, table.t td { text-align:left; padding:5px 8px; border-bottom:1px solid var(--line); vertical-align:top; overflow-wrap:anywhere; }
table.t th { color:var(--muted); font-weight:500; }
td.num, th.num { text-align:right; white-space:nowrap; font-variant-numeric: tabular-nums; }
.plus { color:var(--ok); } .minus { color:var(--bad); }
dialog { border:1px solid var(--line); border-radius:14px; background:var(--card); color:var(--fg); padding:16px; width:min(560px, 94vw); }
dialog::backdrop { background:rgba(0,0,0,.4); }
#pickpath { width:100%; border:1px solid var(--line); border-radius:8px; padding:7px 9px; background:var(--bg); font:13px var(--mono); }
#picklist { max-height:44vh; overflow:auto; margin:8px 0; border:1px solid var(--line); border-radius:8px; }
#picklist button { display:block; width:100%; text-align:left; border:0; border-radius:0; border-bottom:1px solid var(--line); background:transparent; padding:7px 10px; }
#picklist button:hover { background:var(--soft); }
#toast { position:fixed; left:50%; bottom:92px; transform:translateX(-50%); background:var(--fg); color:var(--bg); padding:8px 14px; border-radius:10px; font-size:14px; z-index:30; max-width:90vw; }
@media (max-width: 820px) {
  #app { grid-template-columns: minmax(0, 1fr); }
  #side { position:fixed; inset:0 auto 0 0; width:min(300px, 86vw); z-index:15; transform:translateX(-100%); transition:transform .18s; }
  #side.open { transform:none; box-shadow:8px 0 24px rgba(0,0,0,.15); }
  #menu { display:inline-block; }
  .msg.user { max-width:94%; }
  #top { padding:8px 10px; } #thread { padding:12px 10px 6px; } #question { padding:0 10px; } #composer { padding:8px 10px 10px; }
  .actions button { padding:6px 9px; }
}
</style>
</head>
<body>
<div id="app">
  <aside id="side" aria-label="Sitzungen">
    <div class="brand">ClaudeGravity <span>Chat</span></div>
    <div class="sidepad">
      <button id="new" type="button"></button>
      <button id="projbtn" type="button"><b id="projlbl"></b><span id="projname"></span></button>
    </div>
    <nav id="sessions"></nav>
    <div class="sidefoot"><span id="ver"></span> · <a id="docs" target="_blank" rel="noopener noreferrer"></a></div>
  </aside>
  <main id="main">
    <header id="top">
      <button id="menu" class="ghost" type="button" aria-label="Menü">☰</button>
      <div class="title">
        <div id="task"></div>
        <div class="row"><span id="badge" class="badge" hidden></span><span id="activity"></span></div>
      </div>
      <div class="actions">
        <button id="stop" class="danger" type="button" hidden></button>
        <button id="resume" class="primary" type="button" hidden></button>
        <button id="details" type="button" hidden></button>
      </div>
    </header>
    <div id="scroll"><div id="thread"></div></div>
    <div id="question"></div>
    <footer id="composer"><div class="cwrap">
      <details id="options">
        <summary id="optsum"></summary>
        <div class="optgrid">
          <label><span id="l-strategy"></span><select id="o-strategy"></select></label>
          <label><span id="l-template"></span><select id="o-template"></select></label>
          <label><span id="l-proof"></span><input id="o-proof" type="text" autocomplete="off" spellcheck="false"></label>
          <label><span id="l-extra"></span><input id="o-extra" type="text" autocomplete="off" spellcheck="false" placeholder="--architekt codex"></label>
        </div>
        <div class="checks">
          <label><input id="o-yolo" type="checkbox" checked><span id="l-yolo"></span></label>
          <label><input id="o-plan_auto" type="checkbox"><span id="l-plan_auto"></span></label>
          <label><input id="o-ask" type="checkbox"><span id="l-ask"></span></label>
          <label><input id="o-merge" type="checkbox"><span id="l-merge"></span></label>
        </div>
      </details>
      <div class="inputrow">
        <textarea id="input" rows="1" aria-label="Nachricht"></textarea>
        <button id="send" class="primary" type="button"></button>
      </div>
      <div id="hint" class="muted"></div>
    </div></footer>
  </main>
</div>
<aside id="panel" hidden>
  <div class="row" style="justify-content:space-between"><strong id="p-title"></strong><button id="p-close" class="ghost" type="button" aria-label="Schließen">✕</button></div>
  <div class="grid" id="p-facts"></div>
  <h2 id="p-hfiles"></h2>
  <table class="t"><tbody id="p-files"></tbody></table>
  <p><button id="p-diffbtn" type="button"></button></p>
  <pre id="p-diff" class="wrap" hidden></pre>
  <h2 id="p-hroles"></h2>
  <table class="t"><thead><tr><th id="p-th-role"></th><th id="p-th-agent"></th><th class="num" id="p-th-tokens"></th><th class="num">USD</th></tr></thead><tbody id="p-roles"></tbody></table>
  <h2>LOG.md</h2>
  <pre id="p-log" class="wrap"></pre>
  <h2 id="p-hconsole"></h2>
  <p><button id="p-conbtn" type="button"></button></p>
  <pre id="p-console" class="wrap" hidden></pre>
  <div id="p-reportwrap" hidden><h2 id="p-hreport"></h2><pre id="p-report" class="wrap"></pre></div>
</aside>
<dialog id="picker">
  <strong id="pick-title"></strong>
  <p class="muted" id="pick-help" style="margin:4px 0 8px"></p>
  <input id="pickpath" type="text" autocomplete="off" spellcheck="false" aria-label="Pfad">
  <div class="chips" id="pick-recent" style="justify-content:flex-start; margin-top:8px"></div>
  <div id="picklist"></div>
  <div class="row" style="justify-content:flex-end">
    <span id="pick-info" class="muted" style="margin-right:auto; font-size:13px"></span>
    <button id="pick-cancel" type="button"></button>
    <button id="pick-ok" class="primary" type="button"></button>
  </div>
</dialog>
<div id="toast" hidden role="status"></div>
<script>
"use strict";
const L = {
  de: { newTask:"+ Neue Aufgabe", project:"Projekt", docs:"Anleitung", send:"Senden", answer:"Antworten", stop:"Stopp", stopping:"Hält an …", resume:"Fortsetzen", details:"Details",
    options:"Optionen", strategy:"Strategie", template:"Art der Aufgabe", proof:"Prüfbefehl (Tests)", extra:"Weitere Optionen", auto:"Automatisch (Profil)",
    yolo:"Bauleiter darf im Arbeitsbereich schreiben", planAuto:"Plan ohne Rückfrage freigeben, wenn der Prüfstatiker zustimmt", ask:"KI darf vorab Rückfragen stellen", merge:"Ergebnis in den Ausgangs-Branch mergen",
    strategies:{ balanced:"balanced · ausgewogen", "best-code":"best-code · beste Qualität", eco:"eco · sparsam", hybrid:"hybrid · Cloud plant, lokal baut", "local-free":"local-free · Bau lokal für 0 €" },
    templates:{ "":"Automatisch", bugfix:"Fehler beheben", feature:"Neue Funktion", refactor:"Umbau ohne neues Verhalten" },
    phNew:"Was soll gebaut werden?", phNext:"Nächste Aufgabe für dieses Projekt …", phBusy:"Der Lauf arbeitet. Du kannst zusehen oder ihn anhalten.", phPlan:"Schreibe, was am Plan anders sein soll …", phAnswer:"Deine Antwort …", phTerminal:"Dieser Lauf wurde im Terminal gestartet und wird dort beantwortet.",
    hintNew:"Eingabetaste sendet, Umschalt+Eingabetaste macht eine neue Zeile.", hintPlan:"Knopf wählen oder Änderungswunsch schreiben.",
    welcome:"Was soll gebaut werden?", welcomeSub:"Beschreibe die Aufgabe in deinen Worten. Der Loop besetzt die Rollen selbst.",
    steps:[["🏗️ Architekt","entwirft den Plan"],["🧐 Prüfstatiker","prüft ihn unabhängig"],["👤 Du","gibst frei oder änderst"],["🔨 Bauleiter","setzt um, Tests laufen"],["🔎 Abnahme","ein anderer Anbieter nimmt ab"]],
    detecting:"Suche installierte KIs …", noAgents:"Keine KI gefunden. Installiere und melde eine KI-CLI an (z. B. claude, codex, agy), starte Ollama oder richte mit `claudegravity init` ein.",
    oneAgent:"Nur ein Anbieter gefunden: Plan, Prüfung und Abnahme kommen dann vom selben Modell. Ein zweiter Anbieter macht die Prüfung unabhängig.",
    noGit:"Kein Git-Repository: Der Bauleiter ändert die Dateien direkt in diesem Ordner. Mit Git arbeitet er in einem eigenen Branch.",
    homeProject:"Das ist dein Home-Verzeichnis. Wähle links den Ordner deines Projekts.",
    you:"Du", task:"Aufgabe", starting:"Der Loop startet …", startFailed:"Der Lauf ist vor dem Start gescheitert", exitCode:"Exit-Code",
    roles:{ planner:"Architekt", reviewer:"Prüfstatiker", builder:"Bauleiter", inspector:"Abnahme" }, icons:{ planner:"🏗️", reviewer:"🧐", builder:"🔨", inspector:"🔎" },
    plan:"Plan", planSrc:{ draft:"Entwurf", revision:"überarbeitet nach Review", feedback:"überarbeitet nach deinem Wunsch", manual:"von Hand geändert" }, superseded:"überholt",
    review:"Review Runde", inspection:"Abnahme Runde", approved:"genehmigt", rejected:"Befunde offen", inspOk:"erteilt", inspNo:"verweigert", findings:"Befund(e)",
    build:"Bau-Runde", files:"Datei(en)", noText:"(keine Ausgabe)", proofOk:"✅ Prüfbefehl grün", proofRed:"❌ Prüfbefehl rot", stageOk:"✅ Etappe", stageNo:"❌ Etappe", stageDone:"erledigt", stageOpen:"noch nicht grün",
    resumed:"↻ Fortgesetzt", cast:"Besetzung", escalation:"⬆️ Eskalation", pr:"Pull Request", errorTitle:"🛑 Fehler",
    endOk:"🎉 Fertig", endNo:"⏹️ Beendet ohne Abschluss", endPaused:"⏸️ Angehalten", pausedHint:"Mit „Fortsetzen“ geht es an derselben Stelle weiter.", endReason:"Grund", endStats:"Bau-Runden", tokens:"Tokens", cost:"Kosten (gemeldet)", showChanges:"Änderungen zeigen", nextHint:"Schreibe unten die nächste Aufgabe oder setze diese Sitzung fort.",
    defaultAnswer:"Standard (Eingabetaste)", kinds:{ plan:"Plan freigeben?", plan_open:"Der Prüfstatiker hat noch Befunde. Trotzdem freigeben?", plan_feedback:"Was soll am Plan anders sein?", permission:"Darf der Bauleiter schreiben?", limit:"Limit erreicht. Wie weiter?", questions:"Rückfragen an dich", resume:"Sitzung fortsetzen?", minutes:"Wie lange warten?" },
    answers:{ plan:{ "1":"Plan freigegeben" } }, askTitle:{ questions:"❓ Rückfragen", limit:"🚨 Limit" },
    waitingTerminal:"⏳ Wartet im Terminal auf deine Antwort: ", works:" arbeitet seit ", proofRuns:"🧪 Prüfbefehl läuft seit ",
    running:"läuft", done:"fertig", ended:"beendet", paused:"angehalten", idle:"nicht aktiv", waitingYou:"wartet auf dich",
    phases:{ plan:"Plan", review:"Review", build:"Bau", inspection_open:"Abnahme offen", stage_open:"Etappe offen", completed:"abgeschlossen", candidates:"Kandidaten" },
    phase:"Phase", round:"Bau-Runde", stage:"Etappe", strategyK:"Strategie", branch:"Branch", proofK:"Prüfbefehl", changed:"Geänderte Dateien", noFiles:"Noch keine Änderungen.", newFile:"neu",
    showDiff:"Diff zeigen", hideDiff:"Diff ausblenden", emptyDiff:"Kein Diff.", truncated:"… gekürzt", rolesT:"Rollen", role:"Rolle", agent:"Anbieter / Modell", console:"Konsole", showConsole:"Konsolenausgabe zeigen", hideConsole:"Konsolenausgabe ausblenden", noConsole:"Keine Konsolenausgabe (Lauf nicht aus diesem Chat gestartet).", report:"Bericht",
    pickTitle:"Projektordner wählen", pickHelp:"In diesem Ordner arbeitet der Loop. Pfad eintippen oder durchklicken.", pickOk:"Diesen Ordner nehmen", cancel:"Abbrechen", up:"⬆ Übergeordneter Ordner", pickGit:"Git-Repository", pickSessions:"hat schon Sitzungen", noSub:"Keine Unterordner.",
    offline:"Keine Verbindung zum Chat-Server. Läuft `claudegravity chat` noch?", noSessions:"Noch keine Sitzung in diesem Projekt.", failed:"Das hat nicht geklappt: " },
  en: { newTask:"+ New task", project:"Project", docs:"Guide", send:"Send", answer:"Answer", stop:"Stop", stopping:"Stopping …", resume:"Resume", details:"Details",
    options:"Options", strategy:"Strategy", template:"Kind of task", proof:"Proof command (tests)", extra:"More options", auto:"Automatic (profile)",
    yolo:"Builder may write in the workspace", planAuto:"Approve the plan without asking once the reviewer agrees", ask:"The AI may ask questions first", merge:"Merge the result into the base branch",
    strategies:{ balanced:"balanced", "best-code":"best-code · best quality", eco:"eco · economical", hybrid:"hybrid · cloud plans, local builds", "local-free":"local-free · build locally for 0 €" },
    templates:{ "":"Automatic", bugfix:"Fix a bug", feature:"New feature", refactor:"Refactoring without new behaviour" },
    phNew:"What should be built?", phNext:"Next task for this project …", phBusy:"The run is working. You can watch or stop it.", phPlan:"Write what should be different in the plan …", phAnswer:"Your answer …", phTerminal:"This run was started in a terminal and is answered there.",
    hintNew:"Enter sends, Shift+Enter adds a new line.", hintPlan:"Pick a button or write a change request.",
    welcome:"What should be built?", welcomeSub:"Describe the task in your own words. The loop fills the roles by itself.",
    steps:[["🏗️ Architect","drafts the plan"],["🧐 Reviewer","checks it independently"],["👤 You","approve or change"],["🔨 Builder","implements, tests run"],["🔎 Acceptance","another provider signs off"]],
    detecting:"Looking for installed AIs …", noAgents:"No AI found. Install and sign in to an AI CLI (e.g. claude, codex, agy), start Ollama or run `claudegravity init`.",
    oneAgent:"Only one provider found: plan, review and acceptance then come from the same model. A second provider makes the review independent.",
    noGit:"Not a Git repository: the builder changes the files directly in this folder. With Git it works in its own branch.",
    homeProject:"This is your home directory. Choose your project folder on the left.",
    you:"You", task:"Task", starting:"The loop is starting …", startFailed:"The run failed before it started", exitCode:"Exit code",
    roles:{ planner:"Architect", reviewer:"Reviewer", builder:"Builder", inspector:"Acceptance" }, icons:{ planner:"🏗️", reviewer:"🧐", builder:"🔨", inspector:"🔎" },
    plan:"Plan", planSrc:{ draft:"draft", revision:"revised after review", feedback:"revised on your request", manual:"edited by hand" }, superseded:"superseded",
    review:"Review round", inspection:"Acceptance round", approved:"approved", rejected:"findings open", inspOk:"granted", inspNo:"refused", findings:"finding(s)",
    build:"Build round", files:"file(s)", noText:"(no output)", proofOk:"✅ Proof command green", proofRed:"❌ Proof command red", stageOk:"✅ Stage", stageNo:"❌ Stage", stageDone:"done", stageOpen:"not green yet",
    resumed:"↻ Resumed", cast:"Roles", escalation:"⬆️ Escalation", pr:"Pull request", errorTitle:"🛑 Error",
    endOk:"🎉 Done", endNo:"⏹️ Ended without completion", endPaused:"⏸️ Paused", pausedHint:"“Resume” continues at the same point.", endReason:"Reason", endStats:"Build rounds", tokens:"Tokens", cost:"Cost (reported)", showChanges:"Show changes", nextHint:"Write the next task below or resume this session.",
    defaultAnswer:"Default (Enter)", kinds:{ plan:"Approve the plan?", plan_open:"The reviewer still has findings. Approve anyway?", plan_feedback:"What should be different in the plan?", permission:"May the builder write?", limit:"Limit reached. How to go on?", questions:"Questions for you", resume:"Resume the session?", minutes:"How long to wait?" },
    answers:{ plan:{ "1":"Plan approved" } }, askTitle:{ questions:"❓ Questions", limit:"🚨 Limit" },
    waitingTerminal:"⏳ Waiting for your answer in the terminal: ", works:" working for ", proofRuns:"🧪 Proof command running for ",
    running:"running", done:"done", ended:"ended", paused:"paused", idle:"not active", waitingYou:"waiting for you",
    phases:{ plan:"Plan", review:"Review", build:"Build", inspection_open:"Acceptance open", stage_open:"Stage open", completed:"completed", candidates:"Candidates" },
    phase:"Phase", round:"Build round", stage:"Stage", strategyK:"Strategy", branch:"Branch", proofK:"Proof command", changed:"Changed files", noFiles:"No changes yet.", newFile:"new",
    showDiff:"Show diff", hideDiff:"Hide diff", emptyDiff:"No diff.", truncated:"… truncated", rolesT:"Roles", role:"Role", agent:"Provider / model", console:"Console", showConsole:"Show console output", hideConsole:"Hide console output", noConsole:"No console output (run not started from this chat).", report:"Report",
    pickTitle:"Choose the project folder", pickHelp:"The loop works in this folder. Type a path or click through.", pickOk:"Use this folder", cancel:"Cancel", up:"⬆ Parent folder", pickGit:"Git repository", pickSessions:"already has sessions", noSub:"No subfolders.",
    offline:"No connection to the chat server. Is `claudegravity chat` still running?", noSessions:"No session in this project yet.", failed:"That did not work: " }
};
const token = new URLSearchParams(location.search).get("t") || "";
const store = { get(k) { try { return localStorage.getItem("cg-chat-" + k); } catch (e) { return null; } }, set(k, v) { try { localStorage.setItem("cg-chat-" + k, v); } catch (e) { /* privater Modus */ } } };
const S = { T: L.de, lang: "de", project: store.get("project") || "", chosen: decodeURIComponent(location.hash.slice(1)) || null, follow: null, failed: null, count: 0, data: null, first: true, busy: false, diffOpen: false, conOpen: false, proofSeen: null, now: null, timer: null, optsReady: false, lastQ: null };
const $ = (id) => document.getElementById(id);
function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined && text !== null) e.textContent = String(text); if (cls) e.className = cls; return e; }
function num(n) { return (n === null || n === undefined) ? "–" : Number(n).toLocaleString(S.lang === "en" ? "en-US" : "de-DE"); }
function dur(s) { if (s === null || s === undefined) return ""; s = Math.round(Number(s)); const m = Math.floor(s / 60); return m >= 60 ? Math.floor(m / 60) + " h " + (m % 60) + " min" : (m ? m + " min " + (s % 60) + " s" : s + " s"); }
function since(iso) { if (!iso || !S.now) return ""; return dur(Math.max(0, (new Date(S.now) - new Date(iso)) / 1000)); }
function clock(iso) { return iso ? String(iso).slice(11, 16) : ""; }
function toast(text) { const t = $("toast"); t.textContent = text; t.hidden = false; clearTimeout(toast.timer); toast.timer = setTimeout(() => { t.hidden = true; }, 5000); }
function url(path, extra) { return path + "?" + new URLSearchParams(Object.assign({ t: token }, extra || {})).toString(); }
function getJSON(path, extra) { return fetch(url(path, extra), { cache: "no-store" }).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }); }
function post(path, body) {
  return fetch(url(path), { method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" }, body: JSON.stringify(Object.assign({ project: S.project }, body || {})) })
    .then((r) => r.json().catch(() => ({ ok: false, error: String(r.status) })).then((d) => { if (!r.ok || d.ok === false) throw new Error(d.error || r.status); return d; }));
}

/* ---------- Markdown: nur bekannte Elemente, Inhalte immer als Text ---------- */
function link(href, label) { const a = el("a", label); a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer"; return a; }
function inline(text, parent) {
  const re = /(`+)([\s\S]*?)\1|\*\*([^*\n]+)\*\*|\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>()]*[^\s<>().,;:!?"'`*])/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) parent.append(text.slice(last, m.index));
    if (m[1]) parent.append(el("code", m[2]));
    else if (m[3]) parent.append(el("strong", m[3]));
    else if (m[4]) parent.append(link(m[5], m[4]));
    else parent.append(link(m[6], m[6]));
    last = re.lastIndex;
  }
  if (last < text.length) parent.append(text.slice(last));
}
function cells(line) { return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim()); }
function md(text) {
  const root = document.createDocumentFragment();
  const lines = String(text || "").replace(/\r\n?/g, "\n").split("\n");
  const item = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/, fenceRe = /^\s*(`{3,}|~{3,})\s*(.*)$/, quote = /^\s*>\s?(.*)$/;
  let i = 0, para = [], list = null, m;
  const flush = () => { if (para.length) { const p = el("p"); inline(para.join("\n"), p); root.append(p); para = []; } };
  while (i < lines.length) {
    const line = lines[i];
    if ((m = fenceRe.exec(line))) {
      flush(); list = null;
      const fence = m[1], buf = []; i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence)) buf.push(lines[i++]);
      i++;
      const pre = el("pre"); if (m[2]) pre.append(el("span", m[2], "lang")); pre.append(el("code", buf.join("\n"))); root.append(pre);
      continue;
    }
    if (!line.trim()) { flush(); list = null; i++; continue; }
    if ((m = /^(#{1,6})\s+(.*)$/.exec(line))) { flush(); list = null; const h = el("h" + Math.min(6, m[1].length + 2)); inline(m[2].replace(/\s+#+\s*$/, ""), h); root.append(h); i++; continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flush(); list = null; root.append(el("hr")); i++; continue; }
    if ((m = quote.exec(line))) { flush(); list = null; const buf = [m[1]]; i++; while (i < lines.length && (m = quote.exec(lines[i]))) { buf.push(m[1]); i++; } const q = el("blockquote"); inline(buf.join("\n"), q); root.append(q); continue; }
    if (line.includes("|") && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(lines[i + 1])) {
      flush(); list = null;
      const table = el("table"), head = el("tr");
      cells(line).forEach((c) => { const th = el("th"); inline(c, th); head.append(th); });
      table.append(head); i += 2;
      while (i < lines.length && lines[i].includes("|") && lines[i].trim()) { const tr = el("tr"); cells(lines[i]).forEach((c) => { const td = el("td"); inline(c, td); tr.append(td); }); table.append(tr); i++; }
      root.append(table);
      continue;
    }
    if ((m = item.exec(line))) {
      flush();
      const ordered = /\d/.test(m[2]);
      if (!list || list.ordered !== ordered) { const node = el(ordered ? "ol" : "ul"); if (ordered) node.start = parseInt(m[2], 10) || 1; root.append(node); list = { node, ordered }; }
      const li = el("li"); let content = m[3];
      const box = /^\[( |x|X)\]\s+(.*)$/.exec(content);
      if (box) { li.append(box[1] === " " ? "☐ " : "☑ "); content = box[2]; }
      inline(content, li); if (m[1].length >= 2) li.className = "sub"; list.node.append(li); i++;
      while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !item.test(lines[i]) && !fenceRe.test(lines[i])) { li.append("\n"); inline(lines[i].trim(), li); i++; }
      continue;
    }
    list = null; para.push(line); i++;
  }
  flush();
  return root;
}

/* ---------- Nachrichten ---------- */
function roleMsg(role, title, meta, badge, open) {
  const T = S.T, d = el("details", null, "msg role"); d.open = !!open;
  const sum = el("summary");
  sum.append(el("span", T.icons[role] || "•"), el("span", T.roles[role] || role, "who"), el("span", title));
  if (badge) sum.append(el("span", badge.text, "badge " + badge.cls));
  if (meta) sum.append(el("span", meta, "meta"));
  d.append(sum);
  const body = el("div", null, "body"); d.append(body);
  return { node: d, body };
}
function statText(msg) {
  const parts = [];
  if (msg.agent) parts.push(msg.agent);
  if (msg.stats) { if (msg.stats.model) parts.push(msg.stats.model); if (msg.stats.duration_s) parts.push(dur(msg.stats.duration_s)); if (msg.stats.tokens) parts.push(num(msg.stats.tokens) + " " + S.T.tokens); }
  if (msg.time) parts.push(clock(msg.time));
  return parts.join(" · ");
}
function userMsg(label, text) { const d = el("div", null, "msg user"); d.append(el("span", label, "lbl"), text); return d; }
function sysMsg(text, cls) { return el("div", text, "sys" + (cls ? " " + cls : "")); }
function render(msg) {
  const T = S.T;
  switch (msg.type) {
    case "task": return userMsg(T.you + " · " + T.task + (msg.time ? " · " + clock(msg.time) : ""), msg.text);
    case "resumed": return sysMsg(T.resumed + (msg.time ? " · " + clock(msg.time) : ""));
    case "roles": {
      const who = [["planner", msg.planner], ["reviewer", msg.reviewer], ["builder", msg.builder]].filter((p) => p[1]).map((p) => T.icons[p[0]] + " " + p[1]);
      return sysMsg(T.cast + (msg.strategy ? " (" + msg.strategy + ")" : "") + ": " + who.join("  ·  "));
    }
    case "plan": {
      document.querySelectorAll("details.plan[open]").forEach((d) => { d.open = false; const s = d.querySelector(".state"); if (s) s.textContent = T.superseded; });
      const src = T.planSrc[msg.source] || "";
      const r = roleMsg("planner", T.plan + " v" + (msg.version || "?"), statText(msg), null, true);
      r.node.classList.add("plan");
      r.node.querySelector("summary").insertBefore(el("span", src, "meta state"), r.node.querySelector("summary .meta"));
      r.body.append(md(msg.text || T.noText));
      return r.node;
    }
    case "review": case "inspection": {
      const insp = msg.type === "inspection", ok = !!msg.approved;
      const badge = { text: insp ? (ok ? T.inspOk : T.inspNo) : (ok ? T.approved : T.rejected), cls: ok ? "ok" : "warn" };
      const count = msg.findings ? " · " + msg.findings + " " + T.findings : "";
      const r = roleMsg(insp ? "inspector" : "reviewer", (insp ? T.inspection : T.review) + " " + (msg.round || "") + count, statText(msg), badge, !ok);
      if (msg.reason && msg.reason !== "APPROVED" && msg.reason !== "REVISE") r.body.append(el("p", msg.reason, "muted"));
      r.body.append(md(msg.text || T.noText));
      return r.node;
    }
    case "ask": { const d = el("div", null, "msg"); const b = el("div", null, "body"); b.style.borderTop = "0"; b.append(el("h4", T.askTitle[msg.kind] || "❓"), md(msg.text)); d.append(b); return d; }
    case "answer": {
      const special = (T.answers[msg.kind] || {})[msg.value];
      const text = special || msg.label || (msg.value === "" ? T.defaultAnswer : msg.value);
      return userMsg(T.you + (msg.time ? " · " + clock(msg.time) : ""), text);
    }
    case "build": {
      const files = (msg.files || []).length;
      const r = roleMsg("builder", (msg.label || T.build + " " + (msg.iteration || "")) + (files ? " · " + files + " " + T.files : ""), statText(msg), null, false);
      if (files) { const ul = el("ul"); msg.files.forEach((f) => ul.append(el("li", f))); r.body.append(ul); }
      r.body.append(md(msg.text || T.noText));
      return r.node;
    }
    case "proof": {
      const d = sysMsg((msg.ok ? T.proofOk : T.proofRed) + (msg.command ? " · " + msg.command : ""), msg.ok ? "ok" : "bad");
      if (!msg.ok && msg.output) { const pre = el("pre", msg.output, "wrap"); d.append(pre); }
      return d;
    }
    case "stage": return sysMsg((msg.ok ? T.stageOk : T.stageNo) + " " + msg.index + "/" + msg.total + " " + (msg.ok ? T.stageDone : T.stageOpen) + (msg.text ? ": " + msg.text : ""), msg.ok ? "ok" : "warn");
    case "notice": return sysMsg(msg.text, msg.level === "warning" ? "warn" : "");
    case "escalation": return sysMsg(T.escalation + ": " + (msg.from || "") + " → " + (msg.to || "") + (msg.reason ? " (" + msg.reason + ")" : ""), "warn");
    case "pull_request": { const d = sysMsg(T.pr + ": "); if (/^https:\/\//.test(msg.url || "")) d.append(link(msg.url, msg.url)); return d; }
    case "error": { const d = el("div", null, "endcard bad"); d.append(el("h3", T.errorTitle + (msg.code ? " " + msg.code : "")), el("div", msg.text || "")); return d; }
    case "end": {
      const d = el("div", null, "endcard " + (msg.success ? "ok" : "bad"));
      const paused = !msg.success && pausedBy(msg.reason);
      if (paused) d.className = "endcard";
      d.append(el("h3", msg.success ? T.endOk : (paused ? T.endPaused : T.endNo)));
      if (paused) d.append(el("div", T.pausedHint));
      else if (!msg.success && msg.reason) d.append(el("div", T.endReason + ": " + msg.reason));
      const facts = [];
      if (msg.rounds) facts.push(T.endStats + ": " + msg.rounds);
      if (msg.tokens) facts.push(T.tokens + ": " + num(msg.tokens));
      if (msg.cost_usd) facts.push(T.cost + ": " + Number(msg.cost_usd).toFixed(2) + " USD");
      if (facts.length) d.append(el("div", facts.join(" · "), "muted"));
      const row = el("div", null, "row"); row.style.marginTop = "8px";
      const b = el("button", T.showChanges); b.type = "button"; b.addEventListener("click", () => openPanel(true)); row.append(b);
      d.append(row);
      return d;
    }
    default: return null;
  }
}
function atBottom() { const sc = $("scroll"); return sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 60; }
function toBottom() { const sc = $("scroll"); sc.scrollTop = sc.scrollHeight; }
function setTail(node) { const th = $("thread"); const old = th.querySelector(".tail"); if (old) old.remove(); if (node) { node.classList.add("tail"); th.append(node); } }
function typing(text) { const d = el("div", null, "typing"); d.append(el("i"), el("i"), el("i"), text); return d; }

/* ---------- Ansichten ---------- */
function resetThread() { $("thread").replaceChildren(); S.count = 0; S.lastQ = null; S.diffOpen = false; S.conOpen = false; $("p-diff").hidden = true; $("p-console").hidden = true; }
function choose(name) { S.chosen = name; S.follow = null; S.failed = null; resetThread(); $("side").classList.remove("open"); refresh(); $("input").focus(); }
function renderSide(data) {
  const T = S.T, nav = $("sessions");
  $("new").textContent = T.newTask; $("projlbl").textContent = T.project; $("projname").textContent = data.project.name; $("projbtn").title = data.project.path;
  $("ver").textContent = "v" + data.version; $("docs").textContent = T.docs;
  $("docs").href = "https://github.com/gb-web-de/claudegravity-loop/blob/main/docs/" + (S.lang === "en" ? "en" : "de") + "/chat.md";
  if (!data.sessions.length) { nav.replaceChildren(el("p", T.noSessions, "muted")); nav.firstChild.style.padding = "4px 10px"; return; }
  nav.replaceChildren(...data.sessions.map((s) => {
    const b = el("button", null, "sess" + (s.name === S.chosen ? " on" : "")); b.type = "button";
    const t = el("span", null, "t"); t.append(el("span", null, "dot " + (s.running ? "run" : (s.done || s.phase === "completed" ? "ok" : "open"))), s.task || s.name);
    const n = s.name, when = /^\d{8}_\d{6}/.test(n) ? n.slice(6, 8) + "." + n.slice(4, 6) + ". " + n.slice(9, 11) + ":" + n.slice(11, 13) : n;
    b.append(t, el("span", when + " · " + (s.running ? T.running : (s.done || s.phase === "completed" ? T.done : (T.phases[s.phase] || s.phase || "–"))), "s"));
    b.addEventListener("click", () => choose(s.name));
    return b;
  }));
}
function renderWelcome(data) {
  const T = S.T, w = el("div", null, "welcome");
  w.append(el("h1", T.welcome), el("p", T.welcomeSub, "muted"));
  const steps = el("div", null, "steps"); T.steps.forEach((s) => { const d = el("div", null, "step"); d.append(el("b", s[0]), s[1]); steps.append(d); }); w.append(steps);
  const chips = el("div", null, "chips");
  if (!data.setup) chips.append(el("span", T.detecting, "chip off"));
  else data.setup.agents.forEach((a) => chips.append(el("span", (a.ready ? "✓ " : "✗ ") + a.name + (a.ready ? "" : " · " + a.status), "chip " + (a.ready ? "ok" : "off"))));
  w.append(chips);
  const ready = data.setup ? data.setup.agents.filter((a) => a.ready).length : null;
  if (ready === 0) w.append(el("div", T.noAgents, "note"));
  else if (ready === 1) w.append(el("div", T.oneAgent, "note"));
  if (data.project.home) w.append(el("div", T.homeProject, "note"));
  else if (!data.project.git) w.append(el("div", T.noGit, "note"));
  return w;
}
function pausedBy(reason) { return /Strg\+C|Ctrl\+C/.test(reason || ""); }
function renderHeader(s) {
  const T = S.T, badge = $("badge");
  if (!s) { $("task").textContent = S.follow ? (S.followTask || "") : T.welcome; badge.hidden = true; $("activity").textContent = ""; ["stop", "resume", "details"].forEach((id) => { $(id).hidden = true; }); return; }
  $("task").textContent = s.task.split("\n")[0]; $("task").title = s.task;
  badge.hidden = false;
  if (s.running && s.question) { badge.textContent = T.waitingYou; badge.className = "badge warn"; }
  else if (s.running) { badge.textContent = T.running + " · " + (T.phases[s.phase] || s.phase || "–"); badge.className = "badge run"; }
  else if (s.done || s.phase === "completed") { badge.textContent = T.done; badge.className = "badge ok"; }
  else { badge.textContent = (T.phases[s.phase] || s.phase || "–") + " · " + (pausedBy(s.abort_reason) ? T.paused : (s.abort_reason ? T.ended : T.idle)); badge.className = s.abort_reason && !pausedBy(s.abort_reason) ? "badge bad" : "badge"; }
  const a = s.running ? s.activity : null;
  $("activity").textContent = a ? (a.kind === "proof" ? T.proofRuns + since(a.since) : (T.icons[a.role] || "") + " " + (T.roles[a.role] || a.role || "") + T.works + since(a.since)) : "";
  $("stop").hidden = !(s.running && s.owned); $("stop").textContent = s.stopping ? T.stopping : T.stop;
  $("resume").hidden = !s.can_resume; $("resume").textContent = T.resume;
  $("details").hidden = false; $("details").textContent = T.details + (s.files.length ? " (" + s.files.length + ")" : "");
}
function renderQuestion(s) {
  const T = S.T, box = $("question"), q = s && s.running ? s.question : null;
  const key = q ? (q.id || q.since) + "|" + q.kind : null;
  document.title = (q ? "● " : "") + "ClaudeGravity Chat";
  if (key === S.lastQ) return;
  S.lastQ = key; box.replaceChildren();
  if (!q) return;
  const card = el("div", null, "qcard");
  if (!s.owned) { card.append(el("div", T.waitingTerminal + q.prompt)); box.append(card); return; }
  card.append(el("h3", T.kinds[q.kind] || q.prompt));
  if (T.kinds[q.kind] && ["permission", "resume", "minutes"].includes(q.kind)) card.append(el("div", q.prompt, "muted"));
  const btns = el("div", null, "btns");
  (q.choices || []).forEach((c, i) => {
    const b = el("button", c.label, i === 0 ? "primary" : (/^(5|3|n)$/.test(c.value) && q.kind !== "plan" ? "" : "")); b.type = "button";
    b.addEventListener("click", () => answer(c.value));
    btns.append(b);
  });
  if (btns.children.length) card.append(btns);
  if (q.text && (q.kind === "plan" || q.kind === "plan_open")) card.append(el("div", T.hintPlan, "hint"));
  box.append(card);
  if (atBottom()) toBottom();
}
function renderComposer(data) {
  const T = S.T, s = data.session, input = $("input"), q = s && s.running ? s.question : null;
  const fresh = !s && !S.follow, answering = !!(q && s.owned && q.text), canStart = !s || !s.running;
  $("options").hidden = !(fresh || (s && !s.running));
  $("send").textContent = answering ? T.answer : T.send;
  let ph, hint = "";
  if (answering) { ph = (q.kind === "plan" || q.kind === "plan_open" || q.kind === "plan_feedback") ? T.phPlan : T.phAnswer; }
  else if (S.follow && !s) ph = T.phBusy;
  else if (s && s.running) ph = (q && !s.owned) ? T.phTerminal : T.phBusy;
  else if (s) { ph = T.phNext; hint = s.can_resume ? T.nextHint : ""; }
  else { ph = T.phNew; hint = T.hintNew; }
  input.placeholder = ph; $("hint").textContent = hint;
  const off = !(answering || (canStart && !S.follow)) || S.busy;
  input.disabled = off; $("send").disabled = off;
  if (!S.optsReady) setupOptions(data);
  if (data.project.proof && !$("o-proof").dataset.touched && $("o-proof").dataset.project !== data.project.path) { $("o-proof").value = data.project.proof; $("o-proof").dataset.project = data.project.path; }
}
function setupOptions(data) {
  const T = S.T; S.optsReady = true;
  $("optsum").textContent = T.options; $("l-strategy").textContent = T.strategy; $("l-template").textContent = T.template; $("l-proof").textContent = T.proof; $("l-extra").textContent = T.extra;
  $("l-yolo").textContent = T.yolo; $("l-plan_auto").textContent = T.planAuto; $("l-ask").textContent = T.ask; $("l-merge").textContent = T.merge;
  const st = $("o-strategy"); st.replaceChildren(new Option(T.auto, ""), ...data.strategies.map((k) => new Option(T.strategies[k] || k, k)));
  const tp = $("o-template"); tp.replaceChildren(...[""].concat(data.templates).map((k) => new Option(T.templates[k] || k, k)));
  let saved = {}; try { saved = JSON.parse(store.get("options") || "{}"); } catch (e) { saved = {}; }
  if (saved.strategy) st.value = saved.strategy; if (saved.template) tp.value = saved.template; if (saved.extra) $("o-extra").value = saved.extra;
  ["yolo", "plan_auto", "ask", "merge"].forEach((k) => { if (typeof saved[k] === "boolean") $("o-" + k).checked = saved[k]; });
  $("pick-title").textContent = T.pickTitle; $("pick-help").textContent = T.pickHelp; $("pick-ok").textContent = T.pickOk; $("pick-cancel").textContent = T.cancel;
}
function options() {
  const o = { strategy: $("o-strategy").value, template: $("o-template").value, proof: $("o-proof").value.trim(), extra: $("o-extra").value.trim() };
  ["yolo", "plan_auto", "ask", "merge"].forEach((k) => { o[k] = $("o-" + k).checked; });
  store.set("options", JSON.stringify({ strategy: o.strategy, template: o.template, extra: o.extra, yolo: o.yolo, plan_auto: o.plan_auto, ask: o.ask, merge: o.merge }));
  return o;
}
function renderPanel(s) {
  const T = S.T; if ($("panel").hidden || !s) return;
  const kv = (k, v) => { const d = el("div", null, "kv"); d.append(el("b", k), el("span", v)); return d; };
  $("p-title").textContent = T.details;
  const facts = [kv(T.phase, T.phases[s.phase] || s.phase || "–"), kv(T.round, s.iteration ? s.iteration + (s.max_iterations ? " / " + s.max_iterations : "") : "–"), kv(T.tokens, num(s.tokens)), kv(T.cost, s.cost_usd ? Number(s.cost_usd).toFixed(2) + " USD" : "–")];
  if (s.stages) facts.splice(2, 0, kv(T.stage, s.stage + " / " + s.stages));
  if (s.strategy) facts.push(kv(T.strategyK, s.strategy)); if (s.branch) facts.push(kv(T.branch, s.branch)); if (s.proof) facts.push(kv(T.proofK, s.proof));
  $("p-facts").replaceChildren(...facts);
  $("p-hfiles").textContent = T.changed + " (" + s.files.length + ")"; $("p-diffbtn").textContent = S.diffOpen ? T.hideDiff : T.showDiff;
  $("p-files").replaceChildren(...(s.files.length ? s.files.map((f) => { const tr = el("tr"), c = el("td", null, "num");
    if (f.new) c.append(el("span", T.newFile, "plus")); else c.append(el("span", f.added === null ? "" : "+" + f.added, "plus"), " ", el("span", f.removed === null ? "" : "−" + f.removed, "minus"));
    tr.append(el("td", f.path), c); return tr; }) : [(() => { const tr = el("tr"); tr.append(el("td", T.noFiles, "muted")); return tr; })()]));
  $("p-hroles").textContent = T.rolesT; $("p-th-role").textContent = T.role; $("p-th-agent").textContent = T.agent; $("p-th-tokens").textContent = T.tokens;
  $("p-roles").replaceChildren(...s.roles.map((r) => { const tr = el("tr"); tr.append(el("td", (r.role || "").replace(/\s*\(.*\)\s*$/, "")), el("td", (r.agent || "") + (r.model ? " · " + r.model : "")), el("td", num(r.tokens), "num"), el("td", r.cost_usd ? Number(r.cost_usd).toFixed(2) : "–", "num")); return tr; }));
  $("p-log").textContent = s.log.join("\n");
  $("p-hconsole").textContent = T.console; $("p-conbtn").textContent = S.conOpen ? T.hideConsole : T.showConsole;
  $("p-reportwrap").hidden = !s.report; $("p-hreport").textContent = T.report + (s.done ? " (.done)" : " (AUDIT.md)"); $("p-report").textContent = s.report;
}
function loadDiff() {
  if (!S.chosen) return;
  getJSON("/api/diff", { project: S.project, session: S.chosen }).then((d) => {
    const pre = $("p-diff"), T = S.T; pre.hidden = false;
    const lines = (d.diff || "").split("\n");
    pre.replaceChildren(...(d.diff ? lines.map((line) => el("span", line + "\n", line.startsWith("+") && !line.startsWith("+++") ? "a" : (line.startsWith("-") && !line.startsWith("---") ? "d" : (line.startsWith("@@") || line.startsWith("diff ") ? "h" : "")))) : [el("span", T.emptyDiff, "h")]));
    if (d.truncated) pre.append(el("span", T.truncated, "h"));
  }).catch(() => {});
}
function loadConsole() {
  if (!S.chosen) return;
  getJSON("/api/output", { project: S.project, session: S.chosen }).then((d) => { const pre = $("p-console"); pre.hidden = false; pre.textContent = d.owned ? d.output : S.T.noConsole; pre.scrollTop = pre.scrollHeight; }).catch(() => {});
}
function openPanel(withDiff) { $("panel").hidden = false; if (S.data) renderPanel(S.data.session); if (withDiff) { S.diffOpen = true; $("p-diffbtn").textContent = S.T.hideDiff; loadDiff(); } }

function apply(data) {
  S.data = data; S.lang = data.lang === "en" ? "en" : "de"; S.T = L[S.lang]; S.now = data.now; document.documentElement.lang = S.lang;
  if (!S.project) { S.project = data.project.path; }
  const p = data.pending;
  if (S.follow && p && p.run === S.follow && p.session) { S.chosen = p.session; S.follow = null; resetThread(); return true; }
  if (S.first) {
    S.first = false;
    const running = data.sessions.find((x) => x.running);
    if (!S.chosen && running) { S.chosen = running.name; renderSide(data); return true; }
  }
  renderSide(data);
  const s = data.session, th = $("thread"), stick = atBottom();
  renderHeader(s);
  if (s) {
    if (S.count === 0) th.replaceChildren();
    s.messages.forEach((msg) => { const node = render(msg); if (node) { const tail = th.querySelector(".tail"); if (tail) th.insertBefore(node, tail); else th.append(node); } });
    S.count = s.total;
    const a = s.running && !s.question ? s.activity : null;
    setTail(a ? typing(a.kind === "proof" ? S.T.proofRuns + since(a.since) : (S.T.icons[a.role] || "") + " " + (S.T.roles[a.role] || "") + S.T.works + since(a.since)) : null);
  } else if (S.follow) {
    th.replaceChildren(userMsg(S.T.you + " · " + S.T.task, S.followTask || ""));
    if (p && p.run === S.follow && !p.alive) {
      S.failed = { task: S.followTask || "", code: p.code, output: p.output || "" }; S.follow = null; th.append(failCard());
    } else th.append(typing(S.T.starting));
  } else if (S.failed) { th.replaceChildren(userMsg(S.T.you + " · " + S.T.task, S.failed.task), failCard()); }
  else { th.replaceChildren(renderWelcome(data)); }
  renderQuestion(s); renderComposer(data); renderPanel(s);
  const hash = S.chosen ? "#" + encodeURIComponent(S.chosen) : "";
  if (location.hash !== hash) history.replaceState(null, "", location.pathname + location.search + hash);
  if (stick) toBottom();
  if (S.diffOpen && !$("panel").hidden && s && s.running) loadDiff();
  if (S.conOpen && !$("panel").hidden && s && s.running) loadConsole();
}
function failCard() {
  const d = el("div", null, "endcard bad"); d.append(el("h3", S.T.startFailed), el("div", S.T.exitCode + ": " + S.failed.code, "muted"));
  if (S.failed.output) d.append(el("pre", S.failed.output, "wrap"));
  return d;
}
function schedule(ms) { clearTimeout(S.timer); S.timer = setTimeout(refresh, ms); }
function refresh() {
  const args = { project: S.project, after: String(S.count) }; if (S.chosen) args.session = S.chosen;
  getJSON("/api/state", args).then((d) => {
    if (S.chosen && !d.session && !d.sessions.some((x) => x.name === S.chosen)) { S.chosen = null; resetThread(); }
    const again = apply(d);
    const live = S.follow || (d.session && d.session.running);
    schedule(again ? 50 : (live ? 1500 : 4000));
  }).catch((e) => {
    if (String(e.message) === "400" && S.project) { S.project = ""; store.set("project", ""); schedule(100); return; }
    $("hint").textContent = S.T.offline; $("hint").className = "err"; schedule(4000);
  }).then(() => { if (S.data && $("hint").className === "err" && $("hint").textContent !== S.T.offline) $("hint").className = "muted"; });
}

/* ---------- Aktionen ---------- */
function busy(on) { S.busy = on; $("send").disabled = on; }
function startTask(text) {
  busy(true);
  post("/api/start", Object.assign({ task: text }, options())).then((d) => {
    S.follow = d.run; S.followTask = text; S.failed = null; S.chosen = null; resetThread(); $("input").value = ""; grow(); schedule(100);
  }).catch((e) => toast(S.T.failed + e.message)).then(() => busy(false));
}
function answer(value) {
  const s = S.data && S.data.session; if (!s) return;
  busy(true); $("question").replaceChildren(); S.lastQ = "sent";
  post("/api/answer", { session: s.name, value }).then(() => { $("input").value = ""; grow(); schedule(150); })
    .catch((e) => { S.lastQ = null; toast(S.T.failed + e.message); }).then(() => busy(false));
}
function send() {
  const text = $("input").value.trim(); if (!text || S.busy) return;
  const s = S.data && S.data.session, q = s && s.running ? s.question : null;
  if (q && s.owned && q.text) answer(text);
  else if (!s || !s.running) startTask(text);
}
function grow() { const i = $("input"); i.style.height = "auto"; i.style.height = Math.min(200, i.scrollHeight + 2) + "px"; }
$("send").addEventListener("click", send);
$("input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
$("input").addEventListener("input", grow);
$("o-proof").addEventListener("input", () => { $("o-proof").dataset.touched = "1"; });
$("new").addEventListener("click", () => choose(null));
$("menu").addEventListener("click", () => $("side").classList.toggle("open"));
$("main").addEventListener("click", (e) => { if (!e.target.closest("#menu")) $("side").classList.remove("open"); });
$("stop").addEventListener("click", () => { const s = S.data && S.data.session; if (s) post("/api/stop", { session: s.name }).then(() => schedule(200)).catch((e) => toast(S.T.failed + e.message)); });
$("resume").addEventListener("click", () => { const s = S.data && S.data.session; if (!s) return; $("resume").disabled = true;
  post("/api/resume", { session: s.name }).then(() => { resetThread(); schedule(300); }).catch((e) => toast(S.T.failed + e.message)).then(() => { $("resume").disabled = false; }); });
$("details").addEventListener("click", () => { if ($("panel").hidden) openPanel(false); else $("panel").hidden = true; });
$("p-close").addEventListener("click", () => { $("panel").hidden = true; });
$("p-diffbtn").addEventListener("click", () => { S.diffOpen = !S.diffOpen; $("p-diffbtn").textContent = S.diffOpen ? S.T.hideDiff : S.T.showDiff; if (S.diffOpen) loadDiff(); else $("p-diff").hidden = true; });
$("p-conbtn").addEventListener("click", () => { S.conOpen = !S.conOpen; $("p-conbtn").textContent = S.conOpen ? S.T.hideConsole : S.T.showConsole; if (S.conOpen) loadConsole(); else $("p-console").hidden = true; });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("panel").hidden) $("panel").hidden = true; });

/* ---------- Ordnerauswahl ---------- */
function browse(path) {
  getJSON("/api/dirs", path ? { path } : {}).then((d) => {
    const T = S.T, list = $("picklist"); $("pickpath").value = d.path;
    const rows = [];
    if (d.parent) { const up = el("button", T.up); up.type = "button"; up.addEventListener("click", () => browse(d.parent)); rows.push(up); }
    d.dirs.forEach((name) => { const b = el("button", "📁 " + name); b.type = "button"; b.addEventListener("click", () => browse(d.path.replace(/[\\/]$/, "") + (d.path.includes("\\") ? "\\" : "/") + name)); rows.push(b); });
    if (!d.dirs.length) rows.push(el("p", T.noSub, "muted"));
    list.replaceChildren(...rows); list.scrollTop = 0;
    $("pick-info").textContent = [d.git ? T.pickGit : "", d.sessions ? T.pickSessions : ""].filter(Boolean).join(" · ");
  }).catch(() => {});
}
function setProject(path) {
  post("/api/project", { project: path }).then((d) => {
    S.project = d.project.path; store.set("project", S.project); S.chosen = null; S.follow = null; S.failed = null; S.first = true; resetThread(); $("picker").close(); schedule(50);
  }).catch((e) => toast(S.T.failed + e.message));
}
$("projbtn").addEventListener("click", () => {
  const recent = $("pick-recent"); recent.replaceChildren(...((S.data && S.data.recent) || []).map((p) => { const b = el("button", p.split(/[\\/]/).filter(Boolean).pop() || p, "chip"); b.type = "button"; b.title = p; b.addEventListener("click", () => setProject(p)); return b; }));
  $("picker").showModal(); browse(S.project);
});
$("pickpath").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); browse($("pickpath").value.trim()); } });
$("pick-ok").addEventListener("click", () => setProject($("pickpath").value.trim()));
$("pick-cancel").addEventListener("click", () => $("picker").close());
refresh();
</script>
</body>
</html>
"""
