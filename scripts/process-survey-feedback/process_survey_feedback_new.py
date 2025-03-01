"""
process_survey_feedback_new.py

Cleans and transforms an Excel file for use in Tableau. This script:
- Removes a duplicate or subheading row if found.
- Removes rows where 'Link URL' is missing.
- Removes rows where the 'Q2' column contains the word 'testing'.
- Cleans the 'Link URL' column by removing anchors (#) and adding a trailing slash.
- Reverse-geocodes latitude/longitude into Country, City, and State columns.
- Respects the Nominatim rate limit of about 1 request per second.

Usage:
  python process_survey_feedback_new.py <path_to_input_file> -o <path_to_output_file>

Example:
  python process_survey_feedback_new.py "input.xlsx" -o "cleaned_data.xlsx"
"""

import pandas as pd
import re
import logging
import argparse
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# Configure logging to write to a file and show on the screen
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

    # The first row becomes the column header
    header = list(raw.iloc[0])
    # Remove that row from the dataset
    raw = raw.iloc[1:].reset_index(drop=True)

    # Check if the new first row is a duplicate header or a known subheading
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
    Applies 'clean_url' to each value in the 'Link URL' column.
    Logs each change.
    """
    if 'Link URL' not in data.columns:
        logging.error("Column 'Link URL' not found in the data. No URL updates performed.")
        return data
    
    updated_count = 0

    def update(row):
        nonlocal updated_count
        old = row['Link URL']
        new = clean_url(old)
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

    # Create a geolocator and a rate-limited wrapper
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

    # Assign new columns for Country, City, and State
    data[['Country', 'City', 'State']] = data.apply(reverse_geocode_row, axis=1)
    logging.info("Created columns 'Country', 'City', and 'State' with reverse geocoded data.")
    return data

def main():
    """
    Orchestrates the full cleanup and geocoding process:
      1. Load data and fix headers.
      2. Remove rows without 'Link URL'.
      3. Remove rows with 'testing' in Q2.
      4. Clean 'Link URL' values.
      5. Reverse-geocode lat/long into Country, City, State.
      6. Write the final DataFrame to an Excel file.
    """
    parser = argparse.ArgumentParser(description="Clean up an Excel file for Tableau.")
    parser.add_argument("input_file", help="Path to the input Excel file.")
    parser.add_argument(
        "-o", 
        "--output", 
        default="cleaned_data.xlsx",
        help="Path for the output Excel file (default: cleaned_data.xlsx)"
    )
    args = parser.parse_args()
    
    df = load_data(args.input_file)
    print("First few rows of the DataFrame:")
    print(df.head())

    df = remove_missing_link(df)
    df = remove_q2_testing(df)
    df = update_urls(df)
    df = reverse_geocode_locations(df)

    df.to_excel(args.output, sheet_name="Survey Data", index=False)
    logging.info(f"Cleaned data written to {args.output}")
    print(f"Cleaned data written to {args.output}")
    logging.info("Script completed successfully.")
    print("Script completed successfully.")

if __name__ == '__main__':
    main()