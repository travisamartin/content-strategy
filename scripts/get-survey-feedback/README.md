# Export Qualtrics Survey Responses to XLSX (via API)

`export_qualtrics_to_xlsx.py` automates downloading survey responses from Qualtrics using the REST API, applies an optional saved filter, converts the exported CSV to XLSX, and removes the Qualtrics metadata row that appears in API exports.

## Features
- Export via Qualtrics API
- Optional saved filter
- Handles ZIP or CSV
- Converts CSV to XLSX
- Removes ImportId metadata row

## Requirements
```bash
pip install requests pandas openpyxl
```

Set token in your shell:
```bash
export QUALTRICS_API_TOKEN="your-token-here"
```

## Configuration
Edit these at top of script:
```python
BASE_URL = "https://<yourdc>.qualtrics.com"
SURVEY_ID = "SV_xxxxx"
FILTER_ID = "xxxx"  # or None
OUTPUT_BASENAME = "survey_export_filtered"
```

## Run
```bash
python3 export_qualtrics_to_xlsx.py
```

Output:
```
survey_export_filtered.xlsx
```
