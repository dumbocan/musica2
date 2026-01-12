import argparse
from datetime import date, timedelta

from app.services.billboard import fetch_chart_entries


def align_chart_date(input_date: date) -> date:
    """Billboard charts use Saturday dates."""
    target_weekday = 5  # Saturday
    days_back = (input_date.weekday() - target_weekday) % 7
    return input_date - timedelta(days=days_back)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Billboard chart scraping.")
    parser.add_argument("--chart", default="hot-100", help="Chart slug (hot-100, billboard-global-200)")
    parser.add_argument("--date", default=None, help="Chart date (YYYY-MM-DD). Defaults to latest.")
    args = parser.parse_args()

    if args.date:
        chart_date = date.fromisoformat(args.date)
    else:
        chart_date = align_chart_date(date.today())

    entries = fetch_chart_entries(args.chart, chart_date)
    print(f"Chart {args.chart} @ {chart_date.isoformat()} -> {len(entries)} entries")
    for entry in entries[:5]:
        print(f"{entry['rank']:>3}  {entry['title']} — {entry['artist']}")


if __name__ == "__main__":
    main()
