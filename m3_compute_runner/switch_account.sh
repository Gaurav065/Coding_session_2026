#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Switch active Kaggle credentials between gaurav065 and gaurav06520 on macOS/Linux.
#
# Usage:
#   source switch_account.sh gaurav065
#   source switch_account.sh gaurav06520

TARGET_ACCOUNT="$1"

if [ "$TARGET_ACCOUNT" == "gaurav065" ]; then
    TOKEN="KGAT_9b806157756d5ff934d83a0797ba658b"
    echo "Switching active Kaggle account to: gaurav065 (Primary Grandmaster Ladder)"
elif [ "$TARGET_ACCOUNT" == "gaurav06520" ]; then
    TOKEN="KGAT_ec5e135bd5730eb67df2a539d8fcac64"
    echo "Switching active Kaggle account to: gaurav06520 (Secondary Deployment Port)"
else
    echo "Usage: source switch_account.sh [gaurav065 | gaurav06520]"
    return 1 2>/dev/null || exit 1
fi

export KAGGLE_API_TOKEN="$TOKEN"

# Also update ~/.kaggle/access_token for native kaggle CLI support
mkdir -p "$HOME/.kaggle"
echo "$TOKEN" > "$HOME/.kaggle/access_token"
chmod 600 "$HOME/.kaggle/access_token"

echo "KAGGLE_API_TOKEN exported and ~/.kaggle/access_token updated successfully!"
kaggle config view 2>/dev/null || echo "Active token: ${TOKEN:0:12}..."
