#!/usr/bin/env python3
"""
process_survey_feedback.py

Cleans and transforms an Excel file for use in Tableau.

What it does (summary)
- Loads an Excel file that has no header row and uses the first row as column headers.
- Removes a duplicate second header or a known subheading row.
- Removes rows missing Link URL.
- Removes rows where Q2 contains the word "testing".
- Excludes bogus responses based on a text file of ResponseIds (one per line).
- Scrubs email addresses out of Q2 (replaces email substrings with empty string).
- Normalizes URLs (removes query and fragment, ensures trailing slash).
  Normalizes current_url, Link URL, and canonical URL fields.
- Applies nginx-style redirect mappings (nginx `location` blocks with `return 301 ...;`)
  to rewrite old paths to new canonical URLs (default redirect file path provided).
- Performs a targeted replacement:
    https://docs.nginx.com/nginxaas-azure/known-issues/ -> https://docs.nginx.com/nginxaas/azure/known-issues/
  (logged.)
- Optionally reverse-geocodes LocationLatitude/LocationLongitude into Country/City/State
  when the --geocode flag is provided. Uses Nominatim with a min 1s delay per request.
- Writes cleaned output to an Excel workbook with the sheet name "Survey Data".
- Logs all actions to cleanup_log.txt and to console.

Notes
- Geocoding is optional and disabled by default (--geocode).
- Redirect file default:
  /Users/T.Martin/Projects/git/nginxinc/docs-nginx-conf/nginx-docs-production/etc/nginx/conf.d/azure-redirects-base

Add to repo README and requirements: pandas, openpyxl, geopy (if using --geocode), etc.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from typing import List, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd

# geopy imports are optional and only required when --geocode is used
try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
except Exception:
    Nominatim = None  # type: ignore
    RateLimiter = None  # type: ignore

# -------------------------
# Logging configuration
# -------------------------
LOGFILE = "cleanup_log.txt"
logging.basicConfig(
    filename=LOGFILE,
    level=logging.INFO,
    format="%(asctime)s: %(message)s",
)
_console = logging.StreamHandler()
_console.setLevel(logging.INFO)
_console.setFormatter(logging.Formatter("%(asctime)s: %(message)s"))
logging.getLogger("").addHandler(_console)


# -------------------------
# URL normalization helpers
# -------------------------
def normalize_url(url: str) -> str | None:
    """
    Normalize a URL:
    - trim whitespace
    - remove query and fragment
    - ensure trailing slash on non-empty path
    Returns None for non-string or empty input.
    """
    if not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    parsed = urlsplit(u)
    scheme, netloc, path = parsed.scheme, parsed.netloc, parsed.path
    # ensure trailing slash if path non-empty
    if path and not path.endswith("/"):
        path = path + "/"
    # return without query or fragment
    return urlunsplit((scheme, netloc, path, "", ""))


def ensure_absolute_and_normalize(url: str, base_url: str = "https://docs.nginx.com") -> str | None:
    """
    If url is relative, join with base_url. Then normalize (strip query & fragment).
    Returns normalized absolute URL or None.
    """
    if not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    # convert relative paths to absolute
    if u.startswith("/"):
        u = urljoin(base_url, u)
    elif not urlsplit(u).scheme:
        # no scheme and not starting with '/', treat relative
        u = urljoin(base_url, u)
    # normalize (removes query/fragment and enforces trailing slash)
    return normalize_url(u)


# -------------------------
# Redirect loader (nginx format)
# -------------------------
def load_redirects_from_nginx(nginx_file_path: str, base_url: str = "https://docs.nginx.com") -> List[Tuple[str, str]]:
    """
    Parse an nginx-style redirect file and return list of (old_abs_norm, new_abs_norm).
    Supports:
      - location ... { return 301 /new/; } blocks (single-line or multi-line)
      - simple two-token lines: "/old /new"
    Converts relative targets to absolute using base_url.
    Deduplicates and sorts longest-old-first.
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

        # location line: capture old path (/something)
        m_loc = re.match(r"location\b(?:\s+[^\s]+)?\s+(?P<old>/[^\s\{]*)", line, re.IGNORECASE)
        if m_loc:
            old_path = m_loc.group("old").strip()

            # same-line return: e.g. location /old { return 301 /new/; }
            m_single = re.search(r"return\s+\d{3}\s+([^;]+);", line, re.IGNORECASE)
            if m_single:
                raw_target = m_single.group(1).strip()
                old_abs_norm = ensure_absolute_and_normalize(old_path, base_url)
                target_abs_norm = ensure_absolute_and_normalize(raw_target, base_url) if raw_target.startswith("/") or not urlsplit(raw_target).scheme else normalize_url(raw_target)
                if old_abs_norm and target_abs_norm:
                    mappings.append((old_abs_norm, target_abs_norm))
                i += 1
                continue

            # otherwise scan inside block for return statement
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
                target_abs_norm = ensure_absolute_and_normalize(found_target, base_url) if found_target.startswith("/") or not urlsplit(found_target).scheme else normalize_url(found_target)
                if old_abs_norm and target_abs_norm:
                    mappings.append((old_abs_norm, target_abs_norm))
            i = j
            continue

        # fallback: two-token line "/old /new"
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

    # dedupe keeping first mapping for a given old
    seen: dict[str, str] = {}
    for old, new in mappings:
        if old and new and old not in seen:
            seen[old] = new

    final_mappings = list(seen.items())
    final_mappings.sort(key=lambda t: len(t[0]), reverse=True)
    logging.info(f"Loaded {len(final_mappings)} redirect mappings from {nginx_file_path}")
    if final_mappings:
        logging.info("Sample redirect mappings (first 10):")
        for old, new in final_mappings[:10]:
            logging.info(f"  {old} -> {new}")
    return final_mappings


