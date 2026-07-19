#!/usr/bin/env python3
"""Print current FAL spend tracked in work/manifest.json. Free, read-only.

  python scripts/cost.py
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fal_common import (BUDGET_HARD_CAP, BUDGET_NOTIFY_AT, _load_manifest,  # noqa: E402
                        spend_so_far)


def main():
    s = _load_manifest().get("_spend", {"total": 0.0, "items": []})
    total = spend_so_far()
    by_model = Counter()
    for it in s.get("items", []):
        by_model[it["model"]] += it["cost"]
    print(f"FAL spend so far: ${total:.2f}  (cap ${BUDGET_HARD_CAP:.0f}, "
          f"alert ${BUDGET_NOTIFY_AT:.0f})")
    for model, c in by_model.most_common():
        print(f"  ${c:6.2f}  {model}")
    if total >= BUDGET_NOTIFY_AT:
        print(">>> at/over alert threshold <<<")
    print(f"remaining headroom: ${max(0, BUDGET_HARD_CAP - total):.2f}")


if __name__ == "__main__":
    main()
