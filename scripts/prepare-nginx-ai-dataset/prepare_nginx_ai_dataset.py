#!/usr/bin/env python3
"""
Prepare an AI-ready NGINX documentation feedback dataset.

Input file must contain:
  - Canonical Link URL
  - Q1
  - Q2
  - StartDate

Output file (default):
  nginx_ai_dataset.xlsx

One row per URL including:
  - Canonical Link URL
  - Product
  - avg_q1 (rounded)
  - n (# of ratings)
  - q2_comments (verbatims concatenated using "|||")
"""

import argparse
from pathlib import Path
import pandas as pd


URL_COL = "Canonical Link URL"
Q1_COL = "Q1"
Q2_COL = "Q2"
DATE_COL = "StartDate"
DELIMITER = "|||"


# ---------- PRODUCT MAPPING ----------
def map_product(url: str) -> str:
    if not isinstance(url, str):
        return "Unknown"

    url = url.strip()

    mapping = [
        ("https://docs.nginx.com/nginx-instance-manager/", "NGINX Instance Manager (NIM)"),
        ("https://docs.nginx.com/nginx-one-console/", "NGINX One Console (N1C)"),
        ("https://docs.nginx.com/nginx-ingress-controller/", "NGINX Ingress Controller (NIC)"),
        ("https://docs.nginx.com/nginx-gateway-fabric/", "NGINX Gateway Fabric (NGF)"),
        ("https://docs.nginx.com/nginx-agent/", "NGINX Agent"),
        ("https://docs.nginx.com/nginx-app-protect-dos/", "NGINX App Protect DoS"),
        ("https://docs.nginx.com/nginxaas/azure/", "NGINXaaS Azure"),
        ("https://docs.nginx.com/nginxaas/google/", "NGINXaaS Google"),
        ("https://docs.nginx.com/solutions/", "Subscription Licensing"),
        ("https://docs.nginx.com/waf/", "F5 WAF for NGINX"),
        ("https://docs.nginx.com/nginx-service-mesh/", "NGINX Service Mesh"),
        ("https://docs.nginx.com/nginx-unit/", "NGINX Unit"),
        ("https://docs.nginx.com/nginx-amplify/", "NGINX Amplify"),
        ("https://docs.nginx.com/glossary/", "Glossary"),
        ("https://docs.nginx.com/nginx/", "NGINX (OSS/Plus)"),
    ]

    for prefix, product in mapping:
        if url.startswith(prefix):
            return product

    return "Unknown"


# ---------- BUILD DATASET ----------
def build_ai_dataset(input_path: Path, output_path: Path) -> None:
    df = pd.read_excel(input_path)

    required_cols = [URL_COL, Q1_COL, Q2_COL, DATE_COL]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required column(s): {missing}")

    slim = df[[URL_COL, Q1_COL, Q2_COL, DATE_COL]].copy()
    slim["Date"] = pd.to_datetime(slim[DATE_COL], errors="coerce")
    slim = slim.dropna(subset=["Date", Q1_COL])

    slim[URL_COL] = slim[URL_COL].astype(str).str.strip()
    slim["Product"] = slim[URL_COL].apply(map_product)

    grouped = (
        slim.groupby([URL_COL, "Product"], dropna=False)
            .agg(
                avg_q1=(Q1_COL, "mean"),
                n=(Q1_COL, "count"),
                q2_comments=(Q2_COL, lambda s: DELIMITER.join(str(x) for x in s.dropna()))
            )
            .reset_index()
    )

    grouped["avg_q1"] = grouped["avg_q1"].round(2)

    grouped.to_excel(output_path, index=False)
    print(f"✔ File created: {output_path}")
    print(f"✔ Rows: {len(grouped)}")
    print(f"✔ Columns: {list(grouped.columns)}")


# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Generate nginx_ai_dataset.xlsx for Copilot analysis")
    parser.add_argument("input_file", help="Path to cleaned Qualtrics export (xlsx)")
    parser.add_argument("-o", "--output", help="Output filename (default: nginx_ai_dataset.xlsx)")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output) if args.output else input_path.with_name("nginx_ai_dataset.xlsx")

    build_ai_dataset(input_path, output_path)


if __name__ == "__main__":
    main()