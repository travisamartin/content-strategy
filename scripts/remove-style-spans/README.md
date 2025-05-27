# Fix span tags script

## Overview
This script finds and replaces `<span>` tags with Markdown bold in your `.md` files. It looks for spans whose style includes `font-weight:bold` or `font-weight:bolder` and wraps their content in `**…**`. If the style also includes `white-space: nowrap`, it replaces spaces with `&nbsp;` and hyphens with `&#8209;`.

## Requirements

- Python 3.6 or later

## Installation

1. Save the script as `fix_spans.py`.  
2. (Optional) Make it executable:
3. 
   ```shell
   chmod +x fix_spans.py
   ```

## Usage

Run the script and point it at your docs folder:

```shell
python3 fix_spans.py <rootdir>
```

Replace `<rootdir>` with the path to the directory you want to recurse through. The script edits `.md` files in place and prints each file it updates.
