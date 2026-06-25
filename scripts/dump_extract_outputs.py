"""Fetch raw /extract output for each inbox email → raw_extract_outputs.md."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
OUT_FILE = ROOT / "raw_extract_outputs.md"
BASE_URL = "http://localhost:8472"


def main() -> None:
    lines = [
        "# Raw /extract output per inbox email",
        "",
        "Response from `POST /api/v1/extract` on the local stub.",
        "Regenerate: `python scripts/dump_extract_outputs.py` (stub must be running).",
        "",
    ]

    for path in sorted(INBOX.glob("*.txt")):
        email = path.read_text(encoding="utf-8")

        # Same API call the pipeline makes in extract_client.py
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/extract",
            data=json.dumps({"email": email}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise SystemExit(
                f"Could not reach stub at {BASE_URL}. Start it with: node stub/server.js\n{exc}"
            ) from exc

        lines.extend(
            [
                "---",
                "",
                f"## {path.name}",
                "",
                f"**Model:** `{payload.get('model', '')}`",
                "",
                "### Raw `output` field (exact string returned)",
                "",
                "```text",
                payload["output"],
                "```",
                "",
                "### Full JSON response",
                "",
                "```json",
                json.dumps(payload, indent=2),
                "```",
                "",
            ]
        )

    OUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
