# Reading level report

A simple Python script that walks through a directory of Markdown files, calculates each file’s Flesch‑Kincaid reading grade, and writes the results to a CSV.

## Requirements

- Python 3.7 or later  
- pip-installed packages:
  ```shell
  pip install markdown2 beautifulsoup4 textstat
  ```

## Installation

Installation

1. Save the script as `reading_level.py`.
2. Install dependencies (see Requirements).

## Usage

Run the script with one argument—the path to the folder you want to analyze:

```shell
python3 reading_level.py /path/to/your/markdown-directory
```

By default, it writes results to reading_levels.csv in the current working directory.

## Output

## Output

The CSV has two columns:

| file_path                   | reading_level                       |
|-----------------------------|-------------------------------------|
| content/getting-started.md  | 8.3                                 |
| docs/advanced-guide.md      | Error calculating reading level: …   |

- `file_path` shows the full path to each Markdown file (excluding `_index.md` files).  
- `reading_level` shows the Flesch‑Kincaid grade or an error message if processing failed.

## How it works

1. It reads each `.md` file (skipping `_index.md`).  
2. It converts Markdown to plain text, removing code blocks.  
3. It uses TextStat to compute the Flesch‑Kincaid grade level.  
4. It logs progress to the console and captures errors in the CSV.

## Error handling

- If the script can’t read a file, it writes an error message instead of a numeric score.  
- If `textstat` fails, the script records the exception text in the CSV.