def apply_redirect_mappings_in_place(df: pd.DataFrame, mappings: List[Tuple[str, str]]) -> pd.DataFrame:
    """
    Apply redirect mappings to df['Link URL'] in place:
    - create 'Original Link URL' if missing
    - normalize Link URL values (absolute + remove query/fragment)
    - create 'Canonical Link URL' (mapped value)
    - replace Link URL with Canonical Link URL
    Logs each changed row.
    """
    if "Link URL" not in df.columns:
        logging.warning("No 'Link URL' column found; skipping redirect-based canonicalization.")
        return df

    if "Original Link URL" not in df.columns:
        df["Original Link URL"] = df["Link URL"]

    # normalize existing Link URL values
    df["Link URL"] = df["Link URL"].apply(lambda u: ensure_absolute_and_normalize(u) if isinstance(u, str) else None)

    def map_one(url: str | None) -> str | None:
        if not isinstance(url, str):
            return url
        for old, new in mappings:
            if url.startswith(old):
                mapped = url.replace(old, new, 1)
                return mapped
        return url

    df["Canonical Link URL"] = df["Link URL"].apply(map_one)

    changed_mask = (df["Canonical Link URL"].notna()) & (df["Link URL"].notna()) & (df["Canonical Link URL"] != df["Link URL"])
    changed = df[changed_mask]
    for idx, row in changed.iterrows():
        logging.info(f"Row {idx}: URL canonicalized from {row['Link URL']} to {row['Canonical Link URL']}")
    logging.info(f"Total URLs canonicalized via redirect file: {changed.shape[0]}")

    # replace Link URL with canonical value (we keep Canonical and Original for audit)
    df["Link URL"] = df["Canonical Link URL"]
    return df


# -------------------------
# Data cleaning functions
# -------------------------
def load_data(file_path: str) -> pd.DataFrame:
    """
    Read Excel file with header=None, set first row as header,
    detect and remove duplicate header or known Q2 subheading row.
    """
    raw = pd.read_excel(file_path, header=None)
    logging.info("File read successfully.")
    logging.info(f"Initial shape (rows x columns): {raw.shape}")

    header = list(raw.iloc[0])
    raw = raw.iloc[1:].reset_index(drop=True)

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
    mask = df["Q2"].apply(lambda v: isinstance(v, str) and bool(re.search(r"testing", v, re.IGNORECASE)))
    if mask.any():
        for idx in df[mask].index:
            logging.info(f"Row {idx} deleted because Q2 contains 'testing'.")
        df = df[~mask]
    after = df.shape[0]
    logging.info(f"Rows before removing Q2='testing': {before}, after: {after}")
    return df


def exclude_bogus_responses(df: pd.DataFrame, exclude_file: str) -> pd.DataFrame:
    """
    Exclude rows whose ResponseId appears (one per line) in exclude_file.
    Logs the count and enumerates the ResponseIds removed.
    """
    try:
        with open(exclude_file, "r", encoding="utf-8") as f:
            exclude_ids = {line.strip() for line in f if line.strip()}
        logging.info(f"Exclude file loaded. Excluding {len(exclude_ids)} ResponseIDs.")
    except Exception as e:
        logging.error(f"Error reading exclude file '{exclude_file}': {e}")
        return df

    # Ensure column exists
    if "ResponseId" not in df.columns:
        logging.error("Column 'ResponseId' not found in data. Cannot exclude bogus responses.")
        return df

    # Normalize for comparison (case-sensitive id? keep exact matching -- but strip whitespace)
    df["ResponseId"] = df["ResponseId"].astype(str).str.strip()

    to_remove_df = df[df["ResponseId"].isin(exclude_ids)]
    removed_ids = sorted(to_remove_df["ResponseId"].unique())
    before = df.shape[0]
    df = df[~df["ResponseId"].isin(exclude_ids)]
    after = df.shape[0]

    logging.info(f"Excluded bogus responses: removed {before - after} rows based on ResponseId.")
    if removed_ids:
        logging.info(f"Removed ResponseIDs ({len(removed_ids)}): {removed_ids}")
    else:
        logging.info("No ResponseIDs from exclude-file were found in the dataset.")
    return df


