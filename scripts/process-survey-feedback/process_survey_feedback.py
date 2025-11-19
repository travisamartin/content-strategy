#!/usr/bin/env python3
"""
process_survey_feedback.py

Cleans and transforms an Excel file for use in Tableau.

Features:
- Loads an Excel file that has no header row and uses the first row as column headers.
- Removes a duplicate second header or a known subheading row.
- Removes rows where 'Link URL' is missing.
- Removes rows where 'Q2' contains the word 'testing'.
- Excludes bogus responses based on a text file of ResponseIds.
- Scrubs email addresses from Q2 (replaces found emails with an empty string).
- Cleans Link URL values (removes fragment, ensures trailing slash).
- Rewrites Link URL values according to nginx redirect rules. The redirect file path
  defaults to:
  /Users/T.Martin/Projects/git/nginxinc/docs-nginx-conf/nginx-docs-production/etc/nginx/conf.d/azure-redirects-base
  If the file exists, mappings are loaded and applied. Original Link URL is preserved
  in the column 'Original Link URL' and Link URL is replaced with the canonical URL.
- Optionally reverse geocodes LocationLatitude/LocationLongitude into Country, City,
  and State columns when the --geocode flag is provided. Geocoding respects a 1s
  minimum delay per request to comply with Nominatim usage limits.
- Writes cleaned output to an Excel workbook with the sheet name "Survey Data".

Usage:
    python process_survey_feedback.py input.xlsx -o cleaned_data.xlsx \
        --exclude-file /path/to/excluded-responses.txt \
        --redirect-file /path/to/azure-redirects-base \
        --geocode

Notes:
- Check cleanup_log.txt for detailed logs including removed rows, ResponseIDs removed,
  URL canonicalization operations, email scrubbing, and geocoding activity.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import re
from typing import List, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd

# geopy imports are optional at runtime when geocoding is requested
try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
except Exception:
    Nominatim = None  # type: ignore
    RateLimiter = None  # type: ignore

# --------------------------------------------------------------------
# Logging configuration: file + console
# --------------------------------------------------------------------
logging.basicConfig(
    filename="cleanup_log.txt",
    level=logging.INFO,
    format="%(asctime)s: %(message)s",
)
_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(logging.Formatter("%(asctime)s: %(message)s"))
logging.getLogger("").addHandler(_console)

# --------------------------------------------------------------------
# Utility functions
# --------------------------------------------------------------------
def normalize_url_keep_query(url: str) -> str | None:
    """
    Normalize a URL string:
    - strip whitespace
    - remove fragment
    - ensure path ends with a trailing slash if it is non-empty
    - keep the query string intact
    If input is not a string or is null-like, returns None.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    parsed = urlsplit(url.strip())
    scheme, netloc, path, query, _fragment = parsed.scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment

    # If URL was relative (no scheme/netloc) we return the path as-is (caller may join with base).
    # But we still ensure trailing slash on path if not empty.
    if path and not path.endswith("/"):
        path = path + "/"

    return urlunsplit((scheme, netloc, path, query or "", ""))


def ensure_absolute_and_normalize(url: str, base_url: str = "https://docs.nginx.com") -> str | None:
    """
    Convert relative URLs (starting with '/') to absolute by joining with base_url,
    then normalize using normalize_url_keep_query.
    """
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if url.startswith("/"):
        url = urljoin(base_url, url)
    # if url has no scheme but not starting with '/', treat as relative and join too
    if not urlsplit(url).scheme:
        url = urljoin(base_url, url)
    return normalize_url_keep_query(url)


