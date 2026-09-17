#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Multi-Account Deployment Utility for Kaggle Kaggriculture.

Supports deploying directly to either account:
  - gaurav065  (Primary Grandmaster Ladder Account)
  - gaurav06520 (Secondary Deployment Port & Counter-Tape Explorer)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi

ROOT = Path(__file__).resolve().parent
PORTS_FILE = ROOT / "kaggle_deployment_ports.json"

if not PORTS_FILE.exists():
    PORTS_FILE = ROOT.parent / "kaggriculture_architecture" / "kaggle_deployment_ports.json"

assert PORTS_FILE.exists(), f"Missing deployment ports file: {PORTS_FILE}"

with open(PORTS_FILE, "r", encoding="utf-8") as f:
    PORTS_DATA = json.load(f)["accounts"]

def deploy(account_name, file_path=None, description=None):
    if account_name not in PORTS_DATA:
        print(f"Error: Unknown account '{account_name}'. Available: {list(PORTS_DATA.keys())}")
        sys.exit(1)

    account_info = PORTS_DATA[account_name]
    token = account_info["token"]
    username = account_info["username"]

    # Locate package to deploy
    if not file_path:
        candidates = [
            ROOT / "submission.tar.gz",
            ROOT.parent / "kaggriculture_architecture" / "submission.tar.gz",
            ROOT / "discovered_tapes.json"
        ]
        for c in candidates:
            if c.exists() and c.suffix in (".gz", ".py"):
                file_path = c
                break

    if not file_path or not Path(file_path).exists():
        print(f"Error: Submission package not found. Looked in: {file_path}")
        sys.exit(1)

    file_path = Path(file_path).resolve()
    print("=" * 75)
    print(f"DEPLOYING TO KAGGLE: [{username.upper()}]")
    print(f"Purpose: {account_info.get('purpose', 'N/A')}")
    print(f"Package: {file_path.name} ({file_path.stat().st_size:,} bytes)")
    print("=" * 75)

    # Authenticate
    os.environ["KAGGLE_API_TOKEN"] = token
    api = KaggleApi()
    api.authenticate()

    authenticated_user = api.get_config_value("username")
    assert authenticated_user == username, f"Auth mismatch! Expected {username}, got {authenticated_user}"
    print(f"Authentication verified for: {authenticated_user}")

    # Set message
    msg = description or f"Apex Grandmaster Automated Deploy via M3 [{username}] - {file_path.name}"
    print(f"Submission Message: '{msg}'")

    # Submit
    res = api.competition_submit(
        file_name=str(file_path),
        message=msg,
        competition="kaggriculture"
    )
    print("\nAPI Response:", res)
    print("Waiting 10 seconds for Kaggle to ingest...")
    time.sleep(10)

    subs = api.competition_submissions("kaggriculture")
    latest = subs[0]
    print("\n" + "=" * 75)
    print("SUBMISSION CONFIRMED ON LADDER:")
    print(f"  Submission ID : {latest.ref}")
    print(f"  Account       : {username}")
    print(f"  Timestamp     : {latest.date}")
    print(f"  Status        : {latest.status}")
    print(f"  Initial Score : {latest.public_score}")
    print("=" * 75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaggle Deployment Port Runner")
    parser.add_argument("--account", type=str, required=True, choices=["gaurav065", "gaurav06520"], help="Account to deploy to")
    parser.add_argument("--file", type=str, default=None, help="Path to submission.tar.gz or submission.py")
    parser.add_argument("--message", type=str, default=None, help="Submission description")
    args = parser.parse_args()

    deploy(args.account, args.file, args.message)
