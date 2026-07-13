#!/usr/bin/env python3
"""
Beacon Ops agent — the "brain" half of the ops split (the manifest-scan cron is
the deterministic "muscle"). Runs on a schedule, reads Beacon's own index, and
produces a daily DIGEST with drafted, personalized outreach for a human to send.

Hard rule: this agent PROPOSES, a human SENDS. It writes drafts to a file. It
never emails, DMs, or opens PRs. No exceptions — mass automated outreach gets
domains blocked and the brand burned.

LLM drafting uses Claude when credentials are available (ANTHROPIC_API_KEY or an
`ant auth login` profile); otherwise it falls back to solid templates so the
digest is always produced. Dogfood: discovery runs against Beacon's own API.

Env:
  BEACON_BASE   registry base (default https://registry-ruby.vercel.app)
  GITHUB_TOKEN  optional — enriches targets with public contact info
  OPS_MODEL     optional — Claude model id (default claude-opus-4-8)
  OUT           optional — output path (default BEACON_OPS_DIGEST.md)
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = os.environ.get("BEACON_BASE", "https://registry-ruby.vercel.app").rstrip("/")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
MODEL = os.environ.get("OPS_MODEL", "claude-opus-4-8")
OUT = os.environ.get("OUT", "BEACON_OPS_DIGEST.md")

# Broad terms to surface serious builders across ecosystems.
TERMS = ["langchain", "langgraph", "crewai", "autogen", "llamaindex",
         "mcp server", "ai agent", "rag agent", "browser agent"]
MIN_STARS = 150   # proven-builder bar
TOP_N = 8         # targets per digest


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=25) as r:
        return json.load(r)


def pulse() -> dict:
    try:
        h = _get("/api/v1/health")
        return {"total": h.get("total_agents"), "active": h.get("active_agents_90d")}
    except Exception:
        return {"total": None, "active": None}


def candidates() -> list[dict]:
    """Top active, high-signal, not-yet-claimed builders — deduped by owner."""
    best: dict[str, dict] = {}
    for t in TERMS:
        q = urllib.parse.quote(t)
        try:
            rows = _get(f"/api/v1/search?q={q}&limit=100&sort=top").get("results", [])
        except Exception:
            continue
        for r in rows:
            if not r.get("active"):
                continue
            if int(r.get("stars", 0) or 0) < MIN_STARS:
                continue
            if r.get("registration_source") == "manifest":  # already claimed us
                continue
            aid = r.get("agent_id", "")
            if aid not in best or r["stars"] > best[aid]["stars"]:
                r["_term"] = t
                best[aid] = r
    # dedupe by owner, keep the owner's top repo
    by_owner: dict[str, dict] = {}
    for r in sorted(best.values(), key=lambda x: -int(x.get("stars", 0))):
        owner = r["agent_id"].split("/")[0]
        by_owner.setdefault(owner, r)
    return list(by_owner.values())[:TOP_N]


def contact(owner: str) -> dict:
    """Public GitHub profile fields for an owner (best-effort)."""
    req = urllib.request.Request(f"https://api.github.com/users/{owner}")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.load(r)
        return {"type": d.get("type"), "name": d.get("name"),
                "email": d.get("email"), "blog": d.get("blog"),
                "twitter": d.get("twitter_username")}
    except Exception:
        return {}


def _channels(c: dict) -> str:
    bits = []
    if c.get("email"):
        bits.append(c["email"])
    if c.get("twitter"):
        bits.append(f"@{c['twitter']}")
    if c.get("blog"):
        bits.append(c["blog"])
    return " · ".join(bits) or "github only"


def template_note(t: dict, c: dict) -> str:
    """Deterministic fallback draft — used when no Claude credentials."""
    name = (c.get("name") or t["agent_id"].split("/")[0])
    repo = t["agent_id"].split("/")[-1]
    cap = (t.get("capabilities_tags") or ["ai agent"])[0]
    return (f"Hi {name} — {repo} ranks in the top results for \"{cap}\" on "
            f"Beacon, our open index of {LIVE_TOTAL or '24k'}+ agents. Two things, "
            f"both free: a live \"Beacon Verified\" badge for your README (stars + "
            f"health, auto-updating), and you're already discoverable via our MCP "
            f"server — want the listing tuned? No ask, just making you easier to "
            f"find. — Hamza")


LIVE_TOTAL = None  # filled in main()


def claude_available() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY", "").strip():
        return True
    # An `ant auth login` profile also authenticates the zero-arg client.
    try:
        import anthropic  # noqa: F401
    except Exception:
        return False
    return bool(os.environ.get("ANTHROPIC_AUTH_TOKEN", "").strip()) or \
        os.path.isdir(os.path.expanduser("~/.config/anthropic"))


def claude_notes(targets: list[dict], contacts: dict) -> dict:
    """One Claude call → a personalized draft per target. Returns {agent_id: note}."""
    from anthropic import Anthropic

    items = []
    for t in targets:
        owner = t["agent_id"].split("/")[0]
        c = contacts.get(owner, {})
        items.append({
            "agent_id": t["agent_id"],
            "name": c.get("name") or owner,
            "stars": int(t.get("stars", 0) or 0),
            "top_capabilities": (t.get("capabilities_tags") or [])[:4],
            "is_org": (c.get("type") == "Organization"),
        })

    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["drafts"],
        "properties": {"drafts": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False,
                      "required": ["agent_id", "note"],
                      "properties": {"agent_id": {"type": "string"},
                                     "note": {"type": "string"}}}}},
    }
    prompt = (
        "You are the Beacon growth assistant. Beacon is a neutral search + "
        f"reputation index for open-source AI agents ({LIVE_TOTAL or '24,000'}+ "
        "indexed, ranked by real maintenance health, not just stars; free, no API "
        "key; discoverable via an MCP server `npx -y beacon-mcp`). We also offer a "
        "free live 'Beacon Verified' README badge.\n\n"
        "Draft ONE short, genuine, value-first outreach note per target below, to "
        "be sent BY HAND by a human (Hamza). Rules: reference the target's actual "
        "repo/capabilities; lead with something useful to THEM (badge, discovery, "
        "or a fitting integration); exactly one ask; 4-6 sentences max; no hype, no "
        "mail-merge feel, no emoji spam. Never imply it will be auto-sent.\n\n"
        f"Targets:\n{json.dumps(items, indent=2)}"
    )
    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    return {d["agent_id"]: d["note"] for d in data.get("drafts", [])}


def main() -> None:
    global LIVE_TOTAL
    p = pulse()
    LIVE_TOTAL = p["total"]
    targets = candidates()
    contacts = {t["agent_id"].split("/")[0]: contact(t["agent_id"].split("/")[0])
                for t in targets}

    notes: dict[str, str] = {}
    drafted_by = "templates"
    if claude_available():
        try:
            notes = claude_notes(targets, contacts)
            drafted_by = f"Claude ({MODEL})"
        except Exception as e:
            print(f"[ops] Claude drafting failed ({e}); falling back to templates")
    if not notes:
        notes = {t["agent_id"]: template_note(t, contacts.get(t["agent_id"].split("/")[0], {}))
                 for t in targets}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ratio = ""
    if p["total"] and p["active"]:
        ratio = f" ({round(100 * p['active'] / p['total'])}% active)"

    lines = [
        f"# Beacon Ops digest — {today}",
        "",
        "> **Draft-only.** These notes are proposals. A human reviews and sends "
        "them by hand. Nothing here is auto-sent.",
        "",
        "## Pulse",
        f"- Indexed: **{p['total']:,}**" if p["total"] else "- Indexed: n/a",
        f"- Active (90d): **{p['active']:,}**{ratio}" if p["active"] else "- Active: n/a",
        f"- Drafts by: {drafted_by}",
        "",
        f"## Top {len(targets)} outreach targets (active, ≥{MIN_STARS}★, not yet on Beacon)",
        "",
    ]
    for t in targets:
        owner = t["agent_id"].split("/")[0]
        c = contacts.get(owner, {})
        lines += [
            f"### {t['agent_id']} — ★{int(t.get('stars',0)):,} · health {t.get('health_score')}",
            f"**Channel:** {_channels(c)}  ·  **pushed:** {str(t.get('pushed_at',''))[:10]}",
            "",
            "```",
            notes.get(t["agent_id"], "(no draft)").strip(),
            "```",
            "",
        ]
    lines += [
        "## Suggested actions",
        "1. Review each draft; send the good ones by hand (personalize further if needed).",
        "2. When a target adds a `beacon.json`, run the manifest-scan `?owner=<them>` to verify them instantly.",
        "3. Skip anyone already contacted — one personal message per builder, ever.",
        "",
    ]
    out = "\n".join(lines)
    with open(OUT, "w") as f:
        f.write(out)
    print(out)
    print(f"\n[ops] wrote {OUT} — {len(targets)} targets, drafts by {drafted_by}")


if __name__ == "__main__":
    main()
