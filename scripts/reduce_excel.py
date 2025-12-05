#!/usr/bin/env python3
"""CLI tool to downsample an Excel sheet and overwrite it in place."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Optional

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Downsample the rows of an Excel file and overwrite it with the result."
        )
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to the Excel file (e.g. shared/Nelivaptan_papers.xlsx)",
    )
    parser.add_argument(
        "-f",
        "--fraction",
        type=float,
        default=0.1,
        help="Fraction of rows to keep (default: 0.1, i.e. 10%%).",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for reproducibility.",
    )
    return parser.parse_args()


def sample_dataframe(df: pd.DataFrame, fraction: float, seed: Optional[int]) -> pd.DataFrame:
    if df.empty or fraction <= 0:
        return df.iloc[0:0]

    capped_fraction = min(max(fraction, 0.0), 1.0)
    sample_size = max(1, math.ceil(len(df) * capped_fraction))
    sample_size = min(sample_size, len(df))
    return df.sample(n=sample_size, random_state=seed).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    excel_path = args.path

    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    df = pd.read_excel(excel_path)
    sampled = sample_dataframe(df, args.fraction, args.seed)
    sampled.to_excel(excel_path, index=False)
    print(
        f"Wrote {len(sampled)} rows back to {excel_path} "
        f"(from original {len(df)} rows, fraction={args.fraction})"
    )


if __name__ == "__main__":
    main()
