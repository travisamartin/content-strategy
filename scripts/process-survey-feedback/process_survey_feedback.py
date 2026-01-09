#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_survey_feedback.py

Cleans and transforms an Excel file for use in Tableau.

Usage (example):
  python process_survey_feedback.py "input.xlsx" -o "cleaned_data.xlsx" \
    --exclude-file excluded-responses.txt \
    --redirect-file /path/to/azure-redirects-base \
    --geocode --geocache geo_country_cache.json

Notes:
- Geocoding is disabled by default. Use --geocode to enable.
- Offline geocoding (reverse_geocoder + pycountry) is the default and only geocode mode.
  Install with: pip install reverse_geocoder pycountry
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from typing import List, Tuple
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd

# Optional imports for offline geocoding (required when --geocode is used)
try:
    import reverse_geocoder as rg
    import pycountry
except Exception:
    rg = None
    pycountry = None

# --- Logging setup ---------------------------------------------------------
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


# --- URL normalization helpers --------------------------------------------
def normalize_url(url: str) -> str | None:
    """
    Clean a URL or path:
    - Trim whitespace
    - Fix malformed scheme slashes (e.g. 'https:///path' -> 'https://path')
    - Remove query and fragment
    - Ensure a single trailing slash on the path
    - Return absolute URL if scheme+netloc present, otherwise a clean path starting with '/'
    """
    if not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None

    # Fix malformed scheme slashes like "https:///..."
    u = re.sub(r"^(https?:)/*", r"\1//", u)

    parsed = urlsplit(u)
    scheme, netloc, path = parsed.scheme, parsed.netloc, parsed.path or "/"

    # Remove query & fragment by rebuilding without them
    # Ensure single trailing slash and collapse duplicate slashes
    if not path.endswith("/"):
        path = path + "/"
    path = re.sub(r"/{2,}", "/", path)

    if scheme and netloc:
        return urlunsplit((scheme, netloc, path, "", ""))

    # Return a cleaned path (leading slash)
    if not path.startswith("/"):
        path = "/" + path
    return path


def ensure_absolute_and_normalize(url: str, base_url: str = "https://docs.nginx.com") -> str | None:
    """
    Ensure the URL is absolute using base_url when needed, then normalize.
    """
    if not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None

    u = re.sub(r"^(https?:)/*", r"\1//", u)
    parsed = urlsplit(u)
    if parsed.scheme and parsed.netloc:
        return normalize_url(u)
    joined = urljoin(base_url, u)
    return normalize_url(joined)


def strip_nginx_vars_from_url(u: str) -> str | None:
    """
    Remove nginx variables (like $is_args$args or $variable) from URL strings,
    collapse duplicate slashes, and re-normalize.
    """
    if not isinstance(u, str):
        return u
    cleaned = re.sub(r"\$is_args\$args", "", u)
    cleaned = re.sub(r"\$[A-Za-z0-9_]+", "", cleaned)
    cleaned = re.sub(r"/{2,}", "/", cleaned)
    return ensure_absolute_and_normalize(cleaned) or cleaned


# --- Parse nginx-style redirect file -------------------------------------
def sanitize_nginx_target(raw_target: str) -> str:
    """Trim and remove quotes/variables from nginx return target string."""
    if not isinstance(raw_target, str):
        return ""
    s = raw_target.strip().strip('"').strip("'")
    s = re.sub(r"\$is_args\$args", "", s)
    s = re.sub(r"\$[A-Za-z0-9_]+", "", s)
    s = re.sub(r"/{2,}", "/", s)
    return s


