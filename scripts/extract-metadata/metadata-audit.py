#!/usr/bin/env python3

import sys
import os
import yaml
import pandas as pd
from datetime import datetime

def remove_timezone(dt_value):
    """
    Return dt_value with no time zone information.
    """
    if isinstance(dt_value, datetime) and dt_value.tzinfo is not None:
        return dt_value.replace(tzinfo=None)
    return dt_value

def build_repo_content_path(file_path, content_dir):
    """
    Construct a path of the form /<repoName>/<contentDir>... that
    starts at the parent repo name, then the content directory name,
    then any subfolders or files under that path.
    """
    # Convert content_dir to an absolute path
    content_dir_abs = os.path.abspath(content_dir)

    # Determine the repo name from the folder that contains content_dir
    repo_name = os.path.basename(os.path.dirname(content_dir_abs))

    # Determine the content folder name (often 'content')
    content_folder = os.path.basename(content_dir_abs)

    # Build something like "/docs/content" or "/documentation/content"
    prefix = f"/{repo_name}/{content_folder}"

    # Compute a relative path from content_dir to the file
    rel_path = os.path.relpath(file_path, content_dir_abs)

    # Combine the prefix with the relative path
    joined = os.path.join(prefix, rel_path)

    # Replace backslashes with forward slashes (for Windows compatibility)
    return joined.replace("\\", "/")

def parse_frontmatter(file_path, content_dir):
    """
    Open the file, check if front matter exists, parse it, 
    rename 'title' to 'Title', and remove time zone info from date fields.
    """
    # Build the dynamic path string for the "file" field
    final_path = build_repo_content_path(file_path, content_dir)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        # If the file doesn't start with '---', there's no front matter
        if not raw_content.startswith('---'):
            return {"file": final_path, "No metadata found": True}

        # Split on '---'; we expect at least 3 parts (start, front matter, rest)
        parts = raw_content.split('---', 2)
        if len(parts) < 3:
            return {"file": final_path, "Error in frontmatter": True}

        frontmatter_str = parts[1]
        try:
            # Use YAML to parse the front matter
            data = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            # If parsing fails, return an error
            return {"file": final_path, "Error in frontmatter": True}

        # If the front matter is empty, note that there's no metadata
        if not data:
            return {"file": final_path, "No metadata found": True}

        # Rename 'title' to 'Title' and remove any time zone info
        for key, value in list(data.items()):
            if key.lower() == 'title':
                data['Title'] = remove_timezone(value)
                del data[key]
            else:
                data[key] = remove_timezone(value)

        # Store the final file path in the data dictionary
        data["file"] = final_path
        return data

    except Exception as e:
        # If something unexpected happens while reading the file
        return {"file": final_path, "Error in frontmatter": str(e)}

def main():
    """
    Main entry point: scan the given content directory for Markdown files,
    parse front matter, create a spreadsheet, and print a summary.
    """
    if len(sys.argv) < 2:
        print("Usage: python3 metadata-audit.py /path/to/<repo>/content/")
        sys.exit(1)

    content_dir = sys.argv[1]
    all_metadata = []

    # Walk through the content directory and find .md files
    for root, _, files in os.walk(content_dir):
        for filename in files:
            if filename.lower().endswith('.md'):
                file_path = os.path.join(root, filename)
                frontmatter_data = parse_frontmatter(file_path, content_dir)
                all_metadata.append(frontmatter_data)

    # Convert the collected dictionaries to a Pandas DataFrame
    df = pd.DataFrame(all_metadata)

    # Make sure the 'file' and 'Title' columns always exist
    if 'file' not in df.columns:
        df['file'] = ""
    if 'Title' not in df.columns:
        df['Title'] = ""

    # Place 'file' in column A, 'Title' in column B, sort the remaining columns
    fixed_order = ['file', 'Title']
    other_cols = sorted(col for col in df.columns if col not in fixed_order)
    df = df[fixed_order + other_cols]

    # Sort rows by file ascending, then Title ascending
    df.sort_values(by=['file', 'Title'], ascending=[True, True], inplace=True)

    # Write to an Excel file
    output_file = "metadata_audit.xlsx"
    df.to_excel(output_file, index=False)

    # Print a summary of the process
    total_files = len(df)
    # Count how many files had "No metadata found"
    no_metadata_count = df['No metadata found'].sum() if 'No metadata found' in df.columns else 0
    # Count how many files had "Error in frontmatter"
    error_count = 0
    if 'Error in frontmatter' in df.columns:
        error_count = df['Error in frontmatter'].notna().sum()
    valid_count = total_files - no_metadata_count - error_count

    print(f"Scanned {total_files} Markdown files.")
    print(f"{valid_count} had front matter.")
    print(f"{no_metadata_count} had no metadata.")
    print(f"{error_count} had front matter errors.")
    print(f"Wrote data to {output_file}.")

if __name__ == "__main__":
    main()