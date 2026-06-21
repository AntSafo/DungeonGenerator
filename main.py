"""Dungeon Generator - entry points live in examples/. See README.md for the full pipeline.

Quick starts:

  Single room (ChatGPT image backend; run examples/chatgpt_setup.py and log in first):
      python examples/generate_room.py --location "a vast medieval castle" \
          --room-type "throne room" --items "a treasure chest, a throne"

  A whole set of varied rooms:
      python examples/generate_set.py --set my-set

Running this file just prints these pointers.
"""


def main() -> None:
    print(__doc__)


if __name__ == "__main__":
    main()
