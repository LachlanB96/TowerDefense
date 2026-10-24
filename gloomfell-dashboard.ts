// ============================================================
// Gloomfell Dashboard: what's going on in the GloomFell repo, at /d/gloomfell on the Dashboards server
// (~/AI/Dashboards), which calls page() and wraps it in the page frame. Styled by gloomfell-dashboard.css beside
// this file (prefix gf-).
//
// Everything is read from ctx.dir, the repo (the main checkout on the server, a made-up repo in the test):
//   git        branches (ahead and behind main, last commit), worktrees, commits not on origin/main, uncommitted
//              files: `git -C` in the background, kept for 30 s in ctx.state; open pages redraw when it lands
//   fleet      Assets/Blender/_previews~/fleet.json and each <asset>/pipeline.json, as modev4's page contract
//              (.claude/skills/blender-model-modev4/references/page.md) describes them, and whether serve.py answers
//              on its port (probed in the background, kept 15 s)
//   Blender    each Assets/Blender/blender_*.py: does it carry the preview harness's hook marker, and is its FBX in
//              Assets/Models
//   towers     Assets/Scripts/TowerCosts.cs (_towerInfo and _upgrades), and the TBDs left in each tower's design
//              docs under Obsidian/TD/Towers/<Name>/
//   Unity      Temp/UnityLockfile, which the editor holds open while it has the project
// Files are read again only when their size or mtime changes. The buttons: Start suite (serve.py, detached and
// unfocused, through Lachlan's Start-Unfocused), Run check (check.ps1, as a job) and Refresh.
// ============================================================
import fs from "fs";
import path from "path";
import cp from "child_process";
import type { Ctx, ActionResult } from "../Dashboards/contract";

type GfCtx = Pick<Ctx, "dir" | "projects" | "state" | "refresh" | "job" | "jobStatus">;

// pwsh 7 by full path: powershell.exe 5.1 and the bare pwsh.exe Store alias both misbehave here (global CLAUDE.md)
export const PWSH = "C:\\Program Files\\PowerShell\\7\\pwsh.exe";
export const HOOK_MARKER = "# --- variant hook ---";
const GIT_MAX_AGE = 30000;        // git is read again at most every 30 s while a page is open
const GIT_TIMEOUT = 15000;        // one git call; status on a Unity repo is the slow one
const FIRST_GIT_WAIT = 2500;      // the first draw waits this long for git rather than drawing it empty
const PROBE_MAX_AGE = 15000;      // serve.py is asked again at most every 15 s
const PROBE_TIMEOUT = 1500;
const HEARTBEAT_AMBER = 90;       // seconds; the suite's own thresholds (page.md: amber at 90 s, red at 300 s while running)
const HEARTBEAT_RED = 300;
const CHECK_TIMEOUT = 3 * 3600e3;  // check.ps1 gives the Blender harness 30 min and Unity's batch tests 120 under warden-run

// Tests shorten these: how long Start suite waits for serve.py to answer after starting it
export const timing = { suiteWaitMs: 500, suiteTries: 16 };

// open pages redraw this often: heartbeat ages move, and it's what re-reads git and asks serve.py again
export const redrawEvery = 20;

