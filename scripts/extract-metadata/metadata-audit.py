#!/usr/bin/env python3

import sys
import os
import yaml
import pandas as pd
from datetime import datetime
from openpyxl import Workbook

def remove_timezone(dt_value):
    """
    If dt_value is a datetime that includes time zone information, 
    return a copy without the tzinfo. Otherwise, return dt_value as-is.
    
    This is necessary because some date/datetime fields in front matter 
    might include a time zone (e.g., 2023-01-01T12:00:00+00:00), 
    which can cause problems in Excel.
    """
    if isinstance(dt_value, datetime) and dt_value.tzinfo is not None:
        return dt_value.replace(tzinfo=None)
    return dt_value

def build_repo_content_path(file_path, content_dir):
    """
    Construct a path that begins with /<repoName>/<contentFolder> and 
    ends with the relative subpath to the Markdown file.
    
    For example:
      If content_dir = /Users/jdoe/docs/content
      and file_path = /Users/jdoe/docs/content/foo/bar.md
      The output might be /docs/content/foo/bar.md

    Steps:
      1. Convert content_dir to an absolute path (content_dir_abs).
      2. The folder containing content_dir is the 'repo_name'.
      3. The name of the content_dir folder itself is 'content_folder'.
      4. Combine them into a prefix like: /repoName/content_folder
      5. Compute the relative path from content_dir_abs to file_path.
      6. Join the prefix and the relative path, then replace backslashes 
         with slashes (for Windows compatibility).
    """
    # Convert the content directory to an absolute path
    content_dir_abs = os.path.abspath(content_dir)
    
    # The folder that holds content_dir is effectively the repo's name
    repo_name = os.path.basename(os.path.dirname(content_dir_abs))
    
    # The last part of the path to content_dir (often 'content')
    content_folder = os.path.basename(content_dir_abs)

    # Make a prefix like "/docs/content" or "/documentation/content"
    prefix = f"/{repo_name}/{content_folder}"

    # Get the path of the file relative to content_dir_abs
    rel_path = os.path.relpath(file_path, content_dir_abs)

    # Join prefix with the relative path
    joined = os.path.join(prefix, rel_path)

    # Return with forward slashes (in case of Windows backslashes)
    return joined.replace("\\", "/")

def parse_frontmatter(file_path, content_dir):
    """
    Look for YAML front matter in a Markdown file:
      1. The file must start with '---' to be recognized as having front matter.
      2. Split the file content on '---'; we expect at least 3 parts 
         if there's valid YAML front matter.
      3. Parse the second part (parts[1]) with yaml.safe_load(). 
      4. Remove timezone info from any datetime fields (using remove_timezone).
      5. Capture all keys exactly as found (e.g., 'title', 'Title').
      6. If there's an error or no front matter, return a dict with flags 
         like {"No metadata found": True} or {"Error in frontmatter": True}.
    
    The returned dict also includes a "file" key with the path (from build_repo_content_path).
    """
    # Build a path that references the repo and content folder
    final_path = build_repo_content_path(file_path, content_dir)

    try:
        # Read the full file
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        # If file content doesn't begin with '---', no YAML front matter found
        if not raw_content.startswith('---'):
            return {"file": final_path, "No metadata found": True}

        # parts should have at least 3 items for valid front matter:
        # parts[0] = empty string before the first '---'
        # parts[1] = the YAML block
        # parts[2] = the rest of the file after the YAML block
        parts = raw_content.split('---', 2)
        if len(parts) < 3:
            return {"file": final_path, "Error in frontmatter": True}

        frontmatter_str = parts[1]
        try:
            # Parse the YAML block
            data = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            # If parsing fails, note the error
            return {"file": final_path, "Error in frontmatter": True}

        # If the YAML block is empty, then there's no real metadata
        if not data:
            return {"file": final_path, "No metadata found": True}

        # Remove any timezone info from recognized date/datetime fields
        for key, value in list(data.items()):
            data[key] = remove_timezone(value)

        # Store the final path in the metadata
        data["file"] = final_path
        return data

    except Exception as e:
        # Catch unexpected issues such as file I/O errors
        return {"file": final_path, "Error in frontmatter": str(e)}

