# Step 3 — Spatial Layout: Design Decisions

This document records decisions for the spatial-layout stage (step 3 of the room
pipeline). **Only mutually-agreed ("locked") decisions go in the Locked section.**
Anything still under discussion lives in Open Questions.

---

## Locked

### Coordinate system
- Origin at the **back-left corner** of the room.
- **+x** points toward the viewer (out of the back wall), **+y** points right,
  **+z** points up. This is a right-handed system.

### Units
- **Integer centimeters everywhere** — object sizes, positions, and offsets are
  all whole-cm integers. No decimals anywhere in the layout.

### Room size
- The room footprint/height is chosen from **4 fixed size presets**; the creative
  pass (step 2) picks which preset a given room uses. (Specific preset dimensions: TBD.)

### Object identity
- The creative pass assigns each item a **stable ID**. The spatial pass references
  objects **by ID only** — it never re-describes them in free text.

### Placement model
- Non-relational placement is **center-based**: position is the location of the
  object's center.
- Placement is **coarse cell + fine offset**: pick a cell in a fixed-cell-count
  grid (cell count is constant across rooms; cell size scales with the preset),
  then apply a **per-axis discrete (whole-cm) offset** from the cell center.
- Offset is **per-axis** so a relational placement can pin one axis while leaving
  the other free to vary.

### Placement order — role-based layers
Placement proceeds in this layer order (hard rule); the model has discretion
*within* a layer:
1. Floor coverings (rugs, carpets) — the ground layer.
2. Large floor anchors (bed, table, dresser).
3. Smaller floor objects, placed relative to anchors (nightstand, stool, chest).
4. Surface objects (on tables/shelves) — require their support to exist already.
5. Wall-mounted objects (paintings, mirror, torches).
6. Ceiling-hung objects (chandelier).

- **Floor coverings carry a "no-collide / underlay" flag** and are exempt from the
  overlap check, so floor objects may sit on top of them without being flagged.

### Region relationships — Merge / Attach taxonomy
- **Merge (composite region):** members collapse into a single region; internal
  arrangement is text-only; depth/wireframe shows one primitive. For heavily
  interpenetrating sets (table + chairs). The composite region is a single
  **axis-aligned bounding box** enclosing all members' footprints, with z spanning
  `min(z_bottom) .. max(z_top)`. Member IDs are retained for the legend/text; the
  geometry is that one region. (Default to a box even for cylinder members; a
  bounding cylinder is a possible later refinement.)
- **Attach (separate regions, related position):** member keeps its own region but
  its per-axis position and/or `z_bottom` is defined relative to an anchor object.
  - *Adjacency* flavor: e.g. nightstand beside bed (one axis pinned, other free).
  - *Support/stacking* flavor: e.g. goblet's `z_bottom` = table's `z_top`.

### Grouping & merge trigger
- The **creative pass flags "groupable sets"** — a purely semantic judgment about
  which objects may form a unit (e.g. {table, chairs}), made without geometry.
- The spatial pass uses overlap only as a trigger, **gated by the flag**:
  - Overlap **within a flagged groupable set** → legitimate → **Merge**. Any amount
    of overlap triggers it (no threshold, for now; revisit if results get strange).
  - Overlap of a **non-flagged** pair, or with walls/room bounds → **unintended
    collision → repair** (see below). Overlap alone is never treated as "should group."

### Validator repair (single-phase placement)
Placement is single-phase (no hardcoded coarse capacity allocation — object rotation
and packing make a reliable capacity check infeasible). Unintended collisions are
resolved in escalating order:
1. **Deterministic nudge/jiggle**: shift the offending object to the nearest
   non-colliding position (and try minor reorientation) in code — no LLM, no cost.
2. **Restructuring LLM**: if nudging fails, an LLM re-places the objects **up to and
   including the offending item**; normal sequential placement then **resumes from
   the next item** onward. Bounds the rework and gives a clean handoff.
   - The restructuring pass **preserves existing Merge/Attach relationships** among
     the items it re-places (don't tear a nightstand off its bed unless necessary).
3. **Bounded attempts + fallback**: cap the repair rounds; if still unresolved, drop
   the lowest-priority offending object and `log()` it (no silent truncation, no
   infinite loop).

### Wall mounting
- Each wall-mountable object type has a **reference mount height**, with a
  **discrete vertical offset** allowed around it (so not every painting hangs at
  the same height; a mirror differs from a painting). Wall objects therefore have
  two offset dimensions: along-wall (horizontal) and vertical.

---

## Agreed in principle (specifics TBD)
- **Reference size table**: give the layout model reference sizes (in cm) for
  common items to calibrate scale. Helps more under cm than meters. Exact list TBD.

---

## Inputs from earlier stages
- Step 3 consumes the **creative arrangement prose + per-object placement notes**
  produced by the creative pass (step 2 — see its design doc). Step 3 *realizes* that
  established arrangement as integer-cm geometry rather than placing ad-hoc.

## Open Questions
- **Wireframe vs. depth-map conditioning** for step 6: to be decided empirically;
  renderer should be able to emit both. (Deferred to step 6.)
- Specific room-size presets, grid cell count, and reference-size list.
