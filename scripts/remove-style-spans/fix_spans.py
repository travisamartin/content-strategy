#!/usr/bin/env python3
import argparse
import os
import re
import sys

SPAN_RE = re.compile(
    r'<span\s+style="([^"]*?)"\s*>(.*?)</span>',
    re.IGNORECASE | re.DOTALL
)

def transform_span(style: str, text: str) -> str:
    """
    If style has font-weight:bold or bolder, convert to **text**.
    If it also has white-space: nowrap, replace spaces and hyphens.
    Otherwise, leave the span unchanged.
    """
    style_lc = style.lower()
    if 'font-weight:bold' in style_lc or 'font-weight:bolder' in style_lc:
        # apply nowrap transformations only if requested
        if 'white-space:nowrap' in style_lc or 'white-space: nowrap' in style_lc:
            text = text.replace('-', '&#8209;').replace(' ', '&nbsp;')
        return f'**{text}**'
    # no bold in style → leave original
    return None

def process_file(path: str) -> None:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    def repl(match):
        style, inner = match.group(1), match.group(2)
        new = transform_span(style, inner)
        return new if new is not None else match.group(0)

    new_content = SPAN_RE.sub(repl, content)

    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated: {path}')

def main():
    parser = argparse.ArgumentParser(
        description='Replace certain <span> tags with Markdown bold in-place'
    )
    parser.add_argument(
        'rootdir',
        help='Directory to recurse through looking for .md files'
    )
    args = parser.parse_args()

    if not os.path.isdir(args.rootdir):
        print(f'Error: {args.rootdir} is not a directory', file=sys.stderr)
        sys.exit(1)

    for dirpath, dirnames, filenames in os.walk(args.rootdir):
        # skip hidden folders if you like:
        # dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for name in filenames:
            if name.lower().endswith('.md'):
                process_file(os.path.join(dirpath, name))

if __name__ == '__main__':
    main()