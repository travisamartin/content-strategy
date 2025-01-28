import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd
import time

# List of file extensions to exclude (images, YAML, JS, etc.)
EXCLUDED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", 
                        ".json", ".yaml", ".yml", ".pdf", ".zip", ".mp4", ".woff", ".ttf")

def normalize_url(url):
    # Removes the trailing slash from URLs to keep them consistent
    return url.rstrip('/')

def is_valid_webpage(url):
    # Checks if the URL is a webpage (not an image, YAML, or other excluded asset)
    parsed = urlparse(url)

    # Allow URLs that have no file extension or end with "/" (indicating a webpage)
    if parsed.path.endswith("/") or "." not in parsed.path:
        return True

    # Exclude known non-webpage file types
    return not parsed.path.endswith(EXCLUDED_EXTENSIONS)

def is_valid_subpath(base_url, candidate_url):
    # Ensures the candidate URL is a strict subpath of base_url without matching similar prefixes
    base_parsed = urlparse(base_url)
    candidate_parsed = urlparse(candidate_url)

    # Ensure the candidate URL is within the same domain
    if candidate_parsed.netloc != base_parsed.netloc:
        return False  # Skip external links

    # Ensure it's a strict subpath of base_url
    return candidate_parsed.path.startswith(base_parsed.path.rstrip('/') + '/')

def get_pages(base_url):
    # Recursively fetches all unique URLs under the given base URL

    visited = set()  # Tracks visited URLs to prevent duplicate processing
    to_visit = {normalize_url(base_url)}  # Queue of URLs to process
    found_links = set()  # Stores all discovered valid documentation pages

    while to_visit:
        current_url = to_visit.pop()
        if current_url in visited:
            continue

        print(f"🔍 Visiting: {current_url}")  # Show the URL being visited

        try:
            response = requests.get(current_url, timeout=10)

            # Skip 404 pages and avoid processing broken links
            if response.status_code == 404:
                print(f"❌ Skipping (404 Not Found): {current_url}")
                continue

            response.raise_for_status()  # Raise an error for non-200 responses
            visited.add(current_url)

            # Parse the HTML content to extract links
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a', href=True)

            for link in links:
                absolute_url = urljoin(current_url, link['href'])
                normalized_url = normalize_url(absolute_url)

                # Ensure the link is valid, part of the base URL, and is a webpage
                if is_valid_subpath(base_url, normalized_url) and is_valid_webpage(normalized_url) and '#' not in normalized_url:
                    if normalized_url not in visited:
                        to_visit.add(normalized_url)
                    if normalized_url != base_url:
                        found_links.add(normalized_url)

            # Add a short delay to avoid overwhelming the server
            time.sleep(1)

        except Exception as e:
            print(f"⚠️ Skipping {current_url} due to error: {e}")

    return sorted(found_links)

def scrape_and_save_to_excel(csv_path, output_excel_path):
    # Reads a CSV file, scrapes each doc set, and saves results in an Excel file

    df = pd.read_csv(csv_path)

    # Rename columns to match expected input format
    df = df.rename(columns={"Title": "Doc Set Name", "URL": "Base URL"})

    doc_set_results = {}  # Dictionary to store results for each doc set

    for _, row in df.iterrows():
        doc_set_name = row["Doc Set Name"]
        base_url = row["Base URL"]

        print(f"\n🚀 Scraping doc set: **{doc_set_name}** ({base_url})...\n")

        # Fetch all valid URLs for this doc set
        pages = get_pages(base_url)
        doc_set_results[doc_set_name] = pd.DataFrame({"URLs": pages})

        print(f"\n✅ Completed scraping {doc_set_name}. Found {len(pages)} pages.\n" + "-" * 80)

    # Save results to an Excel file with each doc set as a tab
    with pd.ExcelWriter(output_excel_path) as writer:
        for doc_set, urls_df in doc_set_results.items():
            sheet_name = doc_set[:31]  # Excel sheet names must be <= 31 characters
            urls_df.to_excel(writer, sheet_name=sheet_name, index=False)

    print(f"\n📄 Saved results to: {output_excel_path}")

# Example usage
csv_path = "doc-set-base-links.csv"  # CSV file containing doc sets and their base URLs
output_excel_path = "nginx_doc_inventory.xlsx"  # Output Excel file

scrape_and_save_to_excel(csv_path, output_excel_path)