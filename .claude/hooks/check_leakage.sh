#!/usr/bin/env bash
# PostToolUse hook: re-run the leakage tests whenever src/ changes.
#
# This runs AFTER the edit has landed, so it cannot prevent the write. What
# exit 2 does is send stderr back to Claude as a system message, so the
# failure is in front of the agent immediately and it cannot carry on as if
# the edit were fine. To make "done" itself conditional on green tests, add
# a Stop hook that runs `make test` and exits 2 on failure (check
# stop_hook_active in the payload to avoid looping).
#
# Two ways this hook used to pass silently, both fixed here:
#
#   1. It called `python3` unconditionally. On Windows the venv ships
#      .venv/Scripts/python.exe and no `python3`, and on some machines
#      `python3` is the Microsoft Store alias stub: it exits 49 and prints
#      nothing, so the payload parsed to an empty path, the matcher fell
#      through to `*) exit 0`, and pytest never ran. The interpreter is now
#      probed by actually running it, and failing to find one is loud.
#   2. The `*src/*.py` matcher only matched forward slashes, so a Windows
#      path (...\src\features.py) skipped the check the same silent way.
#      Paths are normalized before matching.
#
# Exit codes: 0 = checked and green, or the file is outside src/ (nothing to
# check); 2 = leakage tests failed, or the hook could not run its checks.
set -uo pipefail

# A hook that cannot run its checks must not exit 0. To the caller, "nothing
# to report" and "all clear" are the same thing, and this hook exists to make
# a leaky edit visible immediately.
fail() {
  echo "check_leakage.sh: $*" >&2
  echo "check_leakage.sh: the edit was NOT checked -- fix this hook." >&2
  exit 2
}

cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || fail "cannot cd to '${CLAUDE_PROJECT_DIR:-.}'"

# Probe every candidate by running it and requiring Python 3 on stdout. A
# name is not evidence: the Store alias is called `python3` and is not a
# Python, and a venv interpreter can exist but be broken (a copied or
# symlinked .venv fails to locate pyvenv.cfg). Both fail the probe and are
# skipped. Venv first, so the tests run where pytest is installed.
find_python() {
  for cand in ".venv/Scripts/python.exe" ".venv/bin/python" "python3" "python"; do
    case "$cand" in
      */*) [ -x "$cand" ] || continue ;;
      *)   command -v "$cand" >/dev/null 2>&1 || continue ;;
    esac
    if [ "$("$cand" -c 'import sys; sys.stdout.write(str(sys.version_info[0]))' 2>/dev/null)" = "3" ]; then
      printf '%s' "$cand"
      return 0
    fi
  done
  return 1
}

PY=$(find_python) || fail "no working Python 3 found (tried .venv/Scripts/python.exe, .venv/bin/python, python3, python)"

"$PY" -m pytest --version >/dev/null 2>&1 || fail "$PY cannot run pytest"

payload=$(cat)

# An unparseable payload is a hook bug, not a clean edit, so it must not be
# mistaken for one. Backslashes are normalized so a Windows path matches the
# same pattern as the forward-slash form.
path=$(printf '%s' "$payload" | "$PY" -c '
import json, sys
d = json.load(sys.stdin)
p = (d.get("tool_input") or {}).get("file_path") or ""
print(p.replace("\\", "/"))
') || fail "could not parse the hook payload as JSON"

[ -n "$path" ] || fail "hook payload carried no tool_input.file_path"

case "$path" in
  *src/*.py) ;;
  *) exit 0 ;;   # outside src/: nothing to check, so a quiet exit is correct
esac

if ! out=$("$PY" -m pytest tests/test_leakage.py -q 2>&1); then
  echo "Leakage tests failed after editing $path:" >&2
  echo "$out" | tail -20 >&2
  exit 2
fi
exit 0
