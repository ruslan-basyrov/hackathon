"""Lenient JSON parsing for LLM responses.

Some instruct-tuned models occasionally:
  * wrap their output in ```json ... ``` markdown fences
  * emit prose before/after the JSON object
  * drop the opening '{' (continuing a body the prompt seemed to start)
  * drop the closing '}'

`loads_lenient` tries the cheapest parse first, then progressively repairs:
  1. plain json.loads on the stripped string
  2. strip markdown code fences
  3. if the body doesn't start with '{' but looks like a JSON body, wrap it
     in braces (handles the dropped-opening-brace case — must be tried BEFORE
     the slice fallback below, otherwise the slice grabs an inner '{}' from
     a nested object instead of recognizing the outer brace is missing)
  4. slice from the first '{' to the last '}' (handles prose before/after)
  5. append a missing closing '}' if the body starts with one but never closes

Returns the parsed dict on success, or None if no repair worked. Callers log
the raw response on failure so we can iterate on the prompt or the repairs.
"""
from __future__ import annotations

import json
from typing import Optional


def loads_lenient(raw: str) -> Optional[dict]:
    if not raw or not raw.strip():
        return None

    s = raw.strip()
    candidates = [s]

    # Strip ```json ... ``` or ``` ... ``` fences.
    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        candidates.append("\n".join(lines).strip())

    body = candidates[-1]

    # Dropped opening '{': try wrapping BEFORE slicing — otherwise the slice
    # would grab an inner brace from a nested object (e.g. personal_data_entered: {})
    # and miss the real missing outer brace.
    if not body.startswith("{") and ":" in body:
        wrapped = "{" + body
        if not wrapped.rstrip().endswith("}"):
            wrapped = wrapped.rstrip() + "}"
        candidates.append(wrapped)

    # Prose before/after: slice from first '{' to last '}'.
    i, j = body.find("{"), body.rfind("}")
    if i != -1 and j > i:
        candidates.append(body[i:j + 1])

    # Body starts with '{' but never closes: append '}'.
    if body.startswith("{") and not body.rstrip().endswith("}"):
        candidates.append(body.rstrip() + "}")

    for c in candidates:
        try:
            out = json.loads(c)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(out, dict):
            return out
    return None
