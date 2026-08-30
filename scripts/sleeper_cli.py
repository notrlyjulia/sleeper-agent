#!/usr/bin/env python3
"""Thin CLI over the `sleeperdraft` library.

Why this exists: each scheduled agent run starts a brand-new session with no
memory of prior runs. Rather than having the agent re-derive the right
sleeperdraft calls (and their exact argument order) from scratch every time,
it gets a small, stable set of subcommands to shell out to. The DECISIONS
(who to draft, who to start, who to claim off waivers) are never made in
here — this file is pure plumbing, same spirit as the library it wraps.

Env vars expected (see repo README):
    SLEEPER_USER              your Sleeper display name (the agent account)
    SLEEPER_TOKEN              its session token
    SLEEPER_HEADLESS=1          keep 1 in a scheduled/unattended run

Examples:
    python3 sleeper_cli.py turn <draft_id> <roster_id>
    python3 sleeper_cli.py drafted <draft_id>
    python3 sleeper_cli.py slots <draft_id>
    python3 sleeper_cli.py myslot <draft_id> <username>
    python3 sleeper_cli.py join <draft_id> [--slot N]
    python3 sleeper_cli.py pick <draft_id> <player_id> "<player name>" --slot N
    python3 sleeper_cli.py chat-read <draft_id>
    python3 sleeper_cli.py chat-send <draft_id> "<text>"
    python3 sleeper_cli.py players [--refresh]
    python3 sleeper_cli.py league <league_id>
    python3 sleeper_cli.py roster <league_id> <roster_id>

Every subcommand prints one JSON value to stdout and exits 0 on success,
or prints an error to stderr and exits 1. That makes it easy for the agent
to call via Bash and read the result back as text.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sleeperdraft as sd  # noqa: E402

PLAYERS_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "memory", "players_cache.json",
)
PLAYERS_MAX_AGE_S = 20 * 60 * 60  # Sleeper: don't fetch this dump more than ~once/day.


def _out(value):
    print(json.dumps(value, indent=2, default=str))


def _err(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def cmd_turn(a):
    _out(sd.draft_turn(a.draft_id, int(a.roster_id)))


def cmd_drafted(a):
    _out(sorted(sd.drafted_player_ids(a.draft_id, max_age=0)))


def cmd_slots(a):
    _out(sd.slot_names(a.draft_id))


def cmd_myslot(a):
    _out(sd.slot_in_draft(a.draft_id, a.username, max_age=0))


def cmd_join(a):
    _out({"slot": sd.join_draft(a.draft_id, slot=a.slot)})


def cmd_pick(a):
    try:
        ok = sd.submit_pick(a.draft_id, a.player_id, a.player_name, slot=a.slot)
        _out({"ok": ok})
    except RuntimeError as e:
        _err(str(e))


def cmd_chat_read(a):
    _out(sd.read_chat(a.draft_id))


def cmd_chat_send(a):
    _out({"ok": sd.send_chat(a.draft_id, a.text)})


def cmd_players(a):
    """Full player metadata dict (id -> name/position/team/injury_status/...).

    Sleeper asks callers not to pull this more than once a day, so it's
    cached to memory/players_cache.json. Commit that file's freshness
    (mtime) is what's checked — pass --refresh to force a re-fetch anyway.
    """
    stale = a.refresh or not os.path.exists(PLAYERS_CACHE) or (
        time.time() - os.path.getmtime(PLAYERS_CACHE) > PLAYERS_MAX_AGE_S)
    if stale:
        with urllib.request.urlopen(
                "https://api.sleeper.app/v1/players/nfl", timeout=30) as r:
            data = json.loads(r.read())
        os.makedirs(os.path.dirname(PLAYERS_CACHE), exist_ok=True)
        with open(PLAYERS_CACHE, "w") as f:
            json.dump(data, f)
    with open(PLAYERS_CACHE) as f:
        data = json.load(f)
    if a.player_id:
        _out(data.get(a.player_id))
    else:
        _out({"cached_players": len(data),
              "cache_file": PLAYERS_CACHE,
              "age_s": round(time.time() - os.path.getmtime(PLAYERS_CACHE))})


def cmd_league(a):
    with urllib.request.urlopen(
            f"https://api.sleeper.app/v1/league/{a.league_id}", timeout=15) as r:
        _out(json.loads(r.read()))


def cmd_rosters(a):
    with urllib.request.urlopen(
            f"https://api.sleeper.app/v1/league/{a.league_id}/rosters",
            timeout=15) as r:
        _out(json.loads(r.read()))


def cmd_matchups(a):
    with urllib.request.urlopen(
            f"https://api.sleeper.app/v1/league/{a.league_id}/matchups/{a.week}",
            timeout=15) as r:
        _out(json.loads(r.read()))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("turn"); s.add_argument("draft_id"); s.add_argument("roster_id"); s.set_defaults(fn=cmd_turn)
    s = sub.add_parser("drafted"); s.add_argument("draft_id"); s.set_defaults(fn=cmd_drafted)
    s = sub.add_parser("slots"); s.add_argument("draft_id"); s.set_defaults(fn=cmd_slots)
    s = sub.add_parser("myslot"); s.add_argument("draft_id"); s.add_argument("username"); s.set_defaults(fn=cmd_myslot)
    s = sub.add_parser("join"); s.add_argument("draft_id"); s.add_argument("--slot", type=int, default=None); s.set_defaults(fn=cmd_join)
    s = sub.add_parser("pick"); s.add_argument("draft_id"); s.add_argument("player_id"); s.add_argument("player_name"); s.add_argument("--slot", type=int, default=None); s.set_defaults(fn=cmd_pick)
    s = sub.add_parser("chat-read"); s.add_argument("draft_id"); s.set_defaults(fn=cmd_chat_read)
    s = sub.add_parser("chat-send"); s.add_argument("draft_id"); s.add_argument("text"); s.set_defaults(fn=cmd_chat_send)
    s = sub.add_parser("players"); s.add_argument("player_id", nargs="?", default=None); s.add_argument("--refresh", action="store_true"); s.set_defaults(fn=cmd_players)
    s = sub.add_parser("league"); s.add_argument("league_id"); s.set_defaults(fn=cmd_league)
    s = sub.add_parser("rosters"); s.add_argument("league_id"); s.set_defaults(fn=cmd_rosters)
    s = sub.add_parser("matchups"); s.add_argument("league_id"); s.add_argument("week"); s.set_defaults(fn=cmd_matchups)

    args = p.parse_args()
    try:
        args.fn(args)
    except Exception as e:  # noqa: BLE001 — surface it, don't silently exit 0
        _err(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
