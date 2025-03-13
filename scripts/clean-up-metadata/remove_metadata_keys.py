#!/usr/bin/env python3

import os
import sys
import time
import yaml
import logging

# Keys to remove completely (not renamed).
UNNEEDED_KEYS = [
    "_build",
    "aliases",
    "display_breadcrumb",
    "linkTitle",
    "menu",
    "catalog",
    "catalogType",
    "journeys",
    "tags",
    "authors",
    "date",
    "versions"
]

# The only allowed values for 'type'.
VALID_TYPE_VALUES = {
    "tutorial",
    "how-to",
    "concept",
    "reference",
    "getting-started",
    "redoc"
}

def setup_logger():
    """
    Creates a logger that writes to a timestamped file and to the console.
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

def to_list(value):
    """
    Returns a list version of the input value.
    If the value is already a list, returns it as is.
    If it's a string, returns a single-element list.
    Otherwise, returns an empty list.
    """
    if isinstance(value, list):
        return value
    elif isinstance(value, str):
        return [value]
    return []

def merge_categories_and_doctypes(front_matter_data, logger):
    """
    Merges 'categories' and 'doctypes' into a single 'type' list.
    Converts single strings to lists, merges them,
    then replaces 'task'/'tasks' with 'how-to' and 'concepts' with 'concept'.
    """
    categories_value = front_matter_data.pop("categories", None)
    doctypes_value = front_matter_data.pop("doctypes", None)

    # If neither 'categories' nor 'doctypes' is present, there's nothing to do.
    if categories_value is None and doctypes_value is None:
        return

    categories_list = to_list(categories_value)
    doctypes_list = to_list(doctypes_value)
    combined = categories_list + doctypes_list

    converted = []
    for item in combined:
        # Replace tasks with how-to
        if item in ["task", "tasks"]:
            converted.append("how-to")
        # Replace concepts with concept
        elif item == "concepts":
            converted.append("concept")
        else:
            converted.append(item)

    front_matter_data["type"] = converted

def filter_type_values(front_matter_data, logger):
    """
    Keeps only allowed values in 'type'. Removes anything else and logs what was removed.
    This also discards non-string items to avoid errors when joining.
    """
    if "type" not in front_matter_data:
        return

    # Discard anything that's not a string.
    original_type_list = [x for x in front_matter_data["type"] if isinstance(x, str)]

    # Keep only items in VALID_TYPE_VALUES.
    filtered = [x for x in original_type_list if x in VALID_TYPE_VALUES]

    # Determine which items were removed and log them.
    removed_items = set(original_type_list) - set(filtered)
    if removed_items:
        removed_items_str = ", ".join(str(item) for item in removed_items)
        logger.info(f"Filtered out invalid type values: {removed_items_str}")

    front_matter_data["type"] = filtered

def remove_unneeded_keys(front_matter_data):
    """
    Removes keys in UNNEEDED_KEYS from the front matter data.
    Returns a list of removed keys for logging.
    """
    removed = []
    for key in UNNEEDED_KEYS:
        if key in front_matter_data:
            removed.append(key)
            del front_matter_data[key]
    return removed

def process_file(filepath, logger):
    """
    Reads a file, parses its front matter, merges categories/doctypes,
    filters type values, removes unneeded keys, and writes updates if needed.
    Logs all activity.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split content based on the front matter markers.
    parts = content.split("---")
    if len(parts) < 3:
        logger.info(f"No valid front matter in {filepath}, skipping.")
        return

    before_front_matter = parts[0]
    front_matter_text = parts[1]
    after_front_matter = "---".join(parts[2:])

    # Parse the front matter as YAML.
    try:
        front_matter_data = yaml.safe_load(front_matter_text) or {}
        if not isinstance(front_matter_data, dict):
            logger.info(f"Front matter not a dictionary in {filepath}, skipping.")
            return
    except yaml.YAMLError as e:
        logger.error(f"YAML parse error in {filepath}: {e}")
        return

    # Track if categories/doctypes keys existed (for logging).
    had_categories = "categories" in front_matter_data
    had_doctypes = "doctypes" in front_matter_data

    # Merge categories/doctypes into 'type'.
    merge_categories_and_doctypes(front_matter_data, logger)

    # Filter out invalid 'type' values.
    filter_type_values(front_matter_data, logger)

    # Remove any keys we don't want.
    removed_keys = remove_unneeded_keys(front_matter_data)

    # Determine if we made changes.
    changed = bool(removed_keys or had_categories or had_doctypes)

    if changed:
        # If we removed everything, log an error but keep an empty block.
        if not front_matter_data:
            logger.error(f"All keys removed in {filepath}, keeping empty front matter block.")

        # Dump the updated YAML (with Unicode allowed).
        updated_front_matter_text = yaml.safe_dump(
            front_matter_data,
            sort_keys=False,
            allow_unicode=True
        ).strip()

        # Rebuild the file with updated front matter.
        new_content = (
            f"{before_front_matter}---\n"
            f"{updated_front_matter_text}\n"
            f"---\n"
            f"{after_front_matter}"
        )

        # Write the changes.
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)

        msgs = []
        if removed_keys:
            msgs.append(f"Removed keys: {', '.join(removed_keys)}")
        if had_categories or had_doctypes:
            msgs.append("Merged categories/doctypes into 'type'")
        logger.info(f"{filepath}: {'; '.join(msgs)}")
    else:
        logger.info(f"No changes in {filepath}")

def main():
    """
    Expects a single command-line argument for the path to the content directory.
    Walks the directory, processes each .md file, and logs progress.
    """
    if len(sys.argv) < 2:
        print("Usage: python remove_metadata_keys.py <content_directory>")
        sys.exit(1)

    content_dir = sys.argv[1]
    if not os.path.isdir(content_dir):
        print(f"{content_dir} is not a directory.")
        sys.exit(1)

    logger = setup_logger()
    logger.info(f"Starting metadata cleanup in {content_dir}")

    # Recursively walk the directory and process Markdown files.
    for root, dirs, files in os.walk(content_dir):
        for file in files:
            if file.lower().endswith(".md"):
                filepath = os.path.join(root, file)
                process_file(filepath, logger)

    logger.info("Cleanup complete.")

if __name__ == "__main__":
    main()