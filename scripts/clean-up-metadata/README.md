# remove_metadata_keys.py

## Summary
This script removes specific metadata keys from Markdown files. It looks for a front matter block (delimited by `---`) in each file, deletes unneeded keys, then writes the file back to disk.

## Requirements
- Python 3
- PyYAML (install with `pip install pyyaml`)

## How to run

1. Open a terminal and go to the directory that holds the script.
2. Run:
  
   ```shell
   python remove_metadata_keys.py /path/to/content
   ```

   Replace `/path/to/content` with the actual directory path that contains your Markdown files.

## How it works

- The script searches for every `.md` file in the target directory.
- It reads each file and locates the front matter that appears between `---` lines.
- It parses that block with PyYAML, removes the specified keys, and rewrites the file only if needed.
- It logs changes and errors to the console and to a timestamped log file in the current folder.