# --------------------------------------------------------------------
# Functions for loading and applying nginx redirect mappings
# --------------------------------------------------------------------
def load_redirects_from_nginx(nginx_file_path: str, base_url: str = "https://docs.nginx.com") -> List[Tuple[str, str]]:
    """
    Parse an nginx-style redirects file and return a list of (old_abs, new_abs) mappings.
    Handles:
    - blocks like:
        location ^~ /old/ {
            return 301 /new/;
        }
      or single-line variants.
    - simple two-token lines: "/old /new"
    - will convert relative targets to absolute using base_url
    Mappings are normalized and deduplicated, then returned sorted longest-old-first.
    """
    mappings: List[Tuple[str, str]] = []

    if not os.path.exists(nginx_file_path):
        logging.warning(f"Redirect file not found: {nginx_file_path}")
        return []

    try:
        with open(nginx_file_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception as e:
        logging.error(f"Failed to read redirect file {nginx_file_path}: {e}")
        return []

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith("#"):
            i += 1
            continue

        # Detect a location line with a path
        m_loc = re.match(r"location\b(?:\s+[^\s]+)?\s+(?P<old>/[^\s\{]*)", line, re.IGNORECASE)
        if m_loc:
            old_path = m_loc.group("old").strip()

            # If return is on same line: location ... { return 301 /new/; }
            m_single = re.search(r"return\s+\d{3}\s+([^;]+);", line, re.IGNORECASE)
            if m_single:
                raw_target = m_single.group(1).strip()
                new_abs = raw_target if not raw_target.startswith("/") and urlsplit(raw_target).scheme else raw_target
                old_abs_norm = ensure_absolute_and_normalize(old_path, base_url)
                target_abs_norm = ensure_absolute_and_normalize(raw_target, base_url) if raw_target.startswith("/") or not urlsplit(raw_target).scheme else normalize_url_keep_query(raw_target)
                if old_abs_norm and target_abs_norm:
                    mappings.append((old_abs_norm, target_abs_norm))
                i += 1
                continue

            # Otherwise scan inner block lines for return statements
            j = i + 1
            found_target = None
            while j < len(lines):
                inner = lines[j].strip()
                if inner.startswith("location "):
                    break
                m_return = re.search(r"return\s+\d{3}\s+([^;]+);", inner, re.IGNORECASE)
                if m_return:
                    found_target = m_return.group(1).strip()
                    break
                j += 1

            if found_target:
                old_abs_norm = ensure_absolute_and_normalize(old_path, base_url)
                target_abs_norm = ensure_absolute_and_normalize(found_target, base_url) if found_target.startswith("/") or not urlsplit(found_target).scheme else normalize_url_keep_query(found_target)
                if old_abs_norm and target_abs_norm:
                    mappings.append((old_abs_norm, target_abs_norm))
            i = j
            continue

        # Match two-token lines like: /old /new
        m_two = re.match(r"(?P<old>/\S+)\s+(?P<new>/\S+)", line)
        if m_two:
            old_path, new_path = m_two.group("old"), m_two.group("new")
            old_abs_norm = ensure_absolute_and_normalize(old_path, base_url)
            new_abs_norm = ensure_absolute_and_normalize(new_path, base_url)
            if old_abs_norm and new_abs_norm:
                mappings.append((old_abs_norm, new_abs_norm))
            i += 1
            continue

        i += 1

    # Deduplicate keeping first mapping for a given old
    seen: dict[str, str] = {}
    for old, new in mappings:
        if old and new and old not in seen:
            seen[old] = new

    final_mappings = list(seen.items())
    # Sort longest-old-first so more specific rules match first
    final_mappings.sort(key=lambda t: len(t[0]), reverse=True)

    logging.info(f"Loaded {len(final_mappings)} redirect mappings from {nginx_file_path}")
    if final_mappings:
        logging.info("Sample redirect mappings (first 10):")
        for old, new in final_mappings[:10]:
            logging.info(f"  {old} -> {new}")

    return final_mappings


def apply_redirect_mappings_in_place(df: pd.DataFrame, mappings: List[Tuple[str, str]]) -> pd.DataFrame:
    """
    Apply mappings to df['Link URL'] in-place:
    - Creates 'Original Link URL' if not present
    - Normalizes current Link URL values
    - Creates 'Canonical Link URL' with the mapped URL
    - Replaces 'Link URL' with canonical mapping
    - Logs each row changed
    """
    if "Link URL" not in df.columns:
        logging.warning("No 'Link URL' column found; skipping redirect-based canonicalization.")
        return df

    # Preserve original for audit
    if "Original Link URL" not in df.columns:
        df["Original Link URL"] = df["Link URL"]

    # Normalize Link URL values to absolute canonical form (if possible)
    df["Link URL"] = df["Link URL"].apply(lambda u: ensure_absolute_and_normalize(u) if isinstance(u, str) else None)

    def map_one(url: str | None) -> str | None:
        if not isinstance(url, str):
            return url
        for old, new in mappings:
            if url.startswith(old):
                # replace prefix occurrence once
                mapped = url.replace(old, new, 1)
                return mapped
        return url

    df["Canonical Link URL"] = df["Link URL"].apply(map_one)

    # Log row-level changes
    changed_mask = (df["Canonical Link URL"].notna()) & (df["Link URL"].notna()) & (df["Canonical Link URL"] != df["Link URL"])
    changed = df[changed_mask]
    for idx, row in changed.iterrows():
        logging.info(f"Row {idx}: URL canonicalized from {row['Link URL']} to {row['Canonical Link URL']}")

    logging.info(f"Total URLs canonicalized via redirect file: {changed.shape[0]}")

    # Replace Link URL with canonical
    df["Link URL"] = df["Canonical Link URL"]

    return df


# --------------------------------------------------------------------
# Data cleaning steps
# --------------------------------------------------------------------
def load_data(file_path: str) -> pd.DataFrame:
    """
    Read the Excel file with header=None, use first row as header,
    remove duplicate second header or a subheading row.
    """
    raw = pd.read_excel(file_path, header=None)
    logging.info("File read successfully.")
    logging.info(f"Initial shape (rows x columns): {raw.shape}")

    # Use the first row as header
    header = list(raw.iloc[0])
    raw = raw.iloc[1:].reset_index(drop=True)

    # Remove duplicate header or known subheading row if present
    if len(raw) > 0:
        first_data_row = list(raw.iloc[0])
        if first_data_row == header:
            logging.info("Second header row detected and removed.")
            raw = raw.iloc[1:].reset_index(drop=True)
        elif "Any suggestions for improvement?" in raw.iloc[0].values:
            logging.info("Subheading row detected and removed.")
            raw = raw.iloc[1:].reset_index(drop=True)

    df = pd.DataFrame(raw.values, columns=header)
    logging.info(f"Dataframe shape after header adjustments: {df.shape}")
    logging.info(f"Columns found: {list(df.columns)}")
    return df


def remove_missing_link(df: pd.DataFrame) -> pd.DataFrame:
    if "Link URL" not in df.columns:
        logging.error("Column 'Link URL' not found. Skipping missing Link URL removal.")
        return df

    before = df.shape[0]
    missing_mask = df["Link URL"].isnull()
    if missing_mask.any():
        for idx in df[missing_mask].index:
            logging.info(f"Row {idx} deleted because Link URL is missing.")
        df = df.dropna(subset=["Link URL"])
    after = df.shape[0]
    logging.info(f"Rows before removing missing Link URL: {before}, after: {after}")
    return df


def remove_q2_testing(df: pd.DataFrame) -> pd.DataFrame:
    if "Q2" not in df.columns:
        logging.warning("Column 'Q2' not found. Skipping Q2 testing removal.")
        return df

    before = df.shape[0]

    def contains_testing(value):
        if isinstance(value, str):
            return bool(re.search(r"testing", value, re.IGNORECASE))
        return False

    mask = df["Q2"].apply(contains_testing)
    if mask.any():
        for idx in df[mask].index:
            logging.info(f"Row {idx} deleted because Q2 contains 'testing'.")
        df = df[~mask]
    after = df.shape[0]
    logging.info(f"Rows before removing Q2='testing': {before}, after: {after}")
    return df


def exclude_bogus_responses(df: pd.DataFrame, exclude_file: str) -> pd.DataFrame:
    """
    Remove rows whose ResponseId is present in exclude_file.
    Logs the number removed and enumerate the ResponseIds removed.
    """
    try:
        with open(exclude_file, "r", encoding="utf-8") as f:
            exclude_ids = {line.strip().upper() for line in f if line.strip()}
        logging.info(f"Exclude file loaded. Excluding {len(exclude_ids)} ResponseIDs.")
    except Exception as e:
        logging.error(f"Error reading exclude file '{exclude_file}': {e}")
        return df

    if "ResponseId" not in df.columns:
        logging.error("Column 'ResponseId' not found in data. Cannot exclude bogus responses.")
        return df

    # Normalize ResponseId column for comparison
    df["ResponseId"] = df["ResponseId"].astype(str).str.strip().str.upper()

    # Identify which ResponseIds will be removed
    to_remove = df[df["ResponseId"].isin(exclude_ids)]
    removed_ids = sorted(to_remove["ResponseId"].unique())

    before = df.shape[0]
    df = df[~df["ResponseId"].isin(exclude_ids)]
    after = df.shape[0]

    logging.info(f"Excluded bogus responses: removed {before - after} rows based on ResponseId.")
    logging.info(f"Removed ResponseIDs: {removed_ids}")
    return df


def scrub_emails_in_q2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove email addresses from the Q2 column by replacing them with an empty string.
    Logs each row that was modified.
    """
    if "Q2" not in df.columns:
        logging.info("Column 'Q2' not found. Skipping email scrub.")
        return df

    email_pattern = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.IGNORECASE)

    def scrub_cell(cell, idx):
        if isinstance(cell, str):
            new_cell, count = email_pattern.subn("", cell)
            if count > 0:
                logging.info(f"Row {idx}: Found and removed {count} email(s) from Q2.")
                return new_cell
        return cell

    df["Q2"] = df.apply(lambda r: scrub_cell(r["Q2"], r.name), axis=1)
    return df


def clean_link_urls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove URL fragments and ensure trailing slash on Link URL column.
    """
    if "Link URL" not in df.columns:
        logging.error("Column 'Link URL' not found. Skipping URL cleaning.")
        return df

    def clean_one(u):
        if not isinstance(u, str) or not u.strip():
            return None
        # remove fragment
        no_fragment = u.split("#", 1)[0].strip()
        # ensure trailing slash
        if not no_fragment.endswith("/"):
            no_fragment += "/"
        # convert relative to absolute for consistency
        return ensure_absolute_and_normalize(no_fragment)

    df["Link URL"] = df["Link URL"].apply(clean_one)
    logging.info("Link URLs cleaned (removed fragments, ensured trailing slash).")
    return df


def reverse_geocode_locations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reverse geocode LocationLatitude/LocationLongitude into Country, City, State.
    Uses Nominatim with a RateLimiter to enforce ~1 request per second.
    """
    if Nominatim is None or RateLimiter is None:
        logging.error("geopy is not available. Install geopy to enable geocoding.")
        return df

    if "LocationLatitude" not in df.columns or "LocationLongitude" not in df.columns:
        logging.warning("LocationLatitude or LocationLongitude not found. Skipping geocoding.")
        return df

    geolocator = Nominatim(user_agent="process_survey_feedback_geocoder")
    reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)

    def geocode_row(row):
        lat = row["LocationLatitude"]
        lon = row["LocationLongitude"]
        if pd.notnull(lat) and pd.notnull(lon):
            try:
                location = reverse((lat, lon), language="en-US")
                if location and getattr(location, "raw", None) and "address" in location.raw:
                    address = location.raw["address"]
                    country = address.get("country")
                    # prefer city, fallback to town or village
                    city = address.get("city") or address.get("town") or address.get("village")
                    state = address.get("state")
                    logging.info(f"Row {row.name}: Reverse geocoded lat={lat}, lon={lon} -> country={country}, city={city}, state={state}")
                    return pd.Series([country, city, state])
                else:
                    logging.warning(f"Row {row.name}: No address result for lat={lat}, lon={lon}")
                    return pd.Series([None, None, None])
            except Exception as e:
                logging.warning(f"Row {row.name}: Error reverse geocoding lat={lat}, lon={lon}: {e}")
                return pd.Series([None, None, None])
        else:
            return pd.Series([None, None, None])

    df[["Country", "City", "State"]] = df.apply(geocode_row, axis=1)
    logging.info("Reverse geocoding complete. Columns 'Country', 'City', 'State' added.")
    return df


# --------------------------------------------------------------------
# Main
# --------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up an Excel file for Tableau.")
    parser.add_argument("input_file", help="Path to the input Excel file.")
    parser.add_argument(
        "-o",
        "--output",
        default="cleaned_data.xlsx",
        help="Path for the output Excel file (default: cleaned_data.xlsx)",
    )
    parser.add_argument(
        "--exclude-file", help="Path to a text file with ResponseIds to exclude (one per line)."
    )
    parser.add_argument(
        "--redirect-file",
        default="/Users/T.Martin/Projects/git/nginxinc/docs-nginx-conf/nginx-docs-production/etc/nginx/conf.d/azure-redirects-base",
        help="Path to nginx-style redirect file used to canonicalize Link URL values.",
    )
    parser.add_argument(
        "--geocode",
        action="store_true",
        help="Enable reverse geocoding of latitude/longitude into Country, City, and State columns.",
    )

    args = parser.parse_args()

    # Load source Excel
    df = load_data(args.input_file)
    logging.info("First few rows of the DataFrame:")
    logging.info("\n" + df.head().to_string())

    # Stepwise cleaning
    df = remove_missing_link(df)
    df = remove_q2_testing(df)

    # Update and clean URLs first (remove fragments and ensure trailing slash)
    df = clean_link_urls(df)

    # Apply redirects canonicalization if redirect file exists
    if args.redirect_file and os.path.exists(args.redirect_file):
        mappings = load_redirects_from_nginx(args.redirect_file, base_url="https://docs.nginx.com")
        if mappings:
            df = apply_redirect_mappings_in_place(df, mappings)
        else:
            logging.info("No mappings loaded from redirect file. Skipping canonicalization.")
    else:
        logging.info(f"Redirect file not provided or not found. Skipping URL canonicalization. ({args.redirect_file})")

    # Replace a specific old path pattern as requested previously
    # (safety: operate only on string values)
    def replace_specific_old(new_df: pd.DataFrame) -> pd.DataFrame:
        if "Link URL" not in new_df.columns:
            return new_df
        old_pat = "https://docs.nginx.com/nginxaas-azure/known-issues/"
        new_pat = "https://docs.nginx.com/nginxaas/azure/known-issues/"
        changed = 0
        for idx, val in new_df["Link URL"].items():
            if isinstance(val, str) and old_pat in val:
                updated = val.replace(old_pat, new_pat)
                logging.info(f"Row {idx}: Link URL updated from {val} to {updated} (specific replacement)")
                new_df.at[idx, "Link URL"] = updated
                changed += 1
        logging.info(f"Total specific replacements performed: {changed}")
        return new_df

    df = replace_specific_old(df)

    # Exclude bogus responses if requested
    if args.exclude_file:
        df = exclude_bogus_responses(df, args.exclude_file)

    # Scrub emails from Q2
    df = scrub_emails_in_q2(df)

    # Optionally geocode
    if args.geocode:
        df = reverse_geocode_locations(df)
    else:
        logging.info("Reverse geocoding disabled (use --geocode to enable).")

    # Final save to Excel with sheet name "Survey Data"
    try:
        df.to_excel(args.output, sheet_name="Survey Data", index=False)
        logging.info(f"Cleaned data written to {args.output}")
        print(f"Cleaned data written to {args.output}")
    except Exception as e:
        logging.error(f"Failed to write output Excel file '{args.output}': {e}")
        print(f"Failed to write output Excel file '{args.output}': {e}")

    logging.info("Script completed successfully.")


if __name__ == "__main__":
    main()