import os
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

# --------- configure these ---------
BASE_URL = "https://f5.co1.qualtrics.com"
SURVEY_ID = "SV_38eQwDFmNLZvIvc"
FILTER_ID = "dd4e3666-f138-4ccc-901f-16a40146a16f"  # set to None to export without filter
OUTPUT_BASENAME = "survey_export_filtered"          # no extension
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300
# -----------------------------------

API_TOKEN = os.environ.get("QUALTRICS_API_TOKEN")


def get_headers():
    if not API_TOKEN:
        raise RuntimeError("QUALTRICS_API_TOKEN is not set in the environment")
    return {
        "X-API-TOKEN": API_TOKEN,
        "Content-Type": "application/json",
    }


def start_export():
    url = f"{BASE_URL}/API/v3/surveys/{SURVEY_ID}/export-responses"
    body = {"format": "csv"}
    if FILTER_ID:
        body["filterId"] = FILTER_ID

    resp = requests.post(url, headers=get_headers(), json=body)
    resp.raise_for_status()
    data = resp.json()
    progress_id = data["result"]["progressId"]
    print(f"Started export. progressId={progress_id}")
    return progress_id


def wait_for_completion(progress_id):
    url = f"{BASE_URL}/API/v3/surveys/{SURVEY_ID}/export-responses/{progress_id}"
    start = time.time()

    while True:
        resp = requests.get(url, headers=get_headers())
        resp.raise_for_status()
        data = resp.json()["result"]

        status = data.get("status")
        percent = data.get("percentComplete")
        file_id = data.get("fileId")

        print(f"Status={status}, percentComplete={percent}, fileId={file_id}")

        if status == "complete" and file_id:
            return file_id

        if status == "failed":
            raise RuntimeError(f"Export failed: {data}")

        if time.time() - start > POLL_TIMEOUT_SECONDS:
            raise TimeoutError("Timed out waiting for export to complete")

        time.sleep(POLL_INTERVAL_SECONDS)


def download_file(file_id, output_path: Path):
    url = f"{BASE_URL}/API/v3/surveys/{SURVEY_ID}/export-responses/{file_id}/file"
    with requests.get(url, headers=get_headers(), stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"Downloaded to {output_path}")


def extract_csv(download_path: Path) -> Path:
    """
    Try to treat the downloaded file as a zip.
    If it is a zip, extract the first CSV file.
    If not, assume it is already a CSV.
    """
    try:
        with zipfile.ZipFile(download_path, "r") as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not csv_names:
                raise RuntimeError("Zip file does not contain any .csv members")
            csv_name = csv_names[0]
            extracted_path = download_path.with_suffix(".csv")
            with zf.open(csv_name) as src, open(extracted_path, "wb") as dst:
                dst.write(src.read())
            print(f"Extracted {csv_name} to {extracted_path}")
            return extracted_path
    except zipfile.BadZipFile:
        print("Download is not a zip file. Treating it as CSV.")
        csv_path = download_path
        if csv_path.suffix.lower() != ".csv":
            new_path = csv_path.with_suffix(".csv")
            csv_path.rename(new_path)
            csv_path = new_path
            print(f"Renamed download to {csv_path}")
        return csv_path


def convert_csv_to_xlsx(csv_path: Path, xlsx_path: Path):
    print(f"Converting {csv_path} to {xlsx_path}")

    # First CSV row is header row
    df = pd.read_csv(csv_path, header=0)

    # Excel:
    #   row 1  = technical headers (StartDate, EndDate, ...)
    #   row 2  = human friendly labels (Start Date, End Date, ...)
    #   row 3  = ImportId metadata row we want to remove
    # After read_csv(header=0):
    #   index 0 = row 2
    #   index 1 = row 3 (ImportId row)
    if len(df) > 1:
        row1 = df.iloc[1].astype(str)
        if row1.str.contains("ImportId").any():
            df = df.drop(index=1)

    df.to_excel(xlsx_path, index=False)
    print("Conversion complete.")


def main():
    out_dir = Path.cwd()
    zip_path = out_dir / f"{OUTPUT_BASENAME}.zip"
    xlsx_path = out_dir / f"{OUTPUT_BASENAME}.xlsx"

    progress_id = start_export()
    file_id = wait_for_completion(progress_id)
    print(f"Export complete. fileId={file_id}")

    download_file(file_id, zip_path)
    csv_path = extract_csv(zip_path)
    convert_csv_to_xlsx(csv_path, xlsx_path)

    print(f"Done. XLSX written to {xlsx_path}")


if __name__ == "__main__":
    main()