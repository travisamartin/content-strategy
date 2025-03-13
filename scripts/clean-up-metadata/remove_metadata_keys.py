#!/usr/bin/env python3

import os
import sys
import time
import yaml
import logging

# These are the metadata keys we remove from each file's front matter.
UNNEEDED_KEYS = [
    "_build",
    "aliases",
    "display_breadcrumb",
    "linkTitle",
    "menu",
    "categories",
    "catalog",
    "catalogType",
    "doctypes",
    "journeys",
    "tags",
    "authors",
    "date",
    "versions"
]

def setup_logger():
    """
    Creates a logger that writes to a file and to the console.
    Names the log file with a timestamp so it's easy to track each run.
    """
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_filename = f"metadata_cleanup_{timestamp}.log"

    logging.basicConfig(
        filename=log_filename,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(console_formatter)
    logging.getLogger().addHandler(console_handler)

    return logging.getLogger()

def remove_keys_from_front_matter(front_matter_data):
    """
    Removes unneeded keys from the parsed YAML dictionary.
    Returns a list of keys actually removed.
    """
    removed_keys = []
    for key in UNNEEDED_KEYS:
        if key in front_matter_data:
            removed_keys.append(key)
            del front_matter_data[key]
    return removed_keys

def process_file(filepath, logger):
    """
    Reads a file, locates its front matter, removes unneeded keys,
    and writes changes if needed. Logs each step.
    """
    # Read the entire file.
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split on the first two '---' markers to find the front matter section.
    parts = content.split("---")
    if len(parts) < 3:
        # No or malformed front matter, so we won't alter this file.
        logger.info(f"No valid front matter in {filepath}, skipping.")
        return

    # The first part is everything before the front matter.
    before_front_matter = parts[0]
    # The second part is the front matter.
    front_matter_text = parts[1]
    # The remainder is everything after the front matter.
    after_front_matter = "---".join(parts[2:])

    # Parse the front matter as YAML.
    try:
        front_matter_data = yaml.safe_load(front_matter_text)
        # If it's not a dictionary, it's not valid.
        if not isinstance(front_matter_data, dict):
            logger.info(f"Front matter not a dictionary in {filepath}, skipping.")
            return
    except yaml.YAMLError as e:
        # Log and skip if the front matter isn't valid YAML.
        logger.error(f"YAML parse error in {filepath}: {e}")
        return

    # Remove the unneeded keys from the front matter.
    removed_keys = remove_keys_from_front_matter(front_matter_data)

    # If we removed any keys, rewrite the file.
    if removed_keys:
        # If the front matter is now empty, log an error but keep the block.
        if not front_matter_data:
            logger.error(f"All keys removed in {filepath}, keeping empty front matter block.")

        # Re-dump the YAML with safe_dump. This also removes empty structures.
        updated_front_matter_text = yaml.safe_dump(front_matter_data, sort_keys=False).strip()

        # Construct the updated file content.
        new_content = (
            f"{before_front_matter}---\n"
            f"{updated_front_matter_text}\n"
            f"---\n"
            f"{after_front_matter}"
        )

        # Overwrite the file with the changes.
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Log which keys were removed.
        removed_keys_list = ", ".join(removed_keys)
        logger.info(f"Removed keys [{removed_keys_list}] from {filepath}")

def main():
    """
    Collects the target directory from the command line and
    processes each .md file inside it.
    """
    if len(sys.argv) < 2:
        print("Run this script with:")
        print("python remove_metadata_keys.py <content_directory>")
        sys.exit(1)

    content_dir = sys.argv[1]
    if not os.path.isdir(content_dir):
        print(f"{content_dir} is not a directory.")
        sys.exit(1)

    # Create the logger to record all changes and errors.
    logger = setup_logger()
    logger.info(f"Starting metadata clean up in {content_dir}")

    # Recursively walk the directory to find Markdown files.
    for root, dirs, files in os.walk(content_dir):
        for file in files:
            if file.lower().endswith(".md"):
                filepath = os.path.join(root, file)
                process_file(filepath, logger)

    logger.info("Clean up complete.")

if __name__ == "__main__":
    main()