
#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# init_script.sh
# Cluster-scoped init script for the SAP-DBX Validation Framework.
#
# Runs on EVERY cluster node at startup (driver + workers).
# Copies pre-compiled .so files from UC Volume → cluster sys.path.
#
# Configure in Databricks cluster settings:
#   Init scripts → Workspace/Volume path → /Volumes/recon_framework/build/init_script.sh
#   (Upload this file to the UC Volume once, then reference it)
#
# Requires: DBR 13.3 LTS+, Unity Catalog enabled
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SO_VOLUME="/Volumes/recon_framework/build/so_cache"
INSTALL_DIR="/usr/local/lib/val_framework_so"
SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")

echo "=== val_framework init script starting ==="
echo "  Python site-packages : $SITE_PACKAGES"
echo "  SO Volume            : $SO_VOLUME"
echo "  Install dir          : $INSTALL_DIR"

# ── Verify the Volume is accessible (DBR 13.3+ required) ─────────────────────
if [ ! -d "$SO_VOLUME" ]; then
    echo "  WARNING: SO Volume not found at $SO_VOLUME"
    echo "  Run build/build_so_on_cluster.py first to compile the library."
    echo "  Falling back to pure-Python .py source files."
    exit 0
fi

# ── Check if a build manifest exists ─────────────────────────────────────────
MANIFEST="$SO_VOLUME/build_manifest.json"
if [ -f "$MANIFEST" ]; then
    BUILT_AT=$(python3 -c "import json; d=json.load(open('$MANIFEST')); print(d.get('built_at','unknown'))")
    FILE_COUNT=$(python3 -c "import json; d=json.load(open('$MANIFEST')); print(d.get('file_count',0))")
    echo "  Build manifest: built_at=$BUILT_AT, files=$FILE_COUNT"
fi

# ── Copy .so files from Volume to cluster-local path ─────────────────────────
mkdir -p "$INSTALL_DIR"

# rsync-style copy: preserve directory structure
find "$SO_VOLUME" -name "*.so" | while read SO_FILE; do
    # Get path relative to SO_VOLUME
    REL_PATH="${SO_FILE#$SO_VOLUME/}"
    DEST="$INSTALL_DIR/$REL_PATH"
    DEST_DIR=$(dirname "$DEST")
    mkdir -p "$DEST_DIR"
    cp "$SO_FILE" "$DEST"
    echo "  Installed: $REL_PATH"
done

# ── Also copy __init__.py files (required for package discovery) ──────────────
# __init__.py files are NOT compiled to .so — they must stay as plain Python
find "$SO_VOLUME" -name "__init__.py" | while read PY_FILE; do
    REL_PATH="${PY_FILE#$SO_VOLUME/}"
    DEST="$INSTALL_DIR/$REL_PATH"
    DEST_DIR=$(dirname "$DEST")
    mkdir -p "$DEST_DIR"
    cp "$PY_FILE" "$DEST"
done

# ── Add to site-packages via .pth file ───────────────────────────────────────
# A .pth file in site-packages is the clean, pip-compatible way to add
# a directory to sys.path without modifying PYTHONPATH env var.
PTH_FILE="$SITE_PACKAGES/val_framework.pth"
echo "$INSTALL_DIR" > "$PTH_FILE"
echo "  Added to sys.path via: $PTH_FILE"

# ── Verify import works ───────────────────────────────────────────────────────
python3 -c "
import sys
sys.path.insert(0, '$INSTALL_DIR')
try:
    import val_framework
    print('  IMPORT CHECK: val_framework OK')
except ImportError as e:
    print(f'  IMPORT CHECK: WARNING — {e}')
    print('  Framework will run in pure-Python fallback mode.')
"

echo "=== val_framework init script complete ==="