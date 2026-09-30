# REVIEW_INBOX.md

## Task 001 — Review round 2

Status: **OPEN**

This file is the repository-visible mirror of actionable PR review feedback. Implementation agents must treat unresolved items here as blocking even if they cannot access private GitHub PR comments.

### R2-1 — Cleanup must never have an unguarded mode

`cleanup_project(..., runtime_root=None)` currently permits callers to omit the trusted root, which bypasses the containment protection entirely.

Required:
- make the trusted runtime root mandatory for automatic cleanup, or otherwise make the unguarded path impossible to invoke accidentally;
- update all tests/callers accordingly;
- add a test proving omission/invalid root refuses cleanup before deletion.

### R2-2 — Mass-deletion guard must run before deletion

`_MAX_REMOVED_GUARD` is currently checked only after files/directories have already been deleted.

Required:
- compute deletion candidates first;
- if the candidate count exceeds the safety threshold, abort before deleting anything;
- test that an over-limit cleanup leaves every candidate untouched.

### R2-3 — Auto calibrations must take precedence over legacy flat files

`newest_calibration()` currently combines `auto/*.npz` and legacy root-level `stereo_*.npz` then selects by mtime. A newer legacy file can therefore override the managed auto history.

Required selection order:
1. explicit file, when configured;
2. newest valid `auto/stereo_*.npz`;
3. only if auto is empty, newest legacy root-level `stereo_*.npz`;
4. only then legacy `./stereo_calib.npz`.

Add a regression test where a legacy root-level file is newer than an auto file and auto must still win.

### R2-4 — Pin/save collision handling must truly be non-overwriting

`promote_calibration()` uses a timestamp with second-level resolution after the first name collision. Multiple promotions of the same name within one second can still target the same destination and overwrite a saved calibration.

Required:
- use collision-proof destination creation (counter/UUID/exclusive creation or equivalent);
- never overwrite an existing saved NPZ or its sidecar;
- add a test that creates 3+ same-name promotions rapidly and verifies all artifacts remain distinct.

### Completion

After fixing all four:
- run the full deterministic suite;
- update TEST_REPORT.md and CHANGE_SUMMARY.md;
- mark each item above RESOLVED with a short implementation note;
- push to the existing PR #1;
- do not merge.
