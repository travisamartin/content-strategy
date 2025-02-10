#!/usr/bin/env python3

import sys
import os
import yaml
import pandas as pd
from datetime import datetime
from openpyxl import Workbook

def remove_timezone(dt_value):
    """
    Return the datetime value without a time zone component.
    """
    if isinstance(dt_value, datetime) and dt_value.tzinfo is not None:
        return dt_value.replace(tzinfo=None)
    return dt_value

def build_repo_content_path(file_path, content_dir):
    """
    Build a path that starts with /<repoName>/<contentFolder>.
    For example:
        /docs/content/search.md
        /documentation/content/search.md
    """
    content_dir_abs = os.path.abspath(content_dir)
    repo_name = os.path.basename(os.path.dirname(content_dir_abs))
    content_folder = os.path.basename(content_dir_abs)
    
    prefix = f"/{repo_name}/{content_folder}"
    rel_path = os.path.relpath(file_path, content_dir_abs)
    joined = os.path.join(prefix, rel_path)
    return joined.replace("\\", "/")

def parse_frontmatter(file_path, content_dir):
    """
    Read a Markdown file. If it starts with '---', parse the middle block as YAML.
    Keep keys exactly as they appear (title, Title, etc.), removing only timezone info
    from date fields. If front matter is missing or invalid, record that.
    """
    final_path = build_repo_content_path(file_path, content_dir)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        # If it doesn't start with '---', no YAML front matter
        if not raw_content.startswith('---'):
            return {"file": final_path, "No metadata found": True}

        parts = raw_content.split('---', 2)
        if len(parts) < 3:
            return {"file": final_path, "Error in frontmatter": True}

        frontmatter_str = parts[1]
        try:
            data = yaml.safe_load(frontmatter_str) or {}
        except yaml.YAMLError:
            return {"file": final_path, "Error in frontmatter": True}

        if not data:
            return {"file": final_path, "No metadata found": True}

        # Remove timezone info from any date/datetime fields
        for key, value in list(data.items()):
            data[key] = remove_timezone(value)

        data["file"] = final_path
        return data

    except Exception as e:
        return {"file": final_path, "Error in frontmatter": str(e)}

def main():
    """
    1. Accept a path to a Hugo-style 'content' directory.
    2. Recursively scan for Markdown files, parse YAML front matter if present.
    3. Capture all metadata keys exactly (including 'title' vs. 'Title' differences).
    4. Write results to an Excel file with a timestamped name.
    5. Sort columns so: file, title, Title, then alphabetical for any others.
    6. Sort rows by the 'file' column only, then print a summary.
    """
    if len(sys.argv) < 2:
        print("Usage: python3 metadata-audit.py /path/to/<repo>/content/")
        sys.exit(1)

    content_dir = sys.argv[1]

    # Derive a string like "/documentation/content/" for reference in Excel
    content_dir_abs = os.path.abspath(content_dir)
    repo_name = os.path.basename(os.path.dirname(content_dir_abs))
    content_folder = os.path.basename(content_dir_abs)
    repo_content_path = f"/{repo_name}/{content_folder}/"

    all_metadata = []
    for root, _, files in os.walk(content_dir):
        for filename in files:
            if filename.lower().endswith('.md'):
                file_path = os.path.join(root, filename)
                frontmatter_data = parse_frontmatter(file_path, content_dir)
                all_metadata.append(frontmatter_data)

    df = pd.DataFrame(all_metadata)

    # Ensure 'file', 'title', and 'Title' columns exist
    for col in ['file', 'title', 'Title']:
        if col not in df.columns:
            df[col] = ""

    # Sort columns so that file = col A, title = col B, Title = col C, then alphabetize the rest
    fixed_order = ['file', 'title', 'Title']
    other_cols = sorted(c for c in df.columns if c not in fixed_order)
    df = df[fixed_order + other_cols]

    # Sort rows only by 'file'
    df.sort_values(by=['file'], ascending=True, inplace=True)

    # Build a timestamped file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"metadata_audit_{timestamp}.xlsx"

    # Write the DataFrame to Excel, offset to leave two header rows and one blank row
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, startrow=3, sheet_name='Sheet1')
        sheet = writer.sheets['Sheet1']
        sheet['A1'] = f"Repo path: {repo_content_path}"
        sheet['A2'] = f"Date: {datetime.now().strftime('%Y-%m-%d')}"
        # Row 3 is blank

    # Summarize
    total_files = len(df)
    no_metadata_count = df['No metadata found'].sum() if 'No metadata found' in df.columns else 0
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