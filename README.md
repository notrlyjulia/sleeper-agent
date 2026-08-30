# Julia's fantasy football agent

An autonomous Sleeper fantasy football manager built on
[aWarmWalrus/sleeperdraft](https://github.com/aWarmWalrus/sleeperdraft) (the
plumbing: reads via Sleeper's public API, writes via Playwright — it makes no
draft decisions itself) plus Claude as the actual decision-maker. Built for
the AI-agent-vs-human league drafting on **2026-09-04, 4:00 PM
America/New_York**.

## Why two different prompts, two different runtimes

Testing turned up a hard constraint: Cowork's cloud sandbox (and its
device-bridge shell on a connected Mac) cannot make raw network calls to
`sleeper.com` — that traffic is blocked by the sandbox's network allowlist.
Sleeper's public *read* API is reachable there via Claude's `WebFetch` tool
(which is proxied, not subject to the block), but anything that *writes* —
joining a draft, submitting a pick, a waiver claim, a lineup change — needs
a real browser hitting the real site, which only exists on Julia's actual
computer.

So:

| | Runs where | Uses |
| --- | --- | --- |
| **Draft day** (`prompts/draft_day_prompt.md`) | A real local terminal on Julia's Mac, outside any Claude sandbox | The `sleeperdraft` Python library directly, via `scripts/sleeper_cli.py` |
| **In-season** (`prompts/season_prompt.md`) | A Cowork scheduled task | `WebFetch` for reads, `Claude in Chrome` for writes |

Draft day gets the battle-tested library (it exists specifically to survive
the draft room's virtualized list, stale DOM handles, and the rest — see the
[upstream README](https://github.com/aWarmWalrus/sleeperdraft)) run somewhere
with a real, unrestricted network. In-season moves are lower-stakes and
lower-frequency, so a Cowork scheduled task driving your real Chrome is a
reasonable trade for not needing you to hand-trigger anything weekly — with
the caveat that it only works while your Mac is on and Chrome is reachable.

## One-time setup

### 1. Sleeper accounts

Neither account is registered yet. Both need to happen before anything else:

1. Join the league yourself: https://sleeper.com/i/Y28zV4mJ692zj
2. Create a **second, separate** Sleeper account for the agent (different
   email), and register *that* account in the same league.
3. Once the commissioner sets up the draft, note the draft's URL — the id is
   the last path segment of `https://sleeper.com/draft/nfl/<draft_id>`.

### 2. Fill in `memory/league_context.md`

League id, draft id, roster ids, both display names, roster/scoring
settings — whatever's known at the time. The agent reads this file first
thing, every run.

### 3. Get a session token for the agent's account

Sleeper's login is behind hCaptcha, which automation can't reliably pass —
so instead of automating login, you obtain a token by hand once and the
library injects it directly:

1. Log in to sleeper.com in a normal browser **as the agent's account**.
2. DevTools → Console → run `localStorage.getItem("token")`.
3. Copy that string. Treat it like a password.

You'll also want your own token the same way if you ever want to check
`logged_in()` diagnostics against your own account, but the agent should
only ever hold *its own* account's token.

### 4. Local setup (for draft day)

```bash
git clone <this-repo-url>
cd sleeper-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# If that fails with a build-isolation/setuptools error, retry with:
#   pip install --no-build-isolation -r requirements.txt
```

Chrome/Chromium: the library prefers your system Chrome and falls back to
Playwright's bundled Chromium automatically, so `playwright install
chromium` is only needed if neither is already present — try without it
first.

Export the agent's credentials in the same shell you'll draft from:

```bash
export SLEEPER_USER="agent's_display_name"
export SLEEPER_TOKEN="eyJhbGciOi..."
export SLEEPER_HEADLESS=1   # 0 to watch the browser — worth doing at least once
```

Sanity-check reads (no browser, no risk):

```bash
python3 scripts/sleeper_cli.py turn <draft_id> <roster_id>
```

### 5. GitHub repo

Push this whole directory to a **private** repo you control. Nothing
secret is committed (`.gitignore` excludes tokens and the players cache) —
`SLEEPER_USER`/`SLEEPER_TOKEN` live only in your shell's environment, never
in git. The repo is what carries `memory/` (the agent's persistent notes)
and the prompts between runs, and what the season scheduled task will
`git clone` fresh each week — give it read access via a fine-grained PAT
scoped to just this repo when we wire up that scheduled task.

## Testing before it's real (do this — the draft has no do-overs)

Start a **mock draft** on Sleeper (no league needed) well before Sep 4:

1. In a normal browser, start a mock draft as the agent's account, note its
   `draft_id`.
2. Mock drafts have no roster/league, so get your slot with:
   `python3 scripts/sleeper_cli.py myslot <draft_id> <agent_username>`
3. Run a local Claude Code session in this directory: start `claude`, then
   paste the full contents of `prompts/draft_day_prompt.md` as your first
   message (swap in the mock's `draft_id`/slot if the league context file
   isn't filled in yet), and let it draft the whole mock. Watch it —
   `SLEEPER_HEADLESS=0` if you want to see the browser itself.
4. Confirm: it correctly detects its turn, finds and picks players
   (including ones far down the list — kickers/defenses are the best
   stress test, per the upstream README), posts/reads chat if it chooses
   to, and writes real reasoning to `memory/strategy_log.md`.

## Draft day runbook (2026-09-04, 4:00 PM ET)

1. Terminal open, in this directory, venv activated, `SLEEPER_USER` /
   `SLEEPER_TOKEN` exported for the *agent's* account.
2. Start `claude`, paste in `prompts/draft_day_prompt.md` as the first
   message.
3. Let it run. Check in periodically — a 10-14 team draft is a lot of
   rounds, and long unattended agent runs are exactly the case worth
   glancing at now and then rather than walking away entirely.

## In-season scheduled task

Once accounts, the draft, and the GitHub repo all exist, come back to
Cowork and we'll set up a recurring scheduled task whose prompt tells it to
clone the repo, read `prompts/season_prompt.md`, and follow it — reading
league state via `WebFetch` and acting through `Claude in Chrome`.

## Repo layout

```
prompts/
  draft_day_prompt.md   system prompt for the local, draft-day session
  season_prompt.md      system prompt for the Cowork in-season scheduled task
memory/
  league_context.md     who/where — filled in once accounts + draft exist
  strategy_log.md        the agent's own running log of what it did and why
scripts/
  sleeper_cli.py         thin CLI over the sleeperdraft library (draft day only)
requirements.txt
```

## A word on terms of service

Same caveat the upstream library gives: this automates a logged-in Sleeper
session. Sleeper's terms may restrict automated play — that's a real
consideration, and this was built for a league whose members opted in with
full knowledge of it.
