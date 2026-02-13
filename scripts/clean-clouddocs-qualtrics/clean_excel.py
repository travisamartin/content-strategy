#!/usr/bin/env python3
"""Clean an Excel data export for use in Tableau by dropping specified columns."""

import argparse
import sys

import pandas as pd


# Columns to drop, specified as Excel-style letters (1-indexed positional).
# Convert to 0-indexed integers.
DROP_COLUMNS = [
    "A", "B", "C", "D", "E", "F", "G",
    "I", "J", "K", "L", "M",
    "P", "Q", "R",
    "V", "W", "X", "Y", "Z",
    "AD",
]


def col_letter_to_index(letter: str) -> int:
    """Convert an Excel column letter (e.g. 'AD') to a 0-based index."""
    result = 0
    for ch in letter.upper():
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


def main():
    parser = argparse.ArgumentParser(description="Clean Excel export for Tableau.")
    parser.add_argument("input_file", help="Path to the input Excel file")
    parser.add_argument("output_file", help="Path for the output Excel file")
    args = parser.parse_args()

    df = pd.read_excel(args.input_file)

    drop_indices = [col_letter_to_index(c) for c in DROP_COLUMNS]
    # Keep only indices that exist in the dataframe
    drop_indices = [i for i in drop_indices if i < len(df.columns)]
    cols_to_drop = [df.columns[i] for i in drop_indices]

    df = df.drop(columns=cols_to_drop)

    # Drop the sub-header row (first data row).
    df = df.iloc[1:].reset_index(drop=True)

    # Recode values in Q1 (originally column S).
    # 10 -> 1, 11 -> 2, ..., 16 -> 7
    recode_map = {10: 1, 11: 2, 12: 3, 13: 4, 14: 5, 15: 6, 16: 7}
    df["Q1"] = pd.to_numeric(df["Q1"], errors="coerce")
    df["Q1"] = df["Q1"].map(recode_map).fillna(df["Q1"])
    df["Q1"] = df["Q1"].astype("Int64")  # nullable integer type

    # Clean URLs in the current_url column: strip everything from the first ? or #.
    col_url = "current_url"
    df[col_url] = df[col_url].astype(str).str.split(r"[?#]").str[0]
    df[col_url] = df[col_url].str.replace("https://clouddocs.f5.com/", "", regex=False)
    df[col_url] = df[col_url].str.replace(".html", "", regex=False)
    df[col_url] = df[col_url].str.rstrip("/")
    df[col_url] = df[col_url].replace("nan", pd.NA)

    df.to_excel(args.output_file, index=False)
    print(f"Wrote {len(df)} rows x {len(df.columns)} columns to {args.output_file}")


if __name__ == "__main__":
    main()