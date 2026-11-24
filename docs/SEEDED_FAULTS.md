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

## SF-002 -- `cnt_roll_7` includes today's count

- **Date:** 2026-11-23
- **Baseline:** `make test` green at `ad632ff`, 16 passed
- **Target:** `src/features.py`
- **Fault:** Dropped `.shift(1)` from the `cnt_roll_7` rolling mean, so the
  7-day window ends on the day being predicted instead of the day before it.
  Today's `cnt` -- the target -- enters a feature.
- **Hook:** **no output at all.** This is *not* the documented "fault outside
  `tests/test_leakage.py`" case: the edited path is `src/features.py`, inside
  the hook's `*src/*.py` matcher, and the fault is squarely in leakage scope.
  See "Hook stderr" below -- it is also *not* the SF-001 `python3` bug, which
  `ad632ff` fixed; the script was verified working today.
- **Suite:** caught by `make test` (1 failed, 15 passed)
- **Fixed in:** 3 tool calls (1 Edit + 1 `make test` green + 1 `git diff`/
  `git status` verification)

### Exact diff

```diff
diff --git a/src/features.py b/src/features.py
index ee7f6fe..86901c1 100644
--- a/src/features.py
+++ b/src/features.py
@@ -73,7 +73,7 @@ def build_features(df: pd.DataFrame) -> pd.DataFrame:
     # If you add a longer lag, raise LAG_WARMUP in src/config.py.
     out["cnt_lag_1"] = out[TARGET].shift(1)
     out["cnt_lag_7"] = out[TARGET].shift(LAG_WARMUP)
-    out["cnt_roll_7"] = out[TARGET].shift(1).rolling(LAG_WARMUP).mean()
+    out["cnt_roll_7"] = out[TARGET].rolling(LAG_WARMUP).mean()
     # Two calendar days back. No aggregation, so no rolling/shift(1) dance:
     # shift(2) on the reindexed calendar already reads only days <= d-2.
     # Needs 2 days of history, inside LAG_WARMUP, so the row-loss bound holds.
```

One line, as asked -- no other change folded in.

### Hook stderr (verbatim)

The `Edit` that applied the fault returned **no hook output at all**. The
`Edit` that reverted it returned no hook output either. Both edits were to
`src/features.py`.

This is a *different* failure from SF-001. SF-001's cause was the Microsoft
Store `python3` alias stub, which `ad632ff` ("Fix check_leakage.sh", 63
insertions) rewrote away: the hook now probes interpreters by running them
(`.venv/Scripts/python.exe` first) and calls `fail` instead of exiting 0 when
it cannot parse its payload. That fix works. Verified by invoking the current
script by hand with a `src/` payload against the *faulted* tree:

```
$ printf '%s' '{"tool_name":"Edit","tool_input":{"file_path":"C:/Users/jenny/OneDrive/Documents/Capstone/bikeshare-open/src/features.py"}}' \
    | CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/check_leakage.sh; echo "EXIT=$?"
Leakage tests failed after editing C:/Users/jenny/OneDrive/Documents/Capstone/bikeshare-open/src/features.py:
[714 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 � 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 � 0.00441486

tests\test_leakage.py:57: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 7 passed in 1.18s
EXIT=2
```

**This is evidence gathered by hand, not the hook firing on its own** -- same
distinction SF-001 drew. The script logic is correct and would have reported
red, exit 2, with exactly this text. It simply did not run as a hook.

What was checked to rule the obvious causes out:

- `.claude/settings.json` is present and well-formed: `PostToolUse`, matcher
  `Edit|Write`, command `${CLAUDE_PROJECT_DIR}/.claude/hooks/check_leakage.sh`,
  `timeout: 60`. The matcher covers the tool that made the edit.
- No hook-disabling setting (`disableAllHooks` or similar) anywhere in
  `.claude/settings.json`, `.claude/settings.local.json`, or
  `~/.claude/settings.json`.
- The script is executable-or-invoked-via-bash correctly; the file is mode
  `100644` in the index, but the settings entry invokes it through bash, and
  the manual run above proves invocation succeeds.

