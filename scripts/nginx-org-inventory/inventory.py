#!/usr/bin/env python3
"""
inventory.py

Scan nginx.org xml docs under xml/<lang>/docs and save an Excel inventory
with file, title, link, and last commit, plus auto-fit columns.

Requirements:
    • Python 3.6 or later
    • pandas
    • openpyxl
    • Git must be installed, and this script must run in a git working directory.

Install libraries:
    pip3 install pandas openpyxl

Run:
    python3 inventory.py --repo-path . --output nginx_docs_inventory.xlsx
"""

import os
import subprocess
import argparse
import xml.etree.ElementTree as ET
import re
import html
import pandas as pd
from openpyxl.utils import get_column_letter

# language codes to include
LANG_CODES = ["cn", "en", "he", "it", "ja", "ru", "tr"]


def get_last_commit_date(repo_path, file_path):
    """
    Return the ISO date of the last git commit for file_path.
    Return empty string if git fails.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", file_path],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def clean_text(text):
    """
    Collapse whitespace and decode HTML entities.
    """
    text = re.sub(r"\s+", " ", text).strip()
    return html.unescape(text)


def extract_title(xml_file):
    """
    Return the document title from xml_file:

    1. Scan every element for <article> or <module> and grab its name.
    2. If none, regex raw text for name="...".
    Then clean whitespace and HTML entities.
    """
    try:
        tree = ET.parse(xml_file)
        for elem in tree.iter():
            tag = elem.tag.split("}")[-1]  # ignore namespace
            if tag in ("article", "module"):
                name = elem.attrib.get("name", "").strip()
                if name:
                    return clean_text(name)
    except ET.ParseError:
        pass

    # fallback to regex on raw text
    try:
        text = open(xml_file, encoding="utf-8").read()
        match = re.search(
            r'<(?:article|module)[^>]*\sname=["\']([^"\']+)["\']',
            text
        )
        if match:
            return clean_text(match.group(1))
    except Exception:
        pass

    return ""


def make_link(rel_path):
    """
    Turn a relative xml path into the public HTML link:
      xml/en/docs/foo.xml → https://nginx.org/en/docs/foo.html
    """
    # remove leading 'xml/' and swap extension
    web_path = rel_path[len("xml/"):].replace(".xml", ".html")
    return f"https://nginx.org/{web_path}"


def build_inventory(repo_path):
    """
    Scan xml/<lang>/docs for each language. Return a dict:
      { lang: [ {file, title, link, last_commit}, ... ] }
    """
    data = {}

    for lang in LANG_CODES:
        records = []
        docs_dir = os.path.join(repo_path, "xml", lang, "docs")
        if not os.path.isdir(docs_dir):
            print(f"warning: folder not found: {docs_dir}")
            continue

        for root, _, files in os.walk(docs_dir):
            for name in files:
                if not name.lower().endswith(".xml"):
                    continue

                full = os.path.join(root, name)
                rel = os.path.relpath(full, repo_path)

                records.append({
                    "file": rel,
                    "title": extract_title(full),
                    "link": make_link(rel),
                    "last_commit": get_last_commit_date(repo_path, rel),
                })

        data[lang] = records

    return data


def write_to_excel(data_dict, output_file):
    """
    Write the inventory to an Excel workbook:
    • one sheet per language code
    • columns: file, title, link, last commit
    • auto-fit each column
    """
    with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
        for lang, records in data_dict.items():
            df = pd.DataFrame(records)
            df = df.rename(columns={"last_commit": "last commit"})
            # ensure column order
            df = df[["file", "title", "link", "last commit"]]
            df.to_excel(writer, sheet_name=lang, index=False)

        # auto-fit columns
        workbook = writer.book
        for sheet in workbook.worksheets:
            for col in sheet.columns:
                max_len = max(len(str(cell.value or "")) for cell in col)
                letter = get_column_letter(col[0].column)
                sheet.column_dimensions[letter].width = max_len + 2

    print(f"inventory written to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Inventory nginx.org xml docs into an Excel file"
    )
    parser.add_argument(
        "--repo-path", default=".",
        help="path to the root of your nginx.org clone"
    )
    parser.add_argument(
        "--output", default="nginx_docs_inventory.xlsx",
        help="Excel file to create"
    )
    args = parser.parse_args()

    inventory = build_inventory(args.repo_path)
    write_to_excel(inventory, args.output)


if __name__ == "__main__":
    main()