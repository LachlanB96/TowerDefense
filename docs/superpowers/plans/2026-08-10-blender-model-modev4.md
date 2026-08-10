# Blender Model Mode v4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/blender-model-modev4` — a scalable fleet workflow (supervisor → per-asset shepherds → per-design makers → fresh reviewer panels) with a mission-control web page and page-embedded chat, per the approved spec `docs/superpowers/specs/2026-08-10-blender-model-modev4-design.md`.

**Architecture:** The unit of concurrency is the *design*: makers propose JSON variant rows (zero merge surface) rendered by the existing `preview.py`/`axis.py`/`orbit.py` toolchain; blind pairwise reviewer panels (via `judge.py`) accept/send-back/scrap; accepts are baked into the asset script and committed to `model/<asset>`, serialized per asset. Tasks 1–6 are small tool deltas with tests in `selftest.py`; task 7 is the new page; tasks 8–9 are the skill documents (the workflow's actual program); task 10 is full verification.

**Tech Stack:** Python 3.13 (system python; stdlib + PIL/numpy/scipy already in use), Blender 5.1 headless (`GLOOMFELL_BLENDER` override), vanilla single-file HTML/JS/CSS pages served by `serve.py`, Claude Code agents (skill markdown).

## Global Constraints

Copied from the spec — every task inherits these:

- **The three laws:** (1) never think about Unity; (2) size unknown — no pixel-size rules or criteria anywhere; (3) no privileged camera — judging uses the seeded orbit. `selftest.py` already bans `184`/`icon`/`unity` tokens from `orbit.py`'s executable code; nothing you add may reintroduce a fixed-size criterion in tool code.
- **Never save/export the real asset:** the `# --- variant hook ---` interlock in `preview.py`/`build_one.py` is never loosened; previews stay non-destructive (`DO_SAVE`/`DO_EXPORT` False).
- **GPU render semaphore stays at 2** (`RENDER_SLOTS` in `preview.py`); never raised by code.
- **UTF-8 on every state-file open** (Windows defaults to cp1252) — pass `encoding="utf-8"` in all new file I/O.
- **`_previews~` keeps its trailing tilde.** Paths are Windows paths under `C:\Users\LachlanB\TD\`.
- **Append-only JSONL for records; temp-file + `os.replace` for rewritten JSON** (with the Windows sharing-violation retry pattern already in `tap.py`/`preview.py`).
- **Run `python Assets/Blender/_tools/selftest.py` after any `_tools/` change** — it must exit 0.
- **Blind pairwise margin 0–3 is the judging instrument** — no scores, no rubric additions to judge briefs.
- Git: short lowercase commit messages (repo convention); commit only the files each task names.

## File Structure

| File | Task | Responsibility |
|---|---|---|
| `Assets/Blender/_tools/preview.py` (modify) | 1 | race-safe run-directory allocation |
| `Assets/Blender/_tools/record.py` (modify) | 2 | `eras()` helper; panel promotions |
| `Assets/Blender/_tools/refine.py` (modify) | 3 | v4 ratchet: era-partitioned vs-incumbent series |
| `Assets/Blender/_tools/serve.py` (modify) | 4 | `POST /chat`; serve `v4.html` |
| `Assets/Blender/_tools/tap.py` (modify) | 5 | multi-asset live publishing |
| `Assets/Blender/_tools/scaffold.py` (create) + `_tools/_scaffold_template.py` (create) | 6 | conforming-from-birth asset generator |
| `Assets/Blender/_tools/gallery/v4.html` (create) | 7 | mission-control page |
| `Assets/Blender/_tools/selftest.py` (modify) | 1–7 | each task registers its test here |
| `.claude/skills/blender-model-modev4/SKILL.md` (create) | 8 | supervisor manual |
| `.claude/skills/blender-model-modev4/references/page.md` (create) | 8 | page + chat data contracts |
| `.claude/skills/blender-model-modev4/references/shepherd.md` (create) | 9 | shepherd operating manual |
| `.claude/skills/blender-model-modev4/references/maker.md` (create) | 9 | maker discipline |
| `.claude/skills/blender-model-modev4/references/reviewer.md` (create) | 9 | panel mechanics |

Testing note: `selftest.py` is the project's test harness — a plain script of `test_*()` functions using `check(label, cond, detail)`, registered in the `TESTS` list, filterable by substring: `python Assets/Blender/_tools/selftest.py <substring>`. "Write the failing test" below means: add the test function + register it in `TESTS`, run it, watch it fail, then implement. Pure-python tests go before the Blender-dependent ones in `TESTS` (matching the existing ordering).

---

### Task 1: Race-safe run allocation in `preview.py`

Two concurrent makers can currently claim the same `run-NNN`: `next_run_dir()` computes `max+1` then `os.makedirs(..., exist_ok=True)`, so the second claimant silently shares the first's directory and the two waves overwrite each other's cells.

**Files:**
- Modify: `Assets/Blender/_tools/preview.py:240-249` (`next_run_dir`)
- Test: `Assets/Blender/_tools/selftest.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `next_run_dir(root, asset_name) -> (path, n, base)` — unchanged signature, now atomic: the returned directory was created by this call with `os.mkdir` (exclusive), never pre-existing.

- [ ] **Step 1: Write the failing test** — add to `selftest.py` (after `test_orbit_draw_is_deterministic_and_unprivileged`, before the Blender tests) and register in `TESTS` right after the orbit test:

```python
def test_next_run_dir_is_race_safe():
    """Concurrent makers must never be handed the same run directory.

    The old body computed max+1 and then makedirs(exist_ok=True): two callers
    that listed the directory before either created run-NNN both got the SAME
    path back, and their waves overwrote each other's cells. mkdir with no
    exist_ok is the atomic claim; a loser increments and retries.
    """
    print("test_next_run_dir_is_race_safe")
    sys.path.insert(0, HERE)
    import concurrent.futures
    import preview

    root = tempfile.mkdtemp(prefix="gf_rundir_")
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda _i: preview.next_run_dir(root, "raceasset"), range(8)))
        ns = sorted(n for _path, n, _base in results)
        check("eight claims got eight distinct run numbers",
              len(set(ns)) == 8, str(ns))
        check("every claimed directory exists on disk",
              all(os.path.isdir(p) for p, _n, _b in results))
        check("numbers are a contiguous block starting at 1",
              ns == list(range(1, 9)), str(ns))
    finally:
        shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python Assets/Blender/_tools/selftest.py race`
Expected: FAIL on "eight claims got eight distinct run numbers" (duplicate numbers in the list).

- [ ] **Step 3: Implement** — replace the body of `next_run_dir` in `preview.py`:

```python
def next_run_dir(root, asset_name):
    """Allocate _previews~/<asset>/run-NNN/, NNN monotonic per asset.

    os.mkdir (no exist_ok) is the atomic claim: with several maker agents
    rendering the same asset concurrently, whoever creates the directory owns
    that number and a loser simply takes the next one. The old makedirs
    (exist_ok=True) body handed two concurrent callers the same directory.
    """
    base = os.path.join(root, asset_name)
    os.makedirs(base, exist_ok=True)
    used = [int(d[4:]) for d in os.listdir(base)
            if d.startswith("run-") and d[4:].isdigit()]
    n = max(used) + 1 if used else 1
    while True:
        path = os.path.join(base, "run-%03d" % n)
        try:
            os.mkdir(path)
            return path, n, base
        except FileExistsError:
            n += 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python Assets/Blender/_tools/selftest.py race`
Expected: all three checks PASS.

- [ ] **Step 5: Run the fast pure-python suite to catch regressions**

Run: `python Assets/Blender/_tools/selftest.py genes` then `python Assets/Blender/_tools/selftest.py orbit`
Expected: PASS (these don't launch Blender; the full suite runs in Task 10).

- [ ] **Step 6: Commit**

```bash
git add Assets/Blender/_tools/preview.py Assets/Blender/_tools/selftest.py
git commit -m "preview: atomic run-dir claim so concurrent makers never share a run"
```

---

### Task 2: `record.py` — script-sha eras and panel promotions

**Files:**
- Modify: `Assets/Blender/_tools/record.py` (docstring + `promote()` at 209-226; new `eras()` after `origin_of` at 133-159)
- Test: `Assets/Blender/_tools/selftest.py`

**Interfaces:**
- Consumes: existing `read_attempts(asset, root)`, `_paths`, `_append`.
- Produces:
  - `eras(asset, design, root=None) -> list[{"script_sha": str|None, "attempts": [int,...]}]` — a design's waves grouped into maximal runs of consecutive attempts sharing a `script_sha`, ordered by attempt. Task 3 consumes this concept (it re-derives the trailing era from wave rows; the helper is the shared, tested definition).
  - `promote(asset, run, cell, by="user", quote="", root=None)` — unchanged signature; now validates `by in ("user", "panel")` and its docstring names the v4 rule (panel accepts promote; the user's directives outrank).

- [ ] **Step 1: Write the failing test** — add to `selftest.py` and register in `TESTS` after `test_next_run_dir_is_race_safe`:

```python
def test_record_eras_and_panel_promote():
    """eras() groups a design's waves by script_sha; promote() accepts by=panel.

    The v4 ratchet is only comparable within one script_sha era (a bake changes
    the geometry cell 1 reproduces), so the grouping itself deserves a test.
    Wave rows are written directly as JSONL rather than through open_attempt(),
    which would demand a real manifest on disk for every row.
    """
    print("test_record_eras_and_panel_promote")
    sys.path.insert(0, HERE)
    import record

    root = tempfile.mkdtemp(prefix="gf_record_")
    try:
        p = os.path.join(root, "era_asset", "attempts.jsonl")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        rows = [
            {"kind": "wave", "design": "d01", "attempt": 1, "run": 10, "script_sha": "aaa"},
            {"kind": "wave", "design": "d01", "attempt": 2, "run": 11, "script_sha": "aaa"},
            {"kind": "wave", "design": "d01", "attempt": 3, "run": 12, "script_sha": "bbb"},
            {"kind": "wave", "design": "d02", "attempt": 1, "run": 13, "script_sha": "bbb"},
            {"kind": "wave", "design": "d01", "attempt": 4, "run": 14, "script_sha": "bbb"},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        got = record.eras("era_asset", "d01", root=root)
        check("two eras for d01",
              [e["script_sha"] for e in got] == ["aaa", "bbb"], str(got))
        check("attempts grouped in order",
              [e["attempts"] for e in got] == [[1, 2], [3, 4]], str(got))
        check("other designs' waves ignored",
              all(3 not in e["attempts"] or e["script_sha"] == "bbb" for e in got))

        refused = False
        try:
            record.promote("era_asset", 10, 1, by="verifier", root=root)
        except SystemExit:
            refused = True
        check("promote refuses an unknown authority", refused)
    finally:
        shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python Assets/Blender/_tools/selftest.py eras`
Expected: FAIL — `AttributeError: module 'record' has no attribute 'eras'`.

- [ ] **Step 3: Implement** — in `record.py`, add after `origin_of()`:

```python
def eras(asset, design, root=None):
    """A design's waves grouped into script_sha eras, oldest first.

    An era is a maximal run of consecutive attempts sharing a script_sha. The
    v4 ratchet (vs-incumbent margins) is only comparable within one era: every
    bake changes the geometry that cell 1 reproduces, so margins from different
    eras measure against different incumbents and must never be pooled.
    """
    waves = sorted([a for a in read_attempts(asset, root)
                    if a.get("kind") == "wave" and a.get("design") == design],
                   key=lambda w: w.get("attempt", 0))
    out = []
    for w in waves:
        sha = w.get("script_sha")
        if not out or out[-1]["script_sha"] != sha:
            out.append({"script_sha": sha, "attempts": []})
        out[-1]["attempts"].append(w.get("attempt"))
    return out
```

and change `promote()`'s opening to:

```python
def promote(asset, run, cell, by="user", quote="", root=None):
    """Make a cell the incumbent.

    Called for a human decision, or — under modev4 — for a panel accept
    (by="panel"). The user's directive channel always outranks a panel verdict;
    see docs/superpowers/specs/2026-08-10-blender-model-modev4-design.md §7.
    """
    if by not in ("user", "panel"):
        raise SystemExit("promote by must be user or panel, not %r" % by)
```

(the rest of the function body is unchanged).

- [ ] **Step 4: Run test to verify it passes**

Run: `python Assets/Blender/_tools/selftest.py eras`
Expected: all four checks PASS.

- [ ] **Step 5: Commit**

```bash
git add Assets/Blender/_tools/record.py Assets/Blender/_tools/selftest.py
git commit -m "record: script-sha eras helper; promote accepts by=panel, refuses anything else"
```

---

### Task 3: `refine.py` — the v4 ratchet (era-partitioned vs-incumbent)

v3 recorded explicit `vs origin` verdicts and `policy()` reads only those. v4 records only `vs incumbent` verdicts (there is no separate origin judging — cell 1 *is* the incumbent, fixed within an era because send-backs never bake). `refine.py` must therefore fall back, when no origin verdicts exist, to the vs-incumbent series of the **trailing script-sha era** for grace/abandon/stall, while report-at-8 counts all judged attempts. v3 data keeps working exactly as before (origin series present → old behaviour).

**Files:**
- Modify: `Assets/Blender/_tools/refine.py` (`_by_attempt` at 65-98, `policy` at 101-154, module docstring)
- Test: `Assets/Blender/_tools/selftest.py`

**Interfaces:**
- Consumes: `record.read_attempts` (wave rows carry `script_sha` — stamped by `preview.py` since v3; `open_attempt` copies it).
- Produces: `packet(asset, design, root=None)` — same shape as today plus `policy` computed from the new series; `_by_attempt` slots gain `"script_sha"`. `policy(hist)` unchanged signature.

- [ ] **Step 1: Write the failing test** — add to `selftest.py`, register after `test_record_eras_and_panel_promote`:

```python
def _refine_fixture(root, asset, rows):
    p = os.path.join(root, asset, "attempts.jsonl")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_refine_v4_ratchet_uses_current_era():
    """With no vs-origin verdicts, policy reads the trailing era's incumbent series.

    Three margins of +0/+0/+0 across THREE eras must not read as a stall: each
    era has a different baseline, so only the trailing era's series counts for
    stall/abandon. And a genuine within-era stall must still fire.
    """
    print("test_refine_v4_ratchet_uses_current_era")
    sys.path.insert(0, HERE)
    import refine

    def wave(n, run, sha):
        return {"kind": "wave", "design": "d01", "attempt": n, "run": run,
                "script_sha": sha}

    def verdict(run, margin, prefer="challenger"):
        return {"kind": "verdict", "run": run, "cell": 2, "vs": "incumbent",
                "prefer": prefer, "margin": margin, "judge": "j1",
                "suggestion": "s%d" % run}

    root = tempfile.mkdtemp(prefix="gf_refine_")
    try:
        # Era-reset case: attempts 1-2 era aaa (+2 then +1), attempt 3 era bbb (+1).
        # Era bbb has one judged attempt: within grace, policy must be refine,
        # and must NOT see era aaa's +2 as "the design's best" to stall against.
        _refine_fixture(root, "ratchet1", [
            wave(1, 10, "aaa"), verdict(10, 2),
            wave(2, 11, "aaa"), verdict(11, 1),
            wave(3, 12, "bbb"), verdict(12, 1),
        ])
        pk = refine.packet("ratchet1", "d01", root=root)
        check("v4 fallback engaged (no origin verdicts, policy still computed)",
              pk["policy"]["call"] == "refine", str(pk["policy"]))

        # Within-era stall: grace is 2, stall is 3 — five attempts in ONE era,
        # best +2 at attempt 1, then four attempts never beating it.
        _refine_fixture(root, "ratchet2",
            [wave(1, 20, "aaa"), verdict(20, 2)] +
            [x for i in range(4) for x in
             (wave(2 + i, 21 + i, "aaa"), verdict(21 + i, 1))])
        pk2 = refine.packet("ratchet2", "d01", root=root)
        check("a genuine within-era stall still calls redesign",
              pk2["policy"]["call"] == "redesign", str(pk2["policy"]))

        # Abandon: after grace, latest era margin at -2.
        _refine_fixture(root, "ratchet3", [
            wave(1, 30, "aaa"), verdict(30, 1),
            wave(2, 31, "aaa"), verdict(31, -1, prefer="incumbent"),
            wave(3, 32, "aaa"), verdict(32, -2, prefer="incumbent"),
        ])
        pk3 = refine.packet("ratchet3", "d01", root=root)
        check("a decisively negative latest margin abandons",
              pk3["policy"]["call"] == "abandon", str(pk3["policy"]))

        # v3 data unchanged: an origin series present -> used as before.
        _refine_fixture(root, "ratchet4", [
            wave(1, 40, "aaa"),
            dict(verdict(40, 2), vs="origin"),
        ])
        pk4 = refine.packet("ratchet4", "d01", root=root)
        check("origin verdicts still take precedence (v3 mode)",
              pk4["policy"]["call"] == "refine", str(pk4["policy"]))

        # Report-at-8 counts attempts ACROSS eras.
        rows8 = []
        for i in range(8):
            rows8.append(wave(1 + i, 50 + i, "sha%d" % (i // 2)))
            rows8.append(verdict(50 + i, 1))
        _refine_fixture(root, "ratchet5", rows8)
        pk5 = refine.packet("ratchet5", "d01", root=root)
        check("report-at-8 spans eras", pk5["policy"]["call"] == "report",
              str(pk5["policy"]))
    finally:
        shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python Assets/Blender/_tools/selftest.py ratchet`
Expected: FAIL — with no origin verdicts, today's `policy()` returns the "no vs-origin comparison has been made yet" refine for every fixture, so the `redesign`, `abandon` and `report` checks fail.

- [ ] **Step 3: Implement** — in `refine.py`:

3a. In `_by_attempt`, capture the wave's sha. Replace the `slot = per.setdefault(...)` statement with:

```python
        w = waves[r["run"]]
        n = w["attempt"]
        slot = per.setdefault(n, {"attempt": n, "run": r["run"],
                                  "script_sha": w.get("script_sha"),
                                  "incumbent": [], "origin": [], "suggestions": []})
```

(and delete the old `n = waves[r["run"]]["attempt"]` line above it — `signed` stays as is).

3b. Add a series selector above `policy()`:

```python
def _ratchet_series(hist):
    """(series, era_len, mode) — the numbers policy() decides from.

    v3 recorded explicit vs-origin verdicts; when any exist they remain the
    ratchet ("origin" mode, exactly the old behaviour). v4 records only
    vs-incumbent verdicts: send-backs never bake, so within one script_sha era
    the incumbent is FIXED and the incumbent series IS the ratchet. A bake
    (any design's) changes the sha and ends the era; margins from different
    eras measure against different baselines, so stall/abandon read only the
    TRAILING era ("incumbent-era" mode). record.eras() is the tested statement
    of the same grouping.
    """
    origin = [h["best_origin"] for h in hist if h["best_origin"] is not None]
    if origin:
        return origin, len(hist), "origin"
    cur = hist[-1]["script_sha"] if hist else None
    era = []
    for h in reversed(hist):
        if h["script_sha"] != cur:
            break
        era.append(h)
    era.reverse()
    series = [h["best_incumbent"] for h in era if h["best_incumbent"] is not None]
    return series, len(era), "incumbent-era"
```

3c. Rewrite `policy()` to read it. Keep every threshold constant and every `why` string's substance; the structural change is `n_total` (report) vs `n_era`/`series` (grace/abandon/stall):

```python
def policy(hist):
    """refine | redesign | abandon | report, from the ratchet series.

    Attempt count for report-at-8 spans the design's whole life; grace, abandon
    and stall evaluate within the current era — see _ratchet_series.
    """
    if not hist:
        return {"call": "refine", "why": "no attempts judged yet"}

    n_total = len(hist)
    series, n_era, mode = _ratchet_series(hist)

    if n_total >= REPORT_AT:
        return {"call": "report",
                "why": "attempt %d. Past this point the decision is the user's, not a "
                       "rule's - the rule exists to stop a design running forever, not "
                       "to kill one the user still wants." % n_total}

    if not series:
        return {"call": "refine",
                "why": "no judged comparison yet%s - convene a panel on the newest wave "
                       "before building again, or progress is unmeasurable"
                       % (" in the current script era" if mode == "incumbent-era" else "")}

    latest, best = series[-1], max(series)

    if n_era <= GRACE_ATTEMPTS:
        return {"call": "refine",
                "why": "attempt %d of the current era is within the grace window; an "
                       "idea gets a real build before any policy can kill it" % n_era}

    if latest <= ABANDON_AT:
        return {"call": "abandon",
                "why": "ratchet %+d after %d judged attempts this era. That is the panel "
                       "saying the IDEA is wrong rather than the execution - refining it "
                       "spends renders on a premise nobody is buying." % (latest, n_era)}

    since = 0
    for v in reversed(series):
        if v >= best:
            break
        since += 1
    if since >= STALL_ROUNDS:
        return {"call": "redesign",
                "why": "%d consecutive attempts have failed to beat this design's best "
                       "ratchet margin (%+d) in the current era. The feedback has "
                       "stopped being actionable; take what landed and open a new "
                       "design rather than grinding this one." % (since, best)}

    if latest >= best and latest > 0:
        return {"call": "refine",
                "why": "ratchet %+d, the design's best this era. It is still climbing - "
                       "carry the critique forward." % latest}

    return {"call": "refine",
            "why": "ratchet %+d against a best of %+d this era. Oscillating but not "
                   "stalled; a design that wobbles is still learning something." % (latest, best)}
```

3d. Update the module docstring's "THE MEASUREMENT PROBLEM" paragraph: append two sentences — *"Under modev4 there are no separate origin verdicts: the incumbent is the baked script and send-backs never bake, so within one script_sha era the vs-incumbent series is the ratchet, and stall/abandon read only the trailing era. Origin verdicts, where they exist (v3 data), still take precedence."*

- [ ] **Step 4: Run test to verify it passes**

Run: `python Assets/Blender/_tools/selftest.py ratchet`
Expected: all five checks PASS.

- [ ] **Step 5: Commit**

```bash
git add Assets/Blender/_tools/refine.py Assets/Blender/_tools/selftest.py
git commit -m "refine: v4 ratchet - era-partitioned vs-incumbent series, v3 origin data still wins"
```

---

### Task 4: `serve.py` — `POST /chat` and the v4 page

**Files:**
- Modify: `Assets/Blender/_tools/serve.py` (`do_POST` at 48-81; page-copy loop at 105-108)
- Test: `Assets/Blender/_tools/selftest.py`

**Interfaces:**
- Consumes: `PREVIEW_ROOT`, `ASSET_RE`, `QuietHandler`.
- Produces:
  - `POST /chat` with JSON body `{"text": str (required, 1..2000 chars after strip), "asset": str (optional, ASSET_RE-validated)}` → appends `{"at", "from": "user", "text"[, "asset"]}` to `<PREVIEW_ROOT>/chat.jsonl`, responds 204. Bad body → 400. This file is the **user's door only**; supervisor replies go in `feed.jsonl`, written by the supervisor directly (never via HTTP) — instructions and replies never share a writer.
  - `GET /v4.html` serves the mission-control page (copied from `gallery/v4.html` at startup, same as the other two pages).

- [ ] **Step 1: Write the failing test** — add to `selftest.py`; register immediately before `test_gallery_server_contract`. A placeholder `gallery/v4.html` is created by this task so the copy loop has something real to copy; Task 7 replaces its content.

```python
def test_chat_endpoint_and_v4_page():
    """POST /chat appends the user's line; /v4.html is served; bad input 400s.

    chat.jsonl is real shared state under the previews root, so the test
    snapshots its length and restores the file afterwards.
    """
    print("test_chat_endpoint_and_v4_page")
    port = 8779
    base = "http://127.0.0.1:%d" % port
    env = dict(os.environ, GLOOMFELL_GALLERY_PORT=str(port))
    chat_path = os.path.join(PREVIEW_ROOT, "chat.jsonl")
    os.makedirs(PREVIEW_ROOT, exist_ok=True)
    before = open(chat_path, encoding="utf-8").read() if os.path.exists(chat_path) else None

    def post(payload):
        req = urllib.request.Request(
            base + "/chat", data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        try:
            return urllib.request.urlopen(req, timeout=5).status
        except urllib.error.HTTPError as e:
            return e.code

    proc = subprocess.Popen([sys.executable, SERVE], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        _wait_for_server(base)
        check("valid chat message accepted", post({"text": "hello fleet"}) == 204)
        check("asset-scoped message accepted",
              post({"text": "more aura", "asset": "mage000"}) == 204)
        check("empty text refused", post({"text": "   "}) == 400)
        check("missing text refused", post({"note": "x"}) == 400)
        check("bad asset refused", post({"text": "x", "asset": "../evil"}) == 400)

        lines = [json.loads(l) for l in open(chat_path, encoding="utf-8")
                 if l.strip()]
        tail = lines[-2:]
        check("both accepted lines landed, in order",
              [l["text"] for l in tail] == ["hello fleet", "more aura"], str(tail))
        check("lines are stamped and attributed",
              all(l.get("at") and l.get("from") == "user" for l in tail), str(tail))
        check("asset field preserved on the scoped line",
              tail[1].get("asset") == "mage000", str(tail[1]))

        v4 = urllib.request.urlopen(base + "/v4.html", timeout=5)
        check("GET /v4.html is 200", v4.status == 200)
        check("v4 page body carries its title marker",
              "Gloomfell · mission control" in v4.read().decode("utf-8"))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        if before is None:
            if os.path.exists(chat_path):
                os.remove(chat_path)
        else:
            with open(chat_path, "w", encoding="utf-8") as fh:
                fh.write(before)
```

- [ ] **Step 2: Create the placeholder page** so the copy loop and title check have a real file — `Assets/Blender/_tools/gallery/v4.html`:

```html
<!doctype html>
<meta charset="utf-8">
<title>Gloomfell · mission control</title>
<body>placeholder — Task 7 builds this page.</body>
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python Assets/Blender/_tools/selftest.py chat`
Expected: FAIL — POSTs return 404 ("valid chat message accepted" fails) and /v4.html 404s (page not yet copied at startup).

- [ ] **Step 4: Implement** — in `serve.py`:

4a. Extend the page-copy loop:

```python
    for page in ("index.html", "live.html", "v4.html"):
```

4b. In `do_POST`, before the existing route lookup, add the chat branch (and add a module comment line to `MARKS`/`DIRECTIVES` area: `# /chat is the user's one free-text door; replies (feed.jsonl) are written by the supervisor process directly, never through HTTP.`):

```python
    def do_POST(self):
        if self.path == "/chat":
            return self._post_chat()
        route = {"/signal": ("mark", MARKS, "user-signals.jsonl"),
                 "/directive": ("directive", DIRECTIVES, "user-directives.jsonl")}.get(self.path)
        ...

    def _post_chat(self):
        """Append one user chat line to the fleet-level chat.jsonl.

        The file is append-only JSONL like the signal files: a crash loses at
        most the line being written, and the supervisor can tail it. Everything
        in this file is user-authored by construction - the supervisor never
        writes here, so provenance is the file name.
        """
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 65536)
            body = json.loads(self.rfile.read(n))
            text = str(body["text"]).strip()
            if not text:
                raise ValueError("empty text")
            rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "from": "user",
                   "text": text[:2000]}
            asset = body.get("asset")
            if asset:
                if not ASSET_RE.match(asset):
                    raise ValueError("bad asset")
                rec["asset"] = asset
        except (KeyError, ValueError, json.JSONDecodeError):
            self.send_error(400)
            return
        os.makedirs(PREVIEW_ROOT, exist_ok=True)
        with open(os.path.join(PREVIEW_ROOT, "chat.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.send_response(204)
        self.end_headers()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python Assets/Blender/_tools/selftest.py chat`
Expected: all eleven checks PASS.

- [ ] **Step 6: Re-run the existing server test** (same file changed):

Run: `python Assets/Blender/_tools/selftest.py gallery_server`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add Assets/Blender/_tools/serve.py Assets/Blender/_tools/gallery/v4.html Assets/Blender/_tools/selftest.py
git commit -m "serve: POST /chat (user door, append-only) and v4.html serving"
```

---

### Task 5: `tap.py` — multi-asset publishing

**Files:**
- Modify: `Assets/Blender/_tools/tap.py` (`main()` at 140-169; docstring usage lines)
- Test: `Assets/Blender/_tools/selftest.py`

**Interfaces:**
- Consumes: existing `scan(root, asset, keep)`, `publish(payload, out_path)`.
- Produces: CLI accepts one **or more** assets — `python tap.py mage000 knight000 [--once]` — publishing each to `<root>/<asset>/live.json`. Single-asset invocations behave exactly as today. The v4 supervisor starts ONE tap for the whole fleet and restarts it when the active-asset set changes.

- [ ] **Step 1: Write the failing test** — add to `selftest.py`, register after `test_refine_v4_ratchet_uses_current_era`:

```python
def test_tap_publishes_multiple_assets():
    """One tap process must be able to follow the whole fleet."""
    print("test_tap_publishes_multiple_assets")
    root = tempfile.mkdtemp(prefix="gf_tap_")
    try:
        for asset in ("fleet_a", "fleet_b"):
            rdir = os.path.join(root, asset, "run-001")
            os.makedirs(rdir, exist_ok=True)
            with open(os.path.join(rdir, "manifest.json"), "w", encoding="utf-8") as fh:
                json.dump({"asset": asset, "run": 1, "started": "2026-08-10T00:00:00",
                           "done": True, "tag": "t", "seed": 1, "audit": None,
                           "variants": [{"n": 1, "label": "x"}]}, fh)
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "tap.py"),
             "fleet_a", "fleet_b", "--once", "--root", root],
            capture_output=True, text=True, timeout=60)
        check("tap exited 0", proc.returncode == 0, proc.stderr[:300])
        for asset in ("fleet_a", "fleet_b"):
            lp = os.path.join(root, asset, "live.json")
            check("live.json published for " + asset, os.path.exists(lp))
            if os.path.exists(lp):
                data = _read_json(lp)
                check(asset + " payload names its asset and run",
                      data.get("asset") == asset and data["runs"]
                      and data["runs"][0]["run"] == 1, str(data)[:200])
    finally:
        shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python Assets/Blender/_tools/selftest.py tap`
Expected: FAIL — argparse errors on the second positional (`unrecognized arguments: fleet_b`), so exit != 0.

- [ ] **Step 3: Implement** — in `tap.py`'s `main()`: change `ap.add_argument("asset")` to `ap.add_argument("assets", nargs="+")`, and rewrite the body after parsing:

```python
    root = os.path.abspath(a.root) if a.root else PREVIEW_ROOT

    def out_path(asset):
        return os.path.join(root, asset, "live.json")

    if a.once:
        for asset in a.assets:
            p = scan(root, asset, a.keep)
            publish(p, out_path(asset))
            print("%s  %d runs (%d unclaimed) -> %s"
                  % (asset, p["total_runs"], p.get("unclaimed_runs", 0), out_path(asset)))
        return 0

    print("tapping %s   (ctrl-c to stop)" % ", ".join(a.assets))
    last = {}
    while True:
        busy = False
        for asset in a.assets:
            p = scan(root, asset, a.keep)
            key = json.dumps(p["runs"], separators=(",", ":"))
            if key != last.get(asset):
                publish(p, out_path(asset))
                last[asset] = key
            busy = busy or any(not r["done"] for r in p["runs"][:3])
        time.sleep(BUSY_S if busy else IDLE_S)
