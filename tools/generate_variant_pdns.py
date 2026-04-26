"""Fetch real Lidraughts PDN game corpora for variants the test suite covers.

Each variant pulls master-level games from the top players on the relevant
Lidraughts leaderboard via the public ``/api/games/user`` endpoint, then
round-trips every PDN through ``BoardClass.from_pdn`` before writing the
corpus. Games that fail to parse or duplicate an existing site URL are
skipped.

Usage:
    python tools/generate_variant_pdns.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from draughts import (
    AntidraughtsBoard,
    BrazilianBoard,
    BreakthroughBoard,
    FryskBoard,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
GAMES_DIR = REPO_ROOT / "test" / "games"

# perfType -> (board class, ordered fallback usernames from the leaderboard)
VARIANTS = {
    "antidraughts": (
        AntidraughtsBoard,
        ["Master1958", "colinas", "GiliardY", "destruidor", "A134", "AnaAmelia"],
    ),
    "breakthrough": (
        BreakthroughBoard,
        ["piers", "hijkneuter", "Nick777", "Tendido", "MoussaBagayogo223", "YaminAblu"],
    ),
    "brazilian": (
        BrazilianBoard,
        ["JustNobody19", "wiilk", "DamirVinicius", "blacksssss", "Arzubeq", "Nyava"],
    ),
    "frysk": (
        FryskBoard,
        ["Karimov", "EdwinGuzman", "BK", "skyfke", "vladislavski", "kimmenno"],
    ),
}

GAMES_PER_VARIANT = 25
PER_USER_MAX = 50
SLEEP_BETWEEN_USERS = 2.0
PDN_SPLIT = re.compile(r"\n\n\n+")
SITE_RE = re.compile(r'\[Site "([^"]+)"\]')


def fetch_user_pdns(user: str, perf: str) -> list[str]:
    url = f"https://lidraughts.org/api/games/user/{user}?max={PER_USER_MAX}&perfType={perf}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/x-pdn", "User-Agent": "py-draughts-tests"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8", errors="replace")
    return [b.strip() for b in PDN_SPLIT.split(text) if b.strip() and "1." in b]


def collect(perf: str, board_cls, users: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for user in users:
        if len(out) >= GAMES_PER_VARIANT:
            break
        try:
            pdns = fetch_user_pdns(user, perf)
        except Exception as e:
            print(f"  {perf}/{user}: fetch failed: {e}", file=sys.stderr)
            continue
        kept = 0
        for pdn in pdns:
            if len(out) >= GAMES_PER_VARIANT:
                break
            site_match = SITE_RE.search(pdn)
            site = site_match.group(1) if site_match else None
            if site and site in seen:
                continue
            try:
                board = board_cls.from_pdn(pdn)
            except Exception:
                continue
            if not board._moves_stack:
                continue
            if site:
                seen.add(site)
            out.append(pdn)
            kept += 1
        print(f"  {perf}/{user}: fetched {len(pdns)}, kept {kept}, total {len(out)}/{GAMES_PER_VARIANT}")
        time.sleep(SLEEP_BETWEEN_USERS)
    return out


def generate_for_variant(name: str, board_cls, users: list[str]) -> None:
    out_dir = GAMES_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    games = collect(name, board_cls, users)
    if len(games) < GAMES_PER_VARIANT:
        print(f"  WARNING: only {len(games)} games for {name}", file=sys.stderr)
    out_path = out_dir / "random_pdns.json"
    out_path.write_text(json.dumps({"pdn_positions": games}, ensure_ascii=False, indent=2))
    print(f"{name}: wrote {len(games)} games -> {out_path.relative_to(REPO_ROOT)}")


def main() -> None:
    for name, (board_cls, users) in VARIANTS.items():
        print(f"\n=== {name} ===")
        generate_for_variant(name, board_cls, users)


if __name__ == "__main__":
    main()
