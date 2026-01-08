import json
import random
from pathlib import Path

import requests

from loguru import logger

target_file = Path(__file__).parent / "random_pdns.json"

# Example tournaments – replace / expand with any IDs you like
# You can find IDs on the website, then use /api/tournament/{id}/games for PDN
TOURNAMENT_IDS = [
    "nyEd2LP6",  # example from docs/forum
]

API_TEMPLATE = "https://lidraughts.org/api/tournament/{id}/games"


def fetch_tournament_pdn(tournament_id: str) -> str:
    url = API_TEMPLATE.format(id=tournament_id)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text  # raw PDN text


def split_pdn_games(pdn_text: str) -> list[str]:
    # Very rough splitter: games separated by blank lines
    games = []
    current = []

    for line in pdn_text.splitlines():
        if line.strip() == "":
            if current:
                games.append("\n".join(current).strip())
                current = []
        else:
            current.append(line)

    if current:
        games.append("\n".join(current).strip())

    # Filter out any tiny fragments
    return [g for g in games if len(g) > 40]


def get_random_pdns(n: int = 30):
    all_games: list[str] = []

    # Collect PDNs from a few tournaments
    for tid in TOURNAMENT_IDS:
        try:
            pdn_text = fetch_tournament_pdn(tid)
        except Exception as e:
            logger.error(f"Error fetching tournament {tid}: {e}")
            continue

        games = split_pdn_games(pdn_text)
        logger.info(f"Fetched {len(games)} games from {tid}")
        all_games.extend(games)

    if not all_games:
        logger.error("No games fetched; check tournament IDs or API availability")
        return

    # Sample without replacement if possible
    n = min(n, len(all_games))
    sampled = random.sample(all_games, n)

    output = {"pdn_positions": sampled}
    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {n} random PDNs to {target_file}")


if __name__ == "__main__":
    get_random_pdns()