def scrub_emails_in_q2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove email substrings from Q2 cells. Leaves the rest of the text intact.
    If multiple emails present, all removed. Logs rows that were changed.
    """
    if "Q2" not in df.columns:
        logging.info("Column 'Q2' not found. Skipping email scrub.")
        return df

    email_pattern = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.IGNORECASE)

    def scrub_cell(cell, idx):
        if isinstance(cell, str):
            new_cell, count = email_pattern.subn("", cell)
            if count > 0:
                logging.info(f"Row {idx}: Removed {count} email(s) from Q2.")
                # collapse repeated whitespace
                new_cell = re.sub(r"\s{2,}", " ", new_cell).strip()
                return new_cell
        return cell

    df["Q2"] = df.apply(lambda r: scrub_cell(r["Q2"], r.name), axis=1)
    return df


def clean_link_urls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize URL columns: remove query & fragment and ensure trailing slash.
    Operates on 'Link URL' and 'current_url' if present. Preserves originals where possible.
    """
    # Preserve originals for audit
    if "Link URL" in df.columns and "Original Link URL" not in df.columns:
        df["Original Link URL"] = df["Link URL"]
    if "current_url" in df.columns and "Original current_url" not in df.columns:
        df["Original current_url"] = df["current_url"]

    if "Link URL" in df.columns:
        df["Link URL"] = df["Link URL"].apply(lambda u: ensure_absolute_and_normalize(u) if isinstance(u, str) else None)
    if "current_url" in df.columns:
        df["current_url"] = df["current_url"].apply(lambda u: ensure_absolute_and_normalize(u) if isinstance(u, str) else None)

    logging.info("URLs normalized (removed query/fragment, ensured trailing slash).")
    return df


def replace_specific_old(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace the old nginxaas-azure known-issues URL with new canonical path.
    """
    if "Link URL" not in df.columns:
        return df
    old_pat = "https://docs.nginx.com/nginxaas-azure/known-issues/"
    new_pat = "https://docs.nginx.com/nginxaas/azure/known-issues/"
    changed = 0
    for idx, val in df["Link URL"].items():
        if isinstance(val, str) and old_pat in val:
            updated = val.replace(old_pat, new_pat)
            logging.info(f"Row {idx}: Link URL updated from {val} to {updated} (specific replacement)")
            df.at[idx, "Link URL"] = updated
            changed += 1
    logging.info(f"Total specific replacements performed: {changed}")
    return df


def reverse_geocode_locations(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reverse geocode LocationLatitude/LocationLongitude into Country, City, State using Nominatim.
    Respects a minimum 1 second delay per request via RateLimiter.
    """
    if Nominatim is None or RateLimiter is None:
        logging.error("geopy not installed. Install geopy to enable geocoding.")
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
                    addr = location.raw["address"]
                    country = addr.get("country")
                    city = addr.get("city") or addr.get("town") or addr.get("village")
                    state = addr.get("state")
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


# -------------------------
# Main
# -------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up an Excel file for Tableau.")
    parser.add_argument("input_file", help="Path to the input Excel file.")
    parser.add_argument("-o", "--output", default="cleaned_data.xlsx", help="Path for the output Excel file.")
    parser.add_argument("--exclude-file", help="Path to a text file with ResponseIds to exclude (one per line).")
    parser.add_argument(
        "--redirect-file",
        default="/Users/T.Martin/Projects/git/nginxinc/docs-nginx-conf/nginx-docs-production/etc/nginx/conf.d/azure-redirects-base",
        help="Path to nginx-style redirect file used to canonicalize Link URL values.",
    )
    parser.add_argument("--geocode", action="store_true", help="Enable reverse geocoding (slow). Default: disabled.")
    args = parser.parse_args()

    # Load
    df = load_data(args.input_file)
    logging.info("First few rows of the DataFrame:")
    logging.info("\n" + df.head().to_string())

    # Cleaning pipeline
    df = remove_missing_link(df)
    df = remove_q2_testing(df)

    # Clean and normalize URLs (removes query & fragment)
    df = clean_link_urls(df)

    # Apply nginx redirect mappings to canonicalize Link URL
    if args.redirect_file and os.path.exists(args.redirect_file):
        mappings = load_redirects_from_nginx(args.redirect_file, base_url="https://docs.nginx.com")
        if mappings:
            df = apply_redirect_mappings_in_place(df, mappings)
        else:
            logging.info("No mappings loaded from redirect file. Skipping canonicalization.")
    else:
        logging.info(f"Redirect file not provided or not found. Skipping URL canonicalization. ({args.redirect_file})")

    # Specific requested replacement (safety)
    df = replace_specific_old(df)

    # Exclude bogus responses (if provided)
    if args.exclude_file:
        df = exclude_bogus_responses(df, args.exclude_file)
    else:
        logging.info("No exclude file provided; skipping bogus-response exclusion.")

    # Scrub emails from Q2
    df = scrub_emails_in_q2(df)

    # Optionally geocode (disabled by default)
    if args.geocode:
        df = reverse_geocode_locations(df)
    else:
        logging.info("Reverse geocoding disabled (use --geocode to enable).")

    # Final save
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