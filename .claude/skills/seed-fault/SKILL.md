---
name: seed-fault
description: Inject one deliberate fault into src/, record exactly what the PostToolUse hook and the test suite say about it, then fix it and log the episode. Use when measuring how the repo's guard rails respond to a specific defect.
allowed-tools: Read, Edit, Bash(git status:*), Bash(git diff:*), Bash(make:*), Bash(python -m pytest:*)
---

# Working tree
!`git status --porcelain -- src/ docs/SEEDED_FAULTS.md`

# Seeding a fault: $ARGUMENTS

The point of this exercise is the *record*, not the fault. An entry that says
"the suite caught it in one run" and an entry that says "nothing failed" are
both results. Never write up an episode you did not actually run, and never
retype hook output or pytest output from memory -- copy it.

## What fires, and when

Reading this first stops you mis-recording the episode:

- `.claude/hooks/check_leakage.sh` is a **PostToolUse** hook on `Edit|Write`.
  It exits 0 for any path that is not `*src/*.py` -- so a fault whose target is
  outside `src/` produces no hook output at all, and the user asked for a `src/`
  target.
- It runs **only** `python -m pytest tests/test_leakage.py -q`. Not the full
  suite. A fault in leakage scope turns the hook red; a fault outside it leaves
  the hook green and only `make test` goes red. **That is the expected common
  case**, not a broken procedure -- record it as "hook fired, exit 0, no stderr"
  and move on.
- On failure it prints `Leakage tests failed after editing <path>:` plus the
  last 20 lines of pytest, to **stderr**, and exits 2. That stderr comes back to
  you as a system message in the tool result. There is no file to redirect; copy
  the text from that message verbatim.
- The *fix* edit is also an `Edit` on `src/`, so the hook fires a second time
  and should exit 0. Prefer fixing with `Edit` over `git checkout` for exactly
  that reason -- it gives you the green hook as evidence.

## Step 0: establish a green baseline

Run `make test` **before** touching anything. If it is not green, stop: you
cannot attribute a red run to a fault you injected on top of an already-failing
suite. Record the pass count and `git rev-parse --short HEAD`.

If `git status --porcelain -- src/` above is non-empty, stop and ask -- a
pre-existing edit will contaminate the diff and the fix.

## Step 1: write down, then apply, the minimal diff

Read the target file first. Decide the **smallest** change that produces the
fault in `$ARGUMENTS` -- one line if one line will do. Apply it with `Edit`, one
edit, nothing else folded in.

Then capture the diff as it actually landed, not as you planned it:

```
git diff -- src/
```

Keep that text; it goes in the log verbatim. "Minimal" is a claim you are
making, so if the fault needed more than the obvious one-liner, say why in the
entry rather than trimming the diff to look tidy.

## Step 2: capture the hook stderr

The hook fires on the Step 1 edit. Copy its stderr verbatim into the entry,
including the `Leakage tests failed after editing ...` line. Two shapes are
legitimate:

- **exit 2** -- paste the stderr.
- **exit 0 / no output** -- write exactly `hook fired, exit 0, no stderr
  (fault outside tests/test_leakage.py)`. Do not leave the section blank and do
  not infer what it "would" have said.

If the harness truncated the message, say it was truncated and where.

## Step 3: capture the red run

`make test`, and paste the output verbatim. `-q` gives you the failure blocks
and a final `N failed, M passed` line; those are the part that matters. If the
section is longer than about 40 lines, keep the first failing traceback and the
final summary and mark each cut with `[... N lines elided ...]` -- an explicit
marker keeps "verbatim" honest; a silent trim does not.

**If `make test` is green here, that is the finding.** The suite did not catch
the fault. Record it as such, fix the fault anyway, and say plainly in the entry
that the guard rail missed it -- a gap is worth more than a fabricated red.

## Step 4: fix it and confirm green

Undo the fault with `Edit` (the hook fires green -- note that too). Then
`make test` must be green. Do not claim green on anything short of the actual
run; do not fix by loosening a test or by adding the faulty column to a
skip-list, which would defeat the point of having seeded it.

Count the cost of the fix and state your basis:

- a **turn** = one tool call issued from the first fix attempt through the
  `make test` run that came back green, inclusive.
- List the calls. "3 tool calls: 2 Edits + 1 make test" is checkable; "~3 turns"
  is not. If you genuinely cannot reconstruct the count, say so -- do not
  invent a number.

## Step 5: append the entry

`docs/SEEDED_FAULTS.md` holds one entry per seeded fault, newest last, numbered
`SF-NNN` continuing from the highest existing number (start at `SF-001`). Create
the file with the header below on first use. This Write is to `docs/`, so no
hook fires. Use this shape:

````markdown
# Seeded faults

Faults injected on purpose into `src/`, with what the guard rails did about
each. Produced by the `/seed-fault` skill. Diffs, hook stderr, and pytest
output are copied verbatim; elisions are marked.

## SF-001 -- <one-line name for the fault>

- **Date:** YYYY-MM-DD
- **Baseline:** `make test` green at `<short sha>`, <N> passed
- **Target:** `src/<file>.py`
- **Fault:** <what `$ARGUMENTS` asked for, in one sentence>
- **Hook:** exit 2 (red) | exit 0, no stderr (fault outside test_leakage.py)
- **Suite:** caught by `make test` | **not caught by `make test`**
- **Fixed in:** <N> tool calls (<breakdown>)

### Exact diff

```diff
<git diff -- src/ output, verbatim>
```

### Hook stderr (verbatim)

```
<stderr, verbatim, or: hook fired, exit 0, no stderr (fault outside tests/test_leakage.py)>
```

### make test (verbatim, red)

```
<output, verbatim, with marked elisions>
```

### Fix

<what was changed back, and the green confirmation>
````

## Done means all of these, checked

- `git diff -- src/` is **empty** -- the fault is fully reverted, not "mostly".
- `make test` green on the current tree.
- `docs/SEEDED_FAULTS.md` is the only file you changed (apart from whatever was
  already dirty before you started).
- Nothing committed. The fault was never meant to land.
