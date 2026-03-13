#!/usr/bin/env python3
"""
Android Bench Results Downloader

This script downloads and extracts compiled model results from the Android Bench
GitHub release directly to the specified directory.

Usage:
  python3 download_results.py --models gemini-3.1-pro-preview claude-opus-4-5
  python3 download_results.py --models all
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path
from urllib.error import HTTPError


def fetch_release_assets(org, repo, tag):
    """Fetches the list of assets available in the release via GitHub API."""
    api_url = f"https://api.github.com/repos/{org}/{repo}/releases/tags/{tag}"
    print(f"Fetching release information for {org}/{repo} @ {tag}...")
    req = urllib.request.Request(api_url)
    req.add_header("Accept", "application/vnd.github.v3+json")

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return data.get("assets", [])
    except HTTPError as e:
        print(f"Error fetching release: HTTP {e.code} - {e.reason}")
        print("Please verify the repository name, organization, and release tag.")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to fetch release information: {e}")
        sys.exit(1)


def download_file(url, dest_path, filename):
    """Downloads a file with a simple progress indicator."""
    print(f"Downloading {filename}...")
    try:
        urllib.request.urlretrieve(url, dest_path)
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
        sys.exit(1)


def assemble_and_extract(model_name, parts, target_dir):
    """Assembles chunked tar.gz parts and extracts them."""
    print(f"\nExtracting {model_name}...")

    # Sort parts alphabetically to ensure correct assembly order
    parts.sort()

    # Create a temporary file to hold the assembled tar.gz
    temp_tar_path = Path(target_dir) / f"{model_name}_assembled.tar.gz"

    try:
        # Assemble
        with open(temp_tar_path, "wb") as outfile:
            for part in parts:
                print(f"  Reading {os.path.basename(part)}...")
                with open(part, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)

        # Extract
        print(f"  Unpacking archive...")
        with tarfile.open(temp_tar_path, "r:gz") as tar:
            tar.extractall(path=target_dir)

        print(f"✓ Successfully extracted {model_name} to {target_dir}")

    except Exception as e:
        print(f"Error during assembly or extraction for {model_name}: {e}")
    finally:
        # Cleanup assembled tar and parts
        if temp_tar_path.exists():
            temp_tar_path.unlink()
        for part in parts:
            Path(part).unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Download Android Bench model results."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="List of models to download (e.g., gemini-3.1-pro-preview), or 'all' to download everything.",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="Target directory to extract the results into. Defaults to current directory.",
    )
    parser.add_argument(
        "--org", type=str, default="android-bench", help="GitHub organization."
    )
    parser.add_argument(
        "--repo", type=str, default="results", help="GitHub repository."
    )
    parser.add_argument("--tag", type=str, default="v1.0.0", help="Release tag.")
    args = parser.parse_args()

    assets = fetch_release_assets(args.org, args.repo, args.tag)
    if not assets:
        print("No assets found in the release.")
        sys.exit(1)

    target_dir = Path(args.dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    downloaded_parts_by_model = {}
    models_to_fetch = set(args.models)
    download_all = "all" in [m.lower() for m in models_to_fetch]

    total_downloaded = 0

    for asset in assets:
        name = asset["name"]
        download_url = asset["browser_download_url"]

        # Asset format: {model_name}.tar.gz or {model_name}.tar.gz.part_aa
        if ".tar.gz" not in name:
            continue

        model_name = name.split(".tar.gz")[0]

        if not download_all and model_name not in models_to_fetch:
            continue

        # Register model for assembly
        if model_name not in downloaded_parts_by_model:
            downloaded_parts_by_model[model_name] = []

        dest_path = target_dir / name
        download_file(download_url, dest_path, name)
        downloaded_parts_by_model[model_name].append(str(dest_path))
        total_downloaded += 1

    if total_downloaded == 0:
        print("\nNo matching models found in the release assets.")
        print("Available models in release:")
        available = list(
            set(
                [
                    a["name"].split(".tar.gz")[0]
                    for a in assets
                    if ".tar.gz" in a["name"]
                ]
            )
        )
        for m in sorted(available):
            print(f"  - {m}")
        sys.exit(1)

    # Process each model
    for model_name, parts in downloaded_parts_by_model.items():
        assemble_and_extract(model_name, parts, target_dir)


if __name__ == "__main__":
    main()
