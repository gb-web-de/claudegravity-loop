"""KI-Backends: CLIs (claude, agy, gemini, codex, copilot, ollama) und OpenAI-kompatible Endpunkte, Erkennung."""

import contextlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import uuid
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .common import (
    CLOUD_TIMEOUT,
    LOCAL_TIMEOUT,
    RateLimitError,
    SETTINGS,
    extract_flag_value,
    extract_reset_time,
    is_rate_limit,
    parse_reset_seconds,
    say,
)
from .i18n import MODEL_DIRECTIVE
from .safety import redact_secrets
from . import sandbox
from .metrics import SessionMetrics


class AgentCLI:
    """Ein Backend in einer Rolle: Name, Programm oder Endpunkt, Aufruffunktion, Modell, Effort und Verbrauch."""

    def __init__(
        self,
        name: str,
        binary: str,
        run_fn,
        metrics_tracker: SessionMetrics | None = None,
        role: str = "Architekt",
        model: str | None = None,
        effort: str | None = None,
        local: bool = False,
    ):
        self.name = name
        self.binary = binary
        self.run_fn = run_fn
        self.metrics_tracker = metrics_tracker
        self.role = role
        self.model = model
        self.effort = effort
        self.local = local
        self.reported_model: str | None = None
        self.session_id: str | None = None
        self.requested_model: str | None = None

    def run(self, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> str:
        """Prompt senden (bei Cloud-Backends mit Datenschutzschild), Antwort liefern und Verbrauch in die Kennzahlen buchen."""
        if self.requested_model is None:
            self.requested_model = extract_flag_value(extra_flags, "--model") or self.model or DEFAULT_MODEL_LABEL
        if SETTINGS.shield and not self.local:
            prompt, found = redact_secrets(prompt)
            if found:
                say(f"🛡️  Datenschutzschild: {', '.join(found)} vor dem Versand an {self.name} geschwärzt.")
        if SETTINGS.lang == "en":
            prompt += MODEL_DIRECTIVE
        text, metrics = self.run_fn(self.binary, prompt, cwd, extra_flags)
        if metrics:
            if metrics.get("reported_model"):
                self.reported_model = metrics["reported_model"]
            if metrics.get("session_id"):
                self.session_id = metrics["session_id"]
            used_model = metrics.get("model") or extract_flag_value(extra_flags, "--model") or self.model
            used_effort = metrics.get("effort") or extract_flag_value(extra_flags, "--effort") or self.effort
            # self.model und self.effort bleiben die gewählten Werte: Gemeldete Namen oder Anzeigetexte
            # wie „high (123 thinking tokens)“ dürfen nicht als --model/--effort in spätere Aufrufe wandern.
            if self.metrics_tracker:
                self.metrics_tracker.add(
                    agent_name=self.name,
                    input_tokens=metrics.get("input_tokens", 0),
                    output_tokens=metrics.get("output_tokens", 0),
                    total_tokens=metrics.get("total_tokens", 0),
                    cost_usd=metrics.get("cost_usd", 0.0),
                    role=self.role,
                    model=used_model,
                    effort=used_effort,
                )
        elif self.metrics_tracker:
            # Kein Verbrauch gemeldet: Aufruf trotzdem zählen (Runden-Kennzahlen)
            self.metrics_tracker.add(agent_name=self.name, role=self.role, model=self.model, effort=self.effort)
        return text


def create_agent(
    binary: str,
    agents: dict[str, AgentCLI],
    role: str = "Architekt",
    model: str | None = None,
    effort: str | None = None,
    metrics_tracker: SessionMetrics | None = None,
) -> AgentCLI:
    """Neue Instanz eines erkannten Backends für eine Rolle; wirft ValueError, wenn es nicht verfügbar ist."""
    base = agents.get(binary)
    if not base:
        # Rollen merken sich das Programm (z. B. `gh` für Copilot); der Schlüssel in `agents` kann anders heißen
        base = next((a for a in agents.values() if a.binary == binary), None)
    if not base:
        raise ValueError(f"Agent-CLI '{binary}' ist nicht verfügbar.")
    return AgentCLI(
        name=base.name,
        binary=base.binary,
        run_fn=base.run_fn,
        metrics_tracker=metrics_tracker,
        role=role,
        model=model,
        effort=effort,
        local=base.local,
    )


EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
# CLIs, die einen Effort-Wert verstehen; bei allen anderen steht er nur im Audit
EFFORT_BINARIES = ("agy", "codex", "copilot", "gh")
DEFAULT_MODEL_LABEL = "CLI-Default"


# Anzeigetexte für „nichts gewählt“; sie gehen nie als Flag an eine CLI
_PLACEHOLDER_MARKERS = ("cli-default", "cli default", "(standard)", "thinking tokens", "nur für agy/codex")
AGY_EFFORT_NAMES = {"low": "Low", "medium": "Medium", "high": "High", "xhigh": "High", "max": "High"}


def is_placeholder_value(value: str | None) -> bool:
    """True für leere Werte und Anzeigetexte wie „CLI-Default“, die kein echtes Modell oder Effort sind."""
    if value is None or not str(value).strip():
        return True
    text = str(value).strip().lower()
    return text in ("default", DEFAULT_MODEL_LABEL.lower()) or any(m in text for m in _PLACEHOLDER_MARKERS)


def agy_model_name(model: str, effort: str | None = None) -> str:
    """Modellname im Format der Antigravity CLI ab 1.4, z.B. gemini-3.8-flash + low → „Gemini 3.8 Flash (Low)“.

    Namen mit Großbuchstaben oder Leerzeichen gelten als schon passend und bleiben unverändert."""
    model = model.strip()
    if model != model.lower() or " " in model:
        return model
    words = []
    if model.startswith("gpt-oss"):
        words.append("GPT-OSS")
        model = model[len("gpt-oss") :]
    for part in model.split("-"):
        if not part:
            continue
        if part == "gpt" or (any(c.isdigit() for c in part) and any(c.isalpha() for c in part)):
            words.append(part.upper())
        else:
            words.append(part[:1].upper() + part[1:])
    level = AGY_EFFORT_NAMES.get((effort or "").strip().lower(), "Medium")
    return f"{' '.join(words)} ({level})"


def model_flags(binary: str, model: str | None, effort: str | None) -> list[str]:
    """--model/--effort für eine CLI; lässt Platzhalter („CLI-Default“) und leere Werte weg.

    Bei agy steckt der Effort im Modellnamen („Gemini 3.8 Flash (High)“), --effort kommt dann nicht dazu."""
    flags: list[str] = []
    has_model = not is_placeholder_value(model)
    has_effort = not is_placeholder_value(effort) and binary in EFFORT_BINARIES
    if has_model:
        name = agy_model_name(str(model), effort if has_effort else None) if binary == "agy" else str(model).strip()
        flags += ["--model", name]
    if has_effort and not (binary == "agy" and has_model):
        flags += ["--effort", str(effort).strip()]
    return flags


def effort_label(binary: str, effort: str | None) -> str | None:
    """Effort für die Anzeige; markiert Stufen, die nur an agy, codex und copilot übergeben werden."""
    if not effort:
        return None
    if effort in EFFORT_LEVELS and binary not in EFFORT_BINARIES:
        return f"{effort} (nur für agy/codex/copilot wirksam)"
    return effort


def describe_agent(agent: "AgentCLI") -> str:
    """Kurzbeschreibung für Shell-Ausgaben: Provider, Modell und Effort, wie sie tatsächlich gewählt sind."""
    desc = agent.name
    if agent.model:
        desc += f" (`{agent.model}`)"
    effort = effort_label(agent.binary, agent.effort)
    if effort:
        desc += f" [Effort: {effort}]"
    return desc


NPM_SHIM_TARGET = re.compile(r'"%dp0%\\([^"]+)"\s+%\*')


def unwrap_npm_cmd_shim(shim_path: Path) -> list[str] | None:
    """Liest einen npm-.cmd-Shim (z.B. claude.cmd) und liefert den direkten Aufruf ohne cmd.exe.

    So landen Prompts nie in der cmd.exe-Kommandozeile, wo Zeilenumbrüche den Aufruf
    abschneiden und Zeichen wie & | % " als Befehle interpretiert würden.
    """
    try:
        content = shim_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = NPM_SHIM_TARGET.search(content)
    if not m:
        return None
    target = shim_path.parent / m.group(1).replace("\\", "/")
    if target.suffix.lower() in (".js", ".cjs", ".mjs"):
        local_node = shim_path.parent / "node.exe"
        node = str(local_node) if local_node.exists() else shutil.which("node")
        if not node:
            return None
        return [node, str(target)]
    return [str(target)]


def quote_cmd_arg(arg: str) -> str:
    """Quotet ein Argument für cmd.exe /c (Fallback für .bat/.cmd ohne npm-Shim)."""
    if "\n" in arg or "\r" in arg:
        raise ValueError("Mehrzeilige Argumente können nicht sicher über cmd.exe übergeben werden.")
    escaped = arg.replace('"', '""').replace("%", "%%cd:~,%")
    trailing = len(escaped) - len(escaped.rstrip("\\"))
    return '"' + escaped + "\\" * trailing + '"'


def build_cli_command(binary: str, args: list[str]) -> tuple[list[str] | str, bool]:
    """Liefert (Befehl, shell) für subprocess.run. cmd.exe wird nur als letzter Ausweg genutzt."""
    resolved = shutil.which(binary) or binary
    if sys.platform != "win32" or not str(resolved).lower().endswith((".cmd", ".bat")):
        return [str(resolved)] + args, False
    direct = unwrap_npm_cmd_shim(Path(resolved))
    if direct:
        return direct + args, False
    return " ".join([quote_cmd_arg(str(resolved))] + [quote_cmd_arg(a) for a in args]), True


CLI_TIMEOUT_DEFAULT = 3600  # Sekunden je CLI-Aufruf; ein Bau-Lauf darf lange dauern, aber nicht ewig hängen


def cli_timeout() -> int | None:
    """Zeitlimit für CLI-Aufrufe in Sekunden aus CLAUDEGRAVITY_CLI_TIMEOUT; 0 bedeutet ohne Limit (None)."""
    raw = os.environ.get("CLAUDEGRAVITY_CLI_TIMEOUT", "")
    value = int(raw) if raw.strip().isdigit() else CLI_TIMEOUT_DEFAULT
    return value or None


def _exec_cli(binary: str, args: list[str], cwd: Path | None = None, stdin: str | None = None) -> str:
    """Startet eine CLI. Prompts gehen über stdin, damit sie weder in der Prozessliste
    auftauchen noch an der Windows-Längengrenze (~32 KB) abgeschnitten werden. Im Bauleiter-Bereich der Sandbox
    (`sandbox.builder_scope`) läuft eine schreibende CLI im Container."""
    scope = sandbox.current_scope()
    try:
        if scope is not None and binary in sandbox.SANDBOX_CLIS:
            cmd, use_shell = sandbox.cli_command(binary, args, scope, cwd), False
        else:
            cmd, use_shell = build_cli_command(binary, args)
    except sandbox.SandboxPathError as ex:
        raise RuntimeError(f"{binary}: {ex}") from ex
    except ValueError as ex:
        raise RuntimeError(f"{binary}: {ex} Installiere die native Version (z.B. {binary}.exe) statt eines .bat-Wrappers.") from ex
    try:
        res = sandbox.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=use_shell,
            timeout=cli_timeout(),
        )
    except subprocess.TimeoutExpired:
        # Kein automatischer Neuversuch: Ein hängender Bau-Lauf würde sonst stundenlang wiederholt.
        raise RuntimeError(
            f"{binary}: CLI-Zeitlimit von {cli_timeout()} s überschritten. "
            f"Mehr Zeit mit CLAUDEGRAVITY_CLI_TIMEOUT=<Sekunden> (0 = ohne Limit)."
        ) from None
    if res.returncode != 0:
        err_msg = res.stderr.strip() or res.stdout.strip() or f"Fehlercode {res.returncode}"
        if is_rate_limit(err_msg):
            r_time = extract_reset_time(err_msg)
            r_secs = parse_reset_seconds(r_time) if r_time else None
            raise RateLimitError(binary, err_msg, r_time, r_secs)
        raise RuntimeError(f"{binary} Fehler (Code {res.returncode}): {err_msg}")
    return res.stdout.strip()


