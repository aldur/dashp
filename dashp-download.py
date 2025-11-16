#!/usr/bin/env python3

"""
Download Dash docsets interactively using fzf.
"""

import http.client
import json
import logging
import subprocess
import sys
import tarfile
from pathlib import Path
from typing import cast

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def fetch_available_docsets() -> list[str]:
    """Fetch available docset names from Kapeli feeds repository."""
    try:
        conn = http.client.HTTPSConnection("api.github.com")
        headers = {"User-Agent": "dashp-download/1.0"}
        conn.request("GET", "/repos/Kapeli/feeds/git/trees/master", headers=headers)
        response = conn.getresponse()

        if response.status != 200:
            logging.error("Failed to fetch docsets: HTTP %d", response.status)
            return []

        response_data = response.read()
        conn.close()

        data: dict[str, object] = cast(dict[str, object], json.loads(response_data))

        # Extract .xml files (these are the docset feed files)
        docsets: list[str] = []
        tree = cast(list[dict[str, object]], data.get("tree", []))
        for item in tree:
            item_type = cast(str, item.get("type", ""))
            item_path = cast(str, item.get("path", ""))
            if item_type == "blob" and item_path.endswith(".xml"):
                # Remove .xml extension to get docset name
                docset_name = item_path[:-4]
                docsets.append(docset_name)

        return sorted(docsets)
    except Exception as e:
        logging.error("Failed to fetch docsets: %s", e)
        return []


def select_docsets_with_fzf(docsets: list[str]) -> list[str]:
    """Display docsets in FZF and return selected ones."""
    if not docsets:
        return []

    fzf_input = "\n".join(docsets)

    try:
        fzf_process = subprocess.run(
            [
                "fzf",
                "--multi",
                "--prompt",
                "Select docsets to download: ",
            ],
            input=fzf_input,
            capture_output=True,
            text=True,
            check=False,
        )

        # Exit code 130 means FZF was interrupted with Esc or Ctrl-C
        if fzf_process.returncode == 130:
            sys.exit(0)

        if fzf_process.returncode != 0:
            logging.error(
                "FZF failed to run with exit code: %d", fzf_process.returncode
            )
            return []

        selected = [
            line.strip()
            for line in fzf_process.stdout.strip().split("\n")
            if line.strip()
        ]
        return selected
    except FileNotFoundError:
        logging.error("FZF is not installed. Please install FZF to use this script.")
        return []


def download_docset(docset_name: str, target_dir: Path) -> bool:
    """Download a docset to the target directory."""
    target_file = target_dir / f"{docset_name}.tgz"

    logging.info("Downloading %s...", docset_name)

    try:
        # Download the file with progress tracking
        conn = http.client.HTTPSConnection("kapeli.com")
        conn.request("GET", f"/feeds/{docset_name}.tgz")
        response = conn.getresponse()

        if response.status != 200:
            logging.error(
                "Failed to download %s: HTTP %d", docset_name, response.status
            )
            conn.close()
            return False

        content_length = response.getheader("Content-Length")
        total_size = int(content_length) if content_length is not None else 0

        with open(target_file, "wb") as f:
            if total_size > 0:
                # Show progress for larger files
                downloaded = 0
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    _ = f.write(chunk)
                    downloaded += len(chunk)
                    percent = (downloaded / total_size) * 100
                    print(f"\r  Progress: {percent:.1f}%", end="", file=sys.stderr)
                print(file=sys.stderr)  # New line after progress
            else:
                # No size info, just read all
                _ = f.write(response.read())

        conn.close()

        # Extract the tarball
        logging.info("Extracting %s...", docset_name)
        with tarfile.open(target_file, "r:gz") as tar:
            tar.extractall(path=target_dir, filter="data")

        # Remove the tarball
        target_file.unlink()

        logging.info("Successfully installed %s", docset_name)
        return True

    except Exception as e:
        logging.error("Failed to install %s: %s", docset_name, e)
        if target_file.exists():
            target_file.unlink()
        return False


def main() -> None:
    if len(sys.argv) < 2:
        logging.error("Usage: %s <target_directory>", sys.argv[0])
        sys.exit(1)

    docset_dir = Path(sys.argv[1])

    if not docset_dir.exists():
        logging.error("Directory does not exist: %s", docset_dir)
        sys.exit(1)

    if not docset_dir.is_dir():
        logging.error("Path is not a directory: %s", docset_dir)
        sys.exit(1)

    logging.info("Fetching available docsets...")
    docsets = fetch_available_docsets()

    if not docsets:
        logging.error("No docsets found or failed to fetch.")
        sys.exit(1)

    logging.info("Found %d docsets", len(docsets))

    selected = select_docsets_with_fzf(docsets)

    if not selected:
        logging.info("No docsets selected.")
        sys.exit(0)

    success_count = 0
    for docset_name in selected:
        if download_docset(docset_name, docset_dir):
            success_count += 1

    logging.info("Downloaded %d of %d selected docsets", success_count, len(selected))
    sys.exit(0 if success_count == len(selected) else 1)


if __name__ == "__main__":
    main()
