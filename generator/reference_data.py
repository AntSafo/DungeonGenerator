"""Locked reference data the layout model is given (see docs/room-presets-and-reference-sizes.md).

The ladder is a set of calibration yardsticks — the model sizes dungeon objects
*relatively* against these, it must never copy a yardstick as a category's size.
"""

# (precise object kind, human-readable size). Spans tiny -> large.
REFERENCE_LADDER = [
    ("330 ml soda can", "diameter 6.6, 11.5 tall"),
    ("standard house brick", "21.5 long x 10 wide x 6.5 tall"),
    ("750 ml wine bottle", "diameter 7.5, 30 tall"),
    ("regulation basketball", "diameter 24"),
    ("55-gallon steel drum", "diameter 61, 86 tall"),
    ("average adult human (standing)", "170 tall, ~40 across shoulders, ~28 deep"),
    ("standard interior door", "81 wide x 203 tall"),
    ("upright refrigerator", "80 wide x 65 deep x 178 tall"),
    ("average sedan car", "445 long x 183 wide x 150 tall"),
]

# Reference CENTER height (cm) for wall-mounted objects; the model applies a small
# vertical offset around these so heights vary.
MOUNT_HEIGHTS = {
    "painting / portrait": 150,
    "mirror": 150,
    "wall sconce / torch": 170,
}
