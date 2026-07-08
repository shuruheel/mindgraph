#!/usr/bin/env python3
"""
check_version.py — version guard for the mindgraph-hermes plugin.

Hermes carries TWO hand-synced version strings and (unlike the other repos) has
no published-package machinery to catch a mismatch, so drift is easy. This is
the self-contained in-repo guard the ecosystem-wide
`release-tools/check_ecosystem.py` documents but can't enforce per-repo:

  * plugin.yaml `version:` == __init__.py `__version__`   (always)
  * on a `v*` tag push, the tag (with the leading `v` stripped) == that version
    (release-time tag==version guard, the one the crates.io / PyPI repos get
    for free from their publish tooling).

The tag is taken from $GITHUB_REF (`refs/tags/vX.Y.Z`); off a tag it's skipped.

Requires Python 3.11+. No third-party deps. Exit 0 = pass, 1 = any mismatch.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# scripts/ lives at <repo>/scripts/, so the repo root is the parent of parent.
ROOT = Path(__file__).resolve().parent.parent

# ── ANSI (suppressed when not a tty) ──────────────────────────────────────────
_tty = sys.stdout.isatty()
def _c(code: str, s: str) -> str: return f"\033[{code}m{s}\033[0m" if _tty else s
def dim(s): return _c("2", s)
def bold(s): return _c("1", s)
def green(s): return _c("32", s)
def red(s): return _c("31", s)

_fails: list[str] = []
_oks = 0

def check(ok: bool, label: str, detail: str = "") -> None:
    global _oks
    if ok:
        _oks += 1
        print(f"  {green('✓')} {label}" + (dim(f"  {detail}") if detail else ""))
    else:
        _fails.append(label)
        print(f"  {red('✗')} {label}" + (f"  {red(detail)}" if detail else ""))


def re_version(p: Path, pattern: str) -> str | None:
    if not p.exists():
        return None
    m = re.search(pattern, p.read_text())
    return m.group(1) if m else None


def main() -> int:
    plugin_v = re_version(ROOT / "plugin.yaml",
                          r'(?m)^\s*version:\s*["\']?([0-9][^\s"\']*)')
    init_v = re_version(ROOT / "__init__.py",
                        r'__version__\s*=\s*["\']([^"\']+)["\']')

    print(bold(f"\nmindgraph-hermes version guard  ({ROOT})\n"))

    check(plugin_v is not None and init_v is not None and plugin_v == init_v,
          "plugin.yaml version == __init__.py __version__",
          f"plugin.yaml {plugin_v} vs __init__.py {init_v}")

    # release-time tag==version guard (only when building off a v* tag).
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/v"):
        tag_v = ref[len("refs/tags/v"):]
        check(tag_v == plugin_v,
              f"git tag v{tag_v} == declared version {plugin_v}",
              f"tag {tag_v} vs version {plugin_v}")
    else:
        print(dim(f"  (not a v* tag build — GITHUB_REF={ref or 'unset'}; tag==version check skipped)"))

    print(bold("\n── summary ──"))
    print(f"  {green(str(_oks) + ' ok')}   {red(str(len(_fails)) + ' fail')}")
    if _fails:
        print(red("\nFAIL — hermes versions are out of sync. Fix the ✗ items above."))
        return 1
    print(green(f"\nOK — hermes version {plugin_v} is consistent."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
