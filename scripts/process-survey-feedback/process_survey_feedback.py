"""
process_survey_feedback_new.py

Cleans and transforms an Excel file for use in Tableau. This script:
- Removes a duplicate or subheading row if found.
- Removes rows where 'Link URL' is missing.
- Removes rows where the 'Q2' column contains the word 'testing'.
- Excludes bogus responses based on a provided exclude file of ResponseIDs.
- Scrubs email addresses from the 'Q2' column (replacing them with an empty string).
- Cleans the 'Link URL' column by removing anchors (#), ensuring a trailing slash,
  and replacing the old URL for known issues.
- Optionally, reverse-geocodes latitude/longitude into Country, City, and State columns,
  if the --geocode flag is provided (default is disabled). The geocoding respects
  Nominatim's rate limit (1 request per second).
- Writes the cleaned data to an Excel file with a worksheet named "Survey Data".

Usage:
  python process_survey_feedback_new.py <path_to_input_file> -o <path_to_output_file> [--exclude-file <path_to_exclude_file>] [--geocode]

Example:
  python process_survey_feedback_new.py "input.xlsx" -o "cleaned_data.xlsx" --exclude-file "excluded-responses.txt" --geocode
"""

import pandas as pd
import re
import logging
import argparse
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Configure logging to write to a file and show on the screen.
logging.basicConfig(
    filename='cleanup_log.txt',
    level=logging.INFO,
    format='%(asctime)s: %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s: %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

def load_data(file_path):
    """
    Reads the Excel file with no header, then:
      1. Uses the first row as column headers.
      2. Checks if the second row is a duplicate header or subheading, and removes it.
      3. Logs each step.
    Returns a pandas DataFrame.
    """
    raw = pd.read_excel(file_path, header=None)
    logging.info("File read successfully.")
    logging.info(f"Initial shape (rows x columns): {raw.shape}")

    # The first row becomes the column header.
    header = list(raw.iloc[0])
    # Remove that row from the dataset.
    raw = raw.iloc[1:].reset_index(drop=True)

    # Check if the new first row is a duplicate header or a known subheading.
    first_data_row = list(raw.iloc[0])
    if first_data_row == header:
        logging.info("Second header row detected and removed.")
        raw = raw.iloc[1:].reset_index(drop=True)
    elif "Any suggestions for improvement?" in raw.iloc[0].values:
        logging.info("Subheading row detected and removed.")
        raw = raw.iloc[1:].reset_index(drop=True)

    data = pd.DataFrame(raw.values, columns=header)
    logging.info(f"Dataframe shape after header adjustments: {data.shape}")
    logging.info(f"Columns found: {list(data.columns)}")
    return data

def remove_missing_link(data):
    """
    Removes rows where the 'Link URL' column is missing.
    Logs which rows were removed.
    """
    if 'Link URL' not in data.columns:
        logging.error("Column 'Link URL' not found in the data. No rows will be dropped.")
        return data

    before_count = data.shape[0]
    missing_mask = data['Link URL'].isnull()
    if missing_mask.any():
        for idx in data[missing_mask].index:
            logging.info(f"Row {idx} deleted because Link URL is missing.")
        data = data.dropna(subset=['Link URL'])
    after_count = data.shape[0]
    logging.info(f"Rows before removing missing Link URL: {before_count}, after: {after_count}")
    return data

def remove_q2_testing(data):
    """
    Removes rows where the 'Q2' column contains the word 'testing' (ignoring case).
    Logs which rows were removed.
    """
    before_count = data.shape[0]

    def contains_testing(value):
        if isinstance(value, str):
            return bool(re.search(r'testing', value, re.IGNORECASE))
        return False

    mask = data['Q2'].apply(contains_testing)
    if mask.any():
        for idx in data[mask].index:
            logging.info(f"Row {idx} deleted because Q2 contains 'testing'.")
        data = data[~mask]

    after_count = data.shape[0]
    logging.info(f"Rows before removing Q2='testing': {before_count}, after: {after_count}")
    return data

def exclude_bogus_responses(data, exclude_file):
    """
    Reads the exclude file (a plain text file with one ResponseID per line) and
    removes rows from the DataFrame where the ResponseID (from the 'ResponseId' column)
    matches any entry in the file.
    Both the ResponseId values from the data and the exclude file are converted to uppercase.
    Logs the ResponseIDs that were removed.
    """
    try:
        with open(exclude_file, "r", encoding="utf-8") as f:
            # Read each line, strip whitespace/newlines, and convert to uppercase.
            exclude_ids = {line.strip().upper() for line in f if line.strip()}
        logging.info(f"Exclude file loaded. Excluding {len(exclude_ids)} ResponseIDs.")
    except Exception as e:
        logging.error(f"Error reading exclude file '{exclude_file}': {e}")
        return data

    if 'ResponseId' not in data.columns:
        logging.error("Column 'ResponseId' not found in the data. Cannot exclude bogus responses.")
        return data

    # Convert the ResponseId column to uppercase strings with no extra whitespace.
    data['ResponseId'] = data['ResponseId'].astype(str).str.strip().str.upper()
    # Capture the list of ResponseIds that are going to be removed.
    to_exclude = data[data['ResponseId'].isin(exclude_ids)]
    removed_ids = sorted(to_exclude['ResponseId'].unique())
    
    before_count = data.shape[0]
    # Exclude rows whose ResponseId is in the exclude_ids set.
    data = data[~data['ResponseId'].isin(exclude_ids)]
    after_count = data.shape[0]
    logging.info(f"Excluded bogus responses: removed {before_count - after_count} rows based on ResponseId.")
    logging.info(f"Removed ResponseIDs: {removed_ids}")
    return data

def scrub_emails_in_q2(data):
    """
    Scans the 'Q2' column for email addresses and replaces them with an empty string.
    Logs each row that was modified.
    """
    email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    def scrub(cell, idx):
        if isinstance(cell, str):
            new_cell, count = email_pattern.subn("", cell)
            if count > 0:
                logging.info(f"Row {idx}: Found and removed {count} email(s) from Q2.")
                return new_cell
        return cell
    
    data['Q2'] = data.apply(lambda row: scrub(row['Q2'], row.name), axis=1)
    return data

def clean_url(url):
    """
    Cleans a single URL by removing everything after '#' and ensuring a trailing slash.
    """
    new_url = url.split('#')[0]
    if not new_url.endswith('/'):
        new_url += '/'
    return new_url

def update_urls(data):
    """
    1. Cleans 'Link URL' by removing anchor fragments and ensuring a trailing slash.
    2. Replaces 'https://docs.nginx.com/nginxaas-azure/known-issues/' with
       'https://docs.nginx.com/nginxaas/azure/known-issues/'.
    3. Logs each change, including the special replacement.
    """
    if 'Link URL' not in data.columns:
        logging.error("Column 'Link URL' not found in the data. No URL updates performed.")
        return data

    updated_count = 0

    def update(row):
        nonlocal updated_count
        old = row['Link URL']
        
        # Step 1: Clean URL (remove anchors, add trailing slash)
        new = clean_url(old)

        # Step 2: Replace the old URL pattern with the new one.
        if "https://docs.nginx.com/nginxaas-azure/known-issues/" in new:
            replaced = new.replace(
                "https://docs.nginx.com/nginxaas-azure/known-issues/",
                "https://docs.nginx.com/nginxaas/azure/known-issues/"
            )
            if replaced != new:
                updated_count += 1
                logging.info(f"Row {row.name}: Link URL updated from {new} to {replaced} (URL replacement)")
                print(f"Row {row.name}: Link URL updated from {new} to {replaced} (URL replacement)")
            new = replaced

        # Log if the final URL differs from the original.
        if new != old:
            updated_count += 1
            logging.info(f"Row {row.name}: Link URL updated from {old} to {new}")

        return new

    data['Link URL'] = data.apply(update, axis=1)
    logging.info(f"Total Link URLs updated: {updated_count}")
    return data

def reverse_geocode_locations(data):
    """
    Reverse-geocodes latitude/longitude to Country, City, and State columns (in US English).
    Respects Nominatim's rate limit of about 1 request per second.
    Logs each geocoding step.
    """
    if 'LocationLatitude' not in data.columns or 'LocationLongitude' not in data.columns:
        logging.warning("LocationLatitude or LocationLongitude not found. Skipping reverse geocoding.")
        return data

    # Create a geolocator and a rate-limited wrapper.
    geolocator = Nominatim(user_agent="my_reverse_geocoder")
    reverse = RateLimiter(geolocator.reverse, min_delay_seconds=1)  # 1 request per second

    def reverse_geocode_row(row):
        lat = row['LocationLatitude']
        lon = row['LocationLongitude']
        if pd.notnull(lat) and pd.notnull(lon):
            try:
                location = reverse((lat, lon), language="en-US")
                if location and location.raw and 'address' in location.raw:
                    address = location.raw['address']
                    country = address.get('country')
                    city = address.get('city') or address.get('town') or address.get('village')
                    state = address.get('state')
                    logging.info(f"Row {row.name}: Reverse geocoded lat={lat}, lon={lon} -> "
                                 f"country={country}, city={city}, state={state}")
                    return pd.Series([country, city, state])
                else:
                    logging.warning(f"Row {row.name}: No address found for lat={lat}, lon={lon}")
                    return pd.Series([None, None, None])
            except Exception as e:
                logging.warning(f"Row {row.name}: Error reverse geocoding lat={lat}, lon={lon}: {e}")
                return pd.Series([None, None, None])
        else:
            logging.info(f"Row {row.name}: lat or lon is null, skipping reverse geocoding.")
            return pd.Series([None, None, None])

    # Assign new columns for Country, City, and State.
    data[['Country', 'City', 'State']] = data.apply(reverse_geocode_row, axis=1)
    logging.info("Created columns 'Country', 'City', and 'State' with reverse geocoded data.")
    return data

def main():
    """
    Orchestrates the full cleanup process:
      1. Load data and fix headers.
      2. Remove rows without 'Link URL'.
      3. Remove rows with 'testing' in Q2.
      4. Exclude bogus responses based on ResponseId.
      5. Clean 'Link URL' values, including the special replacement.
      6. Scrub email addresses from the 'Q2' column.
      7. Optionally, reverse-geocode lat/long into Country, City, State (if --geocode flag is provided).
      8. Write the final DataFrame to an Excel file with the sheet name "Survey Data".
    """
    parser = argparse.ArgumentParser(description="Clean up an Excel file for Tableau.")
    parser.add_argument("input_file", help="Path to the input Excel file.")
    parser.add_argument(
        "-o",
        "--output",
        default="cleaned_data.xlsx",
        help="Path for the output Excel file (default: cleaned_data.xlsx)"
    )
    parser.add_argument(
        "--exclude-file",
        help="Path to a text file with ResponseIds to exclude (one per line)."
    )
    parser.add_argument(
        "--geocode",
        action="store_true",
        help="Enable reverse geocoding of latitude/longitude into Country, City, and State columns."
    )
    args = parser.parse_args()

    df = load_data(args.input_file)
    print("First few rows of the DataFrame:")
    print(df.head())

    df = remove_missing_link(df)
    df = remove_q2_testing(df)
    df = update_urls(df)

    # Exclude bogus responses if an exclude file is provided.
    if args.exclude_file:
        df = exclude_bogus_responses(df, args.exclude_file)

    # Scrub email addresses from Q2.
    df = scrub_emails_in_q2(df)

    # Optionally perform reverse geocoding if the flag is enabled.
    if args.geocode:
        df = reverse_geocode_locations(df)
    else:
        logging.info("Reverse geocoding disabled (use --geocode to enable).")

    df.to_excel(args.output, sheet_name="Survey Data", index=False)
    logging.info(f"Cleaned data written to {args.output}")
    print(f"Cleaned data written to {args.output}")
    logging.info("Script completed successfully.")
    print("Script completed successfully.")

if __name__ == '__main__':
    main()