def load_redirects_from_nginx(nginx_file_path: str, base_url: str = "https://docs.nginx.com") -> List[Tuple[str, str]]:
    """
    Parse nginx-style redirect file and return list of (old_abs_norm, new_abs_norm).
    Keeps the first mapping for each old path and sorts by old path length (desc).
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

        # Try to match `location ... /old/path { ... return 301 /new/; }`
        m_loc = re.match(r"location\b(?:\s+[^\s]+)?\s+(?P<old>/[^\s\{]*)", line, re.IGNORECASE)
        if m_loc:
            old_path = m_loc.group("old").strip()
            # try to find return on same line
            m_return_same = re.search(r"return\s+\d{3}\s+([^;]+);", line, re.IGNORECASE)
            if m_return_same:
                raw_target = m_return_same.group(1).strip()
                sanitized = sanitize_nginx_target(raw_target)
                old_abs_norm = ensure_absolute_and_normalize(old_path, base_url)
                target_abs_norm = ensure_absolute_and_normalize(sanitized, base_url)
                if old_abs_norm and target_abs_norm:
                    mappings.append((old_abs_norm, target_abs_norm))
                i += 1
                continue

            # search following lines for return
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
                sanitized = sanitize_nginx_target(found_target)
                old_abs_norm = ensure_absolute_and_normalize(old_path, base_url)
                target_abs_norm = ensure_absolute_and_normalize(sanitized, base_url)
                if old_abs_norm and target_abs_norm:
                    mappings.append((old_abs_norm, target_abs_norm))
            i = j
            continue

        # Also accept lines like: "/old/path /new/path"
        m_two = re.match(r"(?P<old>/\S+)\s+(?P<new>/\S+)", line)
        if m_two:
            old_path, new_path = m_two.group("old"), m_two.group("new")
            old_abs_norm = ensure_absolute_and_normalize(old_path, base_url)
            new_abs_norm = ensure_absolute_and_normalize(sanitize_nginx_target(new_path), base_url)
            if old_abs_norm and new_abs_norm:
                mappings.append((old_abs_norm, new_abs_norm))
            i += 1
            continue

        i += 1

    # Deduplicate keeping first mapping seen
    seen = {}
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
    Apply redirect mappings to 'Link URL' (and produce 'Canonical Link URL').
    Writes logs for every changed row. Replaces Link URL with canonical value.
    """
    if "Link URL" not in df.columns:
        logging.warning("No 'Link URL' column found; skipping redirect canonicalization.")
        return df

    if "Original Link URL" not in df.columns:
        df["Original Link URL"] = df["Link URL"]

    # Normalize Link URL and strip nginx vars first
    df["Link URL"] = df["Link URL"].apply(lambda u: ensure_absolute_and_normalize(u) if isinstance(u, str) else None)
    df["Link URL"] = df["Link URL"].apply(lambda u: strip_nginx_vars_from_url(u) if isinstance(u, str) else u)

    def map_one(url: str | None) -> str | None:
        if not isinstance(url, str):
            return url
        for old, new in mappings:
            if url.startswith(old):
                mapped = url.replace(old, new, 1)
                mapped = strip_nginx_vars_from_url(mapped) or mapped
                return mapped
        return strip_nginx_vars_from_url(url) or url

    df["Canonical Link URL"] = df["Link URL"].apply(map_one)

    changed_mask = (df["Canonical Link URL"].notna()) & (df["Link URL"].notna()) & (df["Canonical Link URL"] != df["Link URL"])
    changed = df[changed_mask]
    for idx, row in changed.iterrows():
        logging.info(f"Row {idx}: URL canonicalized from {row['Link URL']} to {row['Canonical Link URL']}")
    logging.info(f"Total URLs canonicalized via redirect file: {changed.shape[0]}")

    # Replace Link URL with canonical
    df["Link URL"] = df["Canonical Link URL"]
    return df


# --- Data cleaning steps -------------------------------------------------
def load_data(file_path: str) -> pd.DataFrame:
    """
    Read Excel with header=None; set first row as header; remove duplicate second header or Q2 subheading row.
    Return dataframe with cleaned columns.
    """
    raw = pd.read_excel(file_path, header=None)
    logging.info("File read successfully.")
    logging.info(f"Initial shape (rows x columns): {raw.shape}")

    # First row is header
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
    """Drop rows where Link URL is missing and log each removed row index."""
    if "Link URL" not in df.columns:
        logging.error("Column 'Link URL' not found. Skipping.")
        return df
    before = df.shape[0]
    missing_mask = df["Link URL"].isnull()
    if missing_mask.any():
        for idx in df[missing_mask].index:
            logging.info(f"Row {idx} deleted because Link URL is missing.")
        df = df.dropna(subset=["Link URL"]).reset_index(drop=True)
    logging.info(f"Rows before removing missing Link URL: {before}, after: {df.shape[0]}")
    return df


