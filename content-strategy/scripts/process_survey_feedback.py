# This script processes NGINX feedback dataset by cleaning the data
# and extracting product and document information from URLs.
#
# Steps to use:
# 1. Save this script to a `.py` file, e.g., `process_feedback.py`.
# 2. Replace `path_to_exported_file.xlsx` with the path to your exported dataset.
# 3. Replace `path_to_updated_file.xlsx` with the desired output path for the updated file.
# 4. Run the script using Python:
#    python process_feedback.py
# 5. The script will clean the data, extract product and document information,
#    and save the updated file.

import pandas as pd

def extract_product(url):
    # Extract the product name from the URL.
    if pd.isna(url):
        return None
    parts = url.split('/')
    if len(parts) > 3:
        return parts[3].replace('-', ' ').title()
    return None

def extract_doc(url):
    # Extract the document name from the URL.
    if pd.isna(url):
        return None
    # Handle URL fragments and trailing slashes
    main_url = url.split('#')[0].rstrip('/')
    doc = main_url.split('/')[-1] if main_url else None
    return doc.replace('-', ' ').capitalize() if doc else None

def process_nginx_feedback(input_file, output_file):
    # Load the dataset
    df = pd.ExcelFile(input_file).parse(0)
    
    # Step 1: Data cleaning - Delete specified columns and rows
    columns_to_delete = [
        "Status",
        "Progress",
        "Duration (in seconds)",
        "Finished",
        "RecipientFirstName",
        "RecipientEmail",
        "ExternalReference",
        "DistributionChannel",
        "UserLanguage",
        "Link URL",
        "Q2 - Actionability",
        "Q2 - Effort",
        "Q2 - Effort Numeric",
        "Q2 - Emotion Intensity",
        "Q2 - Emotion",
        "Q2 - Parent Topics",
        "Q2 - Sentiment Polarity",
        "Q2 - Sentiment Score",
        "Q2 - Sentiment",
        "Q2 - Topic Sentiment Label",
        "Q2 - Topic Sentiment Score",
        "Q2 - Topics",
        "Q2 - Topic Hierarchy Level 1"
    ]
    df = df.drop(columns=columns_to_delete, errors='ignore')
    df = df.iloc[53:]  # Delete rows 1-53 (0-based index)

    # Step 2: Extract product and document names based on `current_url` column
    df["Product"] = df["current_url"].apply(extract_product)
    df["Document"] = df["current_url"].apply(extract_doc)
    
    # Step 3: Save the updated DataFrame
    df.to_excel(output_file, index=False)

# File paths
input_file = 'path_to_exported_file.xlsx'  # Replace with your file path
output_file = 'path_to_updated_file.xlsx'  # Replace with desired output path

# Run the script
process_nginx_feedback(input_file, output_file)