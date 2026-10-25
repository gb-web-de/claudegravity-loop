"""Englische Ausgabe (--lang en): Katalog, Übersetzung eingesetzter Werte, Hilfe, Fehlercodes und Modell-Hinweis."""

import ast
import contextlib
import io
import re
import string
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import loop  # noqa: E402
from claudegravity import common, i18n  # noqa: E402

UMLAUT = re.compile(r"[äöüßÄÖÜ]")
GERMAN = re.compile(
    r"[äöüßÄÖÜ]|\b(nicht|keine?|und|oder|mit|wird|ist|der|die|das|Bauleiter|Prüfstatiker|Architekt|Abnahme|"
    r"Aufgabe|Sitzung|erledigt|Etappe|Runde|gespeichert|Weiter)\b"
)


@contextlib.contextmanager
def lang(value: str):
    old = common.SETTINGS.lang
    common.SETTINGS.lang = value
    try:
        yield
    finally:
        common.SETTINGS.lang = old


def literal_template(node) -> str | None:
    """Text eines say()/ask()-Arguments als Katalog-Vorlage; None, wenn Teile berechnet werden."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.replace("{", "{{").replace("}", "}}")
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant):
                parts.append(value.value.replace("{", "{{").replace("}", "}}"))
            else:
                parts.append("{}")
        return "".join(parts)
    return None


def sample(template: str) -> str:
    """Vorlage mit Platzhalterwerten füllen (wie eine echte Meldung)."""
    return "X1".join(p.replace("{{", "{").replace("}}", "}") for p in template.split("{}"))


class CatalogTest(unittest.TestCase):
    def test_templates_compile_and_fit(self):
        for german, english in i18n.EN.items():
            fields = [f for _, f, _, _ in string.Formatter().parse(english) if f is not None]
            self.assertLessEqual(len([f for f in fields if f == ""]), german.count("{}"), german)
            self.assertIsNotNone(i18n._compile(german).fullmatch(sample(german)), german)

    def test_english_texts_have_no_umlauts(self):
        texts = list(i18n.EN.values()) + list(i18n.GLOSSARY.values()) + list(i18n.HELP.values()) + list(i18n.PHRASES.values())
        texts += [t for pair in loop.ERROR_CODES_EN.values() for t in pair]
        self.assertEqual([t for t in texts if UMLAUT.search(t)], [])

    def test_every_german_message_has_an_english_entry(self):
        missing = []
        for path in sorted((ROOT / "claudegravity").glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("say", "ask", "tr") and node.args):
                    continue
                template = literal_template(node.args[0])
                if template is None or not GERMAN.search(template.replace("{}", "")):
                    continue
                text = sample(template)
                if i18n.to_english(text) == text:
                    missing.append(f"{path.name}:{node.lineno}: {template!r}")
        self.assertEqual(missing, [], "Neue Meldungen brauchen einen Eintrag in claudegravity/i18n.py (EN)")

    def test_every_help_text_is_translated(self):
        parser = loop.build_parser(True, lang="de")
        missing = [a.help for a in parser._actions if a.help and a.help not in i18n.HELP and GERMAN.search(a.help)]
        missing += [g.title for g in parser._action_groups if g.title not in i18n.HELP and GERMAN.search(g.title)]
        self.assertEqual(missing, [])


class TranslateTest(unittest.TestCase):
    def test_german_stays_unchanged(self):
        text = "🔨 Ausführender Bauleiter: Claude Code"
        self.assertEqual(i18n.translate(text, "de"), text)

    def test_values_are_translated_recursively(self):
        line = "📍 Bau-Runde 2/10 · Etappe 1/3 · 🔨 Bauleiter Endpoint (http://h/v1) fertig nach 1 min 5 s · +3k Tokens (gesamt 9k Tokens)"
        self.assertEqual(
            i18n.to_english(line),
            "📍 Build round 2/10 · Stage 1/3 · 🔨 Builder endpoint (http://h/v1) done after 1 min 5 s · +3k Tokens (total 9k Tokens)",
        )

    def test_multiline_and_indentation(self):
        text = "\n🔔 Hinweise:\n   ℹ️  Kein --proof: Der Loop führt keine Tests aus; über „fertig“ entscheidet nur die Abnahme."
        self.assertEqual(
            i18n.to_english(text), "\n🔔 Notes:\n   ℹ️  No --proof: the loop runs no tests; only the acceptance check decides “done”."
        )

    def test_unknown_text_stays(self):
        self.assertEqual(i18n.to_english("Das Modell sagt etwas Eigenes."), "Das Modell sagt etwas Eigenes.")

    def test_reordered_placeholders(self):
        self.assertEqual(i18n._fill("{1} vor {0}", ["a", "b"]), "b vor a")

    def test_say_translates_only_in_english(self):
        for value, expected in (("de", "🧹 Git-Workspace freigegeben.\n"), ("en", "🧹 Git workspace released.\n")):
            out = io.StringIO()
            with lang(value), contextlib.redirect_stdout(out):
                common.say("🧹 Git-Workspace freigegeben.")
            self.assertEqual(out.getvalue(), expected)

    def test_error_codes_follow_language(self):
        with lang("en"):
            out = loop.format_error("CG-1003", "/tmp/fehlt")
        self.assertIn("Project folder does not exist", out)
        self.assertIn("docs/en/fehlerbehebung.md#cg-1003", out)
        self.assertIn("Projektordner existiert nicht", loop.format_error("CG-1003"))

    def test_english_error_texts_match_english_doc(self):
        self.assertEqual(set(loop.ERROR_CODES_EN), set(loop.ERROR_CODES))
        doc = (ROOT / "docs" / "en" / "fehlerbehebung.md").read_text(encoding="utf-8")
        for code, (title, fix) in loop.ERROR_CODES_EN.items():
            self.assertIn(f"**{code} · {title}**  \n{fix}\n", doc, code)


class LanguageChoiceTest(unittest.TestCase):
    def test_detect_lang(self):
        self.assertEqual(i18n.detect_lang({}), "de")
        self.assertEqual(i18n.detect_lang({"CLAUDEGRAVITY_LANG": "EN"}), "en")
        self.assertEqual(i18n.detect_lang({"CLAUDEGRAVITY_LANG": "klingonisch"}), "de")
        self.assertEqual(i18n.detect_lang({"CLAUDEGRAVITY_LANG": "auto", "LANG": "de_DE.UTF-8"}), "de")
        self.assertEqual(i18n.detect_lang({"CLAUDEGRAVITY_LANG": "auto", "LANG": "en_US.UTF-8"}), "en")
        self.assertEqual(i18n.detect_lang({"CLAUDEGRAVITY_LANG": "auto", "LC_ALL": "fr_FR.UTF-8", "LANG": "de_DE"}), "en")

    def test_prescan_lang_for_help(self):
        self.assertEqual(i18n.prescan_lang(["--help", "--lang", "en"], {}), "en")
        self.assertEqual(i18n.prescan_lang(["--lang=en", "-h"], {}), "en")
        self.assertEqual(i18n.prescan_lang(["-h"], {"CLAUDEGRAVITY_LANG": "en"}), "en")
        self.assertEqual(i18n.prescan_lang(["-h"], {}), "de")

    def test_english_help(self):
        out = loop.build_parser(lang="en").format_help()
        self.assertIn("Resume an interrupted session", out)
        self.assertIn("Strategy and cost", out)
        self.assertNotIn("Unterbrochene Sitzung", out)

    def test_lang_flag_sets_runtime_language(self):
        with lang("de"):
            parsed = loop.load_cli_config(["x", "--lang", "en"])
            self.assertEqual(common.SETTINGS.lang, "en")
            loop.apply_runtime_settings(parsed[1])
            self.assertEqual(common.SETTINGS.lang, "en")

    def test_models_answer_in_english(self):
        seen = []

        def run_fn(binary, prompt, cwd, flags):
            seen.append(prompt)
            return "ok", {}

        agent = loop.AgentCLI("Fake", "fake", run_fn, local=True)
        with lang("de"):
            agent.run("Plane etwas")
        with lang("en"):
            agent.run("Plane etwas")
        self.assertEqual(seen[0], "Plane etwas")
        self.assertTrue(seen[1].startswith("Plane etwas") and "Write all prose" in seen[1] and "VERDICT:" in seen[1])


if __name__ == "__main__":
    unittest.main()
