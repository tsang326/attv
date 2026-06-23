from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from backend.config import settings
from backend.runner import new_job_dir, run_pipeline


def cmd_run(args: argparse.Namespace) -> int:
    job_id, job_dir = new_job_dir(settings.data_dir)
    print(f"Job {job_id} → {job_dir}")

    def on_progress(status, progress, error=None):
        msg = f"[{progress:3d}%] {status.value}"
        if error:
            msg += f" — {error}"
        print(msg)

    try:
        result = run_pipeline(args.url, job_dir, on_progress=on_progress, voice=args.voice)
        print(f"\nDone: {result['output']}")
        print(f"Caption:\n{result['caption']}")
        return 0
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1


def cmd_batch(args: argparse.Namespace) -> int:
    urls: list[str] = []
    if args.csv:
        with open(args.csv, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("url") or row.get("URL")
                if url:
                    urls.append(url.strip())
    elif args.urls:
        urls = [u.strip() for u in args.urls if u.strip()]

    if not urls:
        print("No URLs provided", file=sys.stderr)
        return 1

    failed = 0
    for url in urls:
        print(f"\n=== Processing: {url} ===")
        job_id, job_dir = new_job_dir(settings.data_dir)
        try:
            result = run_pipeline(url, job_dir, voice=args.voice)
            print(f"OK {job_id}: {result['output']}")
        except Exception as exc:
            print(f"FAIL {url}: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="attv", description="ATTV — Web to TikTok video pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Run pipeline for a single URL")
    run_parser.add_argument("url", help="Web page URL")
    run_parser.add_argument("--voice", default=None, help="edge-tts voice name")
    run_parser.set_defaults(func=cmd_run)

    batch_parser = sub.add_parser("batch", help="Run pipeline for multiple URLs")
    batch_parser.add_argument("urls", nargs="*", help="URLs to process")
    batch_parser.add_argument("--csv", help="CSV file with url column")
    batch_parser.add_argument("--voice", default=None)
    batch_parser.set_defaults(func=cmd_batch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
