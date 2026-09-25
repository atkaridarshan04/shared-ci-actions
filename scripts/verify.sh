#!/usr/bin/env bash
# Everything CI checks, runnable locally with no arguments.
# Run from anywhere; paths resolve against the repo root.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

FAILED=0
section() { printf '\n== %s ==\n' "$1"; }
fail()    { printf '  FAIL  %s\n' "$1"; FAILED=1; }
pass()    { printf '  ok    %s\n' "$1"; }

section "YAML syntax"
while IFS= read -r f; do
  if python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" "$f" 2>/dev/null; then
    pass "$f"
  else
    fail "$f"
    python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" "$f" 2>&1 | sed 's/^/        /'
  fi
done < <(find .github -name '*.yml' -o -name '*.yaml' | sort)

section "Templates render, parse, and leave no placeholders"
if python3 "$SCRIPT_DIR/lib/check_templates.py"; then
  pass "all repo x stage combinations"
else
  fail "template rendering"
fi

section "Third-party actions are SHA-pinned"
if python3 "$SCRIPT_DIR/lib/check_pins.py"; then
  pass "every third-party uses: is a full commit SHA"
else
  fail "unpinned action reference"
fi

section "Shell scripts"
if command -v shellcheck >/dev/null 2>&1; then
  for f in scripts/*.sh; do
    if shellcheck -S warning "$f"; then pass "$f"; else fail "$f"; fi
  done
else
  printf '  skip  shellcheck not installed (CI runs it)\n'
fi

printf '\n'
if [ "$FAILED" -eq 0 ]; then
  printf 'All checks passed.\n'
else
  printf 'One or more checks FAILED.\n'
fi
exit "$FAILED"
