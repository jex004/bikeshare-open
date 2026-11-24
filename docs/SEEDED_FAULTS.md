# Seeded faults

Faults injected on purpose into `src/`, with what the guard rails did about
each. Produced by the `/seed-fault` skill. Diffs, hook stderr, and pytest
output are copied verbatim; elisions are marked.

## SF-001 -- the leakage gate admits `casual` into the feature set

- **Date:** 2026-11-23
- **Baseline:** `make test` green at `52b7bf4`, 16 passed
- **Target:** `src/features.py`
- **Fault:** `feature_columns()` was changed so its `FORBIDDEN` filter admits
  `casual`, putting a component of the target (`casual + registered == cnt`
  exactly) back into the feature set.
- **Hook:** **exit 0, no stderr -- but not the documented "fault outside
  test_leakage.py" case.** The fault is squarely in leakage scope; the hook
  is broken in this environment and cannot fire on any edit. See "Hook
  stderr" below.
- **Suite:** caught by `make test` (2 failed, 14 passed)
- **Fixed in:** 2 tool calls (1 Edit + 1 make test) for the initial fix.
  The fault was re-injected twice afterwards to capture output that earlier
  commands had truncated; those edits and re-runs are bookkeeping, not fix
  cost, and are counted separately below.

### Exact diff

```diff
diff --git a/src/features.py b/src/features.py
index ee7f6fe..a223d9e 100644
--- a/src/features.py
+++ b/src/features.py
@@ -85,7 +85,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
 def feature_columns(df: pd.DataFrame) -> list[str]:
     """Numeric columns that are safe to feed the model."""
     numeric = df.select_dtypes(include="number").columns
-    return [c for c in numeric if c not in FORBIDDEN]
+    return [c for c in numeric if c not in FORBIDDEN or c == "casual"]
 
 
 if __name__ == "__main__":
```

(Git also emitted, before the diff, on stderr rather than stdout:
`warning: in the working copy of 'src/features.py', LF will be replaced by
CRLF the next time Git touches it`. That is a line-ending notice, not a
change to the diff.)

### Hook stderr (verbatim)

The `Edit` that applied the fault above returned **no hook output at all**.
The `Edit` that reverted it returned no hook output either. Neither is the
"fault outside `tests/test_leakage.py`" case: the edited path is
`src/features.py`, which the hook's own `*src/*.py` matcher accepts.

Root cause, verified by running the hook by hand with a `src/` payload:

```
$ printf '%s' '{"tool_input":{"file_path":".../src/features.py"}}' \
    | CLAUDE_PROJECT_DIR="$PWD" bash .claude/hooks/check_leakage.sh
Python was not found; run without arguments to install from the Microsoft Store, or disable this shortcut from Settings > Apps > Advanced app settings > App execution aliases.
HOOK EXIT CODE: 0
```

`command -v python3` resolves to
`/c/Users/jenny/AppData/Local/Microsoft/WindowsApps/python3` -- the Microsoft
Store execution-alias stub, not an interpreter. `.claude/hooks/check_leakage.sh`
parses its payload with `python3 -c ...`, so the stub fails, prints nothing on
stdout, and `path` is the empty string. The empty string matches the `*)`
branch of the hook's `case "$path" in *src/*.py) ;; *) exit 0 ;; esac` and the
hook exits 0 **before pytest is ever reached**. Confirmed by comparing the two
interpreters on the same payload:

```
=== parsed path via python3 (as hook does it) ===
                      <- empty, `cat -A` shows nothing
=== parsed path via .venv python ===
C:/x/src/features.py
```

So the hook is dead here for *every* edit, in or out of leakage scope. This
is a gap in the guard rail, not a property of this fault.

**Evidence gathered by hand, labelled as such.** To record what the hook
*would* have reported, `.venv/Scripts/python.exe` was put on `PATH` behind a
`python3` wrapper and the hook re-run on the faulted tree. This is not the
hook firing on its own; it is the same script invoked manually. Exit code 2,
stderr verbatim:

```
Leakage tests failed after editing C:/Users/jenny/OneDrive/Documents/Capstone/bikeshare-open/src/features.py:
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 rides_2_days_ago
0   2011-01-10     10.0  WINTER  ...    ...          3095.0
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571           1341.0

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests\test_leakage.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
1 failed, 7 passed in 1.80s
```

The detector works. The wiring that is supposed to deliver it does not.

### make test (verbatim, red)

Full output was 85 lines. Both failing tracebacks are kept below, trimmed to
their assertion tail; the summary is complete. Elisions are marked.

