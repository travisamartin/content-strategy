import os
import csv
import sys
from markdown2 import markdown
from bs4 import BeautifulSoup
import textstat

def render_markdown_to_text(md_content):
    # Convert markdown to HTML.
    html = markdown(md_content)
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove code blocks.
    for pre in soup.find_all('pre'):
        pre.decompose()
    
    return soup.get_text()

def process_directory(root_dir, output_csv="reading_levels.csv"):
    # Prepare header and results list.
    rows = [["file_path", "reading_level"]]
    
    # Walk through directory and subdirectories.
    for root, _, files in os.walk(root_dir):
        for file in files:
            # Skip files named _index.md.
            if file.endswith(".md") and file.lower() != "_index.md":
                file_path = os.path.join(root, file)
                print(f"Processing {file_path}...")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        md_content = f.read()
                except Exception as e:
                    error_message = f"Error reading {file_path}: {e}"
                    print(error_message)
                    rows.append([file_path, error_message])
                    continue
                
                # Render markdown to text for an accurate evaluation.
                text = render_markdown_to_text(md_content)
                
                # Calculate the Flesch-Kincaid reading level.
                try:
                    reading_level = textstat.flesch_kincaid_grade(text)
                    print(f"Finished {file_path}. Reading level: {reading_level}")
                except Exception as e:
                    reading_level = f"Error calculating reading level: {e}"
                    print(reading_level)
                
                # Append the result.
                rows.append([file_path, reading_level])
    
    # Write results to CSV.
    try:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(rows)
        print(f"Output written to {output_csv}")
    except Exception as e:
        print(f"Error writing CSV file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reading_level.py <directory>")
    else:
        process_directory(sys.argv[1])