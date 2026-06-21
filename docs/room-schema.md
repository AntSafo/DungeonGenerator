# Room Schema

The room schema is the **canonical data structure and contract between pipeline
stages** — the single source of truth for everything known about the room so far.
Two projections are derived from it:
- **Persisted artifacts** on disk (`01_room.json`, `02_layout.json`, …) for
  inspection, caching, and re-running a stage in isolation.
- **Model-facing views** fed into each LLM call — possibly a tailored / partial
  serialization, not necessarily the raw storage JSON.

Conventions inherited from [step3-spatial-layout-design.md](step3-spatial-layout-design.md):
integer centimeters everywhere; origin back-left; +x toward viewer, +y right, +z up.

This doc fully specifies the **`room.json` (step-2) slice** (what the fixtures
populate) and sketches the later slices.

---

## `room.json` — creative-pass output (fully specified)

```jsonc
{
  "schemaVersion": 1,
  "runId": "string",                  // identifies one end-to-end run

  "input": {                          // echo of the brief, for traceability
    "settingPrompt": "string",
    "keyLocations": [
      { "name": "string", "description": "string", "distanceCm": 0 }
    ]
  },

  "identity": {
    "locationType": "string",         // e.g. "abandoned shrine antechamber"
    "characteristics": "string",      // key physical traits
    "tone": "string"                  // mood / feel
  },

  "surfaces": {                       // room-shell finishes — NOT objects
    "floor":   { "material": "string", "texture": "string" },   // e.g. "flagstone" / "worn, damp"
    "ceiling": { "material": "string", "texture": "string" },
    "walls": {                        // per-wall finishes (origin back-left, +x toward
      "back":  { "material": "string", "texture": "string" },   //   viewer): back = x0 wall (backdrop),
      "front": { "material": "string", "texture": "string" },   //   front = x-max wall (viewer/camera wall, entry door),
      "left":  { "material": "string", "texture": "string" },   //   left = y0 wall,
      "right": { "material": "string", "texture": "string" }    //   right = y-max wall
    }
  },

  "sizePreset": "small | medium | large | grand",   // 1 of 4 (dims TBD per preset)

  "objects": [
    {
      "id": "obj_01",                 // stable ID; referenced by ID everywhere
      "name": "string",
      "description": "string",        // thematic; may carry qualitative size intent
      "role": "floorCovering",        // optional; absent = normal object. "floorCovering"
                                      //   sets the locked no-collide/underlay flag + layer-1 order
      "groupableSetId": "grp_01"      // optional; present iff in a groupable set
    }
  ],

  "groupableSets": [
    { "id": "grp_01", "memberIds": ["obj_03", "obj_04"] }   // semantic only
  ],

  "arrangementProse": "string",       // cohesive description placing ALL objects
                                      //   relative to one another

  "placementNotes": [                 // one per object, derived from the prose
    {
      "objectId": "obj_01",
      "note": "string",               // short location summary
      "relationships": [              // named, to other object IDs / structure
        { "type": "adjacency | support | onWall | onCeiling | nearWall | under",
          "targetId": "obj_03 | null" }   // null target = relative to a wall/structure
      ]
    }
  ]
}
```

Notes:
- No concrete cm sizes or coordinates here — those are step-3 outputs (see Open
  Questions in the step-2 doc). `description` may hint size qualitatively.
- `relationships.type` values map to the locked Merge/Attach + anchor concepts:
  `support` → z-stacking (cup on table); `onWall`/`onCeiling` → mount anchors;
  `adjacency` → Attach adjacency; `nearWall` → floor placement biased against a wall
  (not mounted); `under` → placed centered beneath the target object, on its own layer
  (a small carpet under a table). `adjacency`/`support`/`under` target another object;
  `onWall`/`onCeiling`/`nearWall` use `targetId: null` (relative to room structure).
- "Full-floor texture" is **not** an object — it's part of `surfaces.floor`. A rug
  *object* is always a smaller carpet.
- A **floor covering is marked by `role: "floorCovering"`** (sets the no-collide /
  underlay flag). An object resting *over* a covering needs no relationship (the flag
  prevents a false collision); but a covering MAY use `under` to sit centered beneath a
  companion object. Coverings are always **positioned, never Merged** — a flat covering
  merged with a tall object would make a wrongly tall bounding volume for the depth map.

---

## `layout.json` — spatial-pass output (sketch; finalized when we build step 3)

Per placed region (one object, or one Merge composite):
- `id`, `objectIds` (>1 only for a Merge composite)
- `footprint`: `{ "shape": "rect", "wCm", "dCm" }` or `{ "shape": "circle", "rCm" }`
- `center`: `{ "xCm", "yCm" }` (chosen cell center + per-axis discrete offset)
- vertical extent: `zBottomCm`, `zTopCm`
- `anchor`: `{ "type": "floor | wall | ceiling | on", "refId": "obj_xx | null" }`
- `relationship`: `"merge" | "attach" | null`
- `noCollide`: bool (true for floor coverings)
- assigned sizes live here (sizing is step-3's job, seeded by the reference table)

## Later slices (high-level)
- Render artifacts: `03_wireframe.png`, `03_depth.png` (shared canonical resolution).
- `04_prompt.txt`: assembled image prompt (tone + placement).
- `05_render.png`, `06_ascii.txt`.

See [savedOutputs/README.md](../savedOutputs/README.md) for the on-disk run layout.