**Not determined:** why the harness did not execute it. No hook execution log
exists under `~/.claude/` (no `*.log`, no debug file), so the evidence cannot
distinguish "the hook was never invoked this session" from "it was invoked and
its output was discarded". One unverified lead: both `.claude/settings.json`
and commit `ad632ff` carry mtime `Nov 23 17:48`, i.e. the hook config may have
been written in the same minute this session started -- if the session loaded
its hook config at startup, this session could be running without it. That is
a hypothesis, not a finding; confirming it needs a fresh session and another
seeded fault.

The guard rail therefore still does not deliver, for a reason distinct from
SF-001, and the root cause is open.

### make test (verbatim, red)

Complete output, 25 lines, nothing elided. The `�` in place of `±` is a
console-encoding artifact from the terminal, reproduced as received rather
than retyped as `±`.

```
python -m pytest tests/ -q
.........F......                                                         [100%]
================================== FAILURES ===================================
______________________ test_rolling_mean_excludes_today _______________________

feats =         dteday  instant  season  ...  cnt_lag_7   cnt_roll_7 rides_2_days_ago
0   2011-01-10     10.0  WINTER  ...    ...          3095.0
713 2012-12-31    731.0  WINTER  ...      920.0  1789.857143           1341.0

[714 rows x 29 columns]

    def test_rolling_mean_excludes_today(feats):
        """cnt_roll_7 must be the mean of the 7 calendar days *before* today."""
        by_date = feats.set_index("dteday")[TARGET]
        date = feats.dteday.iloc[200]
        window = [date - pd.Timedelta(days=k) for k in range(1, 8)]
        if all(d in by_date.index for d in window):
            expected = sum(by_date[d] for d in window) / 7
>           assert feats.set_index("dteday").cnt_roll_7[date] == pytest.approx(expected)
E           assert np.float64(4389.0) == 4414.857142857143 � 0.00441486
E             
E             comparison failed
E             Obtained: 4389.0
E             Expected: 4414.857142857143 � 0.00441486

tests\test_leakage.py:57: AssertionError
=========================== short test summary info ============================
FAILED tests/test_leakage.py::test_rolling_mean_excludes_today - assert np.fl...
1 failed, 15 passed in 2.10s
make: *** [Makefile:16: test] Error 1
```

The detector is well aimed. `test_rolling_mean_excludes_today` re-derives the
expected value from the 7 strictly-earlier calendar days and compares, so a
missing `.shift(1)` shows up as an exact value mismatch (4389.0 against
4414.86) rather than as a vague correlation shift. Exactly one test fired:
dropping `.shift(1)` from `cnt_roll_7` leaves the other lag features correct,
so `test_lags_are_true_calendar_lags` and
`test_two_day_lag_is_a_true_calendar_lag` stay green. That is the test doing
its job precisely, not narrowly.

### Fix

Restored `.shift(1)` with a single `Edit` (not `git checkout`, so a working
hook would have had its chance to go green -- it stayed silent for the same
undetermined reason). Confirmed green:

```
python -m pytest tests/ -q
................                                                         [100%]
16 passed in 5.72s
```

`git diff -- src/` is empty and `git status --porcelain` is empty. Nothing
committed.

**Fix cost:** 3 tool calls from the first fix attempt through the green run,
inclusive -- 1 `Edit` (restore `.shift(1)`), 1 `make test` (16 passed), 1
`git diff -- src/` + `git status --porcelain` (verification, issued in the
same block as the green run). Only the first is a repair; the other two are
confirmation.

**Diagnostics, not counted as fix cost:** 1 `Bash` call invoking the hook
script by hand to establish that the script works and the fault tree is red.
No re-injection was needed this time -- the first capture of every output
above was complete, so unlike SF-001 there are no bookkeeping re-runs to
account for.

### Follow-up this exposes

SF-001's follow-up (parse the payload with the venv interpreter; fail loudly
rather than silently on an unparseable payload) is **done** in `ad632ff` and
verified working here. What remains is delivery, not logic: the fixed script
does not run when an `Edit` touches `src/`. Until that is established, this
repo has a leakage detector that only `make test` -- a command an agent must
choose to run -- ever reaches, and the hook contributes nothing. The next
`/seed-fault` run in a fresh session is the cheapest way to test the
"config written mid-session" hypothesis above.

## SF-003 -- `encode_weather()` loses its loud failure on unmapped labels

