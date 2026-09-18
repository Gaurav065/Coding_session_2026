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
import requests

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
            ROOT / "submission.py",
            ROOT / "submission.tar.gz",
        ]
        for c in candidates:
            if c.exists() and c.suffix in (".py", ".gz"):
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

    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Request upload URL and blob token
    content_length = file_path.stat().st_size
    last_modified = int(file_path.stat().st_mtime)
    file_name = file_path.name

    url_endpoint = f"https://www.kaggle.com/api/v1/competitions/kaggriculture/submissions/url/{content_length}/{last_modified}"
    print("1. Requesting upload URL from Kaggle...")
    r_url = requests.post(url_endpoint, headers=headers, data={"fileName": file_name}, timeout=30)
    if r_url.status_code != 200:
        print(f"Error requesting upload URL: {r_url.status_code} {r_url.text}")
        sys.exit(1)

    upload_data = r_url.json()
    upload_token = upload_data["token"]
    create_url = upload_data["createUrl"]
    print(f"   Upload token received: {upload_token[:24]}...")

    # Step 2: Upload file content to Google Cloud Storage
    print(f"2. Uploading {file_name} ({content_length:,} bytes)...")
    with open(file_path, "rb") as fp:
        upload_headers = {
            "Content-Length": str(content_length),
            "Content-Range": f"bytes 0-{content_length - 1}/{content_length}",
        }
        r_upload = requests.put(create_url, data=fp, headers=upload_headers, timeout=60)
        if r_upload.status_code not in (200, 201):
            print(f"Error uploading file content: {r_upload.status_code} {r_upload.text}")
            sys.exit(1)
    print("   File payload upload successful!")

    # Step 3: Register submission with competition
    msg = description or f"Modular Apex Grandmaster [{username}] - {file_path.name}"
    print(f"3. Registering submission with competition: '{msg}'...")
    submit_url = "https://www.kaggle.com/api/v1/competitions/submissions/submit/kaggriculture"
    r_sub = requests.post(submit_url, headers=headers, data={
        "blobFileTokens": upload_token,
        "submissionDescription": msg
    }, timeout=30)
    if r_sub.status_code != 200:
        print(f"Error submitting to competition: {r_sub.status_code} {r_sub.text}")
        sys.exit(1)
    print("   Submission registered successfully!")

    # Step 4: Monitor status and verify on leaderboard
    print("\n4. Polling submission status...")
    for attempt in range(1, 7):
        time.sleep(5)
        list_url = "https://www.kaggle.com/api/v1/competitions/submissions/list/kaggriculture"
        r_list = requests.get(list_url, headers=headers, timeout=30)
        if r_list.status_code == 200:
            subs = r_list.json()
            if subs:
                latest = subs[0]
                status = latest.get("status")
                print(f"   [Poll {attempt}/6] Status: {status} | Ref: {latest.get('ref')}")
                if status in ("complete", "error", "failed", "successful"):
                    break
        else:
            print(f"   [Poll {attempt}/6] Warning: Failed to query status ({r_list.status_code})")

    print("\n" + "=" * 75)
    print("SUBMISSION VERIFICATION SUMMARY:")
    if subs:
        latest = subs[0]
        print(f"  Submission ID : {latest.get('ref')}")
        print(f"  Account       : {username}")
        print(f"  File Name     : {latest.get('fileName')}")
        print(f"  Timestamp     : {latest.get('date')}")
        print(f"  Status        : {latest.get('status')}")
        print(f"  Public Score  : {latest.get('publicScore')}")
        print(f"  Error Details : {latest.get('errorDescription') or 'None'}")
    print("=" * 75)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaggle Deployment Port Runner")
    parser.add_argument("--account", type=str, required=True, choices=["gaurav065", "gaurav06520"], help="Account to deploy to")
    parser.add_argument("--file", type=str, default=None, help="Path to submission.tar.gz or submission.py")
    parser.add_argument("--message", type=str, default=None, help="Submission description")
    args = parser.parse_args()

    deploy(args.account, args.file, args.message)
