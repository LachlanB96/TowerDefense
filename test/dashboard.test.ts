// Part of the check. Gloomfell Dashboard's page() and actions (served by ~/AI/Dashboards) through ~/AI/.typescript/dom.ts,
// against a made-up GloomFell in a temp folder: a tiny git repo with a bare origin and a branch in a worktree, a
// TowerCosts.cs with the real one's shape (test/fixtures, copied from Assets/Scripts), stand-in Blender scripts and
// FBXs, a fake _previews~ fleet and tower docs. serve.py is a stand-in HTTP server on a spare port
// (GLOOMFELL_GALLERY_PORT, which the dashboard reads as serve.py does), and pwsh never runs: proc.run is swapped for a
// stub that records what it was asked. Nothing reads the real repo's data.
import test, { before, after } from "node:test";
import assert from "node:assert";
import fs from "fs";
import os from "os";
import path from "path";
import http from "http";
import cp from "child_process";
import type { AddressInfo } from "net";
import { served, serverCtx, type Served } from "../../.typescript/dom";
import { jobQueue } from "../../Dashboards/jobs";
import type { ActionResult } from "../../Dashboards/contract";
import type * as Dash from "../gloomfell-dashboard";

const MODULE = path.join(__dirname, "..", "gloomfell-dashboard.ts");
const FIXTURE = path.join(__dirname, "fixtures", "TowerCosts.cs");
const SCRATCH = fs.mkdtempSync(path.join(os.tmpdir(), "gloomfell-dash-test-"));
const PROJECTS = path.join(SCRATCH, "AI");                 // the made-up megaproject, ctx.projects
const REPO = path.join(PROJECTS, "GloomFell");             // ctx.dir
const ORIGIN = path.join(SCRATCH, "origin.git");
const NO_HOOKS = path.join(SCRATCH, "no-hooks");           // the fixture's commits skip the PC's gitleaks hook
const PREVIEWS = path.join(REPO, "Assets", "Blender", "_previews~");
const START_UNFOCUSED = path.join(PROJECTS, "Terminal", "code", "LBTerm", "lbterm", "motion", "start-unfocused.ps1");
const PWSH = "C:\\Program Files\\PowerShell\\7\\pwsh.exe";
const realEnv = { GLOOMFELL_GALLERY_PORT: process.env.GLOOMFELL_GALLERY_PORT, GIT_CEILING_DIRECTORIES: process.env.GIT_CEILING_DIRECTORIES };

const mod = require(MODULE) as typeof Dash;
const realRun = mod.proc.run;
const realTiming = { ...mod.timing };
const state: Record<string, unknown> = {};   // what the server keeps across renders
const jobs = jobQueue();
const opts = (o: Partial<{ dir: string; state: Record<string, unknown> }> = {}) => ({ vault: SCRATCH, projects: PROJECTS, dir: o.dir || REPO, state: o.state || state, jobs });
type Result = { ok?: boolean; message?: string };
const act = (name: keyof typeof mod.actions, arg?: unknown): ActionResult | Promise<ActionResult> =>
  (mod.actions[name] as (c: unknown, a?: unknown) => ActionResult | Promise<ActionResult>)(serverCtx(MODULE, opts()), arg);
/** draws once to start the background reads (git, the serve.py probe), waits for them, and draws what landed */
async function view<T>(fn: (p: Served) => T, o: Parameters<typeof opts>[0] = {}): Promise<T> {
  (await served(MODULE, opts(o))).close();
  await mod.settle(o.state || state);
  const p = await served(MODULE, opts(o));
  try { return fn(p); } finally { p.close(); }
}
const text = (el: Element | null): string => (el?.textContent || "").replace(/\s+/g, " ").trim();