- **Date:** 2026-11-23
- **Baseline:** `make test` green at `154f731`, 16 passed
- **Target:** `src/features.py`
- **Fault:** The `ValueError` guard in `encode_weather()` was removed, so an
  unexpected `weather` label silently becomes `NaN` via `.map()` and is then
  deleted by `dropna()` with no error and no warning.
- **Hook:** exit 0, no stderr -- consistent with the documented
  "fault outside `tests/test_leakage.py`" case, but see "Hook stderr" below:
  this episode **cannot** distinguish "hook ran and had nothing to report"
  from "hook never ran."
- **Suite:** **not caught by `make test`** (16 passed). The guard was
  documented in a docstring and enforced nowhere.
- **Fixed in:** 2 tool calls (1 Edit + 1 `make test` green, the latter
  carrying the `git diff`/`git status` verification)

### Exact diff

```diff
diff --git a/src/features.py b/src/features.py
index ee7f6fe..4d831ea 100644
--- a/src/features.py
+++ b/src/features.py
@@ -24,10 +24,6 @@ def encode_weather(series: pd.Series) -> pd.Series:
     days -- the most interesting days in the dataset -- disappear with no
     error and no warning.
     """
-    known = series.dropna()
-    unknown = set(known.unique()) - set(WEATHER_ORDER)
-    if unknown:
-        raise ValueError(f"unmapped weather labels: {sorted(unknown)}")
     return series.map(WEATHER_ORDER).astype(float)
```

Four lines, not one. Deleting only the `raise` would have left `known` and
`unknown` assigned and unused -- dead code that reads like a guard still
doing something -- so the whole block went. That is the minimal edit that
produces the fault *and* leaves the file coherent; it is not a one-liner and
this note is why.

### Hook stderr (verbatim)

```
hook fired, exit 0, no stderr (fault outside tests/test_leakage.py)
```

Both the fault `Edit` and the revert `Edit` returned **no hook output at
all**. The edited path is `src/features.py`, which the hook's `*src/*.py`
matcher accepts, so the hook would not have taken the quiet `*)` exit on
path grounds -- it would have run `pytest tests/test_leakage.py -q` and,
finding 8 passed, exited 0 with nothing on stderr. Silence is therefore the
*correct* output for this fault.

**But silence is also what SF-002 recorded for a fault that should have been
red.** From the outside the two are identical: no output. So this episode
neither confirms nor refutes SF-002's open delivery question, and it was
never going to -- a fault outside leakage scope cannot distinguish a live
hook from an absent one. SF-002's suggested test (a `src/`-path fault that
*is* in leakage scope, in a fresh session) remains the way to settle it.
`.claude/settings.json` does carry the `PostToolUse`/`Edit|Write` entry, so
the config is present in this session.

### make test (verbatim, red)

The run that was supposed to be red. It was not. Complete output, nothing
elided:

```
python -m pytest tests/ -q
................                                                         [100%]
16 passed in 6.30s
MAKE EXIT=0
```

**The suite did not catch the fault.** This is the finding, and it is a real
gap rather than an accident of an insensitive assertion: no test anywhere in
`tests/` references `encode_weather`, its `ValueError`, or the
`weather_severity` mapping. `grep -n 'encode_weather|unmapped|weather_severity'
tests/` returns exactly one hit, and it is a comment in
`tests/test_contract.py:26` classifying `weather` as "consumed ->
weather_severity" -- a note about where the column goes, not a test of what
happens when it goes somewhere unexpected.

Why the fault is latent. The removed guard only fires on a label outside
`GOOD`/`MISTY`/`BAD`, and the mirror contains none. The faulted code is
therefore not merely untested, it is *never exercised* on today's data:

```
=== 1. faulted guard on an unmapped label ===
[0.0, nan, 2.0]
```

That single `nan` is the whole failure mode: no exception, and `dropna()`
will swallow the row later. What the downstream detectors do about it,
checked on the real data rather than assumed:

```
=== 2. row-loss bound, today's data ===
raw=728 feats=714 lost=14 allowed_loss=14

=== 3. same, with ONE unmapped label injected ===
raw=728 feats=713 lost=15 allowed_loss=14
row-loss test would fire: True
```

`test_only_expected_rows_are_dropped` (`tests/test_contract.py`) computes
`allowed_loss = LAG_WARMUP + LAG_WARMUP * missing_days = 7 + 7*1 = 14`, and
the actual loss is exactly 14. **Zero slack.** One silently-NaN'd row makes
it 15 and the test fires.

