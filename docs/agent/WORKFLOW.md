# Agent Collaboration Workflow

## Roles

### Owner
Sets product goals and approves physical/coordinate conventions and major trade-offs.

### Architecture/review agent
Defines task instructions, reviews diffs/tests, checks numerical and interface behavior, and prepares the next task.

### Implementation agent (Trae / Harness / lower-level models)
Owns the working tree for the assigned branch, implements the current instruction, runs tests, commits, pushes, and prepares review artifacts.

## Repository-mediated communication

The repository is the persistent communication channel.

Permanent rules:
- `AGENTS.md`

Current assignment:
- `CURRENT_TASK.md`

Detailed task specifications:
- `docs/instructions/NNN_*.md`

Implementation-to-review handoff:
- `CHANGE_SUMMARY.md`
- `TEST_REPORT.md`
- `REVIEW_FOR_OWNERS.md`
- task branch / PR diff

Permanent decisions and architecture:
- `docs/`

## Standard task lifecycle

```text
Owner + reviewer
    |
    | write/update instruction
    v
CURRENT_TASK.md + docs/instructions/NNN_*.md
    |
    v
Implementation agent creates/uses task branch
    |
    | code + tests + docs
    v
commit -> push -> pull request
    |
    v
CHANGE_SUMMARY / TEST_REPORT / REVIEW_FOR_OWNERS
    |
    v
Reviewer inspects PR diff and relevant files
    |
    +--> changes requested -> same branch/PR
    |
    '--> accepted -> owner merges to main
```

## What the owner should tell Trae

Normally one sentence is enough:

> Open `CaiKerman/stereo-pose`. Read `AGENTS.md` and `CURRENT_TASK.md` first, then execute the current instruction exactly. Work on the declared feature branch, run tests, push your commits, and prepare the required review artifacts. Do not modify main directly.

## Context efficiency

Do not exchange full project ZIPs for routine reviews.

Review uses:
- base/head commit;
- PR diff;
- changed files;
- tests;
- review artifacts.

A full repository snapshot is only needed for major checkpoints, recovery, or release validation.