def remove_q2_testing(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows where Q2 contains 'testing' (case-insensitive)."""
    if "Q2" not in df.columns:
        logging.warning("Column 'Q2' not found. Skipping Q2 testing removal.")
        return df
    before = df.shape[0]
    mask = df["Q2"].apply(lambda v: isinstance(v, str) and bool(re.search(r"testing", v, re.IGNORECASE)))
    if mask.any():
        for idx in df[mask].index:
            logging.info(f"Row {idx} deleted because Q2 contains 'testing'.")
        df = df[~mask].reset_index(drop=True)
    logging.info(f"Rows before removing Q2='testing': {before}, after: {df.shape[0]}")
    return df


def _find_responseid_column(df: pd.DataFrame) -> str | None:
    """
    Find the ResponseId column name in a case-insensitive way.
    Returns canonical column name 'ResponseId' if found.
    """
    for candidate in df.columns:
        if isinstance(candidate, str) and candidate.lower() in ("responseid", "response_id", "response id"):
            # Normalize column name in the dataframe to 'ResponseId'
            if candidate != "ResponseId":
                df.rename(columns={candidate: "ResponseId"}, inplace=True)
            return "ResponseId"
    return None


def exclude_bogus_responses(df: pd.DataFrame, exclude_file: str) -> pd.DataFrame:
    """
    Remove rows whose ResponseId is listed in exclude_file (one id per line).
    Logs the number removed and enumerates the ResponseIds removed.
    """
    try:
        with open(exclude_file, "r", encoding="utf-8") as f:
            exclude_ids = {line.strip() for line in f if line.strip()}
        logging.info(f"Exclude file loaded. Excluding {len(exclude_ids)} ResponseIDs.")
    except Exception as e:
        logging.error(f"Error reading exclude file '{exclude_file}': {e}")
        return df

    col = _find_responseid_column(df)
    if not col:
        logging.error("ResponseId column not found. Skipping exclude.")
        return df

    df["ResponseId"] = df["ResponseId"].astype(str).str.strip()
    before = df.shape[0]
    to_remove_df = df[df["ResponseId"].isin(exclude_ids)]
    removed_ids = sorted(to_remove_df["ResponseId"].unique())
    df = df[~df["ResponseId"].isin(exclude_ids)].reset_index(drop=True)
    removed_count = before - df.shape[0]
    logging.info(f"Excluded bogus responses: removed {removed_count} rows based on ResponseId.")
    if removed_ids:
        logging.info(f"Removed ResponseIDs ({len(removed_ids)}): {removed_ids}")
    else:
        logging.info("No ResponseIDs from exclude-file were found in the dataset.")
    return df


def scrub_emails_in_q2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove email addresses from Q2 cells while preserving other text.
    Logs each row where emails were removed.
    """
    if "Q2" not in df.columns:
        logging.info("Column 'Q2' not found. Skipping email scrub.")
        return df
    # A fairly permissive email regex
    email_pattern = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.IGNORECASE)

    def scrub_cell(cell, idx):
        if isinstance(cell, str):
            new_cell, count = email_pattern.subn("", cell)
            if count > 0:
                logging.info(f"Row {idx}: Removed {count} email(s) from Q2.")
                # collapse extra spaces and trim
                new_cell = re.sub(r"\s{2,}", " ", new_cell).strip()
                # If the remaining text is empty, return empty string per requirement
                return new_cell
        return cell

    df["Q2"] = df.apply(lambda r: scrub_cell(r["Q2"], r.name), axis=1)
    return df


