import os
import csv
import argparse
import logging
from datetime import datetime
import yaml

def setup_logging():
    """
    Sets up the logger to write to a timestamped log file and to the console.
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_filename = f"content_inventory_log_{timestamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_filename),  # Write logs to file
            logging.StreamHandler()             # Also write logs to console
        ]
    )
    logging.info(f"Logging started. Log file: {log_filename}")

def read_mapping(mapping_csv):
    """
    Reads a CSV file with columns like:
      filepath,url
    Each row maps a folder path under /content/... to a production URL.
    Returns a dictionary that maps the folder path to the base URL.
    """
    mapping = {}
    with open(mapping_csv, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Try to find the filepath and url columns
            filepath_key = row.get('filepath') or row.get(' filepath')
            url_key = row.get('url') or row.get(' url')

            # If either column is missing, skip the row
            if not filepath_key or not url_key:
                continue

            key = filepath_key.strip()
            url = url_key.strip().rstrip('/')
            # Store the cleaned-up values in the dictionary
            mapping[key] = url
    return mapping

def build_production_url(abs_file_path, mapping):
    """
    Creates a production URL for a file based on the mapping. Steps:
      1) Convert the path to absolute form with forward slashes.
      2) Find the portion starting at /content/.
      3) If the path is in /content/includes, return None (skip).
      4) Find a matching mapping key (for example, /content/nginx/).
      5) Remove the matched part, strip .md, and remove or adjust _index.
      6) Append leftover path parts to the mapped base URL.
      7) Return "null" if no match is found.
    """
    abs_path = os.path.abspath(abs_file_path).replace(os.sep, '/')

    # Locate "/content/" in the path
    content_idx = abs_path.find('/content/')
    if content_idx == -1:
        return "null"  # Not in the expected structure

    # Extract everything from "/content/" onward
    remainder = abs_path[content_idx:]

    # Skip if it's in "/content/includes"
    if remainder.startswith('/content/includes'):
        return None

    # Loop through mapping keys to find a matching prefix
    for mapping_key, base_url in mapping.items():
        mk = mapping_key.rstrip('/')
        if remainder.startswith(mk):
            # Remove the mapping key from the path
            leftover = remainder[len(mk):]
            leftover = leftover.lstrip('/')

            # Remove ".md" if present
            if leftover.lower().endswith('.md'):
                leftover = leftover[:-3]

            # Handle "_index" files
            if leftover == '_index':
                leftover = ''
            elif leftover.endswith('/_index'):
                leftover = leftover.rsplit('/_index', 1)[0]

            # If leftover is not empty, add a trailing slash
            if leftover:
                return f"{base_url}/{leftover}/"
            else:
                # If leftover is empty, return the base URL with a slash
                return f"{base_url}/"

    # If no mapping key matches, return "null"
    return "null"

def extract_yaml_metadata(file_path):
    """
    Reads the YAML front matter between the first two '---' lines.
    Returns a dictionary of metadata (for example, title, docs).
    If parsing fails or if the file doesn't have front matter, returns an empty dict.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if not lines or not lines[0].startswith('---'):
        return {}

    yaml_lines = []
    for line in lines[1:]:
        # Stop when we see the second '---'
        if line.startswith('---'):
            break
        yaml_lines.append(line)

    try:
        metadata = yaml.safe_load(''.join(yaml_lines))
        if not isinstance(metadata, dict):
            return {}
        return metadata
    except Exception as e:
        logging.warning(f"Error parsing YAML in file {file_path}: {e}")
        return {}

def inventory_docs(doc_path, mapping):
    """
    Recursively walks doc_path to find Markdown files. For each file:
      - Skip files under /content/includes.
      - Extract the 'docs' metadata or log 'null' if missing or blank.
      - Build a production URL from the mapping or log 'null' if not found.
      - Collect all results in a list of dictionaries, each with filename, docsID, url.
    Returns that list.
    """
    inventory = []
    # Walk the directory tree
    for root, dirs, files in os.walk(doc_path):
        for file in files:
            if file.lower().endswith('.md'):
                full_path = os.path.join(root, file)

                # Create the production URL
                prod_url = build_production_url(full_path, mapping)
                # If prod_url is None, the file is in /content/includes
                if prod_url is None:
                    logging.info(f"Skipping includes file {full_path}")
                    continue

                # Extract metadata
                metadata = extract_yaml_metadata(full_path)
                docs_id = metadata.get('docs')
                # If docs: is missing or blank, log 'null'
                if docs_id is None or str(docs_id).strip() == "":
                    docs_id = "null"

                # Use a path relative to doc_path for the CSV
                rel_path = os.path.relpath(full_path, doc_path).replace(os.sep, '/')

                # If prod_url == "null", we log it
                if prod_url == "null":
                    logging.info(f"No mapping found for file {full_path}. URL set to 'null'.")

                # Collect info in the inventory list
                inventory.append({
                    'filename': rel_path,
                    'docsID': docs_id,
                    'url': prod_url
                })
                logging.info(f"Processed {rel_path}")
    return inventory

def write_inventory_csv(inventory):
    """
    Writes the inventory list of dictionaries to a CSV file named:
      output_file_<timestamp>.csv
    with headers filename, docsID, and url.
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    output_csv = f"output_file_{timestamp}.csv"
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['filename', 'docsID', 'url'])
        writer.writeheader()
        for row in inventory:
            writer.writerow(row)
    logging.info(f"Inventory written to {output_csv}")

def main():
    """
    Parses command-line arguments:
      - doc_path: path to the Markdown docs (e.g. content/ or content/nginx/)
      - mapping_csv: CSV file mapping /content/... paths to production URLs
    Then runs the inventory process and writes the output CSV.
    """
    parser = argparse.ArgumentParser(description="Generate content inventory of NGINX docs")
    parser.add_argument('doc_path', help="Path to the markdown docs location (for example, content/ or content/nginx/)")
    parser.add_argument('mapping_csv', help="CSV file with filepath to URL mappings (for example, /content/nginx/, https://docs.nginx.com/nginx/)")
    args = parser.parse_args()

    setup_logging()
    logging.info("Reading mapping CSV")
    mapping = read_mapping(args.mapping_csv)
    logging.info("Starting inventory process")
    inventory = inventory_docs(args.doc_path, mapping)
    write_inventory_csv(inventory)
    logging.info("Done.")

if __name__ == '__main__':
    main()