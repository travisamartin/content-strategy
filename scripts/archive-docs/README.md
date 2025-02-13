# Archive docs script

This Python script processes Hugo documentation by reading Markdown files from a doc set, removing unwanted parts, and producing an archive with updated content. It expands Hugo include shortcodes, removes front matter, HTML comments, and versions shortcodes, and it converts relref links to normal Markdown links so they work with the new folder structure.

## Requirements

- Python 3.7 or newer  
- No extra packages are needed (the script uses only the Python standard library)

## Usage

Run the script from a terminal with two parameters: the path to the doc set and the path to the includes folder. For example:

```bash
python archive_docs.py /Users/T.Martin/Projects/git/nginxinc/documentation/content/controller /Users/T.Martin/Projects/git/nginxinc/documentation/content/includes
```

## What it does

- Skips `_index.md` files: These files are not needed in the archive.
- Strips front matter: Removes the metadata wrapped in `---` lines.
- Expands include shortcodes: Replaces Hugo include shortcodes with the actual content from the file found in the includes folder, handling nested includes as well.
- Removes versions lines: Eliminates lines with versions shortcodes (for example, `{{< versions "3.12" "latest" "ctrlvers" >}}`).
- Removes HTML comments: Strips out any HTML comments from the content.
- Replaces `relref` links: Converts Hugo `relref` links to standard Markdown links using relative paths, ensuring they work in the archive.
- Logs output: Prints file names being processed and any errors encountered. Also writes a log file (`archive.log`) in the archive folder and prints a summary of processed files, successes, and errors.

## Log output

During execution, the script displays on-screen messages listing each file being processed and any errors encountered. It also produces a log file inside the archive folder for later review.

## Customization

Feel free to modify the script or this README as needed to fit your documentation workflow.