```
....F.F.........                                                         [100%]
================================== FAILURES ===================================
_____________________ test_every_raw_column_is_classified _____________________

raw =      instant     dteday  season  ...  weather days_since_2011 cnt_2d_bfr
0          3 2011-01-03  WINTER  ...     GOOD...       729       3095
727      731 2012-12-31  WINTER  ...    MISTY             730       1341

[728 rows x 18 columns]
feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 rides_2_days_ago
0   2011-01-10     10.0  WINTER  ...    ...          3095.0
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571           1341.0

[714 rows x 29 columns]

    def test_every_raw_column_is_classified(raw, feats):
        """A column appended to the raw CSV must not enter the model silently.
[... 46 lines elided: the remainder of this test's docstring, the
unclassified-columns check, and its assertion ...]
        overlap = (set(FORBIDDEN) | set(EXPECTED_RAW_INPUTS)) & cols
>       assert not overlap, f"columns both classified as non-features and used as features: {sorted(overlap)}"
E       AssertionError: columns both classified as non-features and used as features: ['casual']
E       assert not {'casual'}

tests\test_contract.py:124: AssertionError
_________________________ test_no_forbidden_features __________________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 rides_2_days_ago
0   2011-01-10     10.0  WINTER  ...    ...          3095.0
713 2012-12-31    731.0  WINTER  ...      920.0  1531.428571           1341.0

[714 rows x 29 columns]

    def test_no_forbidden_features(feats):
        """Guards the gate, not the data: feature_columns() excludes FORBIDDEN by
        construction, so this cannot discover a *new* leaky column. What it
        catches is someone editing feature_columns() or FORBIDDEN -- which is
        exactly the fault the Step 7 hook demonstrates."""
        cols = set(feature_columns(feats))
>       assert not (cols & FORBIDDEN), f"forbidden columns in feature set: {cols & FORBIDDEN}"
E       AssertionError: forbidden columns in feature set: {'casual'}
E       assert not ({'atemp', 'casual', 'cnt_lag_1', 'cnt_lag_7', 'cnt_roll_7', 'dayofweek', ...} & {'casual', 'cnt', 'cnt_2d_bfr', 'days_since_2011', 'instant', 'registered', ...})

tests\test_leakage.py:31: AssertionError
=========================== short test summary info ============================
FAILED tests/test_contract.py::test_every_raw_column_is_classified - Assertio...
FAILED tests/test_leakage.py::test_no_forbidden_features - AssertionError: fo...
2 failed, 14 passed in 6.56s
make: *** [Makefile:16: test] Error 1
```

Two independent detectors fired, and they caught different things:

- `tests/test_leakage.py::test_no_forbidden_features` caught the leak itself
  (`casual` in the feature set).
- `tests/test_contract.py::test_every_raw_column_is_classified` caught it a
  second way, via the bucket-disjointness assertion: `casual` was simultaneously
  classified as a non-feature (`FORBIDDEN`) and used as a feature. That test
  was written for a different threat (a new raw column slipping in
  unclassified) and caught this one collaterally.

### Fix

Reverted `feature_columns()` to its original single-line filter with `Edit`
(not `git checkout`, so the hook had a chance to go green -- it stayed silent
for the same `python3` reason). Confirmed with `make test`:

```
python -m pytest tests/ -q
................                                                         [100%]
16 passed in 5.33s
```

`git diff -- src/` is empty and `git status --porcelain` is empty.

**Fix cost:** 2 tool calls -- 1 `Edit` (revert) + 1 `make test` (green).

**Separate from the fix:** the fault was re-injected and re-reverted twice
more (4 further `Edit` calls, 3 further `pytest` runs) to recover output that
earlier `tail`/`head`-piped commands had discarded, since this log requires
verbatim text. Those runs reproduced the failure identically (`2 failed, 14
passed`; red output 85 lines both times). They are not counted as fix cost.

### Follow-up this exposes

`.claude/hooks/check_leakage.sh` cannot fire in this environment: it depends
on `python3`, which is a Store alias stub here, and its `case` statement
treats the resulting empty path as "not a src file" and exits 0. Two changes
would fix it -- parse the payload with the venv interpreter, and fail loudly
(not silently) when the payload cannot be parsed. Not made here: this entry
records the fault, and the hook is infrastructure, not the subject.

Note also that the hook runs only `tests/test_leakage.py`, so even when
working it would have shown 1 of the 2 failures above. The second,
`test_contract.py::test_every_raw_column_is_classified`, is only visible to
`make test`.
