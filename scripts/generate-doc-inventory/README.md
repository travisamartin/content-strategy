This script scans markdown files in your docs folder and writes details to a CSV. It also writes logs to a time-stamped file.

## Usage

1. Confirm you have Python 3 and pip.
2. Run `pip install pyyaml`.
3. Place the script in a folder of your choice.
4. Open a terminal in that folder.
5. Run:

   ```shell
   python generate-doc-inventory.py /path/to/content /path/to/filepath-to-url-mapping.csv
   ```

Replace `/path/to/content` with your local path to the docs. Replace `/path/to/filepath-to-url-mapping.csv` with the path to your mapping file.

## Output

- The script writes a CSV named `output_file_<timestamp>.csv` in the current folder.
- The CSV has columns for filename, docsID, and url.
- The script also writes a log file named `content_inventory_log_<timestamp>.log`.