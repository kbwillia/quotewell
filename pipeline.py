#!/usr/bin/env python3
"""
QuoteWell take-home — email → extract → normalize → AMS submit → confirm.

Setup (two terminals):
    node stub/server.js
    python pipeline.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline.extract_client import DEFAULT_BASE_URL
from pipeline.run import PipelineStatus, run_inbox

# Folder this script lives in (project root)
PROJECT_ROOT = Path(__file__).resolve().parent
# Default location of the 4 sample broker emails
INBOX_DIR = PROJECT_ROOT / "inbox"


def main() -> int:
    # Allow optional overrides: stub URL or different inbox folder
    parser = argparse.ArgumentParser(description="QuoteWell submission pipeline")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--inbox", type=Path, default=INBOX_DIR)
    args = parser.parse_args()

    if not args.inbox.is_dir():
        print(f"inbox directory not found: {args.inbox}", file=sys.stderr)
        return 1  # exit code 1 = setup error

    # Run prepare + submit for every .txt file in inbox/
    results = run_inbox(args.inbox, base_url=args.base_url)

    # Count how many emails ended in each terminal state
    confirmed = needs_review = failed = 0

    for result in results:
        print("=" * 72)
        # Print JSON summary: status, warnings, errors, final_record
        print(json.dumps(result.to_display_dict(), indent=2))

        if result.status == PipelineStatus.CONFIRMED:
            confirmed += 1
            print(f"  -> CONFIRMED {result.record_id}")
        elif result.status == PipelineStatus.NEEDS_REVIEW:
            needs_review += 1
            # Prepare step blocked submit (e.g. Tula missing effective date)
            print(f"  -> NEEDS REVIEW: {result.message}")
        else:
            failed += 1
            # Was ready but AMS never confirmed after retries
            print(f"  -> FAILED: {result.message}")

    print("=" * 72)
    print(
        f"Done: {confirmed} confirmed, {needs_review} needs review, {failed} failed "
        f"({len(results)} total)"
    )

    # Exit 1 only if a submittable record failed to land — not for needs_review
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
