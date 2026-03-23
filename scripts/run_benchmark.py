#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from app.evaluation.benchmarking import BenchmarkRunSettings, build_output_dir, run_benchmark, save_current_results, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the TC01-TC14 benchmark against the local LangGraph flow.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/evaluation/ragas_dataset.json"),
        help="Path to the benchmark dataset JSON.",
    )
    parser.add_argument(
        "--case-id",
        type=str,
        default=None,
        help="Optional benchmark case id to run, for example TC-04.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation/results"),
        help="Base directory for generated benchmark reports.",
    )
    parser.add_argument(
        "--no-ragas",
        action="store_true",
        help="Skip RAGAS scoring and only capture raw benchmark outputs.",
    )
    parser.add_argument(
        "--save-current",
        action="store_true",
        help="Also write the canonical current-results snapshot to data/evaluation/.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_settings = BenchmarkRunSettings(
        dataset_path=args.dataset,
        output_dir=build_output_dir(args.output_dir),
        case_id=args.case_id,
        use_ragas=not args.no_ragas,
        save_current=args.save_current,
    )
    results = run_benchmark(run_settings)
    json_path, md_path = write_report(run_settings.output_dir, results)
    print(f"Wrote benchmark JSON report to {json_path}")
    print(f"Wrote benchmark Markdown report to {md_path}")
    if run_settings.save_current:
        current_json_path, current_md_path = save_current_results(results)
        print(f"Updated current benchmark JSON snapshot at {current_json_path}")
        print(f"Updated current benchmark Markdown snapshot at {current_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