// ---------- utils ----------
const esc = (s: unknown): string => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));
const errMsg = (e: unknown): string => (e as Error)?.message || String(e);
const errCode = (e: unknown): string | undefined => (e as NodeJS.ErrnoException | null)?.code;
const sleep = (ms: number): Promise<void> => new Promise(r => setTimeout(r, ms));
const plural = (n: number, one: string, many = one + "s"): string => `${n} ${n === 1 ? one : many}`;
const fmtAgo = (ms: number | null): string => {
  if (!ms) return "never";
  const s = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (s < 60) return s < 10 ? "just now" : `${s}s ago`;
  const m = Math.floor(s / 60); if (m < 60) return m + "m ago";
  const h = Math.floor(m / 60); if (h < 48) return h + "h ago";
  return Math.floor(h / 24) + "d ago";
};
const pad2 = (n: number): string => String(n).padStart(2, "0");
const fmtDate = (ms: number): string => { const d = new Date(ms); return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`; };
const clip = (s: string, n: number): string => s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
const slash = (p: string): string => p.replace(/\\/g, "/");
/** a path inside dir as dir-relative with forward slashes, else as it is */
const rel = (dir: string, p: string): string => {
  const r = path.relative(path.resolve(dir), path.resolve(p));
  if (r === "") return ".";
  return !r.startsWith("..") && !path.isAbsolute(r) ? slash(r) : slash(p);
};
/** a wait that doesn't hold the process open (the first draw's bounded wait for git) */
const softWait = (ms: number): Promise<void> => new Promise(r => { const t = setTimeout(r, ms); (t as { unref?: () => void }).unref?.(); });
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

// ============================================================
//  state kept across renders (ctx.state; the module itself is loaded again every time)
// ============================================================
interface FileCache { size: number; mtimeMs: number; value: unknown }
interface GitState { facts: GitFacts | null; error: string | null; at: number; running: Promise<void> | null }
interface ProbeState { up: boolean | null; error: string | null; at: number; running: Promise<void> | null }
interface CheckLog { at: number; code: number | null; lines: string[] }
interface StartState { running: Promise<{ ok: boolean; message: string }> | null; since: number; last: { ok: boolean; message: string; at: number } | null }
interface UiState { git: GitState; probe: ProbeState; start: StartState; files: Record<string, FileCache>; checkLog: CheckLog | null }
const uiOf = (ctx: Pick<Ctx, "state">): UiState => (ctx.state.gf ||= {
  git: { facts: null, error: null, at: 0, running: null },
  probe: { up: null, error: null, at: 0, running: null },
  start: { running: null, since: 0, last: null },
  files: {}, checkLog: null,
}) as UiState;

/** A file's contents through parse, read again only when its size or mtime changes. null when it isn't there;
 *  anything else (a torn JSON, no permission) throws, so the tile says so instead of looking empty. */
function cached<T>(S: UiState, file: string, parse: (text: string) => T): T | null {
  let st: fs.Stats;
  try { st = fs.statSync(file); } catch (e) { if (errCode(e) === "ENOENT" || errCode(e) === "ENOTDIR") { delete S.files[file]; return null; } throw e; }
  const c = S.files[file];
  if (c && c.size === st.size && c.mtimeMs === st.mtimeMs) return c.value as T;
  const value = parse(fs.readFileSync(file, "utf8"));
  S.files[file] = { size: st.size, mtimeMs: st.mtimeMs, value };
  return value;
}

/** Waits for whatever the page started in the background (git, the serve.py probe). The test awaits it to draw
 *  what landed; it reads ctx.state, so it works across the module being loaded fresh. */
export async function settle(state: Record<string, unknown>): Promise<void> {
  const S = uiOf({ state });
  await Promise.all([S.git.running, S.probe.running, S.start.running]);
}

// ============================================================
//  processes: every one a button starts goes through proc.run, so the test can stand in for pwsh
// ============================================================
export interface RunResult { code: number | null; stdout: string; stderr: string; error: string | null }
export const proc = {
  run(file: string, args: string[], opts: { cwd: string; timeout: number }): Promise<RunResult> {
    return new Promise(resolve => {
      cp.execFile(file, args, { cwd: opts.cwd, timeout: opts.timeout, windowsHide: true, maxBuffer: 32 * 1024 * 1024 }, (err, stdout, stderr) => {
        const e = err as (Error & { code?: unknown; killed?: boolean }) | null;
        const code = !e ? 0 : typeof e.code === "number" ? e.code : null;
        const error = !e || typeof e.code === "number" ? null : e.killed ? `timed out after ${Math.round(opts.timeout / 1000)} s` : e.message;
        resolve({ code, stdout: String(stdout ?? ""), stderr: String(stderr ?? ""), error });
      });
    });
  },
};

// ============================================================
//  git
// ============================================================
export interface Branch { name: string; date: number; subject: string; ahead: number | null; behind: number | null; worktree: string | null }
export interface Worktree { path: string; branch: string | null; head: string; main: boolean; locked: boolean; prunable: boolean }
export interface GitFacts {
  trunk: string | null;                 // main, or master in a repo that uses it
  branches: Branch[];                   // the trunk first, then the newest commit first
  worktrees: Worktree[];                // the main checkout first, as git lists them
  unpushed: number | null;              // commits on the trunk that origin/<trunk> doesn't have
  unpushedWhy: string | null;           // why unpushed is null (no origin/main)
  dirty: string[];                      // git status --porcelain lines on this checkout
}

function git(dir: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    cp.execFile("git", ["-C", dir, ...args], { windowsHide: true, timeout: GIT_TIMEOUT, maxBuffer: 16 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) reject(new Error(String(stderr || err.message).trim().split(/\r?\n/)[0] || "git failed"));
      else resolve(String(stdout));
    });
  });
}

/** `git worktree list --porcelain`: blocks of "worktree <path>", "HEAD <sha>", "branch refs/heads/x" or
 *  "detached", and "locked"/"prunable" with an optional reason, separated by blank lines. */
export function parseWorktrees(text: string): Worktree[] {
  const out: Worktree[] = [];
  for (const block of text.replace(/\r/g, "").split(/\n\n+/)) {
    const lines = block.split("\n").filter(Boolean);
    const at = lines.find(l => l.startsWith("worktree "));
    if (!at) continue;
    const branch = lines.find(l => l.startsWith("branch "));
    out.push({
      path: path.resolve(at.slice("worktree ".length)),
      head: (lines.find(l => l.startsWith("HEAD ")) || "").slice(5, 12),
      branch: branch ? branch.slice("branch ".length).replace(/^refs\/heads\//, "") : null,
      main: out.length === 0,
      locked: lines.some(l => l === "locked" || l.startsWith("locked ")),
      prunable: lines.some(l => l === "prunable" || l.startsWith("prunable ")),
    });
  }
  return out;
}

export async function gatherGit(dir: string): Promise<GitFacts> {
  // %1f (the unit separator) keeps subjects with tabs or spaces in one field; for-each-ref expands %xx itself
  const US = "\x1f";
  const refs = (await git(dir, ["for-each-ref", "--format=%(refname:short)%1f%(committerdate:unix)%1f%(subject)", "refs/heads"]))
    .split(/\r?\n/).filter(Boolean).map(l => { const [name, date, ...subject] = l.split(US); return { name, date: Number(date) * 1000, subject: subject.join(" ") }; });
  const names = refs.map(r => r.name);
  const trunk = names.includes("main") ? "main" : names.includes("master") ? "master" : null;
  const [ab, wtText, unpushed, status] = await Promise.all([
    // ahead-behind is one call for every branch (git 2.41+); without it each branch shows "?"
    trunk ? git(dir, ["for-each-ref", `--format=%(refname:short)%1f%(ahead-behind:${trunk})`, "refs/heads"]).catch(() => "") : Promise.resolve(""),
    git(dir, ["worktree", "list", "--porcelain"]),
    trunk ? git(dir, ["rev-list", "--count", `refs/remotes/origin/${trunk}..refs/heads/${trunk}`]).then(t => ({ n: Number(t.trim()), why: null }), () => ({ n: null, why: `no origin/${trunk}` }))
      : Promise.resolve({ n: null, why: "no main branch" }),
    git(dir, ["status", "--porcelain"]),
  ]);
  const aheadBehind = new Map<string, [number, number]>();
  for (const l of ab.split(/\r?\n/).filter(Boolean)) {
    const [name, counts = ""] = l.split(US);
    const [a, b] = counts.trim().split(/\s+/).map(Number);
    if (isNum(a) && isNum(b)) aheadBehind.set(name, [a, b]);
  }
  const worktrees = parseWorktrees(wtText);
  const branches: Branch[] = refs.map(r => {
    const w = worktrees.find(x => x.branch === r.name);
    const counts = aheadBehind.get(r.name);
    return { ...r, ahead: counts ? counts[0] : null, behind: counts ? counts[1] : null, worktree: w ? w.path : null };
  }).sort((a, b) => (a.name === trunk ? -1 : b.name === trunk ? 1 : b.date - a.date));
  return { trunk, branches, worktrees, unpushed: unpushed.n, unpushedWhy: unpushed.why, dirty: status.split(/\r?\n/).filter(l => l.trim()) };
}

/** Reads git in the background once the last read is GIT_MAX_AGE old; open pages redraw when it lands. */
function kickGit(ctx: GfCtx): void {
  const G = uiOf(ctx).git;
  if (G.running || Date.now() - G.at < GIT_MAX_AGE) return;
  G.running = gatherGit(ctx.dir).then(f => { G.facts = f; G.error = null; }, e => { G.error = errMsg(e); })
    .finally(() => { G.at = Date.now(); G.running = null; ctx.refresh(); });
}

// ============================================================
//  the suite: serve.py on GLOOMFELL_GALLERY_PORT (8777), the same variable serve.py reads
// ============================================================
export const galleryPort = (): number => Number(process.env.GLOOMFELL_GALLERY_PORT) || 8777;
export const suiteUrl = (): string => `http://localhost:${galleryPort()}/v4.html`;

/** A GET of the suite's page: 200 is up (a port that's only listening isn't, as the modev4 skill found). */
async function probeOnce(): Promise<{ up: boolean; error: string | null }> {
  try {
    const r = await fetch(`http://127.0.0.1:${galleryPort()}/v4.html`, { signal: AbortSignal.timeout(PROBE_TIMEOUT) });
    void r.body?.cancel().catch(() => {});
    return r.status === 200 ? { up: true, error: null } : { up: false, error: `answered ${r.status}` };
  } catch (e) {
    const cause = (e as { cause?: { code?: string } }).cause;
    return { up: false, error: cause?.code === "ECONNREFUSED" || /ECONNREFUSED|Unable to connect/i.test(errMsg(e)) ? "not running" : (e as Error).name === "TimeoutError" ? `no answer in ${PROBE_TIMEOUT / 1000} s` : errMsg(e) };
  }
}
/** Asks serve.py now, joining a probe already on its way, and keeps the answer in ctx.state. */
function probeNow(ctx: GfCtx): Promise<void> {
  const P = uiOf(ctx).probe;
  if (P.running) return P.running;
  P.running = probeOnce().then(r => { const changed = r.up !== P.up; P.up = r.up; P.error = r.error; P.at = Date.now(); P.running = null; if (changed) ctx.refresh(); });
  return P.running;
}
function kickProbe(ctx: GfCtx): void {
  const P = uiOf(ctx).probe;
  if (!P.running && Date.now() - P.at >= PROBE_MAX_AGE) void probeNow(ctx);
}

// ============================================================
//  the modelling fleet (modev4's files under Assets/Blender/_previews~)
// ============================================================
interface FleetFile { stamped?: string; note?: string; assets?: { asset?: string; state?: string; makers?: number; queue?: number; accepted?: number; staged?: number; note?: string }[] }
interface PipelineFile { asset?: string; heartbeat?: string; state?: string; note?: string; makers?: unknown[]; queue?: unknown[]; staged?: unknown[] }
export type StateKind = "run" | "pause" | "idle" | "unknown";
export interface AssetRow {
  asset: string; state: string; kind: StateKind; heartbeat: number | null; ageS: number | null;
  makers: number | null; queue: number | null; accepted: number | null; staged: number | null; note: string; error: string | null;
}
export interface FleetView { root: string; exists: boolean; stamped: number | null; note: string; error: string | null; assets: AssetRow[]; running: number }

export const stateKind = (s: string): StateKind => /^run/i.test(s) ? "run" : /^paus/i.test(s) ? "pause" : /^(stop|done|finish|idle|complete)/i.test(s) ? "idle" : "unknown";
/** the suite writes local times without an offset ("2026-08-10T12:00:05"), which Date reads as local time */
const when = (s: unknown): number | null => { if (typeof s !== "string" || !s) return null; const t = Date.parse(s); return Number.isFinite(t) ? t : null; };
const len = (v: unknown): number | null => Array.isArray(v) ? v.length : null;

export function readFleet(S: UiState, dir: string): FleetView {
  const root = path.join(dir, "Assets", "Blender", "_previews~");
  const view: FleetView = { root, exists: fs.existsSync(root), stamped: null, note: "", error: null, assets: [], running: 0 };
  let fleet: FleetFile | null = null;
  try { fleet = cached(S, path.join(root, "fleet.json"), t => JSON.parse(t) as FleetFile); }
  catch (e) { view.error = `fleet.json unreadable: ${errMsg(e)}`; }
  if (fleet && typeof fleet === "object") { view.stamped = when(fleet.stamped); view.note = typeof fleet.note === "string" ? fleet.note : ""; }
  const listed = fleet && Array.isArray(fleet.assets) ? fleet.assets.filter(a => a && typeof a.asset === "string") : [];
  // an asset the fleet doesn't list still shows if it has a pipeline.json (a shepherd from an older fleet); folders
  // starting with _ are the harness's own (_fingerprints, _scratch, _selftest_asset)
  let dirs: string[] = [];
  try { dirs = fs.readdirSync(root, { withFileTypes: true }).filter(d => d.isDirectory() && !d.name.startsWith("_") && fs.existsSync(path.join(root, d.name, "pipeline.json"))).map(d => d.name); }
  catch (e) { if (errCode(e) !== "ENOENT") view.error = view.error || errMsg(e); }
  const names = [...new Set([...listed.map(a => a.asset!), ...dirs.sort()])];
  for (const asset of names) {
    const f = listed.find(a => a.asset === asset);
    let p: PipelineFile | null = null, error: string | null = null;
    try { p = cached(S, path.join(root, asset, "pipeline.json"), t => JSON.parse(t) as PipelineFile); }
    catch (e) { error = `pipeline.json unreadable: ${errMsg(e)}`; }
    // the fleet's word on an asset's state wins over the shepherd's own (page.md)
    const state = (f && typeof f.state === "string" && f.state) || (p && typeof p.state === "string" && p.state) || "unknown";
    const heartbeat = p ? when(p.heartbeat) : null;
    const row: AssetRow = {
      asset, state, kind: stateKind(state), heartbeat, ageS: heartbeat == null ? null : Math.max(0, Math.round((Date.now() - heartbeat) / 1000)),
      makers: isNum(f?.makers) ? f!.makers! : p ? len(p.makers) : null,
      queue: isNum(f?.queue) ? f!.queue! : p ? len(p.queue) : null,
      accepted: isNum(f?.accepted) ? f!.accepted! : null,
      staged: isNum(f?.staged) ? f!.staged! : p ? len(p.staged) : null,
      note: (f && typeof f.note === "string" && f.note) || (p && typeof p.note === "string" && p.note) || "",
      error,
    };
    if (row.kind === "run" && row.ageS != null && row.ageS < HEARTBEAT_RED) view.running++;
    view.assets.push(row);
  }
  return view;
}

// ============================================================
//  Blender scripts
// ============================================================
export interface ScriptRow { file: string; conforms: boolean; fbx: { name: string; exists: boolean; mtime: number | null }[] }

/** The FBX files a script writes: every quoted name ending .fbx outside # comments (boat000.fbx, or tack_shoot.fbx
 *  and wood_disk.fbx for one that writes two), else blender_<x>.py's own <x>.fbx. */
export function fbxNames(src: string, file: string): string[] {
  const names = new Set<string>();
  for (const line of src.split(/\r?\n/)) {
    if (/^\s*#/.test(line)) continue;
    for (const m of line.matchAll(/["']([^"'\r\n]*?\.fbx)["']/gi)) names.add(path.win32.basename(m[1]));
  }
  if (!names.size) names.add(path.basename(file).replace(/^blender_/, "").replace(/\.py$/, "") + ".fbx");
  return [...names];
}

export function readScripts(S: UiState, dir: string): ScriptRow[] {
  const blender = path.join(dir, "Assets", "Blender"), models = path.join(dir, "Assets", "Models");
  let files: string[];
  try { files = fs.readdirSync(blender).filter(f => /^blender_.+\.py$/i.test(f)).sort((a, b) => a.localeCompare(b)); }
  catch (e) { if (errCode(e) === "ENOENT") return []; throw e; }
  return files.map(file => {
    const facts = cached(S, path.join(blender, file), src => ({ conforms: src.includes(HOOK_MARKER), fbx: fbxNames(src, file) }))!;
    return {
      file, conforms: facts.conforms,
      fbx: facts.fbx.map(name => { let mtime: number | null = null; try { mtime = fs.statSync(path.join(models, name)).mtimeMs; } catch { /* not exported */ } return { name, exists: mtime != null, mtime }; }),
    };
  });
}

// ============================================================
//  towers: TowerCosts.cs and the design docs
// ============================================================
export interface TowerInfo { code: string; cost: number; icon: string; range: number; surface: string }
export interface UpgradeCell { cost: number; result: string }
export interface Costs { towers: TowerInfo[]; upgrades: Record<string, UpgradeCell[][]> }   // upgrades[code][path][level]

/** The text between the first { at or after from and the } that closes it (string literals skipped). */
function braced(text: string, from: number): { body: string; end: number } | null {
  const start = text.indexOf("{", from);
  if (start < 0) return null;
  let depth = 0;
  for (let i = start; i < text.length; i++) {
    const c = text[i];
    if (c === '"') { i++; while (i < text.length && text[i] !== '"') { if (text[i] === "\\") i++; i++; } continue; }
    if (c === "{") depth++;
    else if (c === "}" && --depth === 0) return { body: text.slice(start + 1, i), end: i + 1 };
  }
  return null;
}

/** The two tables in TowerCosts.cs. Deliberately simple: it knows the file's own shape (a Dictionary initialiser of
 *  { "code", new TowerInfo(cost, "icon", rangef[, SurfaceType.X]) } and one of { "code", new UpgradeInfo[,] { rows } }
 *  whose rows are { new(cost, "result"), ... }), and skips anything else rather than guessing. */
export function parseTowerCosts(src: string): Costs {
  const text = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  const out: Costs = { towers: [], upgrades: {} };
  const info = /\b_towerInfo\s*=/.exec(text);
  const infoBlock = info ? braced(text, info.index) : null;
  if (infoBlock) {
    for (const m of infoBlock.body.matchAll(/\{\s*"([^"]+)"\s*,\s*new\s+TowerInfo\s*\(\s*(-?\d+)\s*,\s*"([^"]*)"\s*,\s*(-?[\d.]+)f?\s*(?:,\s*SurfaceType\.(\w+)\s*)?\)\s*\}/g))
      out.towers.push({ code: m[1], cost: Number(m[2]), icon: m[3], range: Number(m[4]), surface: m[5] || "Land" });
  }
  const up = /\b_upgrades\s*=/.exec(text);
  const upBlock = up ? braced(text, up.index) : null;
  if (upBlock) {
    const key = /"([^"]+)"\s*,\s*new\s+UpgradeInfo\s*\[\s*,\s*\]/g;
    for (let m: RegExpExecArray | null; (m = key.exec(upBlock.body)); ) {
      const table = braced(upBlock.body, m.index + m[0].length);
      if (!table) break;
      key.lastIndex = table.end;
      out.upgrades[m[1]] = [...table.body.matchAll(/\{([^{}]*)\}/g)].map(row =>
        [...row[1].matchAll(/new\s*(?:UpgradeInfo\s*)?\(\s*(-?\d+)\s*,\s*"([^"]*)"\s*\)/g)].map(c => ({ cost: Number(c[1]), result: c[2] })));
    }
  }
  return out;
}

/** a tower code's family, the name before its tier digits: tack210 is tack */
export const family = (code: string): string => (/^[A-Za-z_]+/.exec(code) || [code])[0];
/** the code an upgrade along path p should give: that path's digit one higher (tack000, path 1 -> tack100) */
export function expectedCode(code: string, p: number): string | null {
  const m = /^(.*?)(\d+)$/.exec(code);
  if (!m || p >= m[2].length) return null;
  const digits = m[2].split("").map(Number);
  digits[p]++;
  return digits[p] > 9 ? null : m[1] + digits.join("");
}

export const DOC_FILES = ["Base.md", "Path1.md", "Path2.md", "Path3.md", "Crosspaths.md"];
export interface PathCell { result: string; cost: number; from: string; codeOk: boolean }
export interface FamilyView {
  name: string; base: TowerInfo; codes: string[];
  paths: (PathCell | null)[][];          // [path][tier - 1]
  docs: { dir: string; tbd: number; files: { file: string; tbd: number; path: string }[] } | null;
}

export function readTowers(S: UiState, dir: string): { file: string; families: FamilyView[]; exists: boolean } {
  const file = path.join(dir, "Assets", "Scripts", "TowerCosts.cs");
  const costs = cached(S, file, parseTowerCosts);
  if (!costs) return { file, families: [], exists: false };
  const towersDir = path.join(dir, "Obsidian", "TD", "Towers");
  let docDirs: string[] = [];
  try { docDirs = fs.readdirSync(towersDir, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name); }
  catch (e) { if (errCode(e) !== "ENOENT") throw e; }
  const families = costs.towers.map(base => {
    const name = family(base.code);
    const keys = Object.keys(costs.upgrades).filter(k => family(k) === name);
    const codes = new Set<string>([base.code, ...keys]);
    const width = Math.max(3, ...keys.map(k => costs.upgrades[k].length));
    const depth = Math.max(3, ...keys.flatMap(k => costs.upgrades[k].map(r => r.length)));
    const paths: (PathCell | null)[][] = Array.from({ length: width }, () => Array.from({ length: depth }, () => null));
    for (const k of keys) costs.upgrades[k].forEach((row, p) => row.forEach((c, level) => {
      if (c.cost <= 0 || !c.result) return;   // a zero-cost cell is "not upgradeable here" (TowerCosts.TryGetUpgrade)
      codes.add(c.result);
      paths[p][level] = { result: c.result, cost: c.cost, from: k, codeOk: expectedCode(k, p) === c.result };
    }));
    // design docs: Obsidian/TD/Towers/<Name>/, the folder named like the family whatever its case (Tack for tack000)
    const docName = docDirs.find(d => d.toLowerCase() === name.toLowerCase());
    let docs: FamilyView["docs"] = null;
    if (docName) {
      const files = DOC_FILES.map(f => {
        const p = path.join(towersDir, docName, f);
        const n = cached(S, p, t => (t.match(/\bTBD\b/gi) || []).length);
        return n == null ? null : { file: f, tbd: n, path: p };
      }).filter((x): x is { file: string; tbd: number; path: string } => !!x);
      docs = { dir: docName, tbd: files.reduce((s, f) => s + f.tbd, 0), files };
    }
    return { name, base, codes: [...codes].sort(), paths, docs };
  });
  return { file, families, exists: true };
}

// ============================================================
//  Unity
// ============================================================
export interface UnityView { open: boolean; lockfile: boolean; since: number | null; version: string | null; error: string | null }

/** The editor keeps Temp/UnityLockfile open with no sharing while it has the project, so opening it fails (EBUSY on
 *  Windows). A lockfile that opens is one a closed or crashed editor left behind. */
export function readUnity(dir: string): UnityView {
  let version: string | null = null;
  try { version = (/m_EditorVersion:\s*(\S+)/.exec(fs.readFileSync(path.join(dir, "ProjectSettings", "ProjectVersion.txt"), "utf8")) || [])[1] || null; }
  catch { /* not a Unity project, or not yet */ }
  const lock = path.join(dir, "Temp", "UnityLockfile");
  let st: fs.Stats;
  try { st = fs.statSync(lock); } catch { return { open: false, lockfile: false, since: null, version, error: null }; }
  try { fs.closeSync(fs.openSync(lock, "r")); return { open: false, lockfile: true, since: st.mtimeMs, version, error: null }; }
  catch (e) {
    if (["EBUSY", "EPERM", "EACCES"].includes(errCode(e) || "")) return { open: true, lockfile: true, since: st.mtimeMs, version, error: null };
    return { open: false, lockfile: true, since: st.mtimeMs, version, error: errMsg(e) };
  }
}

// ============================================================
//  the page
// ============================================================
/** a tile whose own reads can fail without taking the rest of the page with it */
function tile(cls: string, title: string, meta: string, body: () => string): string {
  let inner: string;
  try { inner = body(); } catch (e) { inner = `<div class="gf-err">⚠ ${esc(errMsg(e))}</div>`; }
  return `<section class="gf-tile ${cls}"><div class="gf-tile-head"><h2>${esc(title)}</h2>${meta ? `<span class="gf-meta">${meta}</span>` : ""}</div>${inner}</section>`;
}
const badge = (cls: string, text: string, title = ""): string => `<span class="gf-badge ${cls}"${title ? ` title="${esc(title)}"` : ""}>${esc(text)}</span>`;
const mark = (ok: boolean, yes: string, no: string, title = ""): string => `<span class="gf-mark ${ok ? "good" : "bad"}"${title ? ` title="${esc(title)}"` : ""}>${ok ? "✓" : "✗"} ${esc(ok ? yes : no)}</span>`;
/** a note link for the server's note page, when the file is in the megaproject (it isn't in the test's made-up repo) */
function openAttr(ctx: GfCtx, file: string): string {
  const r = path.relative(ctx.projects, file);
  return r && !r.startsWith("..") && !path.isAbsolute(r) ? ` data-open="${esc(slash(r))}"` : "";
}

export async function page(ctx: GfCtx): Promise<string> {
  const S = uiOf(ctx), dir = ctx.dir;
  kickGit(ctx);
  // the first draw waits a moment for git rather than showing an empty tile; later draws use the last read
  if (!S.git.facts && !S.git.error && S.git.running) await Promise.race([S.git.running, softWait(FIRST_GIT_WAIT)]);
  kickProbe(ctx);

  const G = S.git, P = S.probe;
  let fleet: FleetView | null = null, fleetErr: string | null = null;
  try { fleet = readFleet(S, dir); } catch (e) { fleetErr = errMsg(e); }
  let unity: UnityView | null = null;
  try { unity = readUnity(dir); } catch (e) { unity = { open: false, lockfile: false, since: null, version: null, error: errMsg(e) }; }
  const checkFile = path.join(dir, "check.ps1"), hasCheck = fs.existsSync(checkFile);
  const checkJob = ctx.jobStatus("check"), starting = !!S.start.running;
  const hasServe = fs.existsSync(path.join(dir, "Assets", "Blender", "_tools", "serve.py"));

  // ---------- hero ----------
  function heroHtml(): string {
    const chip = (cls: string, label: string, value: string, title = "", live = false): string =>
      `<span class="gf-chip ${cls}"${title ? ` title="${esc(title)}"` : ""}>${live ? `<span class="gf-live"></span>` : ""}${esc(label)} <b>${esc(value)}</b></span>`;
    const chips = [
      !unity ? "" : unity.error ? chip("bad", "Unity", "can't tell", unity.error)
        : unity.open ? chip("good", "Unity", "open", `the editor has had the project since ${fmtDate(unity.since!)}`, true)
        : chip("", "Unity", unity.lockfile ? "closed (stale lock)" : "closed", unity.version ? `editor ${unity.version}` : ""),
      P.up == null ? chip("wait", "Suite", "checking…") : P.up ? chip("good", "Suite", "up", suiteUrl(), true) : chip("", "Suite", "down", P.error || ""),
      !fleet ? chip("bad", "Fleet", "unreadable") : fleet.running ? chip("good", "Fleet", `${fleet.running} running`, "", true)
        : chip("", "Fleet", fleet.assets.length ? "idle" : "none"),
      G.facts ? chip("", "Branches", String(G.facts.branches.filter(b => b.name !== G.facts!.trunk).length)) : "",
    ].join("");
    const suiteBtn = P.up ? `<button class="gf-btn" data-url="${esc(suiteUrl())}" title="Open the Gloomfell suite in the browser">🖼 Open suite</button>`
      : (P.up === false || starting) && hasServe ? `<button class="gf-btn accent" data-action="startSuite" title="python Assets/Blender/_tools/serve.py, detached and without a window"${starting ? " disabled" : ""}>${starting ? "Starting the suite…" : "▶ Start suite"}</button>` : "";
    const checkBtn = hasCheck
      ? `<button class="gf-btn" data-action="check" title="pwsh -File check.ps1 (TypeScript, the Blender harness, Unity's EditMode tests), as a job"${checkJob.state !== "idle" ? " disabled" : ""}>${checkJob.state === "running" ? "Checking…" : checkJob.state === "queued" ? "Check queued…" : "✔ Run check"}</button>`
      : `<button class="gf-btn" data-action="check" title="There's no check.ps1 in the repo yet" disabled>No check.ps1 yet</button>`;
    const line = (key: string, last: { ok: boolean; message: string | null; at: number } | null, busy: boolean): string => last && last.message && !busy
      ? `<div class="gf-outcome ${last.ok ? "ok" : "err"}" data-job="${key}">${esc(last.message)} <span class="gf-meta">${esc(fmtAgo(last.at))}</span></div>` : "";
    const unpushed = G.facts?.unpushed;
    // the headline is what's live right now; the frame's title already says Gloomfell
    const live = [fleet?.running ? `${plural(fleet.running, "asset")} modelling` : "", unity?.open ? "Unity has the project open" : "", P.up ? "the suite is up" : ""].filter(Boolean);
    const hello = live.length ? live.join(", ").replace(/^./, c => c.toUpperCase()) : "All quiet";
    return `<div class="gf-hero">
      <div class="gf-hero-main">
        <div class="gf-hello">${esc(hello)}<span>Unity 6 tower defence: gothic Templars and wooden tack launchers. The repo, the modelling fleet, the towers' tables and the editor, read from <code>${esc(slash(dir))}</code>.</span></div>
        <div class="gf-chips">${chips}</div>
        <div class="gf-actions">${suiteBtn}${checkBtn}<button class="gf-btn ghost" data-action="refresh" title="Read git, the fleet and the suite again">↻ Refresh</button></div>
        ${line("suite", S.start.last, starting)}${line("check", checkJob.last, checkJob.state !== "idle")}
      </div>
      <div class="gf-hero-side">
        <div class="gf-pulse-value">${unpushed == null ? "–" : unpushed}</div>
        <div class="gf-pulse-label">${unpushed === 1 ? "commit" : "commits"} not pushed</div>
        <div class="gf-pulse-sub">${G.facts?.unpushedWhy ? esc(G.facts.unpushedWhy) : "public repo: pushed only when you ask"}</div>
      </div>
    </div>`;
  }

  // ---------- git ----------
  function gitHtml(): string {
    const meta = G.running && G.facts ? "reading again…" : G.at ? `read ${esc(fmtAgo(G.at))}` : "";
    return tile("gf-tile--wide gf-git", "Git", meta, () => {
      if (!G.facts) return G.error ? `<div class="gf-err">⚠ git: ${esc(G.error)}</div>` : `<div class="gf-empty">Reading git…</div>`;
      const f = G.facts, others = f.branches.filter(b => b.name !== f.trunk), extraWt = f.worktrees.filter(w => !w.main);
      // worktree paths read from the main checkout (".claude/worktrees/x"), whichever checkout this page is served from
      const base = f.worktrees.find(w => w.main)?.path || dir;
      const kpi = (v: string | number, label: string, cls = "", title = ""): string => `<div class="gf-kpi ${cls}"${title ? ` title="${esc(title)}"` : ""}><div class="gf-kpi-value">${esc(v)}</div><div class="gf-kpi-label">${esc(label)}</div></div>`;
      const kpis = `<div class="gf-kpis">
        ${kpi(others.length, others.length === 1 ? "branch besides main" : "branches besides main")}
        ${kpi(extraWt.length, extraWt.length === 1 ? "worktree" : "worktrees")}
        ${kpi(f.unpushed ?? "–", "not pushed", f.unpushed ? "warn" : "", f.unpushedWhy || `on ${f.trunk}, not on origin/${f.trunk}`)}
        ${kpi(f.dirty.length, "uncommitted here", f.dirty.length ? "warn" : "", f.dirty.slice(0, 12).join("\n"))}
      </div>`;
      const rows = f.branches.map(b => {
        const trunk = b.name === f.trunk;
        const vs = trunk ? `<span class="gf-faint">trunk</span>`
          : b.ahead == null ? `<span class="gf-faint">?</span>`
          : `<span class="gf-ahead${b.ahead ? "" : " zero"}" title="commits on ${esc(b.name)} that ${esc(f.trunk)} doesn't have">↑${b.ahead}</span> <span class="gf-behind${b.behind ? "" : " zero"}" title="commits on ${esc(f.trunk)} that ${esc(b.name)} doesn't have">↓${b.behind}</span>${b.ahead === 0 ? ` ${badge("faint", "merged")}` : ""}`;
        const wt = b.worktree ? `<code title="${esc(b.worktree)}">${esc(rel(base, b.worktree))}</code>` : `<span class="gf-faint">–</span>`;
        return `<tr${trunk ? ` class="trunk"` : ""}><td class="gf-branch"><code>${esc(b.name)}</code></td><td class="gf-num">${vs}</td><td class="gf-when" title="${esc(fmtDate(b.date))}">${esc(fmtAgo(b.date))}</td><td class="gf-subject" title="${esc(b.subject)}">${esc(b.subject)}</td><td class="gf-wt">${wt}</td></tr>`;
      }).join("");
      const loose = f.worktrees.filter(w => !w.main && !w.branch).map(w => `<li><code>${esc(rel(base, w.path))}</code> <span class="gf-faint">detached at ${esc(w.head)}</span></li>`).join("");
      const flags = f.worktrees.filter(w => w.prunable).map(w => `<li><code>${esc(rel(base, w.path))}</code> ${badge("warn", "prunable", "its folder is gone: git worktree prune")}</li>`).join("");
      return kpis + `<table class="gf-table"><thead><tr><th>Branch</th><th class="gf-num">vs ${esc(f.trunk || "main")}</th><th>Last commit</th><th>Subject</th><th>Worktree</th></tr></thead><tbody>${rows}</tbody></table>`
        + (loose || flags ? `<ul class="gf-list">${loose}${flags}</ul>` : "");
    });
  }

  // ---------- fleet ----------
  function fleetHtml(): string {
    const link = P.up ? `<a class="gf-link" data-url="${esc(suiteUrl())}">open the suite ↗</a>` : "";
    const meta = [fleet?.stamped ? `fleet.json stamped ${esc(fmtAgo(fleet.stamped))}` : "", link].filter(Boolean).join(" · ");
    return tile("gf-tile--wide gf-fleet", "Modelling fleet", meta, () => {
      if (fleetErr) return `<div class="gf-err">⚠ ${esc(fleetErr)}</div>`;
      const v = fleet!;
      const err = v.error ? `<div class="gf-err">⚠ ${esc(v.error)}</div>` : "";
      if (!v.assets.length) return err + `<div class="gf-empty">No fleet running: nothing in <code>Assets/Blender/_previews~</code> yet. <code>/blender-model-modev4</code> starts one.</div>`;
      const note = v.note ? `<div class="gf-note">${esc(v.note)}</div>` : "";
      const rows = v.assets.map(a => {
        const stCls = a.kind === "run" ? "run" : a.kind === "pause" ? "pause" : "faint";
        // stale heartbeats only matter while the asset is meant to be running (page.md)
        const hbCls = a.kind !== "run" || a.ageS == null ? "faint" : a.ageS >= HEARTBEAT_RED ? "bad" : a.ageS >= HEARTBEAT_AMBER ? "warn" : "good";
        const hb = a.heartbeat == null ? `<span class="gf-faint">no heartbeat</span>`
          : `<span class="gf-hb ${hbCls}" title="${esc(fmtDate(a.heartbeat))}">${esc(fmtAgo(a.heartbeat))}${hbCls === "bad" ? " · stuck?" : ""}</span>`;
        const n = (v: number | null, label: string): string => v == null ? "" : `<span class="gf-count${label === "staged" && v ? " hot" : ""}"><b>${v}</b> ${label}</span>`;
        return `<div class="gf-asset ${stCls}" data-asset="${esc(a.asset)}">
          <div class="gf-asset-head"><code class="gf-asset-name">${esc(a.asset)}</code>${badge(stCls, a.state)}${hb}</div>
          <div class="gf-counts">${[n(a.makers, a.makers === 1 ? "maker" : "makers"), n(a.queue, "queued"), n(a.accepted, "accepted"), n(a.staged, "staged")].filter(Boolean).join(" ")}</div>
          ${a.note ? `<div class="gf-asset-note" title="${esc(a.note)}">${esc(clip(a.note, 220))}</div>` : ""}
          ${a.error ? `<div class="gf-err">⚠ ${esc(a.error)}</div>` : ""}
        </div>`;
      }).join("");
      const head = v.running ? `<div class="gf-fleet-state run">${plural(v.running, "asset")} running</div>` : `<div class="gf-fleet-state">No fleet running${v.assets.length ? `: ${plural(v.assets.length, "asset")} from the last one` : ""}</div>`;
      return err + head + note + `<div class="gf-assets">${rows}</div>`;
    });
  }

  // ---------- Blender scripts ----------
  function scriptsHtml(): string {
    let rows: ScriptRow[] = [], err: string | null = null;
    try { rows = readScripts(S, dir); } catch (e) { err = errMsg(e); }
    const meta = err ? "" : `${rows.filter(r => r.conforms).length} of ${rows.length} conform`;
    return tile("gf-scripts", "Blender scripts", meta, () => {
      if (err) throw new Error(err);
      if (!rows.length) return `<div class="gf-empty">No <code>Assets/Blender/blender_*.py</code>.</div>`;
      const body = rows.map(r => `<tr><td><code>${esc(r.file)}</code></td><td>${r.conforms ? mark(true, "hook", "", "drivable by preview.py and build_one.py") : mark(false, "", "no hook", "saves and exports on every run; preview.py refuses it")}</td><td>${r.fbx.map(x => mark(x.exists, x.name, x.name, x.exists ? `Assets/Models/${x.name}, ${fmtDate(x.mtime!)}` : `no Assets/Models/${x.name}`)).join(" ")}</td></tr>`).join("");
      return `<table class="gf-table"><thead><tr><th>Script</th><th>Preview harness</th><th>FBX in Assets/Models</th></tr></thead><tbody>${body}</tbody></table>`;
    });
  }

  // ---------- towers ----------
  function towersHtml(): string {
    return tile("gf-towers", "Towers", "<code>Assets/Scripts/TowerCosts.cs</code>", () => {
      const t = readTowers(S, dir);
      if (!t.exists) return `<div class="gf-empty">No <code>Assets/Scripts/TowerCosts.cs</code>.</div>`;
      if (!t.families.length) return `<div class="gf-empty">No placeable towers found in <code>_towerInfo</code>.</div>`;
      return `<div class="gf-towerlist">` + t.families.map(fam => {
        const tiers = fam.paths[0]?.length || 3;
        const grid = fam.paths.map((row, p) => {
          const filled = row.filter(Boolean).length;
          const cells = row.map((c, i) => c
            ? `<span class="gf-cell on${c.codeOk ? "" : " odd"}" title="${esc(`${c.from} → ${c.result} for $${c.cost}${c.codeOk ? "" : `: expected ${expectedCode(c.from, p) || "a 3-digit code"}`}`)}"><code>${esc(c.result)}</code><b>$${c.cost}</b></span>`
            : `<span class="gf-cell" title="Path ${p + 1}, tier ${i + 1}: not upgradeable yet">–</span>`).join("");
          // data-route, not data-path: the shared client opens a data-path on the PC
          return `<div class="gf-path" data-route="${p + 1}"><span class="gf-path-label">Path ${p + 1} <b>${filled}/${tiers}</b></span>${cells}</div>`;
        }).join("");
        const docs = !fam.docs ? `<span class="gf-faint">no design docs in Obsidian/TD/Towers</span>`
          : `<span class="gf-docs">${fam.docs.files.map(f => `<span class="gf-doc${f.tbd ? " tbd" : ""}"${openAttr(ctx, f.path)} title="${esc(`${fam.docs!.dir}/${f.file}: ${plural(f.tbd, "TBD")}`)}">${esc(f.file.replace(/\.md$/, ""))}${f.tbd ? ` <b>${f.tbd}</b>` : ""}</span>`).join("")}</span>`;
        return `<div class="gf-tower" data-family="${esc(fam.name)}">
          <div class="gf-tower-head"><span class="gf-tower-name">${esc(fam.name[0].toUpperCase() + fam.name.slice(1))}</span><code>${esc(fam.base.code)}</code><span class="gf-meta">$${fam.base.cost} · range ${fam.base.range} · ${esc(fam.base.surface)}</span>${fam.docs ? badge(fam.docs.tbd ? "warn" : "good", `${fam.docs.tbd} TBD`) : ""}</div>
          <div class="gf-paths">${grid}</div>
          <div class="gf-tower-foot"><span class="gf-codes">${fam.codes.map(c => `<code>${esc(c)}</code>`).join(" ")}</span>${docs}</div>
        </div>`;
      }).join("") + `</div>`;
    });
  }

  // ---------- Unity ----------
  function unityHtml(): string {
    return tile("gf-unity", "Unity", unity?.version ? `editor <code>${esc(unity.version)}</code>` : "", () => {
      const u = unity!;
      if (u.error) return `<div class="gf-err">⚠ Temp/UnityLockfile: ${esc(u.error)}</div>`;
      const state = u.open ? `${badge("run", "open")} <span>The editor has the project open, since ${esc(fmtDate(u.since!))}. Claude drives it through UnityMCP (<code>refresh_unity</code>, <code>read_console</code>).</span>`
        : u.lockfile ? `${badge("faint", "closed")} <span><code>Temp/UnityLockfile</code> is left behind from ${esc(fmtDate(u.since!))}, but nothing holds it: the editor isn't running on this project.</span>`
        : `${badge("faint", "closed")} <span>The editor doesn't have the project open (no <code>Temp/UnityLockfile</code>).</span>`;
      return `<div class="gf-unity-state">${state}</div>`;
    });
  }

  // ---------- check ----------
  function checkHtml(): string {
    const meta = hasCheck ? "<code>check.ps1</code>" : "";
    return tile("gf-check", "Check", meta, () => {
      if (!hasCheck) return `<div class="gf-empty">No <code>check.ps1</code> in the repo yet, so there's nothing to run.</div>`;
      const j = checkJob, log = S.checkLog;
      const state = j.state === "running" ? `<div class="gf-outcome pending">Running check.ps1… <span class="gf-meta">since ${esc(fmtAgo(j.since))}</span></div>`
        : j.state === "queued" ? `<div class="gf-outcome pending">Waiting behind another job…</div>`
        : j.last ? `<div class="gf-outcome ${j.last.ok ? "ok" : "err"}">${esc(j.last.message || (j.last.ok ? "passed" : "failed"))} <span class="gf-meta">${esc(fmtAgo(j.last.at))} · ${(j.last.ms / 1000).toFixed(1)} s</span></div>`
        : `<div class="gf-empty">Not run since the Dashboards server started.</div>`;
      const tail = log && log.lines.length ? `<details class="gf-log"><summary>Last output (${log.lines.length} lines)</summary><pre>${esc(log.lines.join("\n"))}</pre></details>` : "";
      return state + tail;
    });
  }

  function footerHtml(): string {
    return `<div class="gf-syncline">git <b>${esc(G.at ? fmtAgo(G.at) : "reading")}</b> · suite <b>${esc(P.at ? fmtAgo(P.at) : "asking")}</b> on port <b>${galleryPort()}</b> · <code>bun server.ts render gloomfell</code> in Dashboards shows this page</div>`;
  }

  return heroHtml()
    + `<div class="gf-grid">` + gitHtml() + fleetHtml() + scriptsHtml() + towersHtml() + unityHtml() + checkHtml() + `</div>`
    + footerHtml();
}

// ============================================================
//  the buttons
// ============================================================
/** a PowerShell single-quoted string */
const psq = (s: string): string => `'${s.replace(/'/g, "''")}'`;
/** what Start suite runs: python found on PATH (never the Store's WindowsApps alias) started by Start-Unfocused with
 *  no console, from the repo root, so nothing comes up in front or takes the keyboard (global CLAUDE.md) */
export function startScript(startUnfocused: string, serve: string, dir: string): string {
  return [
    "$ErrorActionPreference = 'Stop'",
    "$ProgressPreference = 'SilentlyContinue'",
    `. ${psq(startUnfocused)}`,
    "$py = Get-Command python -CommandType Application -ErrorAction SilentlyContinue | Where-Object Source -notmatch 'WindowsApps' | Select-Object -First 1",
    "if (-not $py) { throw 'python is not on PATH' }",
    `Start-Unfocused -Exe $py.Source -Arguments ${psq(`"${serve}"`)} -WorkingDirectory ${psq(dir)} -NoConsole`,
  ].join("\n");
}
export const startUnfocusedPath = (projects: string): string => path.join(projects, "Terminal", "code", "LBTerm", "lbterm", "motion", "start-unfocused.ps1");
const lastLine = (s: string): string => s.replace(/\r/g, "").split("\n").map(l => l.trim()).filter(Boolean).pop() || "";

/** pwsh runs Start-Unfocused, then serve.py gets a few seconds to answer (it copies the suite's pages into the
 *  previews root before it listens) */
async function startServe(ctx: GfCtx, su: string, serve: string): Promise<{ ok: boolean; message: string }> {
  const S = uiOf(ctx);
  // asked afresh: the page's last answer can be 15 s old, and a second serve.py would only fail to bind the port
  S.probe.at = 0;
  await probeNow(ctx);
  if (S.probe.up) return { ok: true, message: `The suite is already up at ${suiteUrl()}` };
  const r = await proc.run(PWSH, ["-NoProfile", "-NonInteractive", "-EncodedCommand", Buffer.from(startScript(su, serve, ctx.dir), "utf16le").toString("base64")], { cwd: ctx.dir, timeout: 60000 });
  if (r.code !== 0) return { ok: false, message: `✗ Couldn't start serve.py: ${lastLine(r.stderr) || r.error || `pwsh exited ${r.code}`}` };
  const pid = Number(lastLine(r.stdout)) || null;
  for (let i = 0; i < timing.suiteTries; i++) {
    S.probe.at = 0;
    await probeNow(ctx);
    if (S.probe.up) return { ok: true, message: `✓ The suite is up at ${suiteUrl()}${pid ? ` (serve.py, pid ${pid})` : ""}` };
    await sleep(timing.suiteWaitMs);
  }
  return { ok: false, message: `✗ Started serve.py${pid ? ` (pid ${pid})` : ""}, but nothing answers on port ${galleryPort()} yet` };
}

export const actions = {
  /** starts serve.py and answers once it's up or ~8 s have gone by. Not a job: a dashboard's jobs run one at a time,
   *  and this shouldn't wait behind a check that runs Blender and Unity for an hour. A second press, from any page
   *  or the CLI, joins the start on its way rather than starting another. */
  startSuite: (ctx: GfCtx): ActionResult | Promise<ActionResult> => {
    const S = uiOf(ctx);
    const serve = path.join(ctx.dir, "Assets", "Blender", "_tools", "serve.py");
    if (!fs.existsSync(serve)) return { ok: false, message: "✗ There's no Assets/Blender/_tools/serve.py in this checkout" };
    const su = startUnfocusedPath(ctx.projects);
    if (!fs.existsSync(su)) return { ok: false, message: `✗ Start-Unfocused isn't at ${su}` };
    if (!S.start.running) {
      S.start.since = Date.now();
      S.start.running = startServe(ctx, su, serve)
        .catch(e => ({ ok: false, message: `✗ Couldn't start serve.py: ${errMsg(e)}` }))
        .then(r => { S.start.last = { ...r, at: Date.now() }; return r; })
        .finally(() => { S.start.running = null; ctx.refresh(); });
      ctx.refresh();   // every open page shows it starting
    }
    return S.start.running;
  },

  /** check.ps1 in pwsh 7, as a job; its last 40 lines are kept for the Check tile */
  check: (ctx: GfCtx): ActionResult => {
    const file = path.join(ctx.dir, "check.ps1");
    if (!fs.existsSync(file)) return { ok: false, message: "There's no check.ps1 in GloomFell yet, so there's nothing to run" };
    void ctx.job("check", async () => {
      const r = await proc.run(PWSH, ["-NoProfile", "-NonInteractive", "-File", file], { cwd: ctx.dir, timeout: CHECK_TIMEOUT });
      const out = (r.stdout + (r.stderr ? "\n" + r.stderr : "")).replace(/\r/g, "").split("\n");
      while (out.length && !out[out.length - 1].trim()) out.pop();
      uiOf(ctx).checkLog = { at: Date.now(), code: r.code, lines: out.slice(-40) };
      if (r.code === 0) return "✓ Check passed";
      return { ok: false, message: `✗ Check failed${r.code != null ? ` (exit ${r.code})` : ""}: ${r.error || lastLine(r.stderr) || lastLine(r.stdout) || "no output"}` };
    });
    return "Running check.ps1…";
  },

  /** forgets what's cached, so the redraw that follows reads git, the files and serve.py again */
  refresh: (ctx: GfCtx): ActionResult => {
    const S = uiOf(ctx);
    S.git.at = 0; S.probe.at = 0; S.files = {};
    return "Reading git, the fleet and the suite again";
  },
};

/** For the home page's card: facts from files only (no git, no network), from the repo at dir. Give it an object the
 *  caller keeps (its own ctx.state) and the files are read again only when they change, as they are here; without
 *  one it reads everything (about 35 ms on the real repo, most of it the Blender scripts). */
export function summary(dir: string, keep: Record<string, unknown> = {}): { running: number; assets: number; scripts: number; conforming: number; towers: number; tbd: number; unityOpen: boolean } {
  const S = uiOf({ state: (keep.gloomfellSummary ||= {}) as Record<string, unknown> });
  // (only S.files is used here; the rest of the state is the page's)
  const fleet = readFleet(S, dir), scripts = readScripts(S, dir), towers = readTowers(S, dir);
  return {
    running: fleet.running, assets: fleet.assets.length,
    scripts: scripts.length, conforming: scripts.filter(s => s.conforms).length,
    towers: towers.families.length, tbd: towers.families.reduce((n, f) => n + (f.docs?.tbd || 0), 0),
    unityOpen: readUnity(dir).open,
  };
}
