#!/usr/bin/env python3
"""Canary check: is a relay actually serving the model it claims?

Some "cheap" relays silently swap or quantize the model you paid for. This tool
makes that empirical: it sends a fixed set of discriminating "canary" prompts to
**both** a relay endpoint and the official provider (or any reference endpoint),
then diffs the outputs. A downgraded/swapped model shows up as low output
similarity and failed capability probes — reproducible evidence you can paste
into a watch-list report.

Both endpoints are OpenAI-compatible (POST /chat/completions). Keys are read
from flags or env (RELAY_KEY / REF_KEY) and never logged.

Stdlib only. The scoring/verdict logic is pure and unit-tested; the live HTTP
call is a thin wrapper so the tool works with your own keys.

Usage:
  python scripts/canary_check.py \
    --relay-url https://some-relay.example/v1 --relay-key sk-... \
    --ref-url https://api.openai.com/v1       --ref-key  sk-... \
    --model gpt-5.5
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass


# Fixed canaries: each is deterministic and discriminating — a downgraded model
# tends to fail the capability ones and diverge in wording on all of them.
@dataclass(frozen=True)
class Canary:
    id: str
    prompt: str
    must_contain: str | None  # exact-answer capability check (None = compare-only)


CANARIES = [
    Canary("echo", "Reply with EXACTLY this token and nothing else: AGW-CANARY-7F3A2C", "AGW-CANARY-7F3A2C"),
    Canary("primes", "Output only a JSON array of the first 6 prime numbers, no prose.", "[2, 3, 5, 7, 11, 13]"),
    Canary(
        "reason",
        "A bat and a ball cost $1.10 together. The bat costs $1.00 more than the ball. "
        "How much does the ball cost? Reply with only the dollar amount.",
        "0.05",
    ),
    Canary(
        "count",
        "How many times does the letter 'r' appear in the word 'strawberry'? Reply with only the number.",
        "3",
    ),
]


# ── Pure scoring logic (unit-tested) ─────────────────────────────────────────

def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, drop punctuation — for fuzzy comparison."""
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", (text or "").lower())).strip()


def token_similarity(a: str, b: str) -> float:
    """Jaccard similarity over word tokens of two normalized strings (0..1)."""
    sa, sb = set(normalize(a).split()), set(normalize(b).split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def capability_hit(output: str, must_contain: str | None) -> bool | None:
    """Did the output contain the exact expected answer? None if not a capability probe."""
    if must_contain is None:
        return None
    return normalize(must_contain) in normalize(output)


def verdict(rows: list[dict]) -> dict:
    """Aggregate per-canary results into a verdict.

    rows: [{id, similarity, relay_hit, ref_hit}]. relay_hit/ref_hit may be None.
    Returns {label, mean_similarity, downgrade_flags}.
    """
    sims = [r["similarity"] for r in rows]
    mean_sim = sum(sims) / len(sims) if sims else 0.0
    # a "downgrade" signal = reference passed a capability probe the relay failed
    downgrades = [r["id"] for r in rows if r.get("ref_hit") and r.get("relay_hit") is False]
    if downgrades or mean_sim < 0.45:
        label = "SUSPICIOUS — likely a different / downgraded model"
    elif mean_sim < 0.7:
        label = "INCONCLUSIVE — some divergence; re-run with more canaries"
    else:
        label = "OK — outputs consistent with the reference model"
    return {"label": label, "mean_similarity": round(mean_sim, 3), "downgrade_flags": downgrades}


# ── Live call (thin wrapper; not unit-tested) ────────────────────────────────

def call_chat(base_url: str, api_key: str, model: str, prompt: str, timeout: int = 60) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def run(relay_url, relay_key, ref_url, ref_key, model) -> int:
    rows = []
    print(f"canary check · model={model}\n{'id':10} {'sim':>5}  relay  ref")
    for c in CANARIES:
        try:
            relay_out = call_chat(relay_url, relay_key, model, c.prompt)
            ref_out = call_chat(ref_url, ref_key, model, c.prompt)
        except Exception as e:  # noqa: BLE001 - surface any endpoint/network error per-canary
            print(f"{c.id:10}  ERROR  {e}")
            continue
        sim = token_similarity(relay_out, ref_out)
        rh, fh = capability_hit(relay_out, c.must_contain), capability_hit(ref_out, c.must_contain)
        rows.append({"id": c.id, "similarity": sim, "relay_hit": rh, "ref_hit": fh})
        mark = lambda h: "—" if h is None else ("✓" if h else "✗")
        print(f"{c.id:10} {sim:5.2f}  {mark(rh):^5}  {mark(fh):^3}")
    v = verdict(rows)
    print(f"\nmean similarity: {v['mean_similarity']}")
    if v["downgrade_flags"]:
        print(f"capability probes the relay failed but the reference passed: {', '.join(v['downgrade_flags'])}")
    print(f"VERDICT: {v['label']}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Detect a relay silently swapping/downgrading a model.")
    p.add_argument("--relay-url", required=True)
    p.add_argument("--relay-key", default=os.environ.get("RELAY_KEY", ""))
    p.add_argument("--ref-url", required=True)
    p.add_argument("--ref-key", default=os.environ.get("REF_KEY", ""))
    p.add_argument("--model", required=True)
    a = p.parse_args()
    if not a.relay_key or not a.ref_key:
        p.error("provide --relay-key/--ref-key or set RELAY_KEY/REF_KEY env vars")
    return run(a.relay_url, a.relay_key, a.ref_url, a.ref_key, a.model)


if __name__ == "__main__":
    sys.exit(main())
