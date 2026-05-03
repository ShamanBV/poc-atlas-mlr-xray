"""
CLI: seed the curated UK baseline file from existing extractor outputs.

Usage:
    python -m mlr.ingest.seed_baseline \
        [--source /path/to/eval_atlas_*/]      \
        [--out    /path/to/baselines.jsonl]    \
        [--dry-run]

Defaults:
    --source : extractor-service/test_sets/eval_atlas_20260430T172755Z/
    --out    : whatever curated_path() resolves to (MLR_BASELINE_PATH or
               backend/baselines/uk_email_baselines.jsonl)

What it does:
    1. Walks every *.extraction.json in --source.
    2. Per role (PROMOTIONAL_NOTICE / AUDIENCE_RESTRICTION / PI / ...),
       harvests block text and dedupes by exact match.
    3. Writes the result as JSON Lines to --out (one exemplar per line).
    4. Prints a per-role count summary.

This file is intended as the format reference for the extractor service
team: when their approval flow lands, it can write the same shape and
our backend picks it up unchanged.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from mlr.ingest.baseline_bootstrap import (
    bootstrap_from_dir,
    curated_path,
    load_curated_file,
    merge_exemplars,
    write_jsonl,
)


_DEFAULT_SOURCE = Path(
    "/Users/mauricevanleeuwen/Development/dev_projects/extractor-service/"
    "test_sets/eval_atlas_20260430T172755Z"
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seed UK baseline JSONL from extractor outputs.")
    p.add_argument(
        "--source", type=Path, default=_DEFAULT_SOURCE,
        help="Directory of *.extraction.json files (default: extractor-service eval dir).",
    )
    p.add_argument(
        "--out", type=Path, default=None,
        help="Output JSONL file (default: curated_path() — MLR_BASELINE_PATH or "
             "backend/baselines/uk_email_baselines.jsonl).",
    )
    p.add_argument("--dry-run", action="store_true", help="Print summary, don't write.")
    p.add_argument(
        "--merge", action="store_true",
        help="Merge into the existing --out file instead of overwriting. "
             "Dedupes by pattern_id; collisions increment n + take max(coverage).",
    )
    args = p.parse_args(argv)

    src: Path = args.source
    if not src.is_dir():
        print(f"error: source dir not found: {src}", file=sys.stderr)
        return 1

    out = args.out or curated_path()

    incoming = bootstrap_from_dir(src)

    print(f"Source:       {src}")
    print(f"Target file:  {out}")
    print(f"Mode:         {'merge into existing' if args.merge else 'overwrite'}")

    if args.merge and out.is_file():
        existing = load_curated_file(out)
        final = merge_exemplars(existing, incoming)
        new_count = len(final) - len(existing)
        print(f"Existing:     {len(existing)} exemplars in target")
        print(f"Incoming:     {len(incoming)} from source")
        print(f"After merge:  {len(final)} ({new_count} added, {len(incoming) - new_count} merged into existing patterns)")
    else:
        if args.merge:
            print(f"  (target file doesn't exist yet — first write)")
        final = incoming
        print(f"Total:        {len(final)} exemplars")

    by_role = Counter(ex.role for ex in final)
    print("Per role:")
    for role, n in sorted(by_role.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {role:<28} {n}")

    if args.dry_run:
        print("\n[dry-run] not writing.")
        return 0

    n_written = write_jsonl(out, final)
    print(f"\nWrote {n_written} exemplars → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
