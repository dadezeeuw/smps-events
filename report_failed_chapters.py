import argparse
import csv
import json
import sys
from pathlib import Path


NON_FAILURE_STATUSES = {"success"}


def load_json(path):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e


def build_chapter_index(chapters):
    by_url = {}
    by_name = {}

    for index, chapter in enumerate(chapters):
        if chapter.get("url"):
            by_url[chapter["url"]] = index
        if chapter.get("chapter"):
            by_name[chapter["chapter"]] = index

    return by_url, by_name


def find_rerun_index(chapter, by_url, by_name):
    url = chapter.get("url")
    name = chapter.get("chapter")

    if url in by_url:
        return by_url[url]
    if name in by_name:
        return by_name[name]
    return None


def clean_reason(chapter):
    reason = chapter.get("error") or chapter.get("message") or "No error message recorded."
    return " ".join(str(reason).split())


def collect_failed_chapters(status_data, chapters_data):
    batch = status_data.get("batch", {})
    by_url, by_name = build_chapter_index(chapters_data)
    failed = []

    for chapter in status_data.get("chapters", []):
        status = chapter.get("status", "unknown")
        if status in NON_FAILURE_STATUSES:
            continue

        failed.append(
            {
                "chapter": chapter.get("chapter", "Unknown chapter"),
                "status": status,
                "reason": clean_reason(chapter),
                "rerun_batch_index": find_rerun_index(chapter, by_url, by_name),
                "status_batch_index": batch.get("batch_index"),
                "url": chapter.get("url", ""),
            }
        )

    return failed


def print_table(failed, status_data):
    batch = status_data.get("batch", {})
    last_updated = status_data.get("last_updated", "unknown")

    print(f"Scrape status updated: {last_updated}")
    print(
        "Status file batch: "
        f"{batch.get('batch_index', 'unknown')} "
        f"of {batch.get('batch_count', 'unknown')} "
        f"(batch size {batch.get('batch_size', 'unknown')})"
    )
    print()

    if not failed:
        print("No failed chapters found.")
        return

    print(f"Failed chapters: {len(failed)}")
    print()
    print("| Rerun index | Status batch | Status | Chapter | Reason |")
    print("| ---: | ---: | --- | --- | --- |")

    for item in failed:
        rerun_index = (
            str(item["rerun_batch_index"])
            if item["rerun_batch_index"] is not None
            else "unknown"
        )
        status_batch = (
            str(item["status_batch_index"])
            if item["status_batch_index"] is not None
            else "unknown"
        )
        reason = item["reason"].replace("|", "\\|")
        print(
            f"| {rerun_index} | {status_batch} | {item['status']} | "
            f"{item['chapter']} | {reason} |"
        )

    print()
    print("Rerun with:")
    for item in failed:
        if item["rerun_batch_index"] is None:
            continue
        print(f"  .\\rerun_chapter.ps1 -Index {item['rerun_batch_index']}")


def write_csv(failed, output_path):
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "rerun_batch_index",
                "status_batch_index",
                "status",
                "chapter",
                "reason",
                "url",
            ],
        )
        writer.writeheader()
        writer.writerows(failed)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Report chapters in docs/scrape-status.json that did not scrape "
            "successfully, including their single-chapter rerun index."
        )
    )
    parser.add_argument(
        "--status-file",
        default="docs/scrape-status.json",
        type=Path,
        help="Path to scrape-status.json. Defaults to docs/scrape-status.json.",
    )
    parser.add_argument(
        "--chapters-file",
        default="chapters.json",
        type=Path,
        help="Path to chapters.json. Defaults to chapters.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a Markdown table.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Also write the failed chapter report to this CSV path.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        status_data = load_json(args.status_file)
        chapters_data = load_json(args.chapters_file)
    except FileNotFoundError as e:
        print(f"Missing file: {e.filename}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    failed = collect_failed_chapters(status_data, chapters_data)

    if args.csv:
        write_csv(failed, args.csv)

    if args.json:
        print(json.dumps(failed, indent=2))
    else:
        print_table(failed, status_data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
