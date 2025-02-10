## Script details

This script scans Markdown files in a Hugo-style folder for front matter. It removes any time zones from date fields and renames “title” to “Title.” It writes the results to an Excel file named `metadata_audit.xlsx` and prints a summary of its work.

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

1. Finds `.md` files under the `content` folder.  
2. Checks each file for front matter delimited by `---`.  
3. Extracts front matter as metadata, renames “title” to “Title,” and removes time zone info.  
4. Creates a spreadsheet (`metadata_audit.xlsx`) with the findings.  

## What the script writes

- **file** (column A)  
  - A path of this form: `/<repoName>/content/...`  
- **Title** (column B)  
- Other columns for any metadata fields, sorted alphabetically.  
- Rows sorted by the **file** path, then **Title**.

## Troubleshooting

- If you see an error about a missing module, install it with `pip`.  
- “No metadata found” means the file did not start with `---`.  
- “Error in front matter” means the script could not parse the front matter.