def main():
    """
    Main function:
      1. Read the path to a Hugo 'content' directory from the command line.
      2. Recursively find .md files in that folder.
      3. Extract YAML front matter if present, preserving each metadata key 
         exactly as it appears (title vs. Title).
      4. Create a pandas DataFrame with these records.
      5. Ensure the columns 'file', 'title', and 'Title' exist (even if empty).
      6. Sort columns so 'file' is first, 'title' is second, 'Title' is third, 
         and everything else is alphabetical after that.
      7. Sort rows by 'file' only.
      8. Write the results to an Excel file with a timestamped name. The first 
         two rows (and an empty row) are used for the repo path and date.
      9. Print a summary of how many files had front matter, how many didn't, 
         and how many had errors.
    """
    if len(sys.argv) < 2:
        print("Usage: python3 metadata-audit.py /path/to/<repo>/content/")
        sys.exit(1)

    # Get the path to the content directory from command line arguments
    content_dir = sys.argv[1]

    # Build a path like "/docs/content/" or "/documentation/content/" for the Excel header
    content_dir_abs = os.path.abspath(content_dir)
    repo_name = os.path.basename(os.path.dirname(content_dir_abs))
    content_folder = os.path.basename(content_dir_abs)
    repo_content_path = f"/{repo_name}/{content_folder}/"

    # Loop through all files in content_dir, looking for .md
    all_metadata = []
    for root, _, files in os.walk(content_dir):
        for filename in files:
            if filename.lower().endswith('.md'):
                file_path = os.path.join(root, filename)
                frontmatter_data = parse_frontmatter(file_path, content_dir)
                all_metadata.append(frontmatter_data)

    # Convert the list of metadata dictionaries to a pandas DataFrame
    df = pd.DataFrame(all_metadata)

    # Ensure certain columns exist even if no file provided them
    for col in ['file', 'title', 'Title']:
        if col not in df.columns:
            df[col] = ""

    # We want the columns in this order: 
    # 1. 'file', 2. 'title', 3. 'Title', then the rest in alphabetical order
    fixed_order = ['file', 'title', 'Title']
    other_cols = sorted(c for c in df.columns if c not in fixed_order)
    df = df[fixed_order + other_cols]

    # Sort rows by 'file' ascending (ignoring 'title' or 'Title' in row sorting)
    df.sort_values(by=['file'], ascending=True, inplace=True)

    # Create a timestamp for the Excel filename, e.g. "20250301_153022"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"metadata_audit_{timestamp}.xlsx"

    # Use ExcelWriter to create the file. We'll place the DataFrame 
    # starting at row 4, leaving rows 1 and 2 for the path/date, row 3 blank.
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, startrow=3, sheet_name='Sheet1')

        # Write headers in row 1 and 2
        sheet = writer.sheets['Sheet1']
        sheet['A1'] = f"Repo path: {repo_content_path}"
        sheet['A2'] = f"Date: {datetime.now().strftime('%Y-%m-%d')}"
        # Row 3 remains blank

    # Summarize how many Markdown files were scanned and how many had front matter or not
    total_files = len(df)
    no_metadata_count = df['No metadata found'].sum() if 'No metadata found' in df.columns else 0

    # Count how many rows have a non-null error in front matter
    if 'Error in frontmatter' in df.columns:
        error_count = df['Error in frontmatter'].notna().sum()
    else:
        error_count = 0

    valid_count = total_files - no_metadata_count - error_count

    # Print the summary to the console
    print(f"Scanned {total_files} Markdown files.")
    print(f"{valid_count} had front matter.")
    print(f"{no_metadata_count} had no metadata.")
    print(f"{error_count} had front matter errors.")
    print(f"Wrote data to {output_file}.")

if __name__ == "__main__":
    main()