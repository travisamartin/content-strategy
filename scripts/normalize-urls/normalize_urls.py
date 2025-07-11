#!/usr/bin/env python3
import csv
import os
import sys
import argparse

def normalize_url(url: str) -> str:
    """
    Drop any fragment (the ‘#…’ part) and ensure a single trailing slash.
    """
    base = url.split('#', 1)[0].rstrip('/')
    return base + '/'

def main():
    parser = argparse.ArgumentParser(
        description="Normalize URLs in an Adobe Analytics CSV report so they all end with a slash."
    )
    parser.add_argument(
        "input_csv",
        help="Path to the Adobe Analytics CSV file to normalize"
    )
    args = parser.parse_args()

    input_path = args.input_csv
    base, ext = os.path.splitext(input_path)
    output_path = f"{base}_normalized{ext}"

    try:
        with open(input_path, newline='', encoding='utf-8') as infile, \
             open(output_path, 'w', newline='', encoding='utf-8') as outfile:

            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            # copy header row unchanged
            header = next(reader)
            writer.writerow(header)

            for row in reader:
                if not row:
                    # skip blank lines
                    continue

                original = row[0].strip()
                try:
                    if not original:
                        normalized = original
                    else:
                        normalized = normalize_url(original)
                        if normalized != original:
                            print(f"{original} → {normalized}")
                    row[0] = normalized
                except Exception as err:
                    print(f"Error normalizing URL '{original}': {err}")

                writer.writerow(row)

        print(f"\nDone. Saved normalized file as:\n  {output_path}")

    except FileNotFoundError:
        print(f"Error: file not found: {input_path}")
        sys.exit(1)
    except Exception as err:
        print(f"Unexpected error: {err}")
        sys.exit(1)

if __name__ == "__main__":
    main()