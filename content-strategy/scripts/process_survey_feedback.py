# This script processes NGINX survey feedback by:
# 1. Cleaning the dataset (removing unnecessary columns and rows).
# 2. Extracting and standardizing product names based on URLs.
# 3. Extracting document names from URLs.
# 4. Saving the processed data to a new Excel file.

# How to Use:
# 1. Save this script to a file, e.g., `process_survey_feedback.py`.
# 2. Run the script with the following command:
#    python process_survey_feedback.py "/path/to/input_file.xlsx" "/path/to/output_file.xlsx"
#    - Replace `/path/to/input_file.xlsx` with the full path to the input Excel file.
#    - Replace `/path/to/output_file.xlsx` with the desired path for the output file.
# 3. The script will process the input file and save the cleaned, updated file to the specified location.

# Dependencies:
# - pandas
# - openpyxl (for reading/writing Excel files)
# Install dependencies with:
#    python -m pip install pandas openpyxl

import pandas as pd
import argparse

# Product mapping based on the provided URLs
# Maps parts of the URL to their standardized product names
PRODUCT_MAPPING = {
    "nginx-one": "NGINX One",
    "nginx": "NGINX Plus",
    "nginx-instance-manager": "NGINX Instance Manager",
    "nginx-ingress-controller": "NGINX Ingress Controller",
    "nginx-gateway-fabric": "NGINX Gateway Fabric",
    "nginx-agent": "NGINX Agent",
    "solutions": "Subscription Licensing & Solutions",
    "nginx-app-protect-waf": "NGINX App Protect WAF",
    "nginx-app-protect-dos": "NGINX App Protect DoS",
    "nginxaas/azure": "NGINX as a Service for Azure",
    "nginx-amplify": "NGINX Amplify",
}

def extract_product(url):
    # Extracts the product name from the URL and maps it to a standardized product name.
    if pd.isna(url):
        return None
    parts = url.split('/')
    if len(parts) > 3:
        key = parts[3] if parts[3] != "nginxaas" else "nginxaas/azure"
        return PRODUCT_MAPPING.get(key, parts[3].replace('-', ' ').title())
    return None

def extract_doc(url):
    # Extracts the document name from the URL.
    if pd.isna(url):
        return None
    main_url = url.split('#')[0].rstrip('/')
    doc = main_url.split('/')[-1] if main_url else None
    return doc.replace('-', ' ').capitalize() if doc else None

def process_nginx_feedback(input_file, output_file):
    # Processes the NGINX feedback data by cleaning the dataset,
    # extracting product and document names, and saving the updated file.

    # Load the dataset
    df = pd.ExcelFile(input_file).parse(0)

    # Step 1: Data cleaning - Delete unnecessary columns and rows
    columns_to_delete = [
        "Status", "Progress", "Duration (in seconds)", "Finished",
        "RecipientFirstName", "RecipientEmail", "ExternalReference", 
        "DistributionChannel", "UserLanguage", "Link URL", 
        "Q2 - Actionability", "Q2 - Effort", "Q2 - Effort Numeric",
        "Q2 - Emotion Intensity", "Q2 - Emotion", "Q2 - Parent Topics", 
        "Q2 - Sentiment Polarity", "Q2 - Sentiment Score", "Q2 - Sentiment",
        "Q2 - Topic Sentiment Label", "Q2 - Topic Sentiment Score",
        "Q2 - Topics", "Q2 - Topic Hierarchy Level 1"
    ]
    df = df.drop(columns=columns_to_delete, errors='ignore')  # Remove specified columns
    df = df.iloc[53:]  # Remove rows 1-53 (0-based index)

    # Step 2: Extract product and document names based on the 'current_url' column
    df["Product"] = df["current_url"].apply(extract_product)
    df["Document"] = df["current_url"].apply(extract_doc)
    
    # Step 3: Save the cleaned and updated dataset
    df.to_excel(output_file, index=False)

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Process NGINX survey feedback.")
    parser.add_argument("input_file", help="Path to the input Excel file (e.g., '/path/to/input.xlsx').")
    parser.add_argument("output_file", help="Path to save the processed Excel file (e.g., '/path/to/output.xlsx').")

    args = parser.parse_args()

    # Process the feedback data using the provided file paths
    process_nginx_feedback(args.input_file, args.output_file)