def clean_link_urls(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize Link URL and current_url (if present). Preserve originals in audit columns.
    Remove query strings and fragments, fix malformed URLs, strip nginx tokens.
    """
    if "Link URL" in df.columns and "Original Link URL" not in df.columns:
        df["Original Link URL"] = df["Link URL"]
    if "current_url" in df.columns and "Original current_url" not in df.columns:
        df["Original current_url"] = df["current_url"]

    if "Link URL" in df.columns:
        df["Link URL"] = df["Link URL"].apply(lambda u: ensure_absolute_and_normalize(u) if isinstance(u, str) else None)
        df["Link URL"] = df["Link URL"].apply(lambda u: strip_nginx_vars_from_url(u) if isinstance(u, str) else u)

    if "current_url" in df.columns:
        df["current_url"] = df["current_url"].apply(lambda u: ensure_absolute_and_normalize(u) if isinstance(u, str) else None)
        df["current_url"] = df["current_url"].apply(lambda u: strip_nginx_vars_from_url(u) if isinstance(u, str) else u)

    logging.info("URLs normalized and sanitized (removed query/fragment and nginx tokens).")
    return df


def replace_specific_old(df: pd.DataFrame) -> pd.DataFrame:
    """
    Replace the specific old path with the requested new path in Link URL.
    Log every change.
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


# --- Country-only geocoding (cached, offline default) ---------------------
def reverse_geocode_country_only(
    df: pd.DataFrame,
    cache_file: str = "geo_country_cache.json",
    round_decimals: int = 5,
) -> pd.DataFrame:
    """
    Add a 'Country' column to df using offline reverse_geocoder:
    - Deduplicate coordinates by rounding to reduce requests/lookups.
    - Use a persistent JSON cache to avoid repeat lookups across runs.
    - Offline mode uses reverse_geocoder + pycountry for fast local lookups.
    """
    if "LocationLatitude" not in df.columns or "LocationLongitude" not in df.columns:
        logging.warning("LocationLatitude or LocationLongitude not present; skipping country geocoding.")
        return df

    if rg is None or pycountry is None:
        logging.error("Offline geocoding packages not installed. Install with: pip install reverse_geocoder pycountry")
        return df

    # Load cache
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as fh:
                cache = json.load(fh)
            logging.info(f"Loaded geocode cache with {len(cache)} entries from {cache_file}")
        except Exception as e:
            logging.warning(f"Could not read cache file {cache_file}: {e}")

    def round_coord(v):
        try:
            return round(float(v), round_decimals)
        except Exception:
            return None

    coords = {}  # key -> list of row indices
    to_lookup = []
    for idx, row in df.iterrows():
        lat = row.get("LocationLatitude")
        lon = row.get("LocationLongitude")
        if pd.isna(lat) or pd.isna(lon):
            continue
        rlat = round_coord(lat)
        rlon = round_coord(lon)
        if rlat is None or rlon is None:
            continue
        key = f"{rlat},{rlon}"
        coords.setdefault(key, []).append(idx)
        if key not in cache:
            to_lookup.append(key)

    logging.info(f"Unique rounded coords: {len(coords)}; need offline lookup for {len(to_lookup)} coords")

    # Offline mode: reverse_geocoder + pycountry
    coord_list = []
    key_list = []
    for key in to_lookup:
        lat_s, lon_s = key.split(",")
        coord_list.append((float(lat_s), float(lon_s)))
        key_list.append(key)

    try:
        results = rg.search(coord_list, mode=1)
        for k, res in zip(key_list, results):
            cc = res.get("cc")
            country_name = None
            try:
                country = pycountry.countries.get(alpha_2=cc)
                country_name = country.name if country else cc
            except Exception:
                country_name = cc
            cache[k] = country_name
            logging.info(f"Cached {k} -> {country_name} (offline)")
    except Exception as e:
        logging.error(f"Offline reverse_geocoder error: {e}")

    # Persist cache
    try:
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False, indent=2)
        logging.info(f"Wrote geocode cache with {len(cache)} entries to {cache_file}")
    except Exception as e:
        logging.warning(f"Failed to write geocode cache to {cache_file}: {e}")

    # Map cache back into DataFrame (Country column only)
    country_col = []
    for idx, row in df.iterrows():
        lat = row.get("LocationLatitude")
        lon = row.get("LocationLongitude")
        if pd.isna(lat) or pd.isna(lon):
            country_col.append(None)
            continue
        rlat = round_coord(lat); rlon = round_coord(lon)
        if rlat is None or rlon is None:
            country_col.append(None)
            continue
        key = f"{rlat},{rlon}"
        country_col.append(cache.get(key))
    df["Country"] = country_col
    logging.info("Added 'Country' column from reverse geocoding results.")
    return df


# --- Main -----------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Clean up an Excel file for Tableau.")
    parser.add_argument("input_file", help="Path to the input Excel file.")
    parser.add_argument("-o", "--output", default="cleaned_data.xlsx", help="Path for the output Excel file.")
    parser.add_argument("--exclude-file", help="Path to a text file with ResponseIds to exclude (one id per line).")
    parser.add_argument(
        "--redirect-file",
        default="/Users/T.Martin/Projects/git/nginxinc/docs-nginx-conf/nginx-docs-production/etc/nginx/conf.d/azure-redirects-base",
        help="Path to nginx-style redirect file used to canonicalize Link URL values.",
    )
    # New minimal geocode flags per your request
    parser.add_argument("--geocode", action="store_true", help="Enable country-only reverse geocoding (offline). Default: disabled.")
    parser.add_argument("--geocache", default="geo_country_cache.json", help="Path to geocode cache JSON file (default: geo_country_cache.json).")
    args = parser.parse_args()

    # Load and prepare dataframe
    df = load_data(args.input_file)
    logging.info("First few rows of the DataFrame:\n" + df.head().to_string())

    # Cleaning pipeline
    df = remove_missing_link(df)
    df = remove_q2_testing(df)
    df = clean_link_urls(df)

    # Apply redirect mappings (if file exists)
    if args.redirect_file and os.path.exists(args.redirect_file):
        mappings = load_redirects_from_nginx(args.redirect_file, base_url="https://docs.nginx.com")
        if mappings:
            df = apply_redirect_mappings_in_place(df, mappings)
        else:
            logging.info("No mappings loaded from redirect file. Skipping canonicalization.")
    else:
        logging.info(f"Redirect file not provided or not found. Skipping URL canonicalization. ({args.redirect_file})")

    # Do the specific path replacement requested
    df = replace_specific_old(df)

    # Exclude bogus responses if provided
    if args.exclude_file:
        df = exclude_bogus_responses(df, args.exclude_file)
    else:
        logging.info("No exclude file provided; skipping bogus-response exclusion.")

    # Scrub emails in Q2 (PII)
    df = scrub_emails_in_q2(df)

    # Geocode if requested (offline only, as requested)
    if args.geocode:
        df = reverse_geocode_country_only(df, cache_file=args.geocache)
    else:
        logging.info("Reverse geocoding disabled (use --geocode to enable).")

    # Final output
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