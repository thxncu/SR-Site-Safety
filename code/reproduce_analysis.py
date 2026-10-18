#!/usr/bin/env python3
"""Regenerate the package analysis and figures from the supplied scientific inputs."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path,
                        help="Optional directory containing the official review PDFs and matching pdftotext -layout TXT files; rebuild the page retrieval frame only when provided.")
    parser.add_argument("--skip-figures", action="store_true", help="Reproduce all tabular analysis without rerendering the unchanged figures.")
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    code, data, figures = package / "code", package / "data", package / "figures"
    reports = args.reports.resolve() if args.reports is not None else None
    if reports is not None and not reports.is_dir():
        parser.error(f"Report directory does not exist: {reports}")
    figures.mkdir(exist_ok=True)
    commands = [
        [code / "extraction/build_covered_elsewhere_audit.py"],
        [code / "semantic/recompute_semantic_scores.py"],
        [code / "compute_core_results.py"],
        [code / "compute_cohort_and_retrieval_checks.py", "--package", package, "--output", data],
        [code / "audit_selection_context.py", "--package", package, "--output", data],
        [code / "record_checks/check_screening_record.py", package / "specifications/observed_H_1_6_3.json"],
        [code / "draw_figure1.py"],
        [code / "draw_figure2.py", "--output-dir", figures],
        [code / "draw_selection_frame.py", "--accounting", data / "external_review_selection_accounting.csv", "--output", figures],
    ]
    if args.skip_figures:
        commands = commands[:6]
    if reports is not None:
        commands[4].extend(["--reports", reports])
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    for command in commands:
        print(f"Running {Path(command[0]).relative_to(package)}", flush=True)
        subprocess.run([sys.executable, *map(str, command)], cwd=package,
                       env=environment, check=True)
    print("Tabular analysis regenerated; figure rerendering skipped." if args.skip_figures else "Analysis and Figures 1, 2 and S1 regenerated.", flush=True)
    if reports is None:
        print("Figure S1 uses the supplied review-page accounting; use --reports to rebuild that frame from the official reports.", flush=True)


if __name__ == "__main__":
    main()
