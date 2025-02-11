## Script details

This script scans Markdown files in a Hugo-style folder for front matter and writes the results to an Excel file named `metadata_audit_<timestamp>.xlsx`.

## Things you need

- Python 3  
- PyYAML  
- pandas  
- openpyxl  

Install them with:

```shell
pip install pyyaml pandas openpyxl
```

## How to run

1. Copy or clone the script into your local environment.  
2. Open a terminal in the folder with the script.  
3. Run:

   ```shell
   python3 metadata-audit.py /path/to/yourRepo/content
   ```

   Replace `/path/to/yourRepo/content` with the folder that holds your Markdown files. For example:

   ```text
   python3 metadata-audit.py /Users/jdoe/Projects/docs/content
   ```

## What the script does

1. Finds `.md` files under the content folder.
2. Checks each file for front matter at the very start, delimited by `---`.
3. Extracts any keys from the front matter and removes time zone info from date fields.
4. Creates a spreadsheet (`metadata_audit_<timestamp>.xlsx`) with the findings.

## What the script writes

- **file** (column A)
  - A path of this form: `/<repoName>/content/...`
- **title** (column B)
- **Title** (column C)
- Any other metadata keys, sorted alphabetically after those three.
- Rows are sorted by the file path only.

## Troubleshooting

- If you see an error about a missing module, install it with `pip`.  
- “No metadata found” means the file did not start with `---`.  
- “Error in front matter” means the script could not parse the front matter.