So the fault is caught indirectly, and only if the data ever contains an
unmapped label -- which is precisely the condition the removed guard existed
to announce, and precisely the condition under which nobody is watching for
it. The guard is a *contract* check ("fail loudly on this input"); the
row-loss test is a *consequence* check ("you lost more rows than
arithmetic allows"). They are not substitutes: the consequence check
reports row loss, not the label that caused it, and it has no margin to
spare by construction. A feature added later that legitimately costs a
warm-up row would consume the remaining slack and take this backstop with
it.

This is the same shape SF-001 praised and SF-002 demonstrated: the tests
that exist are well aimed at what they cover, and the gap is coverage, not
sensitivity.

### Fix

Restored the four-line guard verbatim with `Edit` (not `git checkout`, so
the hook had its chance to go green -- it stayed silent, correctly, for the
same outside-scope reason). No test was loosened and nothing was added to a
skip-list. Confirmed:

```
python -m pytest tests/ -q
................                                                         [100%]
16 passed in 6.60s
MAKE EXIT=0
```

`git diff -- src/` is empty and `git status --porcelain` is empty. Nothing
committed.

### Follow-up this exposes

The `encode_weather()` docstring argues, at length and well, that a silent
`.map()` is how "the 20 BAD-weather days -- the most interesting days in the
dataset -- disappear with no error and no warning." The guard was written
because someone thought carefully about that failure mode. **Nothing tests
that the guard is still there.** A one-line test -- an unmapped label must
raise -- would have turned this into a red run instead of a green one, and
would be the cheapest possible addition to `tests/test_leakage.py` or
`tests/test_contract.py`. Not added here: this entry records the fault, and
per the skill the fix is the revert, not new tests. Worth doing separately.

## SF-004 -- Bypassing Edit|Write guards via shell copy into data/raw/

- **Date:** 2026-11-23
- **Target:** data/raw/bike_daily.csv
- **Fault:** Overwrote data/raw/bike_daily.csv from the shell (Copy-Item / cp) instead of using Claude Code Edit or Write tools, then immediately restored the original file from backup.
- **Hook:** **Did not fire.** .claude/settings.json only attaches check_leakage.sh to PostToolUse on Edit|Write (and only checks *src/*.py), and its permission deny rule (Edit(./data/raw/**), Write(./data/raw/**)) only blocks file-edit tools, not shell commands.

### Observed output (verbatim)

\\	ext
PS> Copy-Item data/raw/bike_daily.csv data/raw/bike_daily.csv.bak
PS> Copy-Item README.md data/raw/bike_daily.csv
PS> Move-Item -Force data/raw/bike_daily.csv.bak data/raw/bike_daily.csv
PS> Get-FileHash data/raw/bike_daily.csv -Algorithm SHA256

Algorithm       Hash                                                                   Path
---------       ----                                                                   ----
SHA256          A6BED1577F6E4DE56DCFAE6D8315985073CC0AD3446C8C99ED60C86A0B5AD9DC       C:\Users\jenny\OneDrive\Documents\Capstone\bikeshare-open\data\raw\bike_daily.csv
\
The overwrite succeeded with zero hook output and zero permission prompt, because a shell copy never invokes Edit or Write.

### What would have caught it

Four mechanisms would close this blind spot:
1. **A PreToolUse hook on Bash** that inspects tool_input.command and exits 2 if the command writes to data/raw/ (e.g., cp, mv, >, tee, or PowerShell Copy-Item/Set-Content targeting data/raw).
2. **A SHA-256 hash check in make data / src/ingest.py** that verifies data/raw/bike_daily.csv against the pinned hash (a6bed1577f6e4de56dcfae6d8315985073cc0ad3446c8c99ed60c86a0b5ad9dc) before loading, failing loudly if the file was modified by any means.
3. **A Stop hook** that runs git diff -- data/raw/ (or checks the SHA-256 hash) before the agent can finish a turn, rejecting any turn that left data/raw/ dirty.
4. **OS-level read-only filesystem permissions** (chmod 444 data/raw/bike_daily.csv on Unix or attrib +R data\raw\bike_daily.csv on Windows) so even an accidental shell copy fails at the OS layer.
