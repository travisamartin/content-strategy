import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

def get_pages(base_url):
    # Recursively fetch all unique URLs under the given base URL.
    
    visited = set()  # To keep track of visited URLs
    to_visit = {base_url}  # Start with the base URL
    found_links = set()  # Store all matching links

    while to_visit:
        current_url = to_visit.pop()
        if current_url in visited:
            continue
        visited.add(current_url)

        # Skip logging the base URL itself
        if current_url != base_url:
            print(f"Visiting: {current_url}")

        try:
            # Fetch the page
            response = requests.get(current_url)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find all anchor tags with href attributes
            links = soup.find_all('a', href=True)

            for link in links:
                # Resolve relative URLs to absolute
                absolute_url = urljoin(current_url, link['href'])

                # Ensure the link is within the same domain and starts with the base path
                if absolute_url.startswith(base_url) and '#' not in absolute_url:
                    if absolute_url not in visited:
                        to_visit.add(absolute_url)
                    if absolute_url != base_url:
                        found_links.add(absolute_url)

        except Exception as e:
            print(f"Error visiting {current_url}: {e}")

    return sorted(found_links)

# Input the full path to scrape
base_url = input("Enter the full URL to scrape (e.g., https://docs.nginx.com/nginx/deployment-guides): ").strip()

# Get all pages under the specified URL
pages = get_pages(base_url)

# Print the results
print(f"\nAll pages under {base_url}:\n")
for page in pages:
    print(page)

# Save the results to a file
output_file = "found_pages.txt"
with open(output_file, "w") as file:
    file.write("\n".join(pages))
print(f"\nSaved the list of pages to {output_file}")