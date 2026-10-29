# -*- coding: utf-8 -*-
"""Hlava - read-only Discord reader for a personal AI planning assistant.

What it does
------------
Once in a while (run by hand or by a scheduler on the owner's own computer) it reads the newest
messages in a short list of channels and writes them into a local Markdown file, so the owner's
AI assistant knows about announcements and meeting dates.

What it does NOT do
-------------------
- never sends messages, reactions, DMs or joins voice
- never reads DMs, member lists or anything outside the channels listed in DISCORD_CHANNELS
- never stores attachments; user mentions are replaced with "@niekto", e-mails and phone numbers
  are masked, texts are trimmed to 140 characters, at most 15 messages per channel are kept
- no gateway / websocket connection, no privileged intents needed at runtime - plain REST GET
  on /channels/{id}/messages (bot permissions: View Channels + Read Message History)
- the state file and the output stay on the owner's computer; nothing is uploaded anywhere

Usage
-----
  cp .env.example .env     # fill DISCORD_BOT_TOKEN and DISCORD_CHANNELS
  python -I -X utf8 hlava_discord_reader.py
"""
import io, json, os, re, sys, time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, ".env")
STATE = os.path.join(HERE, "state.json")
OUT = os.path.join(HERE, "discord-prehlad.md")
API = "https://discord.com/api/v10"
MAX_PER_CHANNEL, TRIM = 15, 140

RE_MAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RE_PHONE = re.compile(r"(?<!\w)\+?\d[\d \-/()]{6,}\d")


def clean(s, n=None):
    """One line, no e-mails / phone numbers, optionally trimmed."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    s = RE_MAIL.sub("[e-mail]", s)
    s = RE_PHONE.sub("[číslo]", s)
    return s[:n - 1].rstrip() + "…" if n and len(s) > n else s


def load_env():
    env = {}
    if os.path.exists(ENV):
        for line in io.open(ENV, encoding="utf-8-sig"):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return env


def read_state():
    try:
        return json.load(io.open(STATE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(st):
    json.dump(st, io.open(STATE, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def discord_get(path, token, params=None):
    import requests
    for _ in range(2):
        r = requests.get(API + path, headers={"Authorization": "Bot " + token, "User-Agent": "HlavaReader/1.0"},
                         params=params, timeout=20)
        if r.status_code == 429:
            time.sleep(min(float(r.json().get("retry_after", 2)), 10))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("rate limit")


def fetch(env, state, errors):
    token = env["DISCORD_BOT_TOKEN"]
    try:
        days = int(env.get("DISCORD_DAYS") or 3)
    except ValueError:
        days = 3
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = []
    for cid in [c.strip() for c in env.get("DISCORD_CHANNELS", "").split(",") if c.strip().isdigit()]:
        cs = state.setdefault(cid, {"last_id": "0", "name": "", "msgs": []})
        try:
            if not cs.get("name"):
                cs["name"] = clean(discord_get("/channels/%s" % cid, token).get("name"), 60)
            msgs = discord_get("/channels/%s/messages" % cid, token, {"limit": 100})
            last = int(cs.get("last_id") or 0)
            for m in msgs:
                if m.get("type") not in (0, 19):  # len bezne spravy a odpovede; systemove (follow, join...) preskocit
                    continue
                ts = datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00"))
                if int(m["id"]) <= last or ts < cutoff:
                    continue
                a = m.get("author") or {}
                text = re.sub(r"<@[!&]?\d+>", "@niekto", m.get("content") or "")
                if not text.strip() and (m.get("attachments") or m.get("embeds")):
                    text = "[príloha]"
                if text.strip():
                    cs["msgs"].append({"id": m["id"], "ts": ts.astimezone().strftime("%Y-%m-%d %H:%M"),
                                       "author": clean(a.get("global_name") or a.get("username") or "?", 40),
                                       "text": clean(text, TRIM)})
                cs["last_id"] = str(max(int(cs["last_id"] or 0), int(m["id"])))
            cs["msgs"] = [x for x in cs["msgs"] if datetime.strptime(x["ts"], "%Y-%m-%d %H:%M").astimezone() >= cutoff]
            cs["msgs"] = sorted({x["id"]: x for x in cs["msgs"]}.values(), key=lambda x: int(x["id"]))[-MAX_PER_CHANNEL:]
        except Exception as e:
            code = getattr(getattr(e, "response", None), "status_code", "")
            errors.append("kanál %s: %s %s" % (cid, type(e).__name__, code))
        result.append({"name": cs.get("name") or cid, "msgs": cs["msgs"]})
    return result


def build_md(channels, errors, now=None):
    now = now or datetime.now()
    L = ["# Discord - prehľad (aktualizované %s)" % now.strftime("%Y-%m-%d %H:%M"), ""]
    for ch in channels:
        L.append("## #%s" % ch["name"])
        L += ["- %s %s: %s" % (m["ts"][5:], m["author"], m["text"]) for m in ch["msgs"]] or ["- Nič nové."]
        L.append("")
    if errors:
        L += ["## Chyby"] + ["- %s" % e for e in errors]
    return "\n".join(L).rstrip() + "\n"


def main():
    env = load_env()
    if not env.get("DISCORD_BOT_TOKEN") or not env.get("DISCORD_CHANNELS"):
        print("Chýba DISCORD_BOT_TOKEN alebo DISCORD_CHANNELS v %s (vzor: .env.example)." % ENV)
        return 2
    state, errors = read_state(), []
    channels = fetch(env, state, errors)
    state["posledny_beh"] = datetime.now(timezone.utc).isoformat()
    write_state(state)
    md = build_md(channels, errors)
    io.open(OUT, "w", encoding="utf-8").write(md)
    sys.stdout.buffer.write(md.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
