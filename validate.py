"""
Frozen-validator entry point (added 2026-07-11, GOVERNANCE dated note).

THE RULE: adjudication and passport numbers only count when produced by a
FROZEN validator -- a clean clone of this repo checked out at a `validator-*`
tag (canonically D:\\workspace\\rhyme_validator). The strategy side (the dev
repo, where plugins are written and iterated) is the GENERATOR; this clone is
the GRADER. Separating them kills the drift channel where the same pipeline
that writes strategies slowly tunes the harness that grades them until
everything passes (the r/algotrading "build the validator first, freeze it"
lesson, adopted 2026-07-11 -- rhyme's own harness history shows the risk is
real: warm-up dead-zone fix 85e4b67 sign-flipped swing; the corrected_f86d9f4
record lineage exists precisely because grader versions matter).

This script refuses to grade unless BOTH hold:
  1. the working tree it lives in is CLEAN (git status --porcelain empty), and
  2. HEAD is exactly a validator-* tag (git describe --tags --exact-match).
A dirty tree or an untagged checkout is a generator environment, not a
validator. There is deliberately NO override flag.

Upgrading the validator = commit to the dev repo, run the regression suite
(test_backtest_boundary_parity.py at minimum), tag validator-vN+1 with a
dated GOVERNANCE/RESEARCH_LOG note stating what changed and why, and
fast-forward the frozen clone to the new tag. The correction-vs-tampering
line applies: a validator change mid-adjudication invalidates that
adjudication's in-flight runs.

Usage (from the frozen clone, dev venv is fine -- code resolves from cwd):
  cd D:\\workspace\\rhyme_validator
  D:/workspace/rhyme/venv/Scripts/python.exe validate.py \
      --plugin D:/workspace/rhyme/some_plugin.py \
      --instrument USD_JPY --mode intraday \
      --start 2021-01-01 --end 2026-07-01 --fixed-risk 80 [backtest.py args...]

All unrecognized arguments pass through to backtest.py verbatim. Output CSV +
meta.json land in the DEV repo's backtests/ dir (results are data, not
grader code), with the validator tag recorded in the filename and printed.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
DEV_BACKTESTS = Path(r"D:\workspace\rhyme") / "backtests"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True,
                          text=True, timeout=30).stdout.strip()


def verify_frozen() -> str:
    """Return the validator tag, or exit loudly. No override exists."""
    dirty = _git("status", "--porcelain")
    if dirty:
        sys.exit(
            "REFUSED: this checkout has local modifications -- it is a "
            "generator environment, not a frozen validator.\n"
            f"  ({len(dirty.splitlines())} dirty path(s); first: {dirty.splitlines()[0]})\n"
            "Grade from the clean validator clone (D:\\workspace\\rhyme_validator)."
        )
    tag = subprocess.run(["git", "describe", "--tags", "--exact-match"],
                         cwd=HERE, capture_output=True, text=True, timeout=30).stdout.strip()
    if not tag.startswith("validator-"):
        sys.exit(
            f"REFUSED: HEAD is not exactly a validator-* tag (got: {tag or 'no tag'}).\n"
            "Adjudication numbers only count from a tagged frozen validator."
        )
    return tag


def main() -> None:
    tag = verify_frozen()
    commit = _git("rev-parse", "--short", "HEAD")
    print(f"FROZEN VALIDATOR OK: {tag} ({commit}) -- clean tree verified")

    args = sys.argv[1:]
    if "--plugin" in args:
        # Convenience alias: --plugin -> backtest.py's --signals-module
        args[args.index("--plugin")] = "--signals-module"
    if not args:
        sys.exit("usage: validate.py --plugin <path> [backtest.py args...]")

    # Stamp the strategy-name so the output CSV filename carries the
    # validator tag (backtest.py builds the name from --strategy-name).
    if "--strategy-name" not in args:
        plugin_stem = "run"
        if "--signals-module" in args:
            plugin_stem = Path(args[args.index("--signals-module") + 1]).stem
        args += ["--strategy-name", f"{plugin_stem}.{tag}"]

    # Run the FROZEN harness: backtest.py from THIS checkout, cwd = HERE so
    # every import (data.py, risk.py, indicators...) resolves to frozen code.
    # The plugin path may point into the dev repo -- the plugin is the
    # generator's OUTPUT, i.e. the thing being graded; that is correct.
    DEV_BACKTESTS.mkdir(exist_ok=True)
    cmd = [sys.executable, str(HERE / "backtest.py"), *args]
    print("running:", " ".join(cmd))
    rc = subprocess.run(cmd, cwd=HERE).returncode

    # backtest.py writes to <cwd-repo>/backtests/ -- i.e. the frozen clone's
    # backtests dir. Move results to the dev repo so the clone stays pristine.
    frozen_bt = HERE / "backtests"
    if frozen_bt.exists():
        for f in frozen_bt.iterdir():
            target = DEV_BACKTESTS / f.name
            if not target.exists():
                f.replace(target)
                print(f"result -> {target}")
    print(f"validator run complete (exit {rc}) -- graded by {tag} ({commit})")
    sys.exit(rc)


if __name__ == "__main__":
    main()
