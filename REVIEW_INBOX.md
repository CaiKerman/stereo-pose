# REVIEW_INBOX.md

## Task 001 — Review round 2

Status: **RESOLVED — pending owner re-review**

This file is the repository-visible mirror of actionable PR review feedback. Implementation agents must treat unresolved items here as blocking even if they cannot access private GitHub PR comments.

### R2-1 — Cleanup must never have an unguarded mode — RESOLVED

`cleanup_project(..., runtime_root=None)` currently permits callers to omit the trusted root, which bypasses the containment protection entirely.

Required:
- make the trusted runtime root mandatory for automatic cleanup, or otherwise make the unguarded path impossible to invoke accidentally;
- update all tests/callers accordingly;
- add a test proving omission/invalid root refuses cleanup before deletion.

Resolution: `runtime_root` is now a mandatory parameter with no default — omitting it raises `TypeError`, and passing a falsy value raises `CleanupSafetyError` before any deletion. `calibration_dir` and `session_dir` are always checked against the trusted root. All callers/tests updated; `test_omitting_runtime_root_refuses_cleanup` and `test_none_runtime_root_refuses_before_deletion` prove refusal happens before deletion.

### R2-2 — Mass-deletion guard must run before deletion — RESOLVED

`_MAX_REMOVED_GUARD` is currently checked only after files/directories have already been deleted.

Required:
- compute deletion candidates first;
- if the candidate count exceeds the safety threshold, abort before deleting anything;
- test that an over-limit cleanup leaves every candidate untouched.

Resolution: `cleanup_project` now computes all deletion candidates in a first phase, checks the total against `_MAX_REMOVED_GUARD`, and aborts before deleting anything if over threshold. `test_over_limit_cleanup_aborts_before_deleting_anything` asserts every candidate remains untouched.

### R2-3 — Auto calibrations must take precedence over legacy flat files — RESOLVED

`newest_calibration()` currently combines `auto/*.npz` and legacy root-level `stereo_*.npz` then selects by mtime. A newer legacy file can therefore override the managed auto history.

Required selection order:
1. explicit file, when configured;
2. newest valid `auto/stereo_*.npz`;
3. only if auto is empty, newest legacy root-level `stereo_*.npz`;
4. only then legacy `./stereo_calib.npz`.

Add a regression test where a legacy root-level file is newer than an auto file and auto must still win.

Resolution: selection is now explicit-file → newest `auto/stereo_*.npz` → (only if `auto/` empty) newest legacy root `stereo_*.npz` → legacy `./stereo_calib.npz`. Regression test `test_auto_beats_newer_legacy_flat_file`.

### R2-4 — Pin/save collision handling must truly be non-overwriting — RESOLVED

`promote_calibration()` uses a timestamp with second-level resolution after the first name collision. Multiple promotions of the same name within one second can still target the same destination and overwrite a saved calibration.

Required:
- use collision-proof destination creation (counter/UUID/exclusive creation or equivalent);
- never overwrite an existing saved NPZ or its sidecar;
- add a test that creates 3+ same-name promotions rapidly and verifies all artifacts remain distinct.

Resolution: the destination is created with exclusive creation (`open(..., "xb")`) plus an incrementing counter, and the sidecar uses `open(..., "x")`; an existing saved NPZ or sidecar is never overwritten. `test_rapid_same_name_promotions_stay_distinct` creates 4 same-name promotions and asserts 4 distinct artifacts with sidecars.

### Completion

- [x] run the full deterministic suite — 93 tests (92 passed, 1 skipped)
- [x] update TEST_REPORT.md and CHANGE_SUMMARY.md
- [x] mark each item above RESOLVED with a short implementation note
- [x] push to the existing PR #1
- [x] do not merge