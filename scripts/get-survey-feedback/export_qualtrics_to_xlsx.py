import os
import time
import zipfile
import argparse
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://f5.co1.qualtrics.com"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300

API_TOKEN = os.environ.get("QUALTRICS_API_TOKEN")


def get_headers():
    if not API_TOKEN:
        raise RuntimeError("QUALTRICS_API_TOKEN is not set")
    return {
        "X-API-TOKEN": API_TOKEN,
        "Content-Type": "application/json",
    }


def start_export(survey_id: str, filter_id: str | None) -> str:
    url = f"{BASE_URL}/API/v3/surveys/{survey_id}/export-responses"
    body = {"format": "csv"}
    if filter_id:
        body["filterId"] = filter_id

    resp = requests.post(url, headers=get_headers(), json=body)
    resp.raise_for_status()
    progress_id = resp.json()["result"]["progressId"]
    print(f"[{survey_id}] Started export (progressId={progress_id})")
    return progress_id


def wait_for_completion(survey_id: str, progress_id: str) -> str:
    url = f"{BASE_URL}/API/v3/surveys/{survey_id}/export-responses/{progress_id}"
    start = time.time()

    while True:
        resp = requests.get(url, headers=get_headers())
        resp.raise_for_status()
        result = resp.json()["result"]

        status = result.get("status")
        percent = result.get("percentComplete")
        file_id = result.get("fileId")

        print(f"[{survey_id}] Status={status}, percentComplete={percent}")

        if status == "complete" and file_id:
            return file_id

        if status == "failed":
            raise RuntimeError(f"[{survey_id}] Export failed")

        if time.time() - start > POLL_TIMEOUT_SECONDS:
            raise TimeoutError(f"[{survey_id}] Export timed out")

        time.sleep(POLL_INTERVAL_SECONDS)


def download_file(survey_id: str, file_id: str, output_path: Path):
    url = f"{BASE_URL}/API/v3/surveys/{survey_id}/export-responses/{file_id}/file"
    with requests.get(url, headers=get_headers(), stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"[{survey_id}] Downloaded to {output_path}")


def extract_csv(download_path: Path) -> Path:
    try:
        with zipfile.ZipFile(download_path, "r") as zf:
            csv_files = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            csv_name = csv_files[0]
            csv_path = download_path.with_suffix(".csv")
            with zf.open(csv_name) as src, open(csv_path, "wb") as dst:
                dst.write(src.read())
            return csv_path
    except zipfile.BadZipFile:
        if download_path.suffix.lower() != ".csv":
            csv_path = download_path.with_suffix(".csv")
            download_path.rename(csv_path)
            return csv_path
        return download_path


def convert_csv_to_xlsx(csv_path: Path, xlsx_path: Path):
    df = pd.read_csv(csv_path, header=0)

    # Remove ImportId metadata row (Excel row 3 → pandas index 1)
    if len(df) > 1:
        row1 = df.iloc[1].astype(str)
        if row1.str.contains("ImportId").any():
            df = df.drop(index=1)

    df.to_excel(xlsx_path, index=False)
    print(f"Converted to {xlsx_path}")


def process_survey(
    survey_id: str,
    filter_id: str | None,
    explicit_xlsx: Path | None,
    out_dir: Path,
):
    if explicit_xlsx:
        xlsx_path = explicit_xlsx.expanduser().resolve()
        xlsx_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path = xlsx_path.with_suffix(".zip")
    else:
        base = f"{survey_id}_export"
        zip_path = out_dir / f"{base}.zip"
        xlsx_path = out_dir / f"{base}.xlsx"

    progress_id = start_export(survey_id, filter_id)
    file_id = wait_for_completion(survey_id, progress_id)
    download_file(survey_id, file_id, zip_path)
    csv_path = extract_csv(zip_path)
    convert_csv_to_xlsx(csv_path, xlsx_path)


def parse_triplet(value: str):
    parts = value.split(":", 2)

    survey_id = parts[0]
    filter_id = None
    output_path = None

    if len(parts) >= 2 and parts[1]:
        filter_id = parts[1]

    if len(parts) == 3 and parts[2]:
        output_path = Path(parts[2])

    return survey_id, filter_id, output_path


def main():
    parser = argparse.ArgumentParser(
        description="Export Qualtrics surveys to XLSX (survey[:filter[:output]])"
    )
    parser.add_argument(
        "triplets",
        nargs="+",
        help="SurveyID[:FilterID[:/path/to/output.xlsx]]",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=".",
        help="Default output directory (ignored if explicit output path is provided)",
    )

    args = parser.parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    for value in args.triplets:
        survey_id, filter_id, output_path = parse_triplet(value)
        process_survey(survey_id, filter_id, output_path, out_dir)


if __name__ == "__main__":
    main()  