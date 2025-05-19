# NGINX.org docs inventory

This tool scans the `xml/<lang>/docs` folders in the nginx.org repo and builds an Excel workbook with:

- **file**: the XML file’s path relative to the repo root  
- **title**: the document title from `<article name="…">` or `<module name="…">`  
- **last commit**: ISO timestamp of the file’s most recent Git commit  

Each sheet is named for its language code (`cn`, `en`, `he`, `it`, `ja`, `ru`, `tr`), and columns auto-fit their contents.

## what you need

- Python 3.6 or later  
- Git  
- Python packages:
  - pandas  
  - openpyxl  

Install the packages:

```bash
pip3 install pandas openpyxl
```

## Clone the repos

1. Clone the content strategy repo:

   ```shell
   git clone https://github.com/travisamartin/content-strategy.git
   ```

2. Clone the nginx.org repo:

   ```shell
   git clone https://github.com/nginx/nginx.org.git
   ```

## Run the script

1. Change to the folder that has the script:

   ```shell
   cd content-strategy/nginx-org-inventory
   ```

2. Run the script, pointing `--repo-path` to your nginx.org clone:

   ```shell
   python3 inventory.py \
   --repo-path ../../nginx.org \
   --output nginx_docs_inventory.xlsx
   ```

- `--repo-path` is the path to the root of your nginx.org clone
- `--output` is the name of the Excel file to create

When the script finishes, open `nginx_docs_inventory.xlsx`. The Excel file includes one sheet per language with columns for the file path (relative to the nginx.org repo), title, and last commit date.

## How it works

1. It walks every `*.xml` under `xml/<lang>/docs`.
2. It parses each file for `<article name="…">` or `<module name="…">`.
3. It runs git log to find each file’s last commit date.
4. It writes one sheet per language and auto-adjusts column widths.