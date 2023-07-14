from draughts.utils import logger
from draughts.standard import Board
from pathlib import Path
import requests
from time import sleep
import json

target_file = Path(__file__).parent / "random_positions.json"

ENDPOINT = "https://lidraughts.org/tv/feed"

proxies = {
    "https": "http://proxy-lab.krk-lab.nsn-rdnet.net:8080",
    "http": "http://proxy-lab.krk-lab.nsn-rdnet.net:8080",
}


def get_games_fens():
    s = requests.Session()
    a = 5
    max_val = 30
    input_data = {"positions": []}
    with s.get(ENDPOINT, proxies=proxies, stream=True) as resp:
        for line in resp.iter_lines():
            if 1000 < len(line) or len(line) < 10:
                logger.info(len(line))
                continue
            if a > 0:
                a -= 1
                continue
            max_val -= 1
            json_data = line.decode("utf-8").lstrip("data: ")
            try:
                data = json.loads(json_data)
            except json.decoder.JSONDecodeError as e:
                logger.error(f"{line}  {e}")
                continue
            try:
                fen_value = data["d"]["fen"]
            except KeyError:
                continue
            logger.debug(fen_value)
            input_data["positions"].append(fen_value)
            if max_val == 0:
                with open(target_file, "a") as f:
                    json.dump(input_data, f)
                break
            a = 5


if __name__ == "__main__":
    get_games_fens()
