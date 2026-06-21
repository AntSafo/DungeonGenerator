# Room Presets & Reference Sizes

Locked values for step 3. Coordinate frame: origin back-left, +x toward viewer
(depth), +y right (width), +z up (height). All integer centimeters.

---

## Room-size presets (Locked)

"Length" = depth (x, toward camera); "width" = y. Smaller rooms are long-and-narrow
so the horizontal extent fits the camera frame; the grand room is deliberately the
widest (a hall, not a bedroom) and above residential norms.

| preset | depth × width | ratio | area | ceiling (z) | grid cell (d × w) |
|---|---|---|---|---|---|
| small  | 400 × 200 | 2:1 | 8.0 m²  | 240 | 100 × 50 |
| medium | 360 × 360 | 1:1 | 13.0 m² | 260 | 90 × 90 |
| large  | 528 × 352 | 3:2 | 18.6 m² | 290 | 132 × 88 |
| grand  | 432 × 648 | 2:3 | 28.0 m² | 340 | 108 × 162 |

**Divisible-by-8 invariant:** every depth/width is divisible by 8 so that, with a
4×4 grid, each cell size (dim/4) is even and every cell *center* lands on an integer
cm. This is why large is 528×352 rather than a rounder 540×360 (540/4 = 135 → half-cm
centers). The odd numbers are never user-visible.

## Grid (Locked)
- **4×4** per room (16 cells, no center cell — discourages over-centering).
- A cell center is `cell_size * i + cell_size/2`. Placement = chosen cell center +
  per-axis discrete (whole-cm) offset.

---

## Reference-size ladder (Locked)

These are **calibration yardsticks, not a furniture catalog**. They are well-known
objects (mostly things that never appear in the rooms), each named by precise kind,
spanning tiny→large. The layout model sizes a dungeon object *relatively* against
these ("about waist-high on a person, ~3 bricks deep") to preserve size variety —
it must NOT copy a yardstick as the canonical size of a category.

| object (precise kind) | size (cm) | ladder role |
|---|---|---|
| 330 ml soda can | ⌀6.6 × 11.5 | tiny cylinder |
| standard house brick | 21.5 L × 10 W × 6.5 H | tiny box ("how many bricks") |
| 750 ml wine bottle | ⌀7.5 × 30 | small, tall-and-thin |
| regulation basketball | ⌀24 | small sphere |
| 55-gallon steel drum | ⌀61 × 86 | large cylinder |
| average adult human (standing) | 170 H × ~40 shoulders × ~28 deep | **primary human anchor** |
| standard interior door | 81 W × 203 H | human-scale opening (height + width) |
| upright refrigerator | 80 W × 65 D × 178 H | large box |
| average sedan car | 445 L × 183 W × 150 H | very large (grand-room scale) |

## Reference mount heights (Locked, defaults — offset allowed)

For wall-mounted objects, the layout model centers the object near a reference
height and applies a discrete vertical offset (so heights vary):

| mount type | reference center height (z, cm) |
|---|---|
| painting / portrait | 150 |
| mirror | 150 |
| wall sconce / torch | 170 |

---

## Sources
Furniture/room references: [First in Architecture (bricks)](https://www.firstinarchitecture.co.uk/standard-brick-sizes/),
[Crown (330 ml can)](https://www.crowncork.com/beverage-packaging/products/beverage-cans/113oz-330ml-standard),
[Dimensions.com (wine bottle)](https://www.dimensions.com/element/wine-bottle-750-ml-standard),
[Dimensions.com (basketball)](https://www.dimensions.com/element/basketball),
[BascoUSA (55-gal drum)](https://bascousa.com/blog/55-gallon-drum-dimensions-height-weight),
[Healthline (shoulder width)](https://www.healthline.com/health/average-shoulder-width),
[Door'n'More (interior door)](https://www.doornmore.com/help/what-is-the-standard-size-for-residential-homes.html),
[Whirlpool (fridge)](https://www.whirlpool.com/blog/kitchen/guide-to-refrigerator-sizes-dimensions.html),
[ExtraSpace (car)](https://www.extraspace.com/blog/self-storage/average-car-dimensions/),
[Planner5D (bedroom sizes)](https://planner5d.com/blog/standard-bedroom-size/),
[Cedreo (bedroom size)](https://cedreo.com/blog/average-bedroom-size/).
