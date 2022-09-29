import argparse
import json
import logging.config

from spike.bot import Spike


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=str, required=True)
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    logging.config.dictConfig(config["logging"])

    spike = Spike(config["spike"])
    spike.run()


if __name__ == "__main__":
    main()