const write = (rel: string, body: string): void => { const f = path.join(REPO, rel); fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, body); };
const g = (cwd: string, ...args: string[]): string => cp.execFileSync("git",
  ["-c", `core.hooksPath=${NO_HOOKS}`, "-c", "commit.gpgsign=false", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", ...args],
  { cwd, encoding: "utf8", windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
const pad2 = (n: number): string => String(n).padStart(2, "0");
/** the suite's timestamps: local time with no offset */
const local = (ms: number): string => { const d = new Date(ms); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`; };

// ---------- a stand-in serve.py ----------
let suite: http.Server | null = null, port = 0;
function startSuite(): Promise<void> {
  return new Promise(resolve => {
    suite = http.createServer((req, res) => { res.writeHead(req.url === "/v4.html" ? 200 : 404); res.end("suite"); });
    suite.listen(port, "127.0.0.1", () => { port = (suite!.address() as AddressInfo).port; resolve(); });
  });
}
const stopSuite = (): Promise<void> => new Promise(resolve => { if (!suite) return resolve(); suite.close(() => resolve()); suite.closeAllConnections?.(); suite = null; });

before(async () => {
  // git looks no higher than the scratch folder, so the not-a-repo test can't find a repo the temp folder sits in
  process.env.GIT_CEILING_DIRECTORIES = path.dirname(SCRATCH);
  fs.mkdirSync(NO_HOOKS, { recursive: true });
  // the repo: an initial commit pushed to origin; feat/towers, two commits ahead in a worktree; old/merged, behind
  // and with nothing of its own; main one commit past origin; one tracked file changed and one new
  write(".gitignore", ".claude/\nAssets/Blender/_previews~/\nTemp/\n");
  write("Assets/Scripts/TowerCosts.cs", fs.readFileSync(FIXTURE, "utf8"));
  write("Assets/Blender/blender_knight000.py", `import os\nFBX_PATH   = os.path.join(_REPO, "Assets", "Models", "knight000.fbx")\n# --- variant hook -------------------------------------------------------------\nbuild()\n`);
  write("Assets/Blender/blender_tack_shoot.py", `SHOOT_FBX  = os.path.join(_REPO, "Assets", "Models", "tack_shoot.fbx")\nDISK_FBX   = os.path.join(_REPO, "Assets", "Models", "wood_disk.fbx")\n# bpy.ops.export_scene.fbx(filepath="ignored.fbx") lives in a comment\n`);
  write("Assets/Blender/blender_lake.py", "import bpy\n");
  write("Assets/Blender/helper.py", "# not an asset script\n");
  write("Assets/Blender/_tools/serve.py", "# stand-in\n");
  write("Assets/Models/knight000.fbx", "fbx");
  write("Assets/Models/tack_shoot.fbx", "fbx");
  write("Obsidian/TD/Towers/Tack/Base.md", "# Tack\nDamage: TBD\nRange: tbd\n");
  write("Obsidian/TD/Towers/Tack/Path1.md", "Tier 2: TBD. Tier 3: TBD.\n");
  write("Obsidian/TD/Towers/Tack/Path2.md", "All decided.\n");
  write("Obsidian/TD/Towers/Tack/Crosspaths.md", "\n");
  write("Obsidian/TD/Towers/boat/Base.md", "Cost TBD\n");
  write("ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.4.3f1\nm_EditorVersionWithRevision: 6000.4.3f1 (39d1a88d4dd1)\n");
  g(REPO, "init", "-q", "-b", "main");
  g(REPO, "add", "-A");
  g(REPO, "commit", "-q", "-m", "first");
  g(SCRATCH, "init", "-q", "--bare", ORIGIN);
  g(REPO, "remote", "add", "origin", ORIGIN);
  g(REPO, "push", "-q", "origin", "main");
  g(REPO, "branch", "old/merged");
  g(REPO, "worktree", "add", "-q", "-b", "feat/towers", path.join(REPO, ".claude", "worktrees", "towers"), "main");
  const wt = path.join(REPO, ".claude", "worktrees", "towers");
  fs.writeFileSync(path.join(wt, "a.txt"), "a"); g(wt, "add", "a.txt"); g(wt, "commit", "-q", "-m", "towers: a");
  fs.writeFileSync(path.join(wt, "b.txt"), "b"); g(wt, "add", "b.txt"); g(wt, "commit", "-q", "-m", "towers: b");
  write("NOTES.md", "main moves on\n"); g(REPO, "add", "NOTES.md"); g(REPO, "commit", "-q", "-m", "main moves on");
  write("Assets/Blender/blender_lake.py", "import bpy  # changed\n");
  write("scratch.txt", "untracked\n");

  // the fleet: mage000 running with a fresh heartbeat; evilMage000's shepherd says run, but the fleet paused it;
  // knight000 isn't in fleet.json and its heartbeat is ten minutes old; _scratch is the harness's own
  const now = Date.now();
  write("Assets/Blender/_previews~/fleet.json", JSON.stringify({ stamped: local(now - 30e3), note: "two shepherds out", assets: [
    { asset: "mage000", state: "run", makers: 2, queue: 3, accepted: 5, staged: 1, note: "d07 wave rendering" },
    { asset: "evilMage000", state: "pause", makers: 0, queue: 2, accepted: 1, staged: 0, note: "paused by the user" },
  ] }));
  write("Assets/Blender/_previews~/mage000/pipeline.json", JSON.stringify({ asset: "mage000", heartbeat: local(now - 20e3), state: "run", makers: [{ id: "m1" }], queue: [], staged: [] }));
  write("Assets/Blender/_previews~/evilMage000/pipeline.json", JSON.stringify({ asset: "evilMage000", heartbeat: local(now - 3 * 86400e3), state: "run" }));
  write("Assets/Blender/_previews~/knight000/pipeline.json", JSON.stringify({ asset: "knight000", heartbeat: local(now - 600e3), state: "run", makers: [{}, {}], queue: [], staged: [], note: "stuck on d03" }));
  write("Assets/Blender/_previews~/_scratch/pipeline.json", JSON.stringify({ asset: "_scratch", state: "run" }));

  await startSuite();
  process.env.GLOOMFELL_GALLERY_PORT = String(port);
});

after(async () => {
  mod.proc.run = realRun;
  Object.assign(mod.timing, realTiming);
  await stopSuite();
  for (const [k, v] of Object.entries(realEnv)) { if (v === undefined) delete process.env[k]; else process.env[k] = v; }
  fs.rmSync(SCRATCH, { recursive: true, force: true });
});

// ============================================================
//  the parsers, on their own
// ============================================================
test("TowerCosts.cs (the real file's shape): placeable towers and the upgrade table", () => {
  const c = mod.parseTowerCosts(fs.readFileSync(FIXTURE, "utf8"));
  assert.deepStrictEqual(c.towers, [
    { code: "tack000", cost: 300, icon: "UI/tack_icon", range: 3, surface: "Land" },
    { code: "sniper000", cost: 500, icon: "UI/sniper_icon", range: 7, surface: "Land" },
    { code: "boat000", cost: 450, icon: "UI/boat_icon", range: 5.5, surface: "Water" },
  ]);
  const z = { cost: 0, result: "" };
  assert.deepStrictEqual(c.upgrades, {
    tack000: [[{ cost: 500, result: "tack100" }, z, z], [{ cost: 400, result: "tack010" }, z, z], [{ cost: 350, result: "tack001" }, z, z]],
    tack100: [[z, { cost: 900, result: "tack200" }, z], [z, z, z], [z, z, z]],
  });
});

test("the parser skips comments, takes the long UpgradeInfo form, and finds nothing in a file without the tables", () => {
  const c = mod.parseTowerCosts(`
    /* { "ghost000", new TowerInfo(1, "x", 1f) }, */
    private static readonly Dictionary<string, TowerInfo> _towerInfo = new() {
      { "mage000", new TowerInfo(650, "UI/mage_icon", 4.25f) },  // { "fake000", new TowerInfo(2, "y", 2f) }
    };
    private static readonly Dictionary<string, UpgradeInfo[,]> _upgrades = new() {
      { "mage000", new UpgradeInfo[,] { { new UpgradeInfo(200, "mage100") }, { new(300, "mage100") } } },
    };`);
  assert.deepStrictEqual(c.towers.map(t => t.code), ["mage000"]);
  assert.strictEqual(c.towers[0].range, 4.25);
  assert.deepStrictEqual(c.upgrades.mage000, [[{ cost: 200, result: "mage100" }], [{ cost: 300, result: "mage100" }]]);
  assert.deepStrictEqual(mod.parseTowerCosts("public static class TowerCosts { }"), { towers: [], upgrades: {} });
  assert.strictEqual(mod.expectedCode("tack000", 0), "tack100");
  assert.strictEqual(mod.expectedCode("tack100", 0), "tack200");
  assert.strictEqual(mod.expectedCode("tack000", 2), "tack001");
  assert.strictEqual(mod.family("sniper210"), "sniper");
});

test("fbxNames: every quoted .fbx outside comments, Windows raw paths too, else the script's own name", () => {
  assert.deepStrictEqual(mod.fbxNames(`FBX_PATH   = r"C:\\Users\\LachlanB\\TD\\Assets\\Models\\sniper000.fbx"\n`, "blender_sniper000.py"), ["sniper000.fbx"]);
  assert.deepStrictEqual(mod.fbxNames(`A = "x/tack_shoot.fbx"\nB = 'wood_disk.fbx'\n# C = "nope.fbx"\n`, "blender_tack_shoot.py"), ["tack_shoot.fbx", "wood_disk.fbx"]);
  assert.deepStrictEqual(mod.fbxNames("import bpy\n", "blender_lake.py"), ["lake.fbx"]);
});

test("git worktree list --porcelain: the main checkout first, branches, detached, locked and prunable", () => {
  const w = mod.parseWorktrees("worktree C:/r\nHEAD 1234567890\nbranch refs/heads/main\n\nworktree C:/r/.claude/worktrees/x\nHEAD abcdef0123\ndetached\nlocked agent\n\nworktree C:/gone\nHEAD 0000000000\nbranch refs/heads/feat/gone\nprunable gitdir file points to non-existent location\n\n");
  assert.deepStrictEqual(w.map(x => [x.branch, x.main, x.locked, x.prunable, x.head]), [["main", true, false, false, "1234567"], [null, false, true, false, "abcdef0"], ["feat/gone", false, false, true, "0000000"]]);
});

// ============================================================
//  the page
// ============================================================
test("the hero: the suite is up with a link to it, Unity closed, the fleet running, one commit not pushed", () => view(p => {
  const chips = p.$$(".gf-chip").map(text);
  assert.ok(chips.includes("Suite up"), chips.join(" | "));
  assert.ok(chips.includes("Unity closed"), chips.join(" | "));
  assert.ok(chips.includes("Fleet 1 running"), chips.join(" | "));
  assert.ok(chips.includes("Branches 2"), chips.join(" | "));
  assert.match(text(p.$(".gf-hello")), /^1 asset modelling, the suite is up/);
  assert.strictEqual(text(p.$(".gf-pulse-value")), "1");
  assert.match(text(p.$(".gf-pulse-label")), /commit not pushed/);
  assert.strictEqual(p.$(".gf-hero [data-url]")!.getAttribute("data-url"), `http://localhost:${port}/v4.html`);
  assert.ok(!p.$("[data-action=startSuite]"), "no Start suite while it answers");
  assert.ok(p.$("[data-action=refresh]"));
}));

test("git: each branch against main with its worktree, merged ones marked, and the counts", () => view(p => {
  const rows = p.$$(".gf-git tbody tr");
  assert.deepStrictEqual(rows.map(r => text(r.querySelector(".gf-branch"))), ["main", "feat/towers", "old/merged"]);
  assert.strictEqual(text(rows[0].querySelector(".gf-num")), "trunk");
  assert.strictEqual(text(rows[0].querySelector(".gf-wt")), ".");
  assert.strictEqual(text(rows[1].querySelector(".gf-num")), "↑2 ↓1");
  assert.strictEqual(text(rows[1].querySelector(".gf-wt")), ".claude/worktrees/towers");
  assert.strictEqual(text(rows[1].querySelector(".gf-subject")), "towers: b");
  assert.match(text(rows[2].querySelector(".gf-num")), /^↑0 ↓1 merged$/);
  const kpis = Object.fromEntries(p.$$(".gf-git .gf-kpi").map(k => [text(k.querySelector(".gf-kpi-label")), text(k.querySelector(".gf-kpi-value"))]));
  assert.deepStrictEqual(kpis, { "branches besides main": "2", "worktree": "1", "not pushed": "1", "uncommitted here": "2" });
}));

test("the fleet: the fleet's state wins over a shepherd's, heartbeats age only while running, stuck ones flagged", () => view(p => {
  const assets = p.$$(".gf-asset");
  assert.deepStrictEqual(assets.map(a => a.getAttribute("data-asset")), ["mage000", "evilMage000", "knight000"], "fleet.json's order, then the other pipelines; never _scratch");
  const [mage, evil, knight] = assets;
  assert.strictEqual(text(mage.querySelector(".gf-badge")), "run");
  assert.ok(mage.querySelector(".gf-hb.good"));
  assert.match(text(mage.querySelector(".gf-counts")), /2 makers 3 queued 5 accepted 1 staged/);
  assert.ok(mage.querySelector(".gf-count.hot"), "staged work waits on Lachlan");
  assert.strictEqual(text(evil.querySelector(".gf-badge")), "pause");
  assert.ok(evil.querySelector(".gf-hb.faint"), "a paused asset's old heartbeat isn't an alarm");
  assert.strictEqual(text(knight.querySelector(".gf-badge")), "run");
  assert.match(text(knight.querySelector(".gf-hb.bad")), /10m ago · stuck\?/);
  assert.match(text(knight.querySelector(".gf-counts")), /2 makers 0 queued 0 staged/);
  assert.strictEqual(text(p.$(".gf-fleet-state")), "1 asset running");
  assert.strictEqual(text(p.$(".gf-fleet .gf-note")), "two shepherds out");
  assert.strictEqual(p.$(".gf-fleet .gf-tile-head [data-url]")!.getAttribute("data-url"), `http://localhost:${port}/v4.html`);
}));

test("a torn fleet.json says so and still shows the pipelines; no _previews~ is no fleet", async () => {
  const fleet = path.join(PREVIEWS, "fleet.json"), good = fs.readFileSync(fleet, "utf8");
  fs.writeFileSync(fleet, `{"assets": [`);
  try {
    act("refresh");
    await view(p => {
      assert.match(text(p.$(".gf-fleet .gf-err")), /fleet\.json unreadable/);
      assert.deepStrictEqual(p.$$(".gf-asset").map(a => a.getAttribute("data-asset")), ["evilMage000", "knight000", "mage000"]);
      assert.strictEqual(text(p.$(".gf-asset[data-asset=evilMage000] .gf-badge")), "run", "with no fleet.json the shepherd's own state shows");
    });
  } finally { fs.writeFileSync(fleet, good); }
  const off = PREVIEWS.replace(/_previews~$/, "_previews-off~");
  fs.renameSync(PREVIEWS, off);
  try {
    act("refresh");
    await view(p => {
      assert.match(text(p.$(".gf-fleet .gf-empty")), /^No fleet running/);
      assert.ok(p.$$(".gf-chip").map(text).includes("Fleet none"));
    });
  } finally { fs.renameSync(off, PREVIEWS); act("refresh"); }
});

test("Blender scripts: the hook marker, and each FBX the script writes found or not in Assets/Models", () => view(p => {
  const rows = p.$$(".gf-scripts tbody tr").map(r => [...r.querySelectorAll("td")].map(text));
  assert.deepStrictEqual(rows, [
    ["blender_knight000.py", "✓ hook", "✓ knight000.fbx"],
    ["blender_lake.py", "✗ no hook", "✗ lake.fbx"],
    ["blender_tack_shoot.py", "✗ no hook", "✓ tack_shoot.fbx ✗ wood_disk.fbx"],
  ]);
  assert.strictEqual(text(p.$(".gf-scripts .gf-meta")), "1 of 3 conform");
}));

test("towers: each placeable tower's codes, which paths are filled, and the TBDs in its docs", () => view(p => {
  const towers = p.$$(".gf-tower");
  assert.deepStrictEqual(towers.map(t => t.getAttribute("data-family")), ["tack", "sniper", "boat"]);
  const [tack, sniper, boat] = towers;
  assert.deepStrictEqual(text(tack.querySelector(".gf-codes")), "tack000 tack001 tack010 tack100 tack200");
  assert.deepStrictEqual([...tack.querySelectorAll(".gf-path-label")].map(text), ["Path 1 2/3", "Path 2 1/3", "Path 3 1/3"]);
  const path1 = [...tack.querySelectorAll(".gf-path[data-route='1'] .gf-cell")].map(text);
  assert.deepStrictEqual(path1, ["tack100$500", "tack200$900", "–"]);
  assert.ok(!tack.querySelector(".gf-cell.odd"), "every result code matches its path");
  assert.strictEqual(text(tack.querySelector(".gf-tower-head .gf-badge")), "4 TBD");
  const docs = [...tack.querySelectorAll(".gf-doc")];
  assert.deepStrictEqual(docs.map(text), ["Base 2", "Path1 2", "Path2", "Crosspaths"], "Path3.md doesn't exist");
  assert.strictEqual(docs[0].getAttribute("data-open"), "GloomFell/Obsidian/TD/Towers/Tack/Base.md", "a note page link, relative to the megaproject");
  assert.match(text(tack.querySelector(".gf-tower-head .gf-meta")), /\$300 · range 3 · Land/);
  assert.match(text(sniper.querySelector(".gf-tower-foot")), /no design docs/);
  assert.deepStrictEqual([...sniper.querySelectorAll(".gf-cell.on")].length, 0);
  assert.strictEqual(text(boat.querySelector(".gf-tower-head .gf-badge")), "1 TBD", "Towers/boat matched to boat000 whatever its case");
  assert.match(text(boat.querySelector(".gf-tower-head .gf-meta")), /\$450 · range 5\.5 · Water/);
}));

test("towers: an upgrade whose code doesn't match its path is flagged", async () => {
  const file = path.join(REPO, "Assets", "Scripts", "TowerCosts.cs"), good = fs.readFileSync(file, "utf8");
  fs.writeFileSync(file, good.replace(`new(400, "tack010")`, `new(400, "tack020")`));
  try {
    await view(p => {
      const odd = p.$(".gf-tower[data-family=tack] .gf-cell.odd")!;
      assert.strictEqual(text(odd), "tack020$400");
      assert.match(odd.getAttribute("title")!, /expected tack010/);
    });
  } finally { fs.writeFileSync(file, good); }
});

test("Unity: no lockfile is closed; one nothing holds was left behind; one held open is the editor", { skip: !fs.existsSync(PWSH) && "no pwsh 7" }, async () => {
  await view(p => {
    assert.match(text(p.$(".gf-unity .gf-unity-state")), /^closed The editor doesn't have the project open/);
    assert.strictEqual(text(p.$(".gf-unity .gf-meta")), "editor 6000.4.3f1");
  });
  const lock = path.join(REPO, "Temp", "UnityLockfile");
  write("Temp/UnityLockfile", "");
  await view(p => assert.match(text(p.$(".gf-unity .gf-unity-state")), /left behind/));
  // the editor opens it with no sharing; a pwsh holding it the same way stands in for Unity
  const holder = cp.spawn(PWSH, ["-NoProfile", "-NonInteractive", "-Command",
    `$s = [IO.File]::Open('${lock.replace(/'/g, "''")}', 'Open', 'ReadWrite', 'None'); 'held'; Start-Sleep -Seconds 60`], { windowsHide: true, stdio: ["ignore", "pipe", "ignore"] });
  try {
    await new Promise<void>((resolve, reject) => {
      holder.stdout!.on("data", d => { if (String(d).includes("held")) resolve(); });
      holder.on("exit", c => reject(new Error(`the holder exited ${c}`)));
    });
    await view(p => {
      assert.strictEqual(text(p.$(".gf-unity .gf-badge")), "open");
      assert.ok(p.$$(".gf-chip").map(text).includes("Unity open"));
    });
  } finally {
    holder.kill();
    await new Promise(r => holder.once("exit", r));
    fs.rmSync(path.join(REPO, "Temp"), { recursive: true, force: true });
  }
});

test("a folder that isn't a repo says so in the git tile, and every other tile shows its empty state", async () => {
  const bare = path.join(SCRATCH, "empty");
  fs.mkdirSync(bare, { recursive: true });
  await view(p => {
    assert.match(text(p.$(".gf-git .gf-err")), /^⚠ git: /);
    assert.match(text(p.$(".gf-fleet .gf-empty")), /^No fleet running/);
    assert.match(text(p.$(".gf-scripts .gf-empty")), /No Assets\/Blender\/blender_\*\.py/);
    assert.match(text(p.$(".gf-towers .gf-empty")), /No Assets\/Scripts\/TowerCosts\.cs/);
    assert.ok(!p.$("[data-action=startSuite]"), "no serve.py here to start");
  }, { dir: bare, state: {} });
});

// ============================================================
//  the buttons
// ============================================================
interface Call { file: string; args: string[]; cwd: string }
function stub(answer: (c: Call) => Dash.RunResult | Promise<Dash.RunResult>): Call[] {
  const calls: Call[] = [];
  mod.proc.run = async (file, args, o) => { const c = { file, args, cwd: o.cwd }; calls.push(c); return answer(c); };
  return calls;
}
const ok = (stdout = ""): Dash.RunResult => ({ code: 0, stdout, stderr: "", error: null });

test("Run check: without check.ps1 the button says so and pressing it runs nothing", async () => {
  const calls = stub(() => ok());
  await view(p => {
    const b = p.$("[data-action=check]")!;
    assert.ok(b.hasAttribute("disabled"));
    assert.strictEqual(text(b), "No check.ps1 yet");
    assert.match(text(p.$(".gf-check .gf-empty")), /No check\.ps1/);
  });
  const r = act("check") as Result;
  assert.strictEqual(r.ok, false);
  assert.match(r.message!, /no check\.ps1/i);
  assert.strictEqual(jobs.status("check").state, "idle");
  assert.strictEqual(calls.length, 0);
});

test("Run check runs check.ps1 in pwsh 7 as a job: busy while it runs, then how it ended and its output", async () => {
  write("check.ps1", "# stand-in\n");
  let release!: () => void;
  const gate = new Promise<void>(r => { release = r; });
  const calls = stub(async () => { await gate; return ok("tsc: no errors\n# tests 9\n# pass 9\n"); });
  assert.strictEqual(act("check"), "Running check.ps1…");
  await view(p => {
    assert.strictEqual(text(p.$("[data-action=check]")), "Checking…");
    assert.ok(p.$("[data-action=check]")!.hasAttribute("disabled"));
    assert.match(text(p.$(".gf-check .gf-outcome.pending")), /Running check\.ps1/);
  });
  release();
  await jobs.idle();
  assert.deepStrictEqual(calls, [{ file: PWSH, args: ["-NoProfile", "-NonInteractive", "-File", path.join(REPO, "check.ps1")], cwd: REPO }]);
  await view(p => {
    assert.match(text(p.$(".gf-check .gf-outcome.ok")), /^✓ Check passed/);
    assert.match(p.$(".gf-check .gf-log pre")!.textContent!, /# pass 9$/);
    assert.match(text(p.$(".gf-hero .gf-outcome.ok[data-job=check]")), /✓ Check passed/);
  });
  stub(() => ({ code: 1, stdout: "tsc: no errors\nnot ok 3 - towers\n", stderr: "", error: null }));
  act("check");
  await jobs.idle();
  assert.strictEqual(jobs.status("check").last!.message, "✗ Check failed (exit 1): not ok 3 - towers");
  await view(p => assert.match(text(p.$(".gf-check .gf-outcome.err")), /not ok 3 - towers/));
});

test("Start suite: offered only while serve.py doesn't answer, and it needs Start-Unfocused", async () => {
  await stopSuite();
  act("refresh");
  await view(p => {
    assert.ok(p.$$(".gf-chip").map(text).includes("Suite down"));
    assert.strictEqual(text(p.$("[data-action=startSuite]")), "▶ Start suite");
    assert.ok(!p.$(".gf-hero [data-url]"), "nothing to open");
  });
  const calls = stub(() => ok("1"));
  const r = await act("startSuite") as Result;
  assert.strictEqual(r.ok, false);
  assert.match(r.message!, /Start-Unfocused isn't at .*start-unfocused\.ps1/);
  assert.strictEqual(calls.length, 0);
});

test("Start suite starts serve.py through Start-Unfocused with no console, then waits for it to answer", async () => {
  fs.mkdirSync(path.dirname(START_UNFOCUSED), { recursive: true });
  fs.writeFileSync(START_UNFOCUSED, "# stand-in\n");
  let release!: () => void;
  const gate = new Promise<void>(r => { release = r; });
  const calls = stub(async () => { await gate; await startSuite(); return ok("4242\r\n"); });
  // two presses (a double click, the phone and the PC) are one start
  const presses = [act("startSuite"), act("startSuite")];
  const page = await served(MODULE, opts());
  try {
    const b = page.$("[data-action=startSuite]")!;
    assert.strictEqual(text(b), "Starting the suite…", "every page shows it starting");
    assert.ok(b.hasAttribute("disabled"));
  } finally { page.close(); }
  release();
  const [a, b] = await Promise.all(presses) as Result[];
  assert.deepStrictEqual(a, { ok: true, message: `✓ The suite is up at http://localhost:${port}/v4.html (serve.py, pid 4242)` });
  assert.deepStrictEqual(b, a);
  assert.strictEqual(jobs.status("suite").state, "idle", "not on the job queue, where it would wait behind a check");
  assert.strictEqual(calls.length, 1);
  const [c] = calls;
  assert.strictEqual(c.file, PWSH, "pwsh 7 by its full path");
  assert.deepStrictEqual(c.args.slice(0, 3), ["-NoProfile", "-NonInteractive", "-EncodedCommand"]);
  const script = Buffer.from(c.args[3], "base64").toString("utf16le");
  assert.ok(script.includes(`. '${START_UNFOCUSED}'`), script);
  assert.match(script, /Where-Object Source -notmatch 'WindowsApps'/);
  assert.ok(script.includes(`-Arguments '"${path.join(REPO, "Assets", "Blender", "_tools", "serve.py")}"'`), script);
  assert.ok(script.includes(`-WorkingDirectory '${REPO}' -NoConsole`), script);
  await view(p => {
    assert.ok(!p.$("[data-action=startSuite]"));
    assert.strictEqual(text(p.$(".gf-hero [data-url]")), "🖼 Open suite");
  });
  // pressed again while it's up (the CLI, or a page drawn before it came up): nothing starts
  const again = stub(() => ok("1"));
  assert.match(String(((await act("startSuite")) as Result).message), /already up/);
  assert.strictEqual(again.length, 0);
});

test("Start suite says when pwsh fails, and when serve.py never answers", async () => {
  await stopSuite();
  Object.assign(mod.timing, { suiteWaitMs: 20, suiteTries: 3 });
  stub(() => ({ code: 1, stdout: "", stderr: "Exception: Win32_Process.Create failed (9) for C:\\Python313\\python.exe\r\n", error: null }));
  const failed = await act("startSuite") as Result;
  assert.strictEqual(failed.ok, false);
  assert.match(failed.message!, /^✗ Couldn't start serve\.py: Exception: Win32_Process\.Create failed \(9\)/);
  stub(() => ok("77"));
  assert.deepStrictEqual(await act("startSuite"), { ok: false, message: `✗ Started serve.py (pid 77), but nothing answers on port ${port} yet` });
  await view(p => assert.match(text(p.$(".gf-hero .gf-outcome.err[data-job=suite]")), /nothing answers/));
  Object.assign(mod.timing, realTiming);
  await startSuite();
});

test("Refresh forgets what's cached, open pages redraw every 20 s, and the home card's summary reads files only", async () => {
  assert.match(String(act("refresh")), /again/);
  const S = state.gf as { git: { at: number }; probe: { at: number }; files: object };
  assert.strictEqual(S.git.at, 0);
  assert.strictEqual(S.probe.at, 0);
  assert.deepStrictEqual(S.files, {});
  assert.strictEqual(mod.redrawEvery, 20);
  const want = { running: 1, assets: 3, scripts: 3, conforming: 1, towers: 3, tbd: 5, unityOpen: false };
  assert.deepStrictEqual(mod.summary(REPO), want);
  // with an object to keep its reads in, a second call reads nothing that hasn't changed
  const keep: Record<string, unknown> = {};
  assert.deepStrictEqual(mod.summary(REPO, keep), want);
  const files = (keep.gloomfellSummary as { gf: { files: Record<string, { value: unknown }> } }).gf.files;
  const tc = path.join(REPO, "Assets", "Scripts", "TowerCosts.cs"), before = files[tc].value;
  assert.deepStrictEqual(mod.summary(REPO, keep), want);
  assert.strictEqual(files[tc].value, before, "the same parse, not a new one");
});
