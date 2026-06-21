# Step 2 — Creative Pass: Design

The creative pass turns the user's brief into the room's creative identity and a
cohesive, fully-populated arrangement that step 3 will realize geometrically. It is
the **source of truth for object descriptions** — later stages reference objects by
ID and never re-describe them.

> Implementation (exact prompts, model, structured-output enforcement) is deferred —
> this is mostly LLM prompt-tuning. This doc captures the agreed design.

---

## Inputs
- **Setting prompt**: brief text describing the dungeon/setting this room sits in.
- **Key location descriptions**: descriptions of notable nearby locations.
- **Distances**: distance from this room to each key location. **Creative flavor
  only** — distances influence tone/reactivity and the room-size preset choice, never
  geometry directly.

## Outputs (the `room.json` slice of the room schema)
1. **Identity** — location type, key physical characteristics, overall tone/feel.
2. **Size preset** — one of the 4 fixed room-size presets (this is the only way the
   creative pass touches geometry).
3. **Objects** — each with a **stable ID**, a name, and a thematic description.
   Descriptions are authored here and referenced by ID everywhere downstream.
4. **Groupable sets** — semantic flags for objects that may form a unit (e.g.
   {table, chairs}). Purely semantic; geometry/merge decisions happen in step 3.
5. **Arrangement prose** — a cohesive creative description of the room that places
   **every object relative to the others**. This is the "established logic" of the
   room; it preserves cohesion and reduces step-3 corner-painting.
6. **Per-object placement notes** — a short note per object (location + named
   relationships to other object IDs), derived from the arrangement prose.

## Process (two passes within step 2)
1. **Creative + arrangement pass**: produce identity, size preset, objects,
   groupable sets, and the arrangement prose — requiring that prose to mention
   **all** objects with relative locations.
2. **Placement-note extraction pass**: for each object, derive a short structured
   placement note from its description in the prose. If the prose accidentally
   omitted an object, this pass is **forced to assign it an adequate spot**.

The free-prose arrangement is kept (cohesion); the structured notes are what step 3
consumes. Prose also feeds step 5's image prompt.

**Fallback**: if one combined step-2 call produces weak arrangements, split into
step 2 (theme + objects) and step 2.5 (arrangement) — a cheap, isolated change.

---

## Locked
- Distances are creative-only; they influence tone + preset choice, not geometry.
- Objects get stable IDs here; downstream references are by ID only.
- Step 2 outputs both an all-objects arrangement prose **and** per-object placement
  notes (notes derived from the prose; omitted objects forced a spot here).
- Groupable sets are flagged here (semantic only).
- **Front-wall entry door**: the front wall (the viewer's wall at max x — where the
  camera looks from) always carries the entry door, roughly centered at the viewer's
  vantage. The arrangement keeps the floor immediately in front of the door / along the
  camera sightline clear of large objects, so the view into the room isn't blocked.
  (Naming: front wall = viewer's wall at max x; back wall = the opposite, framed
  backdrop at x=0.)

## Open Questions
- **Object sizing** (assumption below, pending confirm): concrete cm dimensions are
  **not** set in step 2. Step 3 assigns sizes (seeded by the reference-size table);
  step 2 may only express *qualitative* size intent in a description ("an oversized
  oak table"), which step 3 honors. Rationale: keep quantitative reasoning in step 3.
- Exact prompts, model choice, and structured-output schema.
- The 4 room-size presets and the reference-size list.
