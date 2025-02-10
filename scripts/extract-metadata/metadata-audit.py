#!/usr/bin/env python3

import sys
import os
import yaml
import pandas as pd
from datetime import datetime
from openpyxl import Workbook

def remove_timezone(dt_value):
    """
    Return the datetime value without a time zone.
    """
    if isinstance(dt_value, datetime) and dt_value.tzinfo is not None:
        return dt_value.replace(tzinfo=None)
    return dt_value

def build_repo_content_path(file_path, content_dir):
    """
    Build a path that starts with /<repoName>/<contentFolder>. 
    For example: /docs/content/ or /documentation/content/.
    """
    # Convert the content directory to an absolute path
    content_dir_abs = os.path.abspath(content_dir)

    # The folder that contains the content directory is the repo name
    repo_name = os.path.basename(os.path.dirname(content_dir_abs))

    # The name of the content folder (often 'content')
    content_folder = os.path.basename(content_dir_abs)

    # Construct something like "/repoName/contentFolder"
    prefix = f"/{repo_name}/{content_folder}"

    # Find the path of file_path relative to the content directory
    rel_path = os.path.relpath(file_path, content_dir_abs)

    # Join prefix with the relative path, then replace any backslashes
    joined = os.path.join(prefix, rel_path)
    return joined.replace("\\", "/")

def parse_frontmatter(file_path, content_dir):
    """
    Open the file, look for front matter, rename 'title' to 'Title', 
    remove time zones, and return the metadata in a dictionary.
    """
    # Build the path that starts with the repo name and content folder
    final_path = build_repo_content_path(file_path, content_dir)

    try:
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        # If there's no opening '---', record no metadata
        if not raw_content.startswith('---'):
            return {"file": final_path, "No metadata found": True}

        # Split on '---'; we expect three parts for valid front matter
        parts = raw_content.split('---', 2)
        if len(parts) < 3:
            return {"file": final_path, "Error in frontmatter": True}

        frontmatter_str = parts[1]
        try:
            # Parse the YAML
            data = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            return {"file": final_path, "Error in frontmatter": True}

        # If the parsed front matter is empty, record no metadata
        if not data:
            return {"file": final_path, "No metadata found": True}

        # Rename 'title' to 'Title' and remove any time zone data
        for key, value in list(data.items()):
            if key.lower() == 'title':
                data['Title'] = remove_timezone(value)
                del data[key]
            else:
                data[key] = remove_timezone(value)

        # Add the file path
        data["file"] = final_path
        return data

    except Exception as e:
        # Record any unexpected error as front matter error
        return {"file": final_path, "Error in frontmatter": str(e)}

def main():
    """
    Walk the specified content directory for Markdown files. 
    Parse front matter, build an Excel file, and print a summary.
    """
    if len(sys.argv) < 2:
        print("Usage: python3 metadata-audit.py /path/to/<repo>/content/")
        sys.exit(1)

    content_dir = sys.argv[1]

    # Build the string used in the Excel header, like "/docs/content/"
    content_dir_abs = os.path.abspath(content_dir)
    repo_name = os.path.basename(os.path.dirname(content_dir_abs))
    content_folder = os.path.basename(content_dir_abs)
    repo_content_path = f"/{repo_name}/{content_folder}/"

    all_metadata = []

    # Recursively scan the content directory for .md files
    for root, _, files in os.walk(content_dir):
        for filename in files:
            if filename.lower().endswith('.md'):
                file_path = os.path.join(root, filename)
                frontmatter_data = parse_frontmatter(file_path, content_dir)
                all_metadata.append(frontmatter_data)

    # Convert collected records into a DataFrame
    df = pd.DataFrame(all_metadata)

    # Ensure "file" and "Title" columns exist
    if 'file' not in df.columns:
        df['file'] = ""
    if 'Title' not in df.columns:
        df['Title'] = ""

    # Place 'file' in column A, 'Title' in column B, then sort other columns
    fixed_order = ['file', 'Title']
    other_cols = sorted(col for col in df.columns if col not in fixed_order)
    df = df[fixed_order + other_cols]

    # Sort the rows by file path, then title
    df.sort_values(by=['file', 'Title'], ascending=[True, True], inplace=True)

    output_file = "metadata_audit.xlsx"

    # Write the DataFrame to the Excel file, starting on row 4
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Start the data on row 4
        df.to_excel(writer, index=False, startrow=3, sheet_name='Sheet1')
        sheet = writer.sheets['Sheet1']

        # Row 1: show the repo path
        sheet['A1'] = f"Repo path: {repo_content_path}"
        # Row 2: show the current date
        today_str = datetime.now().strftime('%Y-%m-%d')
        sheet['A2'] = f"Date: {today_str}"
        # Row 3 is blank

    # Compute summary info
    total_files = len(df)
    no_metadata_count = df['No metadata found'].sum() if 'No metadata found' in df.columns else 0
    error_count = df['Error in frontmatter'].notna().sum() if 'Error in frontmatter' in df.columns else 0
    valid_count = total_files - no_metadata_count - error_count

    # Print summary
    print(f"Scanned {total_files} Markdown files.")
    print(f"{valid_count} had front matter.")
    print(f"{no_metadata_count} had no metadata.")
    print(f"{error_count} had front matter errors.")
    print(f"Wrote data to {output_file}.")

if __name__ == "__main__":
    main()