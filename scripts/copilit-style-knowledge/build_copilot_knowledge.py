#!/usr/bin/env python3
"""
Build grouped Copilot knowledge files from the style guide source.

Usage:
    python build_copilot_knowledge.py --source ./style-guide --output ./copilot-knowledge
"""

import argparse
import os
import sys


SKIP_DIRS = {"templates"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build grouped Copilot knowledge .txt files from style guide .md sources."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Path to the style guide repo root.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to the output directory (created if it doesn't exist).",
    )
    return parser.parse_args()


def collect_groups(source_dir):
    """
    Walk source_dir one level deep. Each immediate subdirectory becomes a group.
    Returns:
        groups: dict of {dir_name: [sorted list of absolute .md paths]}
        skipped: list of (path, reason) tuples
    """
    groups = {}
    skipped = []

    try:
        entries = sorted(os.listdir(source_dir))
    except OSError as e:
        print(f"Error reading source directory: {e}", file=sys.stderr)
        sys.exit(1)

    for entry in entries:
        entry_path = os.path.join(source_dir, entry)

        if not os.path.isdir(entry_path):
            continue

        if entry.startswith("."):
            skipped.append((entry_path, "dot directory"))
            continue

        if entry in SKIP_DIRS:
            skipped.append((entry_path, f"in skip list ({entry})"))
            continue

        md_files = []
        for fname in sorted(os.listdir(entry_path)):
            fpath = os.path.join(entry_path, fname)
            if not os.path.isfile(fpath):
                continue
            if not fname.endswith(".md"):
                skipped.append((fpath, "not a .md file"))
                continue
            md_files.append(fpath)

        if md_files:
            groups[entry] = md_files
        else:
            skipped.append((entry_path, "no .md files found"))

    return groups, skipped


def build_output_file(group_name, md_files, output_dir):
    """Concatenate md_files into <output_dir>/<group_name>.txt with slug dividers.

    Returns:
        (out_path, slugs): path to the written file and list of slugs in order.
    """
    out_path = os.path.join(output_dir, f"{group_name}.txt")
    slugs = []
    with open(out_path, "w", encoding="utf-8") as out_f:
        for md_path in md_files:
            slug = os.path.splitext(os.path.basename(md_path))[0]
            slugs.append(slug)
            out_f.write(f"\n=== {slug} ===\n\n")
            with open(md_path, "r", encoding="utf-8") as in_f:
                out_f.write(in_f.read())
    return out_path, slugs


INSTRUCTIONS_TEMPLATE = """\
You are a technical writing assistant for F5 documentation. Help contributors
write and revise content that meets the F5 Technical Writing Style Guide.

## Your knowledge base

Your knowledge base consists of these files, each covering a category of
style guidelines:

{file_inventory}

Each file contains topics separated by === topic-slug === markers. Search by
topic slug to find relevant guidance.

When you apply a rule, cite the exact topic slug -- the identifier between
the === markers (for example, active-voice, not "Active voice"). Only cite
topics from this list. Never invent a topic name. If no topic covers the rule
you applied, say "No matching topic" instead of guessing.

Valid topics:
{topic_list}

## How to respond

**Review** -- List style issues, the topic slug each violates, and a suggested fix.

**Copy edit** -- Return the revised text. After the text, list each change and
cite the topic slug it applies.

**Draft from notes** -- Ask clarifying questions if anything is unclear, then
write a draft. Identify whether the content is a task, concept, reference, or
troubleshooting topic and structure it accordingly.

## Always apply these rules

Apply all style guide topics consistently, including word list replacements,
grammar rules, and UI term conventions alongside voice and tone guidance. For
tone and voice, follow modern-voice:

- Focus on the customer question. One question = one topic with one answer.
- Give a concise answer. Lead with the 80% case. Cut edge cases and obvious details.
- Make it easy to scan. Put the most important thing first.
- Use normal, relaxed words. Write like you're talking to a colleague. Use contractions.
- Empathize. Never imply the user did something wrong. Acknowledge when a
  process is long or difficult.
- Flesch-Kincaid grade level 8-9: short sentences, plain words, avoid noun
  clusters, use second person, keep technical terms.
- Use active voice and present tense.
- Only apply rules from the style guide.

## Technical accuracy

Flag technical accuracy issues separately from style issues. Do not correct
them yourself -- ask the contributor to verify with a subject matter expert.
"""


def build_instructions_file(file_slugs, output_dir):
    """Write the agent instructions file to output_dir.

    Args:
        file_slugs: dict of {group_name: [slug, ...]} in the order they were written.
        output_dir: path to the output directory.

    Returns:
        Path to the written instructions file.
    """
    inventory_lines = []
    all_slugs = []

    for group_name, slugs in sorted(file_slugs.items()):
        slug_list = ", ".join(slugs)
        inventory_lines.append(f"- {group_name}.txt -- {slug_list}")
        all_slugs.extend(slugs)

    file_inventory = "\n".join(inventory_lines)
    topic_list = ", ".join(sorted(all_slugs))

    content = INSTRUCTIONS_TEMPLATE.format(
        file_inventory=file_inventory,
        topic_list=topic_list,
    )

    out_path = os.path.join(output_dir, "f5-tech-writer-agent-instructions.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


def main():
    args = parse_args()

    source_dir = os.path.abspath(args.source)
    output_dir = os.path.abspath(args.output)

    if not os.path.isdir(source_dir):
        print(f"Error: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    groups, skipped = collect_groups(source_dir)

    files_written = 0
    topic_counts = {}
    file_slugs = {}

    for group_name, md_files in sorted(groups.items()):
        _, slugs = build_output_file(group_name, md_files, output_dir)
        file_slugs[group_name] = slugs
        topic_counts[group_name] = len(md_files)
        files_written += 1

    instructions_path = build_instructions_file(file_slugs, output_dir)

    # Summary
    print(f"\nOutput directory: {output_dir}")
    print(f"Files written: {files_written}\n")

    if topic_counts:
        print("Topics per file:")
        for group_name, count in sorted(topic_counts.items()):
            print(f"  {group_name}.txt — {count} topic{'s' if count != 1 else ''}")

    print(f"\nInstructions file: {os.path.basename(instructions_path)}")

    if skipped:
        print("\nSkipped:")
        for path, reason in skipped:
            rel = os.path.relpath(path, source_dir)
            print(f"  {rel} — {reason}")


if __name__ == "__main__":
    main()
