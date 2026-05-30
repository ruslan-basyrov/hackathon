#!/usr/bin/env python3

"""
simulate.py - Simulate a turn-by-turn conversation between a *persona* agent and
a *chatbot* agent using the Featherless AI API (OpenAI-compatible endpoint).

Both agents run in the same process. Each keeps its OWN independent message
history. On every turn:

  1. The persona model is called. It MUST reply with a single JSON object.
  2. The visible utterance is extracted from that JSON and handed to the chatbot
     as a user message.
  3. The chatbot replies in plain text. That reply is handed back to the persona
     as its next user message.
  4. Repeat until an end condition is met.

--------------------------------------------------------------------------------
PERSONA JSON CONTRACT (must be enforced by the persona system prompt file)
--------------------------------------------------------------------------------
The persona is expected to emit a JSON object on every turn, e.g.:

    {
      "action": "CONTINUE",
      "message": "Hi, do you ship to Austria?"
    }

  * "action"  (REQUIRED) - control signal. The only non-terminal value is
                "CONTINUE". ANY other value (e.g. "BUY", "LEAVE", "NAVIGATE")
                ends the conversation, and that value becomes the run outcome.
  * "message" (the user-visible utterance) - THIS is the field whose text is
                forwarded to the chatbot. `message` is the canonical/documented
                field name chosen for this purpose. A few common synonyms
                (say / utterance / text / response) are accepted defensively,
                but persona prompts should standardize on `message`.

If a turn's output is not valid JSON, or parses but lacks an "action" field, it
counts as a parse failure: a corrective nudge is injected and the persona is
asked to try again. Three *consecutive* parse failures hard-stop the run.

--------------------------------------------------------------------------------
END CONDITIONS (evaluated in this priority order)
--------------------------------------------------------------------------------
  1. Persona action is terminal (anything != CONTINUE) -> outcome = that action
  2. Max --turns reached                                -> outcome = "unresolved"
  3. 3 consecutive JSON parse failures                  -> outcome = "unresolved_parse_error"
  4. API error after 3 attempts w/ exponential backoff  -> outcome = "unresolved_api_error"

--------------------------------------------------------------------------------
OUTPUT
--------------------------------------------------------------------------------
One JSON transcript per run is written to --output-dir:

    {persona_name}_{timestamp}_{outcome}.json

where persona_name is the stem of the persona prompt filename and timestamp is
YYYYMMDD_HHMMSS. Each transcript contains:

    outcome, total_turns, persona_model, chatbot_model,
    conversation  -> [{role, raw_content}, ...],
    parse_errors  -> total parse failures over the run

Set the two model IDs in the PERSONA_MODEL / CHATBOT_MODEL constants near the
top of this file, then:

    export FEATHERLESS_API_KEY=...
    python3 simulate.py persona.md bot.md
    python3 simulate.py persona.md bot.md --turns 30 --runs 5 --output-dir ./outputs
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Models  <-- EDIT THESE. Featherless model IDs for each agent.
# ---------------------------------------------------------------------------

PERSONA_MODEL = "deepseek-ai/DeepSeek-V4-Pro"
CHATBOT_MODEL = "deepseek-ai/DeepSeek-V4-Pro"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENING_MESSAGE = (
    "You have just arrived at the website. "
    "Describe your behaviour and begin the interaction."
)

# `message` is the canonical, documented field for the user-visible utterance.
# The fallbacks are a defensive measure only; persona prompts should use `message`.
MESSAGE_FIELD = "message"
MESSAGE_FIELD_FALLBACKS = (MESSAGE_FIELD, "say", "utterance", "text", "response")

NON_TERMINAL_ACTION = "CONTINUE"

MAX_CONSECUTIVE_PARSE_FAILURES = 3

MAX_API_ATTEMPTS = 3            # total attempts per call (1 try + retries)
INITIAL_BACKOFF_SECONDS = 1.0   # doubles each retry: 1s, 2s, 4s, ...

CORRECTION_MESSAGE = (
    'Your previous response could not be parsed as JSON with an "action" '
    "field. Reply with ONLY a single JSON object containing an \"action\" "
    'field ("CONTINUE" to keep talking, or a terminal action such as "BUY" / '
    '"LEAVE" / "NAVIGATE") and a "message" field with what you say next.'
)


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------

def _find_first_json_object(text):
    """Return the first balanced {...} substring (string-aware), or None."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        c = text[i]
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
        else:
            if c == '"':
                in_string = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def extract_json(text):
    """Best-effort parse of a model reply into a dict. Returns None on failure.

    Handles raw JSON, ```json fenced blocks, and JSON embedded in prose.
    """
    if not text:
        return None

    candidates = [text.strip()]

    # ```json ... ``` or ``` ... ``` fenced blocks
    for m in re.finditer(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE):
        candidates.append(m.group(1).strip())

    # first balanced object anywhere in the text
    obj = _find_first_json_object(text)
    if obj:
        candidates.append(obj)

    for cand in candidates:
        if not cand:
            continue
        try:
            parsed = json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def extract_message(parsed):
    """Pull the user-visible utterance out of a parsed persona dict."""
    for key in MESSAGE_FIELD_FALLBACKS:
        val = parsed.get(key)
        if isinstance(val, str):
            return val
    # Last resort: stringify whatever is under the canonical key, if anything.
    val = parsed.get(MESSAGE_FIELD)
    return "" if val is None else str(val)


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

class APICallError(Exception):
    """Raised when an API call fails after all retry attempts."""


def build_client():
    """Construct the Featherless (OpenAI-compatible) client."""
    from openai import OpenAI  # imported lazily so the module is unit-testable

    api_key = os.environ.get("FEATHERLESS_API_KEY")
    if not api_key:
        sys.exit("ERROR: FEATHERLESS_API_KEY environment variable is not set.")

    return OpenAI(base_url="https://api.featherless.ai/v1", api_key=api_key)


def call_with_retry(client, model, system_prompt, history):
    """Call chat.completions with retries + exponential backoff.

    Mirrors the reference pattern: the system prompt is prepended to the agent's
    own history on every call. Raises APICallError if all attempts fail.
    """
    messages = [{"role": "system", "content": system_prompt}] + history
    backoff = INITIAL_BACKOFF_SECONDS
    last_err = None
    for attempt in range(1, MAX_API_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(model=model, messages=messages)
            content = response.choices[0].message.content
            return content if content is not None else ""
        except Exception as err:  # noqa: BLE001 - retry on any API/transport error
            last_err = err
            if attempt < MAX_API_ATTEMPTS:
                print(
                    f"  [api] attempt {attempt}/{MAX_API_ATTEMPTS} failed: {err!r}; "
                    f"retrying in {backoff:.0f}s",
                    file=sys.stderr,
                )
                time.sleep(backoff)
                backoff *= 2
    raise APICallError(str(last_err))


# ---------------------------------------------------------------------------
# Conversation driver
# ---------------------------------------------------------------------------

def run_conversation(client, persona_system, chatbot_system,
                     persona_model, chatbot_model, max_turns):
    """Drive one full persona<->chatbot conversation. Returns a transcript dict."""
    # Each agent maintains its OWN independent history.
    persona_history = [{"role": "user", "content": OPENING_MESSAGE}]
    chatbot_history = []

    conversation = [{"role": "opening", "raw_content": OPENING_MESSAGE}]

    consecutive_failures = 0
    parse_errors = 0
    outcome = "unresolved"
    turn = 0

    while turn < max_turns:
        turn += 1

        # ---- persona turn (must return JSON) ----
        try:
            persona_raw = call_with_retry(
                client, persona_model, persona_system, persona_history
            )
        except APICallError as err:
            print(f"  [turn {turn}] persona API error: {err}", file=sys.stderr)
            outcome = "unresolved_api_error"
            break
        persona_history.append({"role": "assistant", "content": persona_raw})
        conversation.append({"role": "persona", "raw_content": persona_raw})

        parsed = extract_json(persona_raw)
        action = parsed.get("action") if isinstance(parsed, dict) else None

        if parsed is None or action is None:
            consecutive_failures += 1
            parse_errors += 1
            print(
                f"  [turn {turn}] WARNING: persona output failed JSON/action parse "
                f"({consecutive_failures}/{MAX_CONSECUTIVE_PARSE_FAILURES})",
                file=sys.stderr,
            )
            if consecutive_failures >= MAX_CONSECUTIVE_PARSE_FAILURES:
                outcome = "unresolved_parse_error"
                break
            # Nudge the persona back onto the JSON contract and retry next turn.
            persona_history.append({"role": "user", "content": CORRECTION_MESSAGE})
            continue

        # Successful parse -> reset the consecutive-failure counter.
        consecutive_failures = 0
        action_norm = str(action).strip().upper()

        # End condition #1: terminal action.
        if action_norm != NON_TERMINAL_ACTION:
            outcome = action_norm
            print(f"  [turn {turn}] persona terminal action: {action_norm}")
            break

        message = extract_message(parsed)
        print(f"  [turn {turn}] persona -> {message[:80]!r}")

        # ---- chatbot turn (plain text) ----
        chatbot_history.append({"role": "user", "content": message})
        try:
            chatbot_raw = call_with_retry(
                client, chatbot_model, chatbot_system, chatbot_history
            )
        except APICallError as err:
            print(f"  [turn {turn}] chatbot API error: {err}", file=sys.stderr)
            outcome = "unresolved_api_error"
            break
        chatbot_history.append({"role": "assistant", "content": chatbot_raw})
        conversation.append({"role": "chatbot", "raw_content": chatbot_raw})
        print(f"  [turn {turn}] chatbot -> {chatbot_raw[:80]!r}")

        # Feed the chatbot reply back to the persona as its next user message.
        persona_history.append({"role": "user", "content": chatbot_raw})
    else:
        # while-loop exhausted without break -> End condition #2: max turns.
        outcome = "unresolved"

    return {
        "outcome": outcome,
        "total_turns": turn,
        "persona_model": persona_model,
        "chatbot_model": chatbot_model,
        "conversation": conversation,
        "parse_errors": parse_errors,
    }


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _safe(s):
    """Make a string safe to embed in a filename."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(s)).strip("_")
    return cleaned or "x"


def read_prompt(path):
    p = Path(path)
    if not p.is_file():
        sys.exit(f"ERROR: prompt file not found: {path}")
    return p.read_text(encoding="utf-8")


def save_transcript(transcript, output_dir, persona_name):
    """Write the transcript JSON; returns the path written."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{_safe(persona_name)}_{timestamp}_{_safe(transcript['outcome'])}"
    path = out / f"{base}.json"
    counter = 1
    while path.exists():  # avoid clobbering runs that land in the same second
        path = out / f"{base}_{counter}.json"
        counter += 1
    with path.open("w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, ensure_ascii=False)
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Simulate persona<->chatbot conversations via Featherless AI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'NOTE: the persona system prompt MUST instruct the model to reply with a '
            'single JSON object containing an "action" field ("CONTINUE" or a '
            'terminal action) and a "message" field (the text shown to the chatbot).'
        ),
    )
    parser.add_argument("persona_prompt_file", help="path to persona system prompt (plain text)")
    parser.add_argument("chatbot_prompt_file", help="path to chatbot system prompt (plain text)")
    parser.add_argument("--turns", type=int, default=20, help="max turns before hard stop (default: 20)")
    parser.add_argument("--runs", type=int, default=1, help="number of conversations to simulate (default: 1)")
    parser.add_argument("--output-dir", default="./outputs", help="transcript output folder (default: ./outputs)")
    return parser


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.turns < 1:
        parser.error("--turns must be >= 1")
    if args.runs < 1:
        parser.error("--runs must be >= 1")

    persona_system = read_prompt(args.persona_prompt_file)
    chatbot_system = read_prompt(args.chatbot_prompt_file)
    persona_name = Path(args.persona_prompt_file).stem

    client = build_client()

    print(f"persona model: {PERSONA_MODEL}")
    print(f"chatbot model: {CHATBOT_MODEL}")

    outcomes = Counter()
    for run_idx in range(1, args.runs + 1):
        print(f"=== Run {run_idx}/{args.runs} ===")
        transcript = run_conversation(
            client,
            persona_system,
            chatbot_system,
            PERSONA_MODEL,
            CHATBOT_MODEL,
            args.turns,
        )
        path = save_transcript(transcript, args.output_dir, persona_name)
        outcomes[transcript["outcome"]] += 1
        print(
            f"  outcome={transcript['outcome']} turns={transcript['total_turns']} "
            f"parse_errors={transcript['parse_errors']} -> {path}"
        )

    print("\n=== Summary ===")
    print(f"runs: {args.runs}")
    for outcome, count in outcomes.most_common():
        print(f"  {outcome}: {count}")


if __name__ == "__main__":
    main()
