#!/usr/bin/env python3

"""
Merge multiple Dash docsets and search them with fzf.
"""

import contextlib
import logging
import sqlite3
import subprocess
import sys
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def merge_docsets(docsets: list[Path]) -> sqlite3.Connection:
    with sqlite3.connect(":memory:") as db:
        cursor = db.cursor().execute(
            "CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, docset TEXT, path TEXT);"
        )

        for docset in docsets:
            docset_db_path = docset / "Contents/Resources/docSet.dsidx"
            if not docset_db_path.exists():
                logging.warning("Database not found for docset: %s", docset)
                continue

            with contextlib.closing(
                sqlite3.connect(f"file:{docset_db_path}?mode=ro", uri=True)
            ) as docset_db:
                try:
                    docset_cursor = docset_db.cursor().execute(
                        "SELECT name, type, path FROM searchIndex"
                    )

                except sqlite3.OperationalError:
                    docset_cursor = docset_db.cursor().execute(
                        """
                        SELECT ztokenname                               AS name,
                        ztypename                                       AS type,
                        zpath || ifnull('#' || nullif(zanchor, ''), '') AS url
                        FROM ztoken
                        JOIN ztokenmetainformation
                            ON ztokenmetainformation.z_pk = ztoken.zmetainformation
                        JOIN zfilepath
                            ON zfilepath.z_pk = ztokenmetainformation.zfile
                        JOIN ztokentype
                            ON ztokentype.z_pk = ztoken.ztokentype
                        """
                    )

                rows: list[tuple[str, str, str]] = docset_cursor.fetchall()

                for name, entry_type, path in rows:
                    # https://github.com/jmymay/zealcore/commit/7a04435f65876bc5c9bb4c663e1aa3ef96197190
                    path = re.sub(r"<dash_entry_.*>", "", path)
                    prefixed_path = (
                        # This is necessary because path could start with a leading /
                        f"{str(docset / 'Contents/Resources/Documents') + '/' + path}"
                    )
                    cursor = cursor.execute(
                        "INSERT INTO searchIndex (name, type, docset, path) VALUES (?, ?, ?, ?)",
                        (name, entry_type, str(docset.stem), str(prefixed_path)),
                    )

        return db


def launch_fzf(db: sqlite3.Connection) -> str | None:
    rows: list[tuple[str, str, str, str]] = (
        db.cursor()
        .execute("SELECT name, type, docset, path FROM searchIndex")
        .fetchall()
    )
    fzf_input = "\n".join(
        f"{name} ({entry_type}, {docset})\t{path}"
        for name, entry_type, docset, path in rows
    )

    try:
        fzf_process = subprocess.run(
            [
                "fzf",
                "--with-nth",
                "1",
                "--delimiter",
                "\t",
                "--accept-nth",
                "-1",
                "--bind",
                "enter:execute(w3m '{-1}')",
                "--bind",
                "ctrl-v:execute(echo '{-1}')+abort",
            ],
            input=fzf_input,
            capture_output=True,
            text=True,
            check=False,
        )

        # Exit code 130 means FZF was interrupted with Esc or Ctrl-C
        if fzf_process.returncode == 130:
            return None

        if fzf_process.returncode != 0:
            logging.error(
                "FZF failed to run with exit code: %d", fzf_process.returncode
            )
            sys.exit(fzf_process.returncode)

        if selected_line := fzf_process.stdout.strip():
            return selected_line
    except FileNotFoundError:
        logging.error("FZF is not installed.")

    return None


def main() -> None:
    if len(sys.argv) < 2:
        logging.error("Usage: %s <docset1> <docset2> ...", sys.argv[0])
        sys.exit(1)

    docsets = [
        Path(arg) for arg in sys.argv[1:] if arg.removesuffix("/").endswith(".docset")
    ]

    if not docsets:
        logging.error("No docsets provided.")
        sys.exit(1)

    with contextlib.closing(merge_docsets(docsets)) as db:
        if selected_path := launch_fzf(db):
            print(selected_path)
            sys.exit(0)

        sys.exit(1)


if __name__ == "__main__":
    main()
