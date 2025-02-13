#!/usr/bin/env python3

import os
import sys
import re
import datetime

# This pattern matches Hugo's include shortcode, e.g.:
# {{< include "path/to/file.md" >}}
include_pattern = re.compile(r'{{<\s*include\s*["\']([^"\']+)["\']\s*>}}')

def read_file_lines(path):
    """
    Read all lines from a file using UTF-8 encoding.
    """
    with open(path, 'r', encoding='utf-8') as f:
        return f.readlines()

def write_file_lines(path, lines):
    """
    Write lines to a file, ensuring the destination directory exists.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def strip_front_matter(lines):
    """
    Remove Hugo front matter delimited by lines with '---'.
    """
    stripped = []
    in_front_matter = False
    for line in lines:
        if line.strip() == "---":
            in_front_matter = not in_front_matter
            continue
        if not in_front_matter:
            stripped.append(line)
    return stripped

def remove_html_comments(text):
    """
    Remove HTML comments from text, including multi-line comments.
    """
    return re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)

def remove_versions_lines(lines):
    """
    Remove lines that contain Hugo's versions shortcode.
    For example: {{< versions "3.12" "latest" "ctrlvers" >}}
    """
    pattern = re.compile(r'{{<\s*versions\s+.*?>}}')
    return [line for line in lines if not pattern.search(line)]

def expand_includes(lines, includes_path, log_messages, stats):
    """
    Replace include shortcodes with the actual content from the include file.
    This function processes a list of lines recursively.
    """
    expanded = []
    for line in lines:
        match = include_pattern.search(line)
        if match:
            # If we find an include shortcode, split the line.
            parts = re.split(include_pattern, line)
            replaced_line = []
            idx = 0
            while idx < len(parts):
                if idx % 2 == 0:
                    # Even indexes are plain text.
                    replaced_line.append(parts[idx])
                else:
                    # Odd indexes are the file path from the include shortcode.
                    inc_file_path = parts[idx]
                    # Remove any leading slash from the file reference.
                    inc_file_path_stripped = inc_file_path.lstrip('/')
                    # Build the full path to the include file.
                    full_inc_path = os.path.join(includes_path, inc_file_path_stripped)
                    if os.path.isfile(full_inc_path):
                        # Read the include file's content.
                        inc_lines = read_file_lines(full_inc_path)
                        # Remove front matter from the include file.
                        inc_lines = strip_front_matter(inc_lines)
                        # Recursively process any includes inside the included content.
                        inc_lines = expand_includes(inc_lines, includes_path, log_messages, stats)
                        replaced_line.append("".join(inc_lines))
                    else:
                        # Log an error if the include file is missing.
                        msg = f"ERROR: Missing include: {inc_file_path}"
                        print(msg)
                        log_messages.append(msg + "\n")
                        stats['errors'] += 1
                idx += 1
            expanded.append("".join(replaced_line))
        else:
            expanded.append(line)
    return expanded

def replace_relref(text, current_file_dir, doc_set_name):
    """
    Replace Hugo relref links with normal Markdown links.
    
    The function finds relref shortcodes like:
    {{< relref "/controller/path/to/file.md" >}}
    It removes the leading doc set name if present and calculates a relative path
    from the current file's directory.
    """
    relref_pattern = re.compile(r'{{<\s*relref\s*["\']([^"\']+)["\']\s*>}}')
    
    def repl(match):
        target = match.group(1)
        # Remove the doc set prefix if present.
        if target.startswith(f"/{doc_set_name}/"):
            target_relative = target[len(f"/{doc_set_name}/"):]
        elif target.startswith("/"):
            target_relative = target[1:]
        else:
            target_relative = target
        # Use a new variable for the current file's directory.
        cur_dir = current_file_dir if current_file_dir else "."
        # Compute a relative link from the current file's directory.
        relative_link = os.path.relpath(target_relative, start=cur_dir)
        return relative_link

    return relref_pattern.sub(repl, text)

def main():
    """
    Main function that processes the doc set:
    - Reads each Markdown file (except _index.md)
    - Removes front matter and versions lines
    - Expands includes and relref links
    - Removes HTML comments
    - Writes the processed content to an archive folder
    - Logs processing status and errors
    """
    if len(sys.argv) != 3:
        print("Usage: python archive_docs.py <doc_set_path> <includes_path>")
        sys.exit(1)
    
    doc_set_path = sys.argv[1]
    includes_path = sys.argv[2]
    # Determine the name of the doc set (for example, "controller")
    doc_set_name = os.path.basename(os.path.normpath(doc_set_path))

    # Create an archive folder with a timestamp in its name:
    # For example, controller_archive_20250213123456
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    archive_folder = f"{doc_set_name}_archive_{timestamp}"
    log_file = os.path.join(archive_folder, "archive.log")

    log_messages = []
    stats = {'processed': 0, 'success': 0, 'errors': 0}

    print(f"Archive folder: {archive_folder}")
    print("Starting...")

    # Walk through the doc set directory.
    for root, dirs, files in os.walk(doc_set_path):
        for file_name in files:
            # Skip _index.md files.
            if file_name == "_index.md":
                continue
            if file_name.endswith(".md"):
                stats['processed'] += 1
                source_path = os.path.join(root, file_name)
                # Compute the relative path from the doc set folder.
                rel_path = os.path.relpath(source_path, doc_set_path)
                target_path = os.path.join(archive_folder, rel_path)

                print(f"Processing: {source_path}")

                try:
                    error_count_before = stats['errors']
                    # Read the Markdown file.
                    lines = read_file_lines(source_path)
                    # Remove front matter.
                    lines = strip_front_matter(lines)
                    # Replace include shortcodes with actual content.
                    lines = expand_includes(lines, includes_path, log_messages, stats)
                    # Remove lines with versions shortcodes.
                    lines = remove_versions_lines(lines)
                    # Combine lines to process the entire text.
                    full_text = "".join(lines)
                    # Remove HTML comments.
                    full_text = remove_html_comments(full_text)
                    # Compute the directory for the current file.
                    current_file_dir = os.path.dirname(rel_path)
                    # Replace relref links with standard Markdown links.
                    full_text = replace_relref(full_text, current_file_dir, doc_set_name)
                    # Split the full text back into lines.
                    lines = full_text.splitlines(keepends=True)
                    # Write the processed content to the target file.
                    write_file_lines(target_path, lines)
                    log_messages.append(f"Processed: {source_path}\n")
                    # Count as a success if no new errors were logged.
                    if stats['errors'] == error_count_before:
                        stats['success'] += 1

                except Exception as e:
                    # Log any exceptions that occur.
                    msg = f"ERROR while reading {source_path}: {str(e)}"
                    print(msg)
                    log_messages.append(msg + "\n")
                    stats['errors'] += 1

    # Write the log messages to a log file in the archive folder.
    os.makedirs(archive_folder, exist_ok=True)
    with open(log_file, 'w', encoding='utf-8') as lf:
        lf.writelines(log_messages)

    # Print a summary of the processing.
    print("Done.")
    print("Summary:")
    print(f"Total files processed: {stats['processed']}")
    print(f"Successfully processed: {stats['success']}")
    print(f"Files with errors: {stats['errors']}")

if __name__ == "__main__":
    main()