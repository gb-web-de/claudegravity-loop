# ClaudeGravity-Sandbox: Python, Node, Git und die KI-CLIs, damit ein CLI-Bauleiter im Container bauen kann.
#
#   docker build -t claudegravity-sandbox sandbox/
#   claudegravity "Aufgabe" --sandbox an --sandbox-image claudegravity-sandbox --proof "python -m pytest -q"
#
# Eigene Werkzeuge des Projekts (Composer, Go, Rust …) in einem eigenen Image ergänzen: FROM claudegravity-sandbox
FROM node:22-bookworm-slim

ARG CLIS="@anthropic-ai/claude-code @openai/codex @google/gemini-cli @github/copilot"

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv git ca-certificates ripgrep \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && npm install -g $CLIS \
    && npm cache clean --force

# pytest für den üblichen Prüfbefehl; Projekt-Abhängigkeiten gehören in ein eigenes Image
RUN python3 -m pip install --no-cache-dir --break-system-packages pytest

WORKDIR /work
