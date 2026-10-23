<#
GloomFell's check (project rule 5): nothing lands on main until this passes.

  pwsh -File check.ps1                         every part
  pwsh -File check.ps1 -Only ts,harness,unity  some of them

Run it from anywhere; it checks the folder it sits in (the main checkout or a worktree).
Don't wrap it in warden-run: it queues its own heavy parts with the Process Warden.

  ts       TypeScript 7 type-checks the repo's .ts (the dashboard, the gallery suite) and runs
           its *.test.ts, through the megaproject's ..\.typescript\check.cts. Skipped until
           there's a tsconfig.json.
  harness  the Blender preview harness's pytest suite (Assets\Blender\_tools\tests). It starts
           Blender, so it runs through warden-run.
  unity    the EditMode tests (Assets\Tests\Editor) in Unity batch mode, through warden-run.
           Unity can't open a project its editor already has open, so with the editor open on
           this folder this part fails and says so (Lachlan's pick, 2026-10-24): close the
           editor, or run them from it (Test Runner window, or UnityMCP's run_tests).

A worktree has no Library, and importing the project from scratch takes a long while, so in a
worktree Library becomes a junction to one shared cache, %LOCALAPPDATA%\GloomFell\check-library,
copied once from the main checkout's Library. Each check then reimports only what its branch
changed. One check uses the cache at a time (a lock file beside it). land unlinks junctions
before it removes a worktree, and the folders Unity leaves in a worktree (Logs, UserSettings,
Temp) are removed again here, so land can take the worktree afterwards.
#>
param(
  [ValidateSet('ts', 'harness', 'unity')]
  [string[]]$Only = @('ts', 'harness', 'unity')
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$state = Join-Path $env:LOCALAPPDATA 'GloomFell\check'
New-Item -ItemType Directory -Force -Path $state | Out-Null
$results = [ordered]@{}

function Say([string]$text) { Write-Host "[check] $text" }

function Find-WardenRun {
  $cmd = Get-Command warden-run -ErrorAction SilentlyContinue
  if (-not $cmd) { throw "warden-run isn't on PATH (Process Dashboard's install-hooks.ps1 puts its shim in ~\.local\bin)" }
  $cmd.Source
}

# Is the Unity editor holding this project? It keeps Temp\UnityLockfile open for as long as it's up.
function Test-EditorOpen([string]$project) {
  $lock = Join-Path $project 'Temp\UnityLockfile'
  if (-not (Test-Path -LiteralPath $lock)) { return $false }
  try { [IO.File]::Open($lock, 'Open', 'ReadWrite', 'None').Dispose(); return $false } catch { return $true }
}

# The main checkout, when $root is a worktree; $null when $root is the main checkout itself.
function Get-MainCheckout {
  $gitDir = (git -C $root rev-parse --absolute-git-dir).Trim()
  $common = (git -C $root rev-parse --path-format=absolute --git-common-dir).Trim()
  if ([IO.Path]::GetFullPath($gitDir) -eq [IO.Path]::GetFullPath($common)) { return $null }
  Split-Path -Parent $common
}

function Invoke-TypeScript {
  if (-not (Test-Path -LiteralPath (Join-Path $root 'tsconfig.json'))) { Say 'ts: no tsconfig.json yet, skipped'; return 'skipped' }
  $checkCts = Join-Path $root '..\.typescript\check.cts'
  if (-not (Test-Path -LiteralPath $checkCts)) {
    throw "no ..\.typescript\check.cts beside this folder. In a worktree that's the junction <repo>\.claude\worktrees\.typescript (~\.claude\reference\typescript.md)"
  }
  Push-Location $root
  # Out-Host: a native command's output inside a function would otherwise become its return value.
  try { node $checkCts | Out-Host; $code = $LASTEXITCODE } finally { Pop-Location }
  if ($code) { 'failed' } else { 'passed' }
}

function Invoke-Harness {
  $tests = Join-Path $root 'Assets\Blender\_tools\tests'
  $warden = Find-WardenRun
  # Several Blenders at once (preview.py runs up to 4 builds, see granted_cpus()), each a GPU context.
  $env:PYTHONDONTWRITEBYTECODE = '1'
  & $warden --name gloomfell-harness --cpus 8 --mem 12 --gpu --max 30m -- python -m pytest $tests -p no:cacheprovider -q | Out-Host
  if ($LASTEXITCODE) { 'failed' } else { 'passed' }
}

function Invoke-Unity {
  if (Test-EditorOpen $root) {
    Say "unity: the Unity editor has $root open, and batch mode can't open it beside the editor. Close the editor and run the check again, or run the EditMode tests from the editor (Test Runner, or UnityMCP's run_tests)."
    return 'failed'
  }
  $version = ((Get-Content -LiteralPath (Join-Path $root 'ProjectSettings\ProjectVersion.txt') | Select-String '^m_EditorVersion:\s*(\S+)').Matches[0].Groups[1].Value)
  $unity = if ($env:GLOOMFELL_UNITY) { $env:GLOOMFELL_UNITY } else { Join-Path $env:ProgramFiles "Unity\Hub\Editor\$version\Editor\Unity.exe" }
  if (-not (Test-Path -LiteralPath $unity)) { throw "Unity $version isn't at $unity (set GLOOMFELL_UNITY)" }

  $main = Get-MainCheckout
  $lockStream = $null
  $made = @()
  try {
    if ($main) {
      # A worktree: borrow the shared Library cache (see the header).
      $cache = Join-Path $env:LOCALAPPDATA 'GloomFell\check-library'
      try { $lockStream = [IO.File]::Open("$cache.lock", 'OpenOrCreate', 'ReadWrite', 'None') }
      catch { Say "unity: another check is using the shared Library ($cache); run this one when it's done"; return 'failed' }
      foreach ($d in 'Logs', 'UserSettings', 'Temp') { if (-not (Test-Path -LiteralPath (Join-Path $root $d))) { $made += $d } }

      $library = Join-Path $root 'Library'
      if (-not (Test-Path -LiteralPath $library)) {
        if (-not (Test-Path -LiteralPath $cache)) {
          $mainLibrary = Join-Path $main 'Library'
          if ((Test-Path -LiteralPath $mainLibrary) -and -not (Test-EditorOpen $main)) {
            Say "unity: first worktree check on this PC: copying the main checkout's Library to $cache (about 3 GB, once)"
            robocopy $mainLibrary $cache /E /MT:16 /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
            if ($LASTEXITCODE -ge 8) { throw "robocopy of the Library failed (exit $LASTEXITCODE)" }
          } else {
            Say "unity: no Library to copy (the main checkout's is missing or its editor is open), so Unity imports the project from scratch into $cache. That takes a while, once."
            New-Item -ItemType Directory -Force -Path $cache | Out-Null
          }
        }
        New-Item -ItemType Junction -Path $library -Target $cache | Out-Null
      }
    }

    $name = Split-Path -Leaf $root
    $xml = Join-Path $state "$name-editmode.xml"
    $log = Join-Path $state "$name-unity.log"
    Remove-Item -LiteralPath $xml -ErrorAction SilentlyContinue
    Say "unity: EditMode tests in batch mode (log: $log)"
    $warden = Find-WardenRun
    # No -quit: -runTests exits by itself, with 0 (passed), 2 (tests failed) or 3 (couldn't run).
    & $warden --name gloomfell-unity-tests --cpus 4 --mem 8 --max 120m -- $unity -batchmode -nographics -projectPath $root -runTests -testPlatform EditMode -testResults $xml -logFile $log | Out-Host
    $code = $LASTEXITCODE

    if (Test-Path -LiteralPath $xml) {
      [xml]$run = Get-Content -LiteralPath $xml -Raw
      $tr = $run.'test-run'
      Say "unity: $($tr.total) tests, $($tr.passed) passed, $($tr.failed) failed, $($tr.skipped) skipped"
      foreach ($case in $run.SelectNodes("//test-case[@result='Failed']")) {
        Say "  FAILED $($case.fullname): $($case.failure.message.'#cdata-section' ?? $case.failure.message)"
      }
    } else {
      Say "unity: no results file. The end of the log:"
      if (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Tail 40 | ForEach-Object { Write-Host "    $_" } }
    }
    if ($code -eq 0 -and (Test-Path -LiteralPath $xml)) { 'passed' } else { 'failed' }
  } finally {
    if ($main) {
      # What Unity left in the worktree that git ignores, so land can remove the worktree.
      foreach ($d in $made) {
        $p = Join-Path $root $d
        if ((Test-Path -LiteralPath $p) -and ((Resolve-Path -LiteralPath $p).Path.StartsWith($root))) { Remove-Item -LiteralPath $p -Recurse -Force -ErrorAction SilentlyContinue }
      }
    }
    if ($lockStream) { $lockStream.Dispose() }
  }
}

foreach ($part in 'ts', 'harness', 'unity') {
  if ($Only -notcontains $part) { continue }
  Say "--- $part"
  try {
    $results[$part] = switch ($part) {
      'ts' { Invoke-TypeScript }
      'harness' { Invoke-Harness }
      'unity' { Invoke-Unity }
    }
  } catch {
    Say "$part couldn't run: $_"
    $results[$part] = 'failed'
  }
}

Say ('--- ' + (($results.GetEnumerator() | ForEach-Object { "$($_.Key) $($_.Value)" }) -join ', '))
if ($results.Values -contains 'failed') { exit 1 }
Say 'Check passed'
exit 0
