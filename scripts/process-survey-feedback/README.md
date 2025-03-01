## Script Description

This script cleans and transforms an Excel file for use in Tableau. It performs these steps:

1. Loads the file with no header and uses the first row as column headers.  
2. Removes a duplicate or subheading row if found.  
3. Removes rows where the “Link URL” column is missing.  
4. Removes rows where the “Q2” column contains the word “testing.”  
5. Cleans URLs by removing anchor fragments and adding a trailing slash.  
6. Reverse-geocodes latitude and longitude into Country, City, and State columns (in US English).  
7. Writes the cleaned data to a new Excel file named “Survey Data.”  

## Requirements

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
2. Run the script in a terminal:

```bash
python process_survey_feedback_new.py "/path/to/NGINX Article Effectiveness Survey.xlsx" -o "/path/to/cleaned_data.xlsx"
```

- `/path/to/NGINX Article Effectiveness Survey.xlsx` is the path to your input file.
- `-o /path/to/cleaned_data.xlsx` is the path to your cleaned output file.

## Notes

- The script uses the OpenStreetMap [Nominatim](https://nominatim.org/) service for reverse geocoding. That service has usage limits and may block your requests if you send them too quickly.
- We added a rate limiter to stay below one request per second. If you have a large dataset, consider adding more delay or using a different geocoding service with higher rate limits.
- Check `cleanup_log.txt` for detailed logs. You’ll see information about removed rows, URL changes, and geocoding results.