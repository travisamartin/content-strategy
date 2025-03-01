import pandas as pd
import re
import logging
import argparse

# set up logging to file and screen
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
    raw = pd.read_excel(file_path, header=None)
    logging.info("File read successfully.")
    logging.info(f"Initial shape (rows x columns): {raw.shape}")

    # The first row becomes the column header
    header = list(raw.iloc[0])
    raw = raw.iloc[1:].reset_index(drop=True)

    # Check if the new first row is a duplicate header or subheading
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
    new_url = url.split('#')[0]
    if not new_url.endswith('/'):
        new_url += '/'
    return new_url

def update_urls(data):
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

def main():
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

    # Rename the worksheet to "Survey Data"
    df.to_excel(args.output, sheet_name="Survey Data", index=False)
    logging.info(f"Cleaned data written to {args.output}")
    print(f"Cleaned data written to {args.output}")
    logging.info("Script completed successfully.")
    print("Script completed successfully.")

if __name__ == '__main__':
    main()