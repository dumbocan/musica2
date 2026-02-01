#!/usr/bin/env python3
"""Generate a JSON report with artists missing metadata."""

from app.services.data_quality import write_report


def main() -> None:
    report = write_report()
    print(f"Found {len(report)} artists missing data. Report saved under cache/data_quality.")


if __name__ == "__main__":
    main()