```

Update the module docstring's usage lines to show `tap.py mage000 knight000` and note: *one process follows the whole fleet; the supervisor restarts it when the active-asset set changes.*

- [ ] **Step 4: Run test to verify it passes**

Run: `python Assets/Blender/_tools/selftest.py tap`
Expected: all six checks PASS.

- [ ] **Step 5: Commit**

```bash
git add Assets/Blender/_tools/tap.py Assets/Blender/_tools/selftest.py
git commit -m "tap: follow multiple assets from one process for the v4 fleet"
```

---

### Task 6: `scaffold.py` + template — conforming-from-birth assets

Genesis (spec §8) needs a generator that emits a new asset script that is safe for the harness from its first run: hook marker, `DO_SAVE`/`DO_EXPORT` behind `_flag()`, `RENDER_ONLY`/`SAMPLE_SCALE` honoured, `EXTRA_VIEWS` orbit loop with per-cell `rig_yaw`, mask passes, a named `Ground` object (what `render_mask` hides), and a placeholder blockout the maker will replace. The template reproduces mage000's debugged idioms (`_flag` at `blender_mage000.py:61`, `set_rig_yaw`/`render_mask`/`render_view` at 3126-3235, `EXTRA_VIEWS` loop at 3317-3324) in minimal form.

**Files:**
- Create: `Assets/Blender/_tools/scaffold.py`
- Create: `Assets/Blender/_tools/_scaffold_template.py`
- Test: `Assets/Blender/_tools/selftest.py`

**Interfaces:**
- Consumes: `genes.build_map` (validation), `preview.run` (smoke), `orbit.draw`/`orbit.views` (orbit smoke).
- Produces: `scaffold.scaffold(asset, dist=5.6, aim_z=1.15, out_dir=None, force=False) -> path` — writes `blender_<asset>.py` into `out_dir` (default `Assets/Blender/`), refusing to overwrite without `force`, refusing an asset code not matching `^[a-z][a-z0-9_]{1,40}$`. CLI: `python _tools/scaffold.py <asset> [--dist F] [--aim-z F] [--force]`.

- [ ] **Step 1: Write the failing test** — add to `selftest.py`, register at the END of `TESTS` (it launches Blender twice; slow tests go last):

```python
def test_scaffolded_asset_conforms():
    """A scaffolded script must be harness-drivable and orbit-ready from birth.

    Genesis (modev4) trusts this: the generated script renders under
    preview.py, its genes map cleanly, and an orbit cell renders BOTH the view
    and its _mask.png companion (chips and measure.py need the mask).
    """
    print("test_scaffolded_asset_conforms")
    sys.path.insert(0, HERE)
    import genes
    import orbit
    import preview
    import scaffold

    tmp = tempfile.mkdtemp(prefix="gf_scaffold_")
    try:
        path = scaffold.scaffold("scafftest", dist=4.0, aim_z=0.8, out_dir=tmp)
        check("generated file is where scaffold says", os.path.exists(path), path)
        src = open(path, encoding="utf-8").read()
        check("hook marker present", preview.HOOK_MARKER in src)
        check("save/export behind flags",
              'DO_SAVE' in src and 'DO_EXPORT' in src and '_flag(' in src)

        m = genes.build_map(path)
        check("gene map conforming", m["conforming"], str(m["hook_line"]))
        check("gene map found tunables", m["count"] >= 5, str(m["count"]))
        check("no derived genes in the template", m["derived_count"] == 0,
              str([n for n, g in m["genes"].items() if g["derived_from"]]))

        refused = False
        try:
            scaffold.scaffold("scafftest", out_dir=tmp)
        except SystemExit:
            refused = True
        check("refuses to overwrite without force", refused)

        root = os.path.join(tmp, "previews")
        man = preview.run(asset=path, variants=[{"label": "baseline"}],
                          views=["front"], root=root)
        v = man["variants"][0]
        check("scaffolded asset builds and renders", v["exit"] == 0,
              v["stderr_tail"][:400])
        check("front view rendered", v["renders"] == ["v1/front.png"],
              str(v["renders"]))

        cells = orbit.views(orbit.draw(7), 4.0, 0.8)[:2]
        man2 = preview.run(asset=path,
                           variants=[{"label": "orbit",
                                      "vars": {"EXTRA_VIEWS": cells}}],
                           views=["orb0", "orb1"], root=root)
        v2 = man2["variants"][0]
        check("orbit cells render", v2["exit"] == 0, v2["stderr_tail"][:400])
        run_dir = os.path.join(root, "scafftest",
                               "run-%03d" % man2["run"], "v1")
        check("orbit view + mask companion on disk",
              os.path.exists(os.path.join(run_dir, "orb0.png"))
              and os.path.exists(os.path.join(run_dir, "orb0_mask.png")),
              str(os.listdir(run_dir) if os.path.isdir(run_dir) else "missing"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python Assets/Blender/_tools/selftest.py scaffold`
Expected: FAIL — `ModuleNotFoundError: No module named 'scaffold'`.

- [ ] **Step 3: Write `Assets/Blender/_tools/_scaffold_template.py`** — the full template. Tokens `__ASSET__`, `__DIST__`, `__AIMZ__` are replaced by `scaffold.py`; note `___ASSET__` in `RENDER_DIR` is the literal `_` folder-prefix convention plus the token:

```python
"""Gloomfell asset script for __ASSET__. Generated by _tools/scaffold.py.

Conforming from birth: variant hook, RENDER_ONLY/SAMPLE_SCALE, EXTRA_VIEWS orbit
cells with per-cell rig yaw, quarter-res silhouette masks, save/export behind
DO_SAVE/DO_EXPORT. Blockout stage - grow the model by editing build_asset() and
adding ALLCAPS gene globals; keep genes independent (no module-level arithmetic
between them) so they stay sweepable through `vars`.
"""

import math
import os

import bpy
from mathutils import Vector

bpy.ops.wm.read_homefile(use_empty=True, use_factory_startup=True)
SCENE = bpy.context.scene

# -- Paths (hardcoded per project convention) ----------------------------------
BLEND_PATH = r"C:\Users\LachlanB\TD\Assets\Blender\__ASSET__.blend"
FBX_PATH   = r"C:\Users\LachlanB\TD\Assets\Models\__ASSET__.fbx"
RENDER_DIR = r"C:\Users\LachlanB\TD\Assets\Blender\___ASSET__"


def _flag(name, default=False):
    """Headless: blender -b -P blender___ASSET__.py -- save export render.
    In-session: seed the name in the namespace before exec'ing (build_one.py)."""
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return globals().get(name, default) or name.replace("DO_", "").lower() in argv


DO_RENDER = _flag("DO_RENDER")
DO_EXPORT = _flag("DO_EXPORT")
DO_SAVE   = _flag("DO_SAVE")

BASE_SAMPLES = 96

# -- Orbit framing constants: per-asset, never fitted to the candidate ---------
ORBIT_DIST  = __DIST__
ORBIT_AIM_Z = __AIMZ__

# -- Genes: ALLCAPS module globals, all independent ----------------------------
BODY_R   = 0.42
BODY_H   = 1.15
HEAD_R   = 0.26
GROUND_R = 1.6
C_BODY   = (0.35, 0.36, 0.40, 1.0)
C_GROUND = (0.10, 0.10, 0.11, 1.0)

PARTS = []


def _mat(name, rgba):
    m = bpy.data.materials.new(name)
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba
    return m


def _sphere(name, r, loc, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc,
                                         segments=48, ring_count=24)
    ob = bpy.context.active_object
    ob.name = name
    ob.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    PARTS.append(ob)
    return ob


def build_ground():
    # Named "Ground" so render_mask() can hide it - the mask must be the figure alone.
    bpy.ops.mesh.primitive_cylinder_add(radius=GROUND_R, depth=0.06,
                                        location=(0, 0, -0.03))
    ob = bpy.context.active_object
    ob.name = "Ground"
    ob.data.materials.append(_mat("M_Ground", C_GROUND))
    bpy.ops.object.shade_smooth()


def build_asset():
    """Blockout: a body mass and a head. Faces -Y, Z-up, origin between the feet."""
    body = _mat("M_Body", C_BODY)
    _sphere("Body", BODY_R, (0.0, 0.0, BODY_H * 0.5), body)
    _sphere("Head", HEAD_R, (0.0, 0.0, BODY_H + HEAD_R * 0.8), body)


def build_rig():
    bpy.ops.object.camera_add(location=(0.0, -ORBIT_DIST, ORBIT_AIM_Z))
    cam = bpy.context.active_object
    SCENE.camera = cam
    for loc, energy in (((2.2, -2.6, 3.2), 400.0),
                        ((-2.6, -1.4, 1.8), 120.0),
                        ((0.4, 2.8, 2.4), 180.0)):
        bpy.ops.object.light_add(type='AREA', location=loc)
        bpy.context.active_object.data.energy = energy
    return cam


def look_at_euler(cam_loc, target):
    d = Vector(target) - Vector(cam_loc)
    return d.to_track_quat('-Z', 'Y').to_euler()


def set_rig_yaw(deg):
    """Rotate every light about world Z so lighting follows the orbit bearing.
    Remembers each light's authored transform so repeated yaws compose from the
    original rather than accumulating drift across a multi-cell render."""
    if deg is None:
        return
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    for ob in bpy.data.objects:
        if ob.type != 'LIGHT':
            continue
        if "_rig0" not in ob:
            ob["_rig0"] = list(ob.location)
            ob["_rot0"] = list(ob.rotation_euler)
        x0, y0, z0 = ob["_rig0"]
        ob.location = (x0 * ca - y0 * sa, x0 * sa + y0 * ca, z0)
        r0 = ob["_rot0"]
        ob.rotation_euler = (r0[0], r0[1], r0[2] + a)


def render_mask(name, cam_loc, target, res, lens):
    """`<name>_mask.png`: quarter-res RGBA silhouette with the ground hidden.
    A boolean geometric mask for chips/measure.py - never photometry."""
    r = SCENE.render
    ground = bpy.data.objects.get("Ground")
    prev = (r.film_transparent, r.image_settings.color_mode,
            r.resolution_x, r.resolution_y, r.filepath,
            getattr(SCENE.eevee, "taa_render_samples", None),
            ground.hide_render if ground else None)
    try:
        if ground:
            ground.hide_render = True
        r.film_transparent = True
        r.image_settings.color_mode = 'RGBA'
        r.resolution_x, r.resolution_y = max(64, res[0] // 4), max(64, res[1] // 4)
        if hasattr(SCENE.eevee, "taa_render_samples"):
            SCENE.eevee.taa_render_samples = 8
        r.filepath = os.path.join(RENDER_DIR, name + "_mask.png")
        bpy.ops.render.render(write_still=True)
    finally:
        if ground:
            ground.hide_render = prev[6]
        (r.film_transparent, r.image_settings.color_mode,
         r.resolution_x, r.resolution_y, r.filepath) = prev[:5]
        if prev[5] is not None and hasattr(SCENE.eevee, "taa_render_samples"):
            SCENE.eevee.taa_render_samples = prev[5]


def render_view(name, cam_loc, target=None, res=(900, 1300), lens=62,
                samples=None, rig_yaw=None, mask=False):
    only = globals().get("RENDER_ONLY")
    if only is not None and name not in only:
        return
    set_rig_yaw(rig_yaw)
    if target is None:
        target = (0.0, 0.0, ORBIT_AIM_Z)
    cam = SCENE.camera
    cam.location = cam_loc
    cam.rotation_euler = look_at_euler(cam_loc, target)
    cam.data.lens = lens
    SCENE.render.resolution_x, SCENE.render.resolution_y = res
    # ALWAYS set the sample count, never inherit the previous view's.
    scale = globals().get("SAMPLE_SCALE", 1.0)
    want = samples if samples else globals().get("BASE_SAMPLES", 96)
    if hasattr(SCENE.eevee, "taa_render_samples"):
        SCENE.eevee.taa_render_samples = max(16, int(want * scale))
    os.makedirs(RENDER_DIR, exist_ok=True)
    SCENE.render.filepath = os.path.join(RENDER_DIR, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered %s" % SCENE.render.filepath)
    if mask:
        render_mask(name, cam_loc, target, res, lens)


def export_fbx():
    for ob in bpy.data.objects:
        ob.select_set(ob in PARTS)
    if PARTS:
        bpy.context.view_layer.objects.active = PARTS[0]
    bpy.ops.export_scene.fbx(
        filepath=FBX_PATH, use_selection=True,
        object_types={'MESH', 'EMPTY'}, add_leaf_bones=False,
        mesh_smooth_type='FACE',
        # These two land a -Y-facing figure facing +Z in Unity.
        axis_forward='-Z', axis_up='Y', global_scale=1.0)
    print("Exported:", FBX_PATH)


# --- variant hook -------------------------------------------------------------
# Copied verbatim from _tools/_selftest_asset.py - do not "clean up" into a
# shared function; globals() must resolve to THIS module's namespace.
_v = globals().get("VARIANT", {})
globals().update({k: v for k, v in _v.items() if not k.startswith("_")})
if _v.get("_patch"):
    exec(_v["_patch"], globals())
# ------------------------------------------------------------------------------

build_ground()
build_asset()
build_rig()

if DO_SAVE:
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    print("Saved:", BLEND_PATH)

if DO_RENDER:
    render_view("front", (0.0, -ORBIT_DIST, ORBIT_AIM_Z), lens=70)
    render_view("hero_34", (-ORBIT_DIST * 0.58, -ORBIT_DIST * 0.72,
                            ORBIT_AIM_Z + 0.6))
    # ORBIT CELLS - the judged stimulus, delivered through the hook as
    # EXTRA_VIEWS by _tools/axis.py. Masks default ON: chips and measure.py
    # read them. A plain CLI run renders nothing extra.
    for _spec in (globals().get("EXTRA_VIEWS") or []):
        render_view(_spec["name"], tuple(_spec["cam_loc"]),
                    target=tuple(_spec.get("target", (0.0, 0.0, ORBIT_AIM_Z))),
                    res=tuple(_spec.get("res", (900, 1300))),
                    lens=_spec.get("lens", 62),
                    samples=_spec.get("samples"),
                    rig_yaw=_spec.get("rig_yaw"),
                    mask=_spec.get("mask", True))

if DO_EXPORT:
    export_fbx()
```

- [ ] **Step 4: Write `Assets/Blender/_tools/scaffold.py`:**

```python
"""Generate a conforming-from-birth Gloomfell asset script.

    python Assets/Blender/_tools/scaffold.py boar000
    python Assets/Blender/_tools/scaffold.py boar000 --dist 4.2 --aim-z 0.8

Writes Assets/Blender/blender_<asset>.py from _scaffold_template.py: variant
hook, RENDER_ONLY/SAMPLE_SCALE, EXTRA_VIEWS orbit cells with rig yaw, mask
passes, save/export behind DO_SAVE/DO_EXPORT. Used by modev4 genesis so a new
asset is drivable by preview.py from its first commit - retrofitting later is
how eight of the nine legacy scripts became undrivable.

Refuses to overwrite an existing script without --force: a generated blockout
must never silently replace a grown asset.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)
TEMPLATE = os.path.join(HERE, "_scaffold_template.py")

# Lowercase alnum/underscore, letter first: matches the <name>000 convention and
# stays a valid module/file name. Same shape serve.py's ASSET_RE trusts.
ASSET_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def scaffold(asset, dist=5.6, aim_z=1.15, out_dir=None, force=False):
    """Write blender_<asset>.py and return its path."""
    if not ASSET_RE.match(asset):
        raise SystemExit(
            "asset code must be lowercase letters/digits/underscores starting "
            "with a letter, not %r" % asset)
    out_dir = out_dir or BLENDER_DIR
    out = os.path.join(out_dir, "blender_%s.py" % asset)
    if os.path.exists(out) and not force:
        raise SystemExit("refusing to overwrite %s (pass --force if the "
                         "blockout really should replace it)" % out)
    with open(TEMPLATE, encoding="utf-8") as fh:
        src = fh.read()
    # Numbers first (they contain no token text), then the asset name - which
    # also fills ___ASSET__ (the _<asset> render-folder convention).
    src = src.replace("__DIST__", repr(float(dist)))
    src = src.replace("__AIMZ__", repr(float(aim_z)))
    src = src.replace("__ASSET__", asset)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("asset", help="asset code, e.g. boar000")
    ap.add_argument("--dist", type=float, default=5.6,
                    help="orbit camera distance (per-asset framing constant)")
    ap.add_argument("--aim-z", type=float, default=1.15,
                    help="orbit aim height (per-asset framing constant)")
    ap.add_argument("--out-dir", help="target directory (default Assets/Blender)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out = scaffold(a.asset, a.dist, a.aim_z, a.out_dir, a.force)
    print("scaffolded %s" % out)
    print("next: preview it -  python Assets/Blender/_tools/preview.py %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run test to verify it passes** (launches Blender twice, ~30 s)

Run: `python Assets/Blender/_tools/selftest.py scaffold`
Expected: all twelve checks PASS. If `orb0_mask.png` is missing, the mask branch is broken — check `render_mask` restores and that `EXTRA_VIEWS` defaults `mask=True`.

- [ ] **Step 6: Commit**

```bash
git add Assets/Blender/_tools/scaffold.py Assets/Blender/_tools/_scaffold_template.py Assets/Blender/_tools/selftest.py
git commit -m "scaffold: conforming-from-birth asset generator for modev4 genesis"
```

---### Task 7: `gallery/v4.html` — the mission-control page

Replaces Task 4's placeholder. Single self-contained file, no external requests, dark tokens and `h()`-builder conventions copied from the existing pages (`live.html` palette; `index.html`'s escaping discipline — never `innerHTML` with data).

**Files:**
- Modify (replace content): `Assets/Blender/_tools/gallery/v4.html`
- Test: existing `test_chat_endpoint_and_v4_page` (title marker must survive); the rest is a manual smoke in Task 10.

**Interfaces (data contracts — also documented in `references/page.md`, Task 8):**
- Reads `GET /fleet.json` (supervisor-written):
  ```json
  {"stamped": "2026-08-10T12:00:00", "note": "",
   "assets": [{"asset": "mage000", "state": "run", "makers": 2, "queue": 3,
               "accepted": 5, "staged": 0, "note": "d07 wave rendering"}]}
  ```
- Reads `GET /<asset>/pipeline.json` (shepherd-written):
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
- Reads `GET /<asset>/live.json` (tap), `GET /<asset>/champion.json` (record.py) — existing shapes.
- Reads `GET /chat.jsonl` + `GET /feed.jsonl` — lines `{"at", "from": "user"|"supervisor", "text"[, "asset"]}`; merged by `at` (ties: user first).
- Writes `POST /chat` `{"text", "asset"?}` (asset = focused asset when the "to this asset" toggle is on; omitted otherwise).
- All fetches use the `?t=Date.now()` cache-bust for JSON/JSONL (never images), 1 s poll for pipeline/live/chat, 5 s for fleet/champion; missing files are normal (404 → zone shows its empty state, never an error banner; the error banner is reserved for the server itself being unreachable).

- [ ] **Step 1: Build the page.** Full required structure (implement exactly; styling within these constraints is the implementer's craft):

  - `<title>Gloomfell · mission control</title>` — the test's marker string.
  - CSS tokens copied from `live.html` (`--bg:#12151c; --panel:#181c25; --panel2:#1e2331; --line:#2b3242; --ink:#e3e7f0; --ink2:#a8b0c2; --mute:#6f7891; --accent:#8e9bee; --ok:#5fbe99; --warn:#d2a05c;` plus `--dead:#d03b3b; --shelf:#9085e9;` from index.html). `color-scheme: dark`. Layout: CSS grid — header (fleet strip) spanning full width; main content left; chat dock right (`320px`, collapsible via a button that sets `localStorage['gf-v4-chat']`); at `max-width:1100px` the chat becomes a bottom sheet.
  - **Fleet strip**: one card per `fleet.json` asset — asset name, state pill (`run`/`pause`/`stop` with the pulse animation from index.html on `run`), `makers`/`queue`/`accepted`/`staged` counts, heartbeat age from that asset's `pipeline.json` (`hb 12s`, amber ≥ 90 s, red ≥ 300 s while state is `run` — same thresholds as index.html's `renderHealth`). Clicking a card focuses the asset (updates `?asset=` via `history.replaceState`). Focused asset defaults to `?asset=` param, else first fleet entry.
  - **Asset view** (focused asset), three stacked sections:
    1. *Champion*: image from `champion.json` (`/<asset>/run-NNN/<sheet>` — zero-pad run to 3), caption `promoted by <by> · <at> · <quote>`; empty state "no champion yet".
    2. *Designs*: one lane per `pipeline.json.designs[]` — id (mono), origin chip (`agent`-authored labelled explicitly, per the provenance law), status chip, summary, `last_margins` rendered as signed chips (`+2` green, `-2` red, `0/±1` grey), chips list in amber, `staged` cards prominent (amber border): "panel accepted — <chips> — say `promote <design>` in chat or file a directive". Below the lanes, the *queue* as one compact row per entry, and *events* (last ~15) as a mono feed with relative times.
    3. *Live renders*: the run strip exactly as `live.html` renders it (claimed/unclaimed, shots row, click-to-zoom overlay) — copy that page's `shotEl`/`render` approach against `live.json`.
  - **Chat dock**: merged conversation (user right-aligned, supervisor left, `at` shown as relative time via one shared `fmtRel`), auto-scroll pinned to bottom unless the user scrolled up; input box + send button + "to <focused asset>" toggle; Enter sends; POST failure shows a transient inline "not delivered — server down?" row (does not clear the input). Under the input, a static hint line with the chat verbs: `stop · pause <asset> · resume <asset> · status · add design <asset>: <text> · new <hero|npc|tower> [name]: <desc> · new N npcs · makers <asset> N · promote <design> · finish <asset>`.
  - **Header right**: connection dot (green = last fleet poll OK, red after 3 consecutive failures + banner "server unreachable — showing last good state", matching live.html's failure styling).
  - JS conventions: `'use strict'`, one `esc()`/`h()` pair copied from index.html (`h(tag, attrs, ...kids)` builder), a single `S` state object, per-file `lastStamp` guards so the DOM only rebuilds when payloads change (`live.html`'s pattern), all timers via one `setInterval(tick, 1000)` plus a modulo for the 5 s fetches, `prefers-reduced-motion` respected.

- [ ] **Step 2: Serve it and check the contract test still passes**

Run: `python Assets/Blender/_tools/selftest.py chat`
Expected: PASS (title marker unchanged, POSTs unaffected).

- [ ] **Step 3: Manual render smoke with fixtures.** Create throwaway fixtures under the REAL previews root (cleaned up after):

```powershell
$root = "Assets/Blender/_previews~"
@'
{"stamped":"2026-08-10T12:00:00","note":"fixture","assets":[{"asset":"_selftest_asset","state":"run","makers":1,"queue":2,"accepted":1,"staged":1,"note":"fixture"}]}
'@ | Set-Content -Encoding utf8 "$root/fleet.json"
@'
{"asset":"_selftest_asset","heartbeat":"2026-08-10T12:00:05","state":"run","note":"fixture","makers":[{"id":"m1","design":"d01","attempt":1,"status":"rendering"}],"queue":[{"id":"d02","origin":"user","summary":"queued fixture design"}],"designs":[{"id":"d01","summary":"fixture design","origin":"agent","status":"refining","attempts":1,"last_margins":[1,-1],"staged":false,"chips":[]}],"staged":[{"design":"d01","run":1,"cell":2,"margins":[2,2],"chips":["INV-4 detached"],"at":"2026-08-10T11:58:00"}],"events":[{"at":"2026-08-10T11:59:00","text":"d01 a1: send back (+1,-1)"}]}
'@ | Set-Content -Encoding utf8 "$root/_selftest_asset/pipeline.json"
python Assets/Blender/_tools/tap.py _selftest_asset --once
python Assets/Blender/_tools/serve.py    # foreground is fine for a manual check; ctrl-c after
```

Open `http://localhost:8777/v4.html?asset=_selftest_asset` and verify: fleet card with counts and green heartbeat; design lane with margin chips (+1 grey/-1 grey), staged card amber; queue row; events feed; live strip showing `_selftest_asset` runs if any exist on disk; chat dock — type "hello", confirm 204 in the network tab and the message appearing (from `chat.jsonl`) within a second; kill the server, confirm the red dot + banner. Then delete the fixtures:

```powershell
Remove-Item "$root/fleet.json", "$root/_selftest_asset/pipeline.json"
# restore chat.jsonl if the hello line should not persist:
Remove-Item "$root/chat.jsonl" -ErrorAction SilentlyContinue
```

- [ ] **Step 4: Commit**

```bash
git add Assets/Blender/_tools/gallery/v4.html
git commit -m "gallery: v4 mission-control page - fleet strip, design lanes, live strip, chat dock"
```

---

### Task 8: Skill docs I — `SKILL.md` and `references/page.md`

The skill documents are the workflow's actual program. House style: v2/v3's voice — rules stated with their evidence, mechanisms over exhortation, all paths absolute, `<placeholders>` only in dispatch templates where the dispatching agent fills them from its own context.

**Files:**
- Create: `.claude/skills/blender-model-modev4/SKILL.md`
- Create: `.claude/skills/blender-model-modev4/references/page.md`

**Interfaces:**
- Consumes: everything Tasks 1–7 built; the spec (§4, §5, §8, §9, §12 govern these two files).
- Produces: the supervisor manual other tasks' docs refer to as "SKILL.md"; the data contracts page whose schemas MUST byte-match Task 7's (fleet.json, pipeline.json, chat/feed lines, POST /chat body).

- [ ] **Step 1: Write `SKILL.md`** with this exact frontmatter and these sections:

```markdown
---
name: blender-model-modev4
description: Gloomfell Blender modelling — v4. A scalable fleet: per-asset shepherds, per-design makers proposing variant rows, fresh blind-pairwise reviewer panels with accept/send-back/scrap power, a mission-control page with embedded chat. Invoke ONLY when the user explicitly types /blender-model-modev4. Never auto-invoke, even when Blender or modelling come up in conversation.
---
```

Sections, in order, each with the content named:

1. **Who you are** — the SUPERVISOR: own the chat, run genesis, spawn/monitor shepherds, handle incidents; never design, model, or judge quality. Who reads what: this file is yours alone; shepherds read `references/shepherd.md`; makers/reviewers read no skill file ever (their briefs are self-contained); `references/page.md` is the page/state contract; the spec at `docs/superpowers/specs/2026-08-10-blender-model-modev4-design.md` holds the why.
2. **The three laws** — verbatim from the spec §3 bullet 1, marked as user law overriding everything else, required in every brief you or a shepherd writes.
3. **Ask first** — first action is a question, not a tool call: *(1) Which asset(s) — existing, new, or a batch? (2) A loose brief for each — a sentence is enough.* Until answered, read nothing, build nothing.
4. **Never save/export until "finish"** — verbatim rule + the finish sequence (per asset): set `control.json` state `stop` → shepherd exits → `blender -b -P Assets/Blender/blender_<asset>.py -- save export render` → prune `asset-facts.md` → final report (accepts, margin story, panel-vs-user signal agreement, shelf contents).
5. **Pre-flight (before any shepherd)** — the checklist: asset script git-tracked (`git ls-files --error-unmatch`); script conforming (hook marker) — genesis assets are conforming by construction, legacy ones must be conformed first; gallery answering via HTTP request not port check (`Invoke-WebRequest http://localhost:8777/v4.html -TimeoutSec 5` → 200), else kill stale listener and start `serve.py` backgrounded **with stdout redirected** (the unredirected-print LISTEN-hang is measured, not theory); one `tap.py <asset...>` process for the fleet, restarted when the active set changes; `control.json` present per asset (template below); tell the user the URL in plain words: open `http://localhost:8777/v4.html` and leave the tab open.
6. **State you own** — `_previews~/fleet.json` (schema from `references/page.md`, restamped whenever fleet shape changes), `_previews~/feed.jsonl` (your replies — you never write `chat.jsonl`; the page owns it), per-asset `control.json` (only you write it; stamped `YYYY-MM-DD (supervisor):` notes; template with `{"state":"run","notes":[],"makers":2,"panel":2,"escalate_to":3,"accept_margin":2,"reject_margin":-2,"wave_max_cells":8,"grace":2,"stall":3,"abandon_at":-2,"report_at":8}`), `design-queue.jsonl` (you append user-origin designs; shepherd appends agent-origin ones, labelled).
7. **The chat loop** — watch `_previews~/chat.jsonl` (Monitor the file, or a wakeup loop at ≤ 60 s while any shepherd runs); on each new line: interpret, act, reply into `feed.jsonl` (`{"at","from":"supervisor","text"[,"asset"]}`). The verbs table (must match the page hint line and `references/page.md` exactly): `stop` / `pause <asset>|all` / `resume <asset>|all` → write `control.json` state; `status` → read pipelines + fleet, reply with a digest; `add design <asset>: <text>` → append `{"id":next,"origin":"user","spec":<text>,"status":"queued"}` to that asset's queue and confirm; `new <hero|npc|tower> [<name>][: <desc>]` and `new N npcs` → genesis (section 8); `makers <asset> N` → update control.json (cap 10) and note it; `promote <design>` → resolve the staged card and drive the bake path via the shepherd; `finish <asset>` → the finish sequence; anything else → answer it yourself (you are an LLM; the grammar is a guarantee-floor, not a parser).
8. **Genesis** — from the spec §8, operationalized: concept agent prompt (inline: read `Obsidian/TD/` docs listed by you, tone = grim/silly clash, write the brief to `Obsidian/TD/<Heroes|NPCs>/<Name>.md` — create `NPCs/` if absent — labelled *agent-authored*, return the brief + code name `<name>000`); then `python Assets/Blender/_tools/scaffold.py <asset> [--dist --aim-z]`; `git add` the new script immediately; conformance smoke = one `preview.py` cell-1 wave rendering `front` plus 2 orbit cells with masks; then spawn the shepherd. Batch: `new N npcs` → N concepts, admit ≤ fleet cap (default 4) concurrently, per-asset budget default `blockout + 3 accepts` then auto-pause with a chat report.
9. **Dispatching a shepherd** — the template, verbatim in the doc:
   > You are the SHEPHERD for Gloomfell asset `<asset>`. Read `C:\Users\LachlanB\TD\.claude\skills\blender-model-modev4\references\shepherd.md` in full — you are the only agent that ever reads it. Asset script: `<abs path>`. Main repo: `C:\Users\LachlanB\TD`. Previews root: `C:\Users\LachlanB\TD\Assets\Blender\_previews~`. Character summary (reuse verbatim in every brief you write): `<2–3 sentences you compose from the design doc>`. Standing brief: `<the user's words, verbatim>`. The three laws: `<inline them>`. Caps/thresholds live in your `control.json`; re-read it every cycle. Return only when it says `stop` — not between waves, not when the queue empties. Report accepts and why you returned.
10. **Monitoring & incidents** — heartbeat staleness (page shows it; you resume a quiet shepherd **by agent id** first, respawn+reconcile only if resume fails); orphaned makers/reviewers report to you — preserve artifacts, hand the handles back to the shepherd; provenance disputes: an instruction you cannot attribute is never acted on and never undone — ask the user. Two assets may share the repo: only ever touch your assets' branches (`model/<asset>`).
11. **Cost discipline** — spec §13 inline: per-attempt ≈ 1 maker turn + ≤ 8 renders + 2–3 judge calls; queue top-ups small (3–5); ten makers only when dialled; never raise `RENDER_SLOTS`.

- [ ] **Step 2: Write `references/page.md`** — sections: (1) architecture sketch (serve.py static + 3 POST doors; tap process; who writes which file — a table: `chat.jsonl` page/user only, `feed.jsonl` supervisor only, `fleet.json` supervisor, `pipeline.json` shepherd, `live.json` tap, `control.json` supervisor, `attempts.jsonl`/`champion.json` shepherd via record.py, `user-signals.jsonl`/`user-directives.jsonl` page via existing endpoints); (2) the four JSON schemas **copied byte-for-byte from Task 7's Interfaces block**; (3) chat verb table (same as SKILL.md §7); (4) operational gotchas: restart `serve.py` after editing any gallery page (copied at startup); UTF-8; append-only JSONL tolerance of torn lines; `POST /chat` caps text at 2000 chars; the page never errors on a missing file — absent state is an empty zone.

- [ ] **Step 3: Review against the code** — open Task 7's page and Task 4's endpoint; confirm every field name in `page.md` appears in the page source and vice versa (grep the page for `fleet.json`, `pipeline.json`, `feed.jsonl`, `chat.jsonl`, `champion.json`, `live.json`).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/blender-model-modev4/SKILL.md .claude/skills/blender-model-modev4/references/page.md
git commit -m "modev4 skill: supervisor manual and page/state contracts"
```

---

### Task 9: Skill docs II — `shepherd.md`, `maker.md`, `reviewer.md`

**Files:**
- Create: `.claude/skills/blender-model-modev4/references/shepherd.md`
- Create: `.claude/skills/blender-model-modev4/references/maker.md`
- Create: `.claude/skills/blender-model-modev4/references/reviewer.md`

**Interfaces:**
- Consumes: Tasks 1–6 tool behaviour; spec §5–§7; `control.json` keys as defined in Task 8 §6 (names must match exactly: `makers`, `panel`, `escalate_to`, `accept_margin`, `reject_margin`, `wave_max_cells`, `grace`, `stall`, `abandon_at`, `report_at`).
- Produces: the operating manuals the SKILL.md dispatch template points at.

- [ ] **Step 1: Write `references/shepherd.md`** — sections:

1. **You may be killed at any moment** — v2's discipline verbatim in spirit: if it is only in your context it does not exist; write records the moment you have them; on any (re)start, reconcile `attempts.jsonl` against run directories **before** dispatching — rendered-but-unjudged waves are judged first.
2. **The cycle** — read `control.json` → read `design-queue.jsonl` → top up (spawn a text-only designer batch of 3–5 specs when empty; label `origin: agent`) → keep ≤ `makers` maker agents dispatched, one design each → collect wave returns (poll run dirs; `--tag`/`--design` in the manifest is the attribution, never self-report) → chips triage → panel → decision → records → publish `pipeline.json` (schema in `references/page.md`) with a fresh `heartbeat` every cycle.
3. **Chips triage** — winning cell `inert` → bounce to maker without judges (the cheapest guard; an inert pair is where a forced-choice judge confabulates); any other `blocks_auto` chip → panel runs normally but an accept becomes **staged** (record it in `pipeline.json.staged`, tell the supervisor via an `events` line; the user promotes by chat/directive).
4. **The panel** — mechanics, exact commands:
   - Brief: `python <tools>/judge.py <asset> --run <N> --cell <C> --summary-file <abs summary file> --incumbent <N>:1 --judge j1 --root <previews-root>` → stdout is the reviewer's brief. **Always pass `--incumbent <N>:1`** — cell 1 of the same wave is the incumbent; never let it default to `champion.json` (an older run's seed ⇒ judge.py refuses, correctly).
   - Spawn a FRESH reviewer agent per verdict with prompt = that brief + one closing line: *"Return exactly: PREFER: A|B|TIE / MARGIN: 0-3 / WORKS: one sentence / PROBLEMS: one sentence / SUGGESTION: one outcome sentence."* Reviewers are never resumed, never told the clauses, never given chips, rules or preferences.
   - Record: `python <tools>/judge.py <asset> --run <N> --cell <C> --summary-file <...> --incumbent <N>:1 --judge j1 --answer <A|B|TIE> --margin <M> --suggestion "<verbatim>" --root <previews-root>` — the tool decodes A/B via the derived flip; A/B never enters the record.
   - Judges j1 and j2 always; j3 per the decision rule.
5. **The decision rule** — the spec §6 table verbatim (thresholds by `control.json` key name, never numbers), plus: tie → incumbent; staged path; send-back = resume the same maker with the `refine.py` packet (`python <tools>/refine.py <asset> --design <id> --root <...>` output inline); scrap = shelve (write `shelf/<design>.json` = row spec + verdict digest + final run pointer; leave renders; log it).
6. **Accept: the bake** — serialized (you do one at a time): tell the design's maker to bake (its manual says how) → maker returns a commit sha on `model/<asset>` → verify: render a cell-1-only wave from the baked script under the winning wave's seed and compare against the winning cell (`python <tools>/measure.py <winning v-dir> <bake v-dir> --views orb0,...` — every view must be near-identical: no view over ~2% changed pixels; a failed verify goes back to the maker, nothing is promoted) → `python <tools>/record.py <asset> --promote --run <N> --cell <C> --by panel --note "<margins>" --root <...>` → update overlap flags: any in-flight design whose row touches genes/builders the bake touched gets `needs re-judge` — its next wave is judged fresh, and that is logistics, never reported to its maker as a rejection.
7. **The branch** — `git branch model/<asset> <base>` once at startup if missing; every bake commit lands there (the maker commits; you verify the sha is on the branch); you never commit to `main`, never touch the user's working copy.
8. **Dispatching makers** — front-loading table (maker gets inlined: design spec, the three laws, character summary, asset facts whole, symbol map via `grep -n "^[A-Z_0-9]\+ *=\|^def \|^class \|# --- variant hook ---" <script>`, fully-resolved commands, worktree-free: it edits the MAIN repo script ONLY during a bake it was told to do, otherwise it edits nothing); maker template pointing at `references/maker.md` is NOT used — instead the whole maker brief is self-contained (write the template into this section, from Task 9 Step 2's content, so shepherd copies don't drift: the maker template lives HERE, `maker.md` is its reference copy for humans and future edits — the two must match).
9. **Refine/redesign/abandon/report** — run `refine.py`, obey its call; `report` → an `events` line + supervisor notification and the design pauses for the user.
10. **What the supervisor will ask you** — keep answerable from records: accepts, margin story per design, staged list, queue depth, era boundaries seen.

- [ ] **Step 2: Write `references/maker.md`** — the maker brief template (the shepherd inlines it filled):

   > You are a MAKER for Gloomfell asset `<asset>`, owning design `<id>`.
   > THE THREE LAWS: (1) never think about Unity; (2) size is unknown and may change drastically — no pixel rules, no "reads at N"; (3) no privileged camera — the orbit is the stimulus.
   > THE DESIGN: `<full spec paragraph>`.
   > CHARACTER: `<summary verbatim>`. ASSET FACTS (mechanical; ignoring one produces a render that cannot work): `<whole file inline>`.
   > YOUR FILE: `<abs script path>` (`<N>` lines). MAP: `<symbol index>`. You edit it ONLY when told to bake. For attempts you write rows, not edits.
   > EACH ATTEMPT: (1) design a row — `{"label": "...", "clauses": [{"name","vars"|"patch"}...]}`, ≤ 3 clauses, factorially honest (each clause separable); check every gene FIRST: `python <tools>/genes.py <asset> --check A,B` — a refusal names the fix; use `patch` to recompute deriveds, NEVER to route around a refusal. (2) `python <tools>/axis.py <asset> row.json --seed <given> --dist <d> --aim-z <z> --out wave.json` (3) `python <tools>/preview.py <asset> --variants wave.json --samples 0.3 --tag <your-id> --design <id> --root <previews-root>` — report the run number the moment it prints. (4) Nominate your best cell and return: row spec, run, nominated cell, what you expect it to show.
   > ON A RETRY: the packet below is the judges' words. Take at most THREE points; a point two judges raise outranks one; you may CONTEST a point with a measurement (judges see pixels, you can inspect the model — measured contests ran 5/5 right); never contest with an opinion. `<refine.py output inline>`
   > ON "BAKE run N cell C": fold that cell's clauses into the script as new defaults — `vars` become the gene assignments, `patch` builders land as real code in place of what they replaced; change nothing else; keep genes independent (no new module-level arithmetic between tunables — a derived gene is unsweepable and genes.py will refuse it for everyone after you). Then `git -C <repo> add <script>` and `git -C <repo> commit -m "<asset>: bake <design> a<attempt> — <one line>"` on branch `model/<asset>` (the shepherd created it; `git -C <repo> checkout model/<asset>` first if needed — you touch no other branch, no other file). Reply with the sha.
   > NEVER: save/export, run `--audit`, touch another file, render outside `--root`, or write a `patch` that bypasses a genes.py refusal.

   Plus two short sections: *Why rows, not edits* (d26 conflation story, three lines) and *Mechanical discoveries* (return any new rig fact; the shepherd curates asset-facts).

- [ ] **Step 3: Write `references/reviewer.md`** — short: reviewers are fresh per verdict, blind, taste-only (the calibrated instrument; two absolute scales collapsed — do not add rubrics, scores, or checklists to their brief, do not show them chips/clauses/previous verdicts); the exact spawn/record flow (same commands as shepherd.md §4 — state that shepherd.md §4 is the operating copy and this file explains WHY: flip derivation kills position bias, `--judge` ids decorrelate flips across a panel, seed-equality refusal prevents cross-camera comparisons, SUGGESTION is asked last so it cannot become the optimisation target); and the reviewer-authority table (accept / send back / scrap map to the user's three named powers, thresholds live in control.json).

- [ ] **Step 4: Consistency pass** — grep all five skill docs for: `control.json` key names (must match Task 8 §6 list exactly), the tool command lines (must match the real CLIs from Tasks 1–6: flag names `--summary-file`, `--incumbent`, `--judge`, `--answer`, `--margin`, `--suggestion`, `--root`, `--tag`, `--design`, `--seed`, `--dist`, `--aim-z`, `--out`), and the file names (`pipeline.json`, `fleet.json`, `feed.jsonl`, `chat.jsonl`, `shelf/`). Fix any drift.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/blender-model-modev4/references/shepherd.md .claude/skills/blender-model-modev4/references/maker.md .claude/skills/blender-model-modev4/references/reviewer.md
git commit -m "modev4 skill: shepherd, maker and reviewer manuals"
```

---

### Task 10: Full verification

**Files:** none new — runs everything.

- [ ] **Step 1: Full selftest** (launches Blender many times, ~3–5 min):

Run: `python Assets/Blender/_tools/selftest.py`
Expected: `All checks passed.` — every pre-existing test plus the six new ones (`race`, `eras`, `ratchet`, `tap`, `chat`, `scaffold`). Fix anything red before proceeding; the suite is the gate for `_tools` changes.

- [ ] **Step 2: End-to-end genesis dry run (nothing committed, nothing kept).** Scaffold a real throwaway asset into the true `Assets/Blender/` to prove the default path works, preview it, then remove it:

```powershell
python Assets/Blender/_tools/scaffold.py zztest000
python Assets/Blender/_tools/preview.py zztest000 --views front --samples 0.3
python Assets/Blender/_tools/tap.py zztest000 --once
Remove-Item Assets/Blender/blender_zztest000.py
Remove-Item -Recurse "Assets/Blender/_previews~/zztest000"
Remove-Item -Recurse "Assets/Blender/_zztest000" -ErrorAction SilentlyContinue
```

Expected: preview run exits 0 with `v1/front.png`; tap prints `1 runs`; cleanup leaves `git status` showing nothing new.

- [ ] **Step 3: Repeat Task 7 Step 3's page smoke** once more against the final page (fixtures in, look, fixtures out) if anything in Tasks 8–9 changed a contract.

- [ ] **Step 4: Verify skill loads.** Confirm `.claude/skills/blender-model-modev4/SKILL.md` frontmatter parses (name + description present, description contains the "Invoke ONLY when the user explicitly types /blender-model-modev4" sentence).

- [ ] **Step 5: Final commit if the verification produced fixes**

```bash
git add -A Assets/Blender/_tools .claude/skills/blender-model-modev4
git commit -m "modev4: verification fixes"
```

(skip if the tree is clean).

---

## Plan self-review record

- **Spec coverage:** §4 topology → Tasks 8–9 (docs are the program) + 4–5 (transport); §5 lifecycle → Tasks 6 (genesis), 9 (maker/shepherd), 3 (arc policy); §6 verdicts → Task 9 (§4–5 of shepherd.md) on the unchanged `judge.py`, ratchet in Task 3; §7 bake → Task 9 shepherd.md §6–7, promotions in Task 2; §8 genesis → Tasks 6 + 8; §9 page/chat → Tasks 4, 5, 7, 8; §10 state files → Tasks 7 (schemas), 8 (ownership table); §11 tooling deltas 1–8 → Tasks 4, 7, 5, 1, 2, 3, 6, (selftest folded into 1–6); §12 packaging → Tasks 8–9; §13/§14 → SKILL.md §10–11 content. No gaps found.
- **Placeholder scan:** dispatch templates deliberately carry `<angle-bracket>` slots — those are runtime fill-ins by the dispatching agent, per the front-loading law, not plan placeholders. No TBD/TODO remains.
- **Type consistency:** `next_run_dir` signature unchanged (Task 1 note); `eras()` shape matches Task 3's re-derivation comment; `control.json` key list stated once (Task 8 §6) and referenced by name elsewhere; judge/record/refine CLI flags checked against current sources in Task 9 Step 4.