def _exec_claude(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    args = ["-p", "--output-format", "json"]
    if extra_flags:
        for f in extra_flags:
            if f not in ["--output-format", "json", "text"]:
                args.append(f)
    raw = _exec_cli(binary, args, cwd, stdin=prompt)
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise json.JSONDecodeError("kein Objekt", raw, 0)
        if data.get("is_error"):
            err_msg = data.get("result") or data.get("api_error_status") or "Unbekannter Fehler"
            if is_rate_limit(str(err_msg)):
                r_time = extract_reset_time(str(err_msg))
                r_secs = parse_reset_seconds(r_time) if r_time else None
                raise RateLimitError(binary, str(err_msg), r_time, r_secs)
            raise RuntimeError(f"Claude Fehler: {err_msg}")

        text = data.get("result") or ""
        usage = data.get("usage") or {}
        inp = (
            (usage.get("input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
        )
        out = usage.get("output_tokens") or 0
        tot = inp + out
        cost = float(data.get("total_cost_usd") or 0.0)

        model_name = None
        model_usage = data.get("modelUsage") or {}
        if model_usage:
            model_name = list(model_usage.keys())[0]
        if not model_name:
            model_name = extract_flag_value(extra_flags, "--model")
        effort_val = extract_flag_value(extra_flags, "--effort")

        metrics = {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": tot,
            "cost_usd": cost,
            "model": model_name,
            "effort": effort_val,
            "reported_model": next(iter(model_usage), None) if model_usage else None,
            "session_id": data.get("session_id"),
        }
        return text, metrics
    except json.JSONDecodeError:
        return raw, {
            "input_tokens": len(prompt) // 4,
            "output_tokens": len(raw) // 4,
            "total_tokens": (len(prompt) + len(raw)) // 4,
            "cost_usd": 0.0,
            "model": extract_flag_value(extra_flags, "--model"),
            "effort": extract_flag_value(extra_flags, "--effort"),
        }


# Von agy gemeldete Modelle je Programm, damit nach einem Fehlgriff alle weiteren Aufrufe passen
_AGY_AVAILABLE_MODELS: dict[str, list[str]] = {}


def parse_agy_available_models(message: str) -> list[str]:
    """Liest die Liste unter „Available models:“ aus einer Fehlermeldung der Antigravity CLI."""
    lines = message.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("available models"):
            models = []
            for entry in lines[i + 1 :]:
                if not entry.strip() or not entry[:1].isspace():
                    break
                models.append(entry.strip())
            return models
    return []


def _model_key(name: str) -> tuple[str, str]:
    """Vergleichsschlüssel (Basisname ohne Sonderzeichen, Effort-Stufe) für agy-Modellnamen."""
    match = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", name)
    base, level = (match.group(1), match.group(2)) if match else (name, "")
    return re.sub(r"[^a-z0-9]", "", base.lower()), level.strip().lower()


def match_agy_model(requested: str, effort: str | None, available: list[str]) -> str | None:
    """Passender Eintrag aus der agy-Modellliste: gleicher Basisname, bevorzugt gleiche Effort-Stufe, sonst Medium."""
    base, level = _model_key(requested)
    wanted = AGY_EFFORT_NAMES.get((effort or "").strip().lower(), "").lower() or (level if level in ("low", "medium", "high") else "")
    candidates = [m for m in available if _model_key(m)[0] == base]
    for target in (wanted, "medium"):
        for m in candidates:
            if target and _model_key(m)[1] == target:
                return m
    return candidates[0] if candidates else None


def _strip_model_flags(flags: list[str]) -> list[str]:
    """Flag-Liste ohne --model/--effort samt Werten."""
    out: list[str] = []
    skip = False
    for f in flags:
        if skip:
            skip = False
            continue
        if f in ("--model", "--effort"):
            skip = True
            continue
        if f.startswith(("--model=", "--effort=")):
            continue
        out.append(f)
    return out


def _resolve_agy_flags(binary: str, flags: list[str], available: list[str]) -> list[str] | None:
    """Ersetzt ein unbekanntes --model durch den passenden Namen aus der agy-Liste; ohne Treffer gilt der CLI-Default.

    Liefert None, wenn sich nichts ändern würde."""
    requested = extract_flag_value(flags, "--model")
    effort = extract_flag_value(flags, "--effort")
    if requested and requested in available:
        return None
    base = _strip_model_flags(flags)
    match = match_agy_model(requested, effort, available) if requested else None
    if match:
        say(f"ℹ️  agy kennt das Modell „{requested}“ nicht, nehme „{match}“.")
        return base + ["--model", match]
    if requested or effort is not None:
        say(f"⚠️  agy kennt das Modell „{requested}“ nicht, nutze das Standardmodell der CLI. Verfügbar: {', '.join(available)}")
        return base
    return None


AGY_EMPTY_FOLLOWUP = (
    "Dein letzter Zug endete ohne Antworttext, vermutlich weil ein Befehl nicht freigegeben wurde. "
    "Führe keine Befehle mehr aus. Gib jetzt dein vollständiges Ergebnis als Text aus, im verlangten Antwortformat."
)


def _agy_followup_empty(binary: str, conversation_id: str, cwd: Path | None, flags: list[str]) -> tuple[str, dict]:
    """Fragt einmal in derselben agy-Unterhaltung nach, wenn die Antwort leer blieb.

    agy beendet den Zug im Druckmodus ohne Text, sobald ein Befehl (z.B. pytest) ohne Freigabe abgelehnt wird,
    meldet aber trotzdem SUCCESS."""
    say("ℹ️  agy hat ohne Antworttext geendet (abgelehnter Befehl?). Frage einmal in derselben Unterhaltung nach.")
    try:
        raw = _exec_cli(binary, ["-p", AGY_EMPTY_FOLLOWUP, "--output-format", "json", "--conversation", conversation_id, *flags], cwd)
        data = json.loads(raw)
    except (RuntimeError, json.JSONDecodeError) as ex:
        say(f"⚠️  Nachfrage bei agy fehlgeschlagen: {ex}")
        return "", {}
    if not isinstance(data, dict) or data.get("status") == "ERROR":
        return "", {}
    usage = data.get("usage") or {}
    inp, out = usage.get("input_tokens") or 0, usage.get("output_tokens") or 0
    return data.get("response") or "", {"input_tokens": inp, "output_tokens": out, "total_tokens": usage.get("total_tokens") or (inp + out)}


def _exec_agy(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    flags = [f for f in (extra_flags or []) if f not in ["--output-format", "json", "text"]]
    if binary in _AGY_AVAILABLE_MODELS:
        flags = _resolve_agy_flags(binary, flags, _AGY_AVAILABLE_MODELS[binary]) or flags
    try:
        raw = _exec_cli(binary, ["-p", prompt, "--output-format", "json", *flags], cwd)
    except RuntimeError as ex:
        # agy ab 1.4 erwartet Namen wie „Gemini 3.8 Flash (Medium)“ und nennt bei einem Fehlgriff die gültigen
        available = parse_agy_available_models(str(ex))
        retry = _resolve_agy_flags(binary, flags, available) if available else None
        if retry is None:
            raise
        _AGY_AVAILABLE_MODELS[binary] = available
        flags = retry
        raw = _exec_cli(binary, ["-p", prompt, "--output-format", "json", *flags], cwd)
    extra_flags = flags
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise json.JSONDecodeError("kein Objekt", raw, 0)
        if data.get("status") == "ERROR":
            err_msg = data.get("response") or "Unbekannter Fehler"
            if is_rate_limit(str(err_msg)):
                r_time = extract_reset_time(str(err_msg))
                r_secs = parse_reset_seconds(r_time) if r_time else None
                raise RateLimitError(binary, str(err_msg), r_time, r_secs)
            raise RuntimeError(f"Antigravity Fehler: {err_msg}")

        text = data.get("response") or ""
        usage = data.get("usage") or {}
        inp = usage.get("input_tokens") or 0
        out = usage.get("output_tokens") or 0
        tot = usage.get("total_tokens") or (inp + out)
        if not text.strip() and data.get("conversation_id"):
            text, extra = _agy_followup_empty(binary, str(data["conversation_id"]), cwd, extra_flags)
            inp, out = inp + extra.get("input_tokens", 0), out + extra.get("output_tokens", 0)
            tot += extra.get("total_tokens", 0)

        model_name = extract_flag_value(extra_flags, "--model") or data.get("model") or DEFAULT_MODEL_LABEL
        effort_val = extract_flag_value(extra_flags, "--effort")
        if not effort_val and (usage.get("thinking_tokens") or 0) > 0:
            effort_val = f"high ({usage['thinking_tokens']} thinking tokens)"

        metrics = {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": tot,
            "cost_usd": 0.0,
            "model": model_name,
            "reported_model": data.get("model") or extract_flag_value(extra_flags, "--model"),
            "effort": effort_val,
        }
        if data.get("conversation_id"):
            metrics["session_id"] = str(data["conversation_id"])
        return text, metrics
    except json.JSONDecodeError:
        model_fallback = extract_flag_value(extra_flags, "--model") or DEFAULT_MODEL_LABEL
        return raw, {
            "input_tokens": len(prompt) // 4,
            "output_tokens": len(raw) // 4,
            "total_tokens": (len(prompt) + len(raw)) // 4,
            "cost_usd": 0.0,
            "model": model_fallback,
            "reported_model": extract_flag_value(extra_flags, "--model"),
            "effort": extract_flag_value(extra_flags, "--effort"),
        }


def _exec_gemini(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    # Ohne Terminal an stdin läuft die Gemini CLI nicht-interaktiv und liest den Prompt von dort.
    args = list(extra_flags or [])
    raw = _exec_cli(binary, args, cwd, stdin=prompt)
    return raw, {
        "input_tokens": len(prompt) // 4,
        "output_tokens": len(raw) // 4,
        "total_tokens": (len(prompt) + len(raw)) // 4,
        "cost_usd": 0.0,
    }


CODEX_EFFORTS = {"low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh", "max": "xhigh"}


def build_codex_args(extra_flags: list[str] | None) -> list[str]:
    """Baut `codex exec`-Argumente: Sandbox aus `-s`, Modell und Effort, Prompt über stdin (`-`).
    Mit `--resume <id>` setzt `codex exec resume <id>` eine frühere Sitzung fort."""
    sandbox = extract_flag_value(extra_flags, "-s") or "read-only"
    args = ["exec", "-s", sandbox, "--json"]
    model = extract_flag_value(extra_flags, "--model")
    if model:
        args += ["-m", model]
    effort = extract_flag_value(extra_flags, "--effort")
    if effort and effort.split()[0] in CODEX_EFFORTS:
        args += ["-c", f'model_reasoning_effort="{CODEX_EFFORTS[effort.split()[0]]}"']
    resume_id = extract_flag_value(extra_flags, "--resume")
    if resume_id:
        args += ["resume", resume_id]
    return args + ["-"]


def codex_thread_id(raw: str) -> str | None:
    """Sitzungs-ID aus dem Ereignis `thread.started` von `codex exec --json` (für `codex exec resume`)."""
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "thread.started" and event.get("thread_id"):
            return str(event["thread_id"])
    return None


def parse_codex_events(raw: str) -> tuple[str | None, dict, str | None]:
    """Liest die JSONL-Ereignisse von `codex exec --json`: (Antwort, Usage, Fehler)."""
    text, usage, error = None, {}, None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        item = event.get("item") or {}
        if etype == "item.completed" and item.get("type") == "agent_message":
            text = item.get("text", text)
        elif etype == "turn.completed":
            usage = event.get("usage") or usage
        elif etype == "turn.failed":
            error = (event.get("error") or {}).get("message") or "turn.failed"
        elif etype == "error":
            error = event.get("message") or "error"
    return text, usage, error


def _exec_codex(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    raw = _exec_cli(binary, build_codex_args(extra_flags), cwd, stdin=prompt)
    text, usage, error = parse_codex_events(raw)
    if error and not text:
        if is_rate_limit(error):
            r_time = extract_reset_time(error)
            raise RateLimitError(binary, error, r_time, parse_reset_seconds(r_time) if r_time else None)
        raise RuntimeError(f"Codex Fehler: {error}")
    if text is None:
        text = raw
    inp = usage.get("input_tokens") or len(prompt) // 4
    out = usage.get("output_tokens") or len(text) // 4
    return text, {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "cost_usd": 0.0,
        "model": extract_flag_value(extra_flags, "--model"),
        "effort": extract_flag_value(extra_flags, "--effort"),
        "session_id": codex_thread_id(raw),
    }


COPILOT_BINARIES = ("copilot", "gh")


def build_copilot_args(binary: str, extra_flags: list[str] | None) -> tuple[list[str], str]:
    """Baut die Argumente für die Copilot CLI im Skriptmodus (Prompt über stdin, nur die Antwort mit `-s`).

    Rechte, Modell und `--reasoning-effort` kommen aus den Flags. Ohne `--resume <id>` vergibt der Loop selbst
    eine Sitzungs-ID (`--session-id`), damit spätere Runden die Sitzung fortsetzen können. Liefert (Argumente, ID).
    Über `gh` läuft dieselbe CLI als `gh copilot -- <argumente>`."""
    flags = list(extra_flags or [])
    resume_id = extract_flag_value(flags, "--resume")
    model = extract_flag_value(flags, "--model")
    effort = extract_flag_value(flags, "--effort")
    rest: list[str] = []
    skip = False
    for i, flag in enumerate(flags):
        if skip:
            skip = False
            continue
        if flag in ("--resume", "--model", "--effort") and i + 1 < len(flags):
            skip = True
            continue
        rest.append(flag)
    session_id = resume_id or str(uuid.uuid4())
    args = ["-s", f"--resume={session_id}"] if resume_id else ["-s", "--session-id", session_id]
    if model:
        args += ["--model", model]
    if effort and effort.split()[0] in EFFORT_LEVELS:
        args += ["--reasoning-effort", effort.split()[0]]
    args += rest
    return (["copilot", "--"] + args if binary == "gh" else args), session_id


def _exec_copilot(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    args, session_id = build_copilot_args(binary, extra_flags)
    raw = _exec_cli(binary, args, cwd, stdin=prompt)
    if raw.lstrip().startswith(("Error:", "! ")) and len(raw) < 2000:
        # Die CLI meldet Anmelde- und Installationsfehler teils mit Rückgabe 0 auf stdout
        if is_rate_limit(raw):
            r_time = extract_reset_time(raw)
            raise RateLimitError(binary, raw, r_time, parse_reset_seconds(r_time) if r_time else None)
        raise RuntimeError(f"Copilot Fehler: {raw.strip().splitlines()[0]}")
    return raw, {
        "input_tokens": len(prompt) // 4,
        "output_tokens": len(raw) // 4,
        "total_tokens": (len(prompt) + len(raw)) // 4,
        "cost_usd": 0.0,
        "model": extract_flag_value(extra_flags, "--model"),
        "effort": extract_flag_value(extra_flags, "--effort"),
        "session_id": session_id,
    }


def _exec_ollama_cli(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
    model = extract_flag_value(extra_flags, "--model") or "qwen2.5-coder:latest"
    raw = _exec_cli(binary, ["run", model], cwd, stdin=prompt)
    return raw, {
        "input_tokens": len(prompt) // 4,
        "output_tokens": len(raw) // 4,
        "total_tokens": (len(prompt) + len(raw)) // 4,
        "cost_usd": 0.0,
        "model": model,
        "effort": "local",
    }


def normalize_endpoint_url(raw_url: str) -> str:
    """Basis-URL eines OpenAI-kompatiblen Servers auf den Pfad /v1/chat/completions ergänzen."""
    url = raw_url.strip().rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


LOCAL_SUFFIXES = (".local", ".lan", ".home", ".home.arpa", ".internal", ".intranet", ".fritz.box", ".localdomain")


def is_private_endpoint(url: str) -> bool:
    """True für localhost, private IPs (192.168.*, 10.*, 172.16-31.*) und Rechnernamen im Heimnetz."""
    raw = url.strip()
    if "://" not in raw:
        raw = "http://" + raw
    try:
        host = (urllib.parse.urlsplit(raw).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    if host == "localhost" or host.endswith(LOCAL_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        pass
    # Name ohne Punkt (z. B. "nas") gibt es nur im eigenen Netz
    return "." not in host


def endpoint_timeout(url: str) -> int:
    """Lokale Modelle laufen oft auf schwacher Hardware und bekommen deshalb mehr Zeit pro Runde."""
    if SETTINGS.endpoint_timeout:
        return SETTINGS.endpoint_timeout
    return LOCAL_TIMEOUT if is_private_endpoint(url) else CLOUD_TIMEOUT


def ollama_base_url() -> str:
    """Adresse des Ollama-Servers aus OLLAMA_HOST (wie bei der Ollama-CLI), sonst localhost:11434."""
    host = os.environ.get("OLLAMA_HOST", "").strip()
    if not host:
        return "http://localhost:11434"
    if "://" not in host:
        host = "http://" + host
    parts = urllib.parse.urlsplit(host)
    name = parts.hostname or "localhost"
    if name in ("0.0.0.0", "::"):
        name = "localhost"
    if ":" in name:
        name = f"[{name}]"
    return f"{parts.scheme}://{name}:{parts.port or 11434}"


# Bevorzugte Ollama-Modelle je Rolle (Familien in Reihenfolge, Name beginnt mit dem Eintrag)
OLLAMA_ROLE_PREFERENCES = {
    "builder": ("qwen3-coder", "qwen2.5-coder", "devstral", "deepseek-coder", "codestral", "codellama", "starcoder"),
    "reviewer": ("gpt-oss", "qwen3:", "deepseek-r1", "qwen3", "gemma3", "llama3", "mistral"),
    "planner": ("qwen3:", "gpt-oss", "qwen3", "deepseek-r1", "qwen2.5-coder", "gemma3", "llama3"),
}
# Größere Modelle passen auf typischen Rechnern (bis ~48 GB) nicht mehr neben ein zweites
OLLAMA_MAX_AUTO_BYTES = 25 * 1024**3


def list_ollama_models(base_url: str, timeout: float = 2.0) -> list[dict]:
    """Installierte Modelle laut /api/tags: [{"name": ..., "size": Bytes}], leer bei Fehlern."""
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, ValueError):
        return []
    models = []
    for m in data.get("models") or []:
        name = m.get("name") or m.get("model")
        if name:
            models.append({"name": name, "size": int(m.get("size") or 0)})
    return models


def pick_ollama_model(models: list[dict], role: str, exclude: set[str] | tuple = ()) -> str | None:
    """Wählt ein installiertes Modell für die Rolle: bevorzugte Familie, darin das größte, das noch passt."""
    candidates = [m for m in models if m["name"] not in exclude and "embed" not in m["name"].lower()]
    if not candidates:
        return None

    def best(group: list[dict]) -> str:
        fitting = [m for m in group if m["size"] <= OLLAMA_MAX_AUTO_BYTES]
        if fitting:
            return max(fitting, key=lambda m: m["size"])["name"]
        return min(group, key=lambda m: m["size"])["name"]

    for prefix in OLLAMA_ROLE_PREFERENCES.get(role, ()):
        group = [m for m in candidates if m["name"].lower().startswith(prefix)]
        if prefix == "qwen3" or prefix == "qwen3:":
            group = [m for m in group if not m["name"].lower().startswith("qwen3-coder")]
        if group:
            return best(group)
    return best(candidates)


def is_endpoint_reachable(url: str, timeout: float = 0.3) -> bool:
    """Kurzer GET-Test; auch 401/403/404/405 zählen als erreichbar, weil dort ein Server antwortet."""
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "ClaudeGravity/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in [200, 401, 403, 404, 405]
    except Exception:
        return False


def _exec_openai_api(
    endpoint_url: str, model: str, prompt: str, api_key: str | None = None, extra_flags: list[str] | None = None
) -> tuple[str, dict]:
    full_url = normalize_endpoint_url(endpoint_url)
    key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("CLAUDEGRAVITY_API_KEY") or ""
    headers = {"Content-Type": "application/json", "User-Agent": "ClaudeGravity/1.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    chosen_model = extract_flag_value(extra_flags, "--model") or model or "default"
    payload = {
        "model": chosen_model,
        "messages": [
            {
                "role": "system",
                "content": "Du bist ein erfahrener Software-Architekt und Senior Developer. Antworte präzise und befolge alle Anweisungen strikt.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(full_url, data=data_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=endpoint_timeout(endpoint_url)) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            try:
                data = json.loads(resp_body)
            except json.JSONDecodeError:
                raise RuntimeError(f"Leere Antwort vom Endpunkt {endpoint_url} (kein JSON): {resp_body[:200]}") from None
            if not isinstance(data, dict):
                raise RuntimeError(f"Leere Antwort vom Endpunkt {endpoint_url}: {resp_body[:200]}")

            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError(f"Leere Antwort vom Endpunkt {endpoint_url}: {resp_body[:200]}")

            text = ((choices[0] or {}).get("message") or {}).get("content") or ""
            usage = data.get("usage") or {}
            inp = usage.get("prompt_tokens") or len(prompt) // 4
            out = usage.get("completion_tokens") or len(text) // 4
            tot = usage.get("total_tokens") or (inp + out)

            is_local_or_private = is_private_endpoint(endpoint_url)
            cost = 0.0 if is_local_or_private else float(usage.get("cost") or data.get("cost_usd") or 0.0)

            metrics = {
                "input_tokens": inp,
                "output_tokens": out,
                "total_tokens": tot,
                "cost_usd": cost,
                "model": chosen_model,
                "effort": extract_flag_value(extra_flags, "--effort") or ("0€ Lokal/Intranet" if is_local_or_private else "API"),
            }
            return text, metrics

    except urllib.error.HTTPError as http_err:
        err_body = ""
        with contextlib.suppress(Exception):
            err_body = http_err.read().decode("utf-8")
        err_msg = f"HTTP {http_err.code} ({http_err.reason}): {err_body}"
        if is_rate_limit(err_msg) or http_err.code == 429:
            r_time = extract_reset_time(err_msg)
            r_secs = parse_reset_seconds(r_time) if r_time else 60
            raise RateLimitError(endpoint_url, err_msg, r_time, r_secs) from http_err
        raise RuntimeError(f"API-Fehler an {endpoint_url}: {err_msg}") from http_err
    except urllib.error.URLError as url_err:
        raise RuntimeError(f"Verbindungsfehler zu {endpoint_url}: {url_err.reason}") from url_err
    except ConnectionError as conn_err:
        raise RuntimeError(f"Verbindungsfehler zu {endpoint_url}: {conn_err}") from conn_err
    except TimeoutError as timeout_err:
        raise RuntimeError(
            f"Zeitüberschreitung nach {endpoint_timeout(endpoint_url)} s bei {endpoint_url}. "
            f"Mehr Zeit pro Runde: --timeout <Sekunden> oder CLAUDEGRAVITY_TIMEOUT."
        ) from timeout_err


def _exec_endpoint_runner(endpoint_url: str, default_model: str, api_key: str | None = None):
    def runner(binary: str, prompt: str, cwd: Path | None = None, extra_flags: list[str] | None = None) -> tuple[str, dict]:
        model = extract_flag_value(extra_flags, "--model") or default_model
        return _exec_openai_api(endpoint_url, model, prompt, api_key=api_key, extra_flags=extra_flags)

    return runner


def detect_installed_agents(
    custom_endpoint: str | None = None, api_key: str | None = None, default_model: str | None = None
) -> dict[str, AgentCLI]:
    """Installierte CLIs im PATH und erreichbare Endpunkte (eigener, Umgebung, localhost) als Backends erkennen."""
    agents = {}

    # 1. Standard-CLIs
    if shutil.which("claude"):
        agents["claude"] = AgentCLI("Claude Code", "claude", _exec_claude)
    if shutil.which("agy"):
        agents["agy"] = AgentCLI("Antigravity (agy)", "agy", _exec_agy)
    if shutil.which("gemini"):
        agents["gemini"] = AgentCLI("Gemini CLI", "gemini", _exec_gemini)
    if shutil.which("codex"):
        agents["codex"] = AgentCLI("Codex CLI", "codex", _exec_codex)
    if shutil.which("copilot"):
        agents["copilot"] = AgentCLI("GitHub Copilot CLI", "copilot", _exec_copilot)
    elif shutil.which("gh") and check_cli_auth("gh")[0]:
        # `gh` allein reicht nicht: `gh copilot` braucht die heruntergeladene Copilot CLI
        agents["copilot"] = AgentCLI("GitHub Copilot CLI (gh)", "gh", _exec_copilot)
    if shutil.which("ollama"):
        agents["ollama-cli"] = AgentCLI("Ollama CLI", "ollama", _exec_ollama_cli, local=True)

    # 2. Lokale Server prüfen (Ollama, auch über OLLAMA_HOST im Heimnetz, LM Studio)
    ollama_url = ollama_base_url()
    if is_endpoint_reachable(ollama_url, timeout=0.3 if "localhost" in ollama_url else 1.5):
        agents["ollama"] = AgentCLI(
            f"Ollama ({'Lokal' if 'localhost' in ollama_url else 'Netzwerk'}: {ollama_url})",
            "ollama",
            _exec_endpoint_runner(ollama_url, default_model or "qwen2.5-coder:latest", api_key),
            local=True,
        )
    if is_endpoint_reachable("http://localhost:1234"):
        agents["lmstudio"] = AgentCLI(
            "LM Studio (Lokal: http://localhost:1234)",
            "lmstudio",
            _exec_endpoint_runner("http://localhost:1234", default_model or "default", api_key),
            local=True,
        )

    # 3. Benutzerdefiniertes Netzwerk / Firmen-Server / Env-Var
    env_endpoint = (
        custom_endpoint or os.environ.get("CLAUDEGRAVITY_ENDPOINT") or os.environ.get("OPENAI_BASE_URL") or os.environ.get("AI_ENDPOINT")
    )
    if env_endpoint:
        is_local = is_private_endpoint(env_endpoint)
        label = "Netzwerk-Server" if is_local else "KI-Server"
        agents["endpoint"] = AgentCLI(
            f"{label} ({env_endpoint})",
            "endpoint",
            _exec_endpoint_runner(env_endpoint, default_model or "qwen2.5-coder:32b", api_key),
            local=is_local,
        )

    return agents


def check_cli_auth(binary: str) -> tuple[bool, str]:
    """Schnelle Prüfung, ob eine CLI einsatzbereit und angemeldet ist.

    Liefert (is_ready: bool, status_message: str).
    """
    try:
        if binary == "claude":
            res = subprocess.run(["claude", "auth", "status"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0 and '"loggedIn":true' in res.stdout.replace(" ", ""):
                return True, "angemeldet"
            return False, "nicht angemeldet (claude login)"
        elif binary == "gemini":
            res = subprocess.run(["gemini", "-p", "check"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=4.0)
            err_text = (res.stderr + res.stdout).lower()
            if "invalid auth method" in err_text or res.returncode == 41:
                return False, "nicht angemeldet (gemini auth login)"
            if res.returncode == 0:
                return True, "angemeldet"
            msg = (res.stderr or res.stdout).strip().splitlines()[-1] if (res.stderr or res.stdout).strip() else "nicht bereit"
            return False, msg
        elif binary == "gh":
            # `gh copilot` startet die Copilot CLI, meldet eine fehlende CLI aber mit Rückgabe 0
            res = subprocess.run(
                ["gh", "copilot", "--", "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5.0
            )
            text = (res.stderr + res.stdout).lower()
            if res.returncode != 0 or "not installed" in text or "unknown command" in text:
                return False, "Copilot CLI fehlt (npm install -g @github/copilot oder gh copilot)"
            return True, "bereit"
        elif binary == "copilot":
            res = subprocess.run(["copilot", "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0:
                return True, "bereit"
            return False, "nicht installiert (npm install -g @github/copilot, danach copilot login)"
        elif binary == "agy":
            acc_file = Path.home() / ".gemini" / "antigravity" / "google_accounts.json"
            if acc_file.exists():
                return True, "angemeldet"
            res = subprocess.run(["agy", "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2.0)
            return (True, "bereit") if res.returncode == 0 else (False, "nicht bereit")
        elif binary == "codex":
            res = subprocess.run(["codex", "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=2.0)
            return (True, "bereit") if res.returncode == 0 else (False, "nicht bereit")
        elif binary in ("ollama", "ollama-cli"):
            return True, "lokal"
    except (subprocess.TimeoutExpired, OSError, Exception):
        return False, "nicht erreichbar"
    return True, "bereit"
