# Script Description

This script cleans and transforms an Excel file for use in Tableau. It performs the following steps:

1. Loads the file with no header and uses the first row as column headers.  
2. Removes a duplicate or subheading row if found.  
3. Removes rows where the “Link URL” column is missing.  
4. Removes rows where the “Q2” column contains the word “testing.”  
5. Cleans URLs by removing anchor fragments and adding a trailing slash, and replaces any occurrence of  
   `https://docs.nginx.com/nginxaas-azure/known-issues/` with  
   `https://docs.nginx.com/nginxaas/azure/known-issues/`.  
6. Excludes bogus responses based on ResponseIDs listed in an external exclude file.  
7. Scrubs email addresses from the “Q2” column, replacing them with an empty string.  
8. Optionally reverse-geocodes latitude and longitude into Country, City, and State columns (in US English).  
9. Writes the cleaned data to a new Excel file with a worksheet named “Survey Data.”

# Requirements

Install the following Python packages:

```text
et_xmlfile==2.0.0
numpy==2.2.2
openpyxl==3.1.5
pandas==2.2.3
python-dateutil==2.9.0.post0
pytz==2024.2
six==1.17.0
tzdata==2025.1
geopy==2.3.0
```

Use a virtual environment or another Python environment manager if you want to keep dependencies isolated.

## Usage

1. Place your Excel file in a known location.
2. Prepare a text file containing bogus ResponseIDs to exclude (one per line).
3. Run the script in a terminal:

   ```shell
   python process_survey_feedback_new.py "/path/to/NGINX Article Effectiveness Survey.xlsx" -o "/path/to/cleaned_data.xlsx" --exclude-file "/path/to/excluded-responses.txt" [--geocode]
   ```

   - `/path/to/NGINX Article Effectiveness Survey.xlsx` is the path to your input file.
   - `-o /path/to/cleaned_data.xlsx` is the path to your cleaned output file.
   - `--exclude-file /path/to/excluded-responses.txt` is the path to a text file containing ResponseIDs to exclude.
   - The `--geocode` flag enables reverse geocoding; it is disabled by default.

# Notes

- The script uses the OpenStreetMap [Nominatim](https://nominatim.org/) service for reverse geocoding. This service has usage limits and may block your requests if you send them too quickly.
- A rate limiter is included to stay below one request per second. If you have a large dataset, consider adding more delay or using a different geocoding service with higher rate limits.
- The script scrubs email addresses from the “Q2” column to remove personally identifiable information (PII).
- Bogus responses are excluded based on ResponseIDs read from an external text file. Plain text is used here for simplicity, though a CSV file could be used if additional metadata is needed later.
- Check `cleanup_log.txt` for detailed logs, including which rows and ResponseIDs were removed, URL changes, email scrubbing, and geocoding results.