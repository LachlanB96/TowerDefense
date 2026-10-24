# Mission control — page and state contracts (modev4)

The page (`_tools/gallery/v4.html`, served at `http://localhost:8777/v4.html`) is
**the Gloomfell suite** (2026-08-12): fleet overview → per-asset war room (tabs
Overview · Live · Compare) → design dossier slide-over. It polls static files only;
the server computes nothing. Its script is TypeScript, `_tools/gallery/v4.ts` (since
2026-10-24). **Reload the page after editing either file** — `serve.py` copies the
page into the previews root and bundles `v4.ts` there as `v4.js` with Bun (with a
source map, `v4.js.map`), at startup and again whenever a request for the page finds
a source changed (build output: never edited or committed). The old URLs `/`,
`/index.html` and `/live.html` are server redirects into the suite (they map
`?asset=x` onto the router), so they can never show stale data. Schemas here must stay byte-compatible with the page
source (`v4.ts`, whose interfaces mirror them); when you change one, change both and
grep the other skill docs for the field name.

**One session per asset, since 2026-10-24.** The supervisor and the per-asset shepherd
are one thing now: the Claude session that owns the asset (`SKILL.md`). Several asset
sessions can run at once, each in its own LBTerm tab, sharing this page, the chat, the
feed and `fleet.json`. The files and fields below are the ones the page has always
read; only who writes them changed. Where the page's own text says "supervisor" (the
chat's other side, empty states) or "shepherd heartbeat", read "the asset's session":
the labels are the page's and are unchanged.

## Who writes which file

All paths relative to `Assets/Blender/_previews~/`. UTF-8 always. Append-only JSONL
readers tolerate a torn final line; rewritten JSON uses temp-file + `os.replace`.

| File | Writer | Reader(s) |
|---|---|---|
| `chat.jsonl` | the page, via `POST /chat` — **user-authored by construction** | every asset session, page |
| `feed.jsonl` | the asset sessions (directly, never via HTTP), each line naming its `asset` | page |
| `fleet.json` | the asset sessions, **each writing only its own entry** | page |
| `<asset>/pipeline.json` | that asset's session | page |
| `<asset>/live.json` | that asset's tap process (one per session) | page |
| `<asset>/control.json` | that asset's session only (the user's channel); the session that ran genesis writes a new asset's first one | that session, page (read-only dials) |
| `<asset>/design-queue.jsonl` | that asset's session (user designs from chat, agent designs from designer batches) | that session, page via pipeline digest |
| `<asset>/attempts.jsonl`, `<asset>/champion.json` | that asset's session via `record.py` | everyone, **including the page** (dossier, ratchet, run attribution, champion lineage) |
| `<asset>/user-signals.jsonl`, `<asset>/user-directives.jsonl` | the page via `POST /signal` / `POST /directive` (existing) | that session, page (reflects marks / pending directives) |
| `<asset>/latest.json`, `<asset>/run-NNN/manifest.json` | `preview.py` | page (Compare tab) |
| `<asset>/session.json` | that asset's session | that session and the next one for the asset; **not the page** |
| `_claims/chat-<N>/` | the first session to `mkdir` it, claiming chat line N | the other sessions (they leave that line alone) |
| `_logs/` | the gallery server's and each tap's redirected stdout/stderr | people |

Instructions never share a door with status: chat and feed are separate files with
separate writers, exactly like directives vs signals.

## Schemas

`POST /chat` body — `{"text": str (required, 1..2000 after strip), "asset": str
(optional, `^[A-Za-z0-9_-]{1,64}$`)}` → 204, appends to `chat.jsonl`:

```json
{"at": "2026-08-10T12:00:00", "from": "user", "text": "more aura", "asset": "mage000"}
```

`feed.jsonl` line (an asset session's reply): same shape with `"from": "supervisor"`
(the page's name for the session's side) and `asset` always set, since several sessions
share the feed. The page merges both by `at` (ties: user first) and shows the last 200.

`fleet.json` (shared by the asset sessions: each re-reads it right before writing,
replaces only its own entry and `stamped`, keeps every other entry as found, and
writes it with temp-file + `os.replace`; it republishes its entry every pass, so a lost
update heals by itself; `makers` is the dial after the budget clamp):

```json
{"stamped": "2026-08-10T12:00:00", "note": "",
 "assets": [{"asset": "mage000", "state": "run", "makers": 2, "queue": 3,
             "accepted": 5, "staged": 0, "note": "d07 wave rendering"}]}
```

`<asset>/pipeline.json` (that asset's session, republished with a fresh `heartbeat`
every pass, and at least every 60 s while the state is `run`: the session's watch wakes
it when its heartbeat reaches 60 s, so the page's amber at 90 s means the session
itself is dead or blocked):

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
first. `note` carries the session's subagent budget line every pass (`agents 5/8: 2
makers, 1 designer, 2 reviewers · cap 4 (a render waits for the GPU) · d07 waits for a
reviewer slot`); clamps of the dials are also `events` lines. `makers[].status` is free
text shown verbatim, including `waiting for a slot` and `queued for the GPU: <reason>`. `last_margins` are signed ints (sign toward the challenger). `origin` is
`user` | `agent` — the page labels agent work explicitly (provenance law).

`<asset>/session.json` (that asset's session; the page never reads it):

```json
{"asset": "mage000", "session": "<CLAUDE_CODE_SESSION_ID>", "started": "2026-10-24T12:00:00",
 "chat_line": 42,
 "running": [{"agent": "<agent id>", "role": "maker", "design": "d07", "since": "2026-10-24T12:03:00"},
             {"agent": "<agent id>", "role": "reviewer", "design": "d05", "judge": "j2",
              "since": "2026-10-24T12:04:00"}],
 "makers": {"d07": {"agent": "<agent id>", "label": "m1"}}}
```

`chat_line` is how many lines of `chat.jsonl` the session has handled. `running` is
every subagent with a turn in flight (the slot count); `makers` maps each design to
its maker's agent id, for resuming it. A session that finds another session's id here
with a heartbeat under 300 s old leaves the asset alone; with an older one it takes the
asset over and reconciles. Rewritten with temp-file + `os.replace`, like every JSON
file here.

`<asset>/live.json` and `<asset>/champion.json` keep their existing shapes (`tap.py`
and `record.py` respectively); the page builds the champion image path as
`/<asset>/run-NNN/<sheet>` with the run zero-padded to 3.

## Page behaviour the tools rely on

- **Routes** (hash-based): `#/` fleet overview · `#/a/<asset>` war room Overview tab ·
  `#/a/<asset>/live` Live tab · `#/a/<asset>/compare` Compare tab ·
  `#/a/<asset>/d/<design>` dossier slide-over. Legacy `?asset=<name>` links (and the
  old `/`, `index.html` and `live.html` URLs, which `serve.py` redirects) map onto
  these on load. Clicking a fleet-strip card refocuses and rewrites the URL.
- Poll cadence: focused asset's pipeline + chat/feed at 1 s; fleet, `assets.json`,
  champion, `control.json` (read-only dials display), signals/directives and other
  assets' pipelines at 5 s; `live.json` at 1 s **only while the Live tab is mounted**;
  `latest.json` only while the Compare tab is mounted, with prior manifests fetched
  once and memoized (immutable). `attempts.jsonl` is gated by a HEAD
  content-length/mtime check so a large file is re-parsed only when it actually grew.
  `?t=` cache-bust on JSON/JSONL only, **never images** (renders are immutable).
- A missing file is an **empty state naming the producer and the exact command**
  (tap, preview.py, supervisor — the asset's session), never an error. The red banner
  means one thing only: the server itself did not answer three polls running. Torn
  final JSONL lines are skipped; unknown `kind`s in `attempts.jsonl` are skipped.
- Heartbeat badge: amber ≥ 90 s, red ≥ 300 s ("stuck?"), only while that asset's
  state is `run`; the heartbeat is the asset session's own. Fleet state wins over
  `pipeline.json.state` over `control.json`.
- The **needs-you inbox** (top-bar bell + fleet view) aggregates: `staged[]` entries,
  stale heartbeats while `run`, and paused assets holding staged work.
- **Verb buttons never POST silently**: Promote / add-design pre-fill the chat input
  and the user presses Enter — a chat.jsonl line is user-authored by construction.
  Star/cross and rework/revert/resurrect go through the existing `/signal` and
  `/directive` doors with `attempt` set to the page's row key
  (`<design>·a<attempt>·r<run>`).
- The chat scope toggle appends `asset` to the POST body for the focused asset.
- NEW-since-last-look watermark: per-asset localStorage snapshot keyed by row; "mark
  seen" commits; hiding the tab commits; archive rotation resets it via a generation
  signature.
- Testing: `GLOOMFELL_PREVIEW_ROOT` env var points `serve.py` at a scratch root
  (never test POST doors against the live previews root).

## The chat verbs (floor, not parser)

`stop` · `pause <asset>` · `resume <asset>` · `status` ·
`add design <asset>: <text>` · `new <hero|npc|tower> [name]: <desc>` · `new N npcs` ·
`makers <asset> N` · `designers <asset> N` · `promote <design>` · `finish <asset>` —
each asset session interprets anything else in context, for the lines that are its own
(`SKILL.md`, "Several sessions, one page"). This list appears in three places: here, SKILL.md's table,
and the page's hint line; keep them identical.
