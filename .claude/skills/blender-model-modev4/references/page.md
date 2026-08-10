# Mission control — page and state contracts (modev4)

The page (`_tools/gallery/v4.html`, served at `http://localhost:8777/v4.html`) polls
static files only; the server computes nothing. **Restart `serve.py` after editing any
gallery page** — pages are copied into the previews root at startup. Schemas here must
stay byte-compatible with the page source; when you change one, change both and grep
the other four skill docs for the field name.

## Who writes which file

All paths relative to `Assets/Blender/_previews~/`. UTF-8 always. Append-only JSONL
readers tolerate a torn final line; rewritten JSON uses temp-file + `os.replace`.

| File | Writer | Reader(s) |
|---|---|---|
| `chat.jsonl` | the page, via `POST /chat` — **user-authored by construction** | supervisor, page |
| `feed.jsonl` | supervisor (directly, never via HTTP) | page |
| `fleet.json` | supervisor | page |
| `<asset>/pipeline.json` | that asset's shepherd | page, supervisor |
| `<asset>/live.json` | the tap process | page |
| `<asset>/control.json` | supervisor only (the user's channel) | shepherd |
| `<asset>/design-queue.jsonl` | supervisor (user designs) + shepherd (agent designs) | shepherd, page via pipeline digest |
| `<asset>/attempts.jsonl`, `<asset>/champion.json` | shepherd via `record.py` | everyone |
| `<asset>/user-signals.jsonl`, `<asset>/user-directives.jsonl` | the page via `POST /signal` / `POST /directive` (existing) | shepherd |

Instructions never share a door with status: chat and feed are separate files with
separate writers, exactly like directives vs signals.

## Schemas

`POST /chat` body — `{"text": str (required, 1..2000 after strip), "asset": str
(optional, `^[A-Za-z0-9_-]{1,64}$`)}` → 204, appends to `chat.jsonl`:

```json
{"at": "2026-08-10T12:00:00", "from": "user", "text": "more aura", "asset": "mage000"}
```

`feed.jsonl` line (supervisor replies): same shape with `"from": "supervisor"`.
The page merges both by `at` (ties: user first) and shows the last 200.

`fleet.json` (supervisor):

```json
{"stamped": "2026-08-10T12:00:00", "note": "",
 "assets": [{"asset": "mage000", "state": "run", "makers": 2, "queue": 3,
             "accepted": 5, "staged": 0, "note": "d07 wave rendering"}]}
```

`<asset>/pipeline.json` (shepherd, republished with a fresh `heartbeat` every cycle):

```json
{"asset": "mage000", "heartbeat": "2026-08-10T12:00:05", "state": "run",
 "note": "",
 "makers": [{"id": "m1", "design": "d07", "attempt": 2, "status": "rendering"}],
 "queue": [{"id": "d09", "origin": "user", "summary": "raven on the shoulder"}],
 "designs": [{"id": "d07", "summary": "torn hem", "origin": "agent",
              "status": "refining", "attempts": 2, "last_margins": [1, 1],
              "staged": false, "chips": []}],
 "staged": [{"design": "d05", "run": 412, "cell": 3, "margins": [2, 2],
             "chips": ["INV-4 detached"], "at": "2026-08-10T11:58:00"}],
 "events": [{"at": "2026-08-10T11:59:00", "text": "d07 a2: send back (+1,+1)"}]}
```

`events` is **append-order (oldest first, keep ~30)**; the page displays the newest 15
first. `last_margins` are signed ints (sign toward the challenger). `origin` is
`user` | `agent` — the page labels agent work explicitly (provenance law).

`<asset>/live.json` and `<asset>/champion.json` keep their existing shapes (`tap.py`
and `record.py` respectively); the page builds the champion image path as
`/<asset>/run-NNN/<sheet>` with the run zero-padded to 3.

## Page behaviour the tools rely on

- Poll cadence: pipeline/live/chat at 1 s; fleet/champion at 5 s; `?t=` cache-bust on
  JSON/JSONL only, never images.
- A missing file is an **empty state**, never an error. The red banner means one thing
  only: the server itself did not answer three polls running.
- Heartbeat badge: amber ≥ 90 s, red ≥ 300 s, only while that asset's state is `run`.
- `?asset=<name>` deep-links focus; clicking a fleet card refocuses and rewrites the
  URL.
- The chat scope toggle appends `asset` to the POST body for the focused asset.

## The chat verbs (floor, not parser)

`stop` · `pause <asset>` · `resume <asset>` · `status` ·
`add design <asset>: <text>` · `new <hero|npc|tower> [name]: <desc>` · `new N npcs` ·
`makers <asset> N` · `promote <design>` · `finish <asset>` — the supervisor interprets
anything else in context. This list appears in three places: here, SKILL.md's table,
and the page's hint line; keep them identical.
