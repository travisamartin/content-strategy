import os
import csv
import argparse
import logging
from datetime import datetime
import yaml

# We import the function to build production URLs from a separate file.
from url_utils import build_production_url

def setup_logging():
    """
    Sets up a logger to write messages to a timestamped file and to the console.
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    log_filename = f"content_inventory_log_{timestamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_filename),  # Sends logs to a file
            logging.StreamHandler()             # Sends logs to the console
        ]
    )
    logging.info(f"Logging started. Log file: {log_filename}")

def read_mapping(mapping_csv):
    """
    Reads a CSV file that maps a path under /content/... to a base production URL.
    For example:
      /content/nginx/, https://docs.nginx.com/nginx
    Returns a dictionary that holds these mappings.
    """
    mapping = {}
    with open(mapping_csv, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Extract the filepath and url columns
            filepath_key = row.get('filepath') or row.get(' filepath')
            url_key = row.get('url') or row.get(' url')
            if not filepath_key or not url_key:
                # Skip rows that do not have the required columns
                continue

            # Clean up spacing and trailing slashes
            key = filepath_key.strip()
            url = url_key.strip().rstrip('/')
            mapping[key] = url
    return mapping

def extract_yaml_metadata(file_path):
    """
    Reads YAML front matter from the file.
    It looks for text between the first and second '---' lines.
    Returns a dictionary with metadata, or an empty one if not found.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # If the file does not start with '---', it probably does not have front matter
    if not lines or not lines[0].startswith('---'):
        return {}

    yaml_lines = []
    # Collect lines until we reach the second '---'
    for line in lines[1:]:
        if line.startswith('---'):
            break
        yaml_lines.append(line)

    try:
        # Parse the YAML content
        metadata = yaml.safe_load(''.join(yaml_lines))
        # If the content is not a dictionary, return an empty one
        if not isinstance(metadata, dict):
            return {}
        return metadata
    except Exception as e:
        logging.warning(f"Error parsing YAML in file {file_path}: {e}")
        return {}

def inventory_docs(doc_path, mapping):
    """
    Walks through all markdown files in doc_path.
    For each file:
      - Skips includes if build_production_url returns None
      - Extracts 'docs' from YAML front matter, or logs 'null' if missing or blank
      - Builds a production URL or logs 'null' if no mapping applies
      - Records the results in a list of dictionaries
    Returns that list for further processing.
    """
    inventory = []
    # Recursively walk the doc_path directory
    for root, dirs, files in os.walk(doc_path):
        for file in files:
            if file.lower().endswith('.md'):
                full_path = os.path.join(root, file)

                # Use the build_production_url function from url_utils
                prod_url = build_production_url(full_path, mapping)
                if prod_url is None:
                    # This means it is in /content/includes
                    logging.info(f"Skipping includes file {full_path}")
                    continue

                # Read metadata to find the docs ID
                metadata = extract_yaml_metadata(full_path)
                docs_id = metadata.get('docs')
                if docs_id is None or str(docs_id).strip() == "":
                    docs_id = "null"

                # Build a path relative to doc_path
                rel_path = os.path.relpath(full_path, doc_path).replace(os.sep, '/')

                # Log if the mapping was not found
                if prod_url == "null":
                    logging.info(f"No mapping found for file {full_path}. URL set to 'null'.")

                # Collect the data
                inventory.append({
                    'filename': rel_path,
                    'docsID': docs_id,
                    'url': prod_url
                })
                logging.info(f"Processed {rel_path}")
    return inventory

def write_inventory_csv(inventory):
    """
    Writes the collected data to a CSV file with a timestamp in its name.
    The file has columns: filename, docsID, and url.
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
    Runs the script.
    - doc_path: folder with markdown files (for example, content/ or content/nginx/)
    - mapping_csv: CSV with lines like /content/nginx/, https://docs.nginx.com/nginx
    """
    parser = argparse.ArgumentParser(description="Generate content inventory of NGINX docs")
    parser.add_argument('doc_path', help="Path to the markdown docs location (for example, content/ or content/nginx/)")
    parser.add_argument('mapping_csv', help="CSV file with filepath to URL mappings (for example, /content/nginx/, https://docs.nginx.com/nginx/)")
    args = parser.parse_args()

    # Set up logging to file and console
    setup_logging()

    # Read the folder-to-URL mapping
    logging.info("Reading mapping CSV")
    mapping = read_mapping(args.mapping_csv)

    # Walk the docs folder and build an inventory
    logging.info("Starting inventory process")
    inventory = inventory_docs(args.doc_path, mapping)

    # Write the inventory to a timestamped CSV file
    write_inventory_csv(inventory)
    logging.info("Done.")

if __name__ == '__main__':
    main()