"""Clear transient files from Project Maestro. Run at the end of every session.

Empties scratch/, drops __pycache__ and stray editor/backup files, then reports
anything that looks like superseded sprawl (_v2/_old/_backup) for review rather
than deleting it silently.
"""
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
SPRAWL = ("_v2", "_v3", "_old", "_backup", "_bak", "_copy", "_tmp", "_final")
JUNK_EXT = (".pyc", ".pyo", ".log", "~", ".orig", ".rej")


def main():
    removed = []

    scratch = os.path.join(ROOT, "scratch")
    os.makedirs(scratch, exist_ok=True)
    for name in os.listdir(scratch):
        path = os.path.join(scratch, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        else:
            os.remove(path)
        removed.append(os.path.join("scratch", name))

    for dirpath, dirnames, filenames in os.walk(ROOT):
        for d in list(dirnames):
            if d in ("__pycache__", ".ipynb_checkpoints"):
                shutil.rmtree(os.path.join(dirpath, d), ignore_errors=True)
                dirnames.remove(d)
                removed.append(os.path.relpath(os.path.join(dirpath, d), ROOT))
        for f in filenames:
            if f.endswith(JUNK_EXT):
                os.remove(os.path.join(dirpath, f))
                removed.append(os.path.relpath(os.path.join(dirpath, f), ROOT))

    print("removed %d transient item(s)" % len(removed))
    for r in removed:
        print("  -", r)

    flagged = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if os.path.basename(dirpath) == "scratch":
            dirnames[:] = []
            continue
        for f in filenames:
            stem = os.path.splitext(f)[0]
            if any(stem.endswith(s) for s in SPRAWL):
                flagged.append(os.path.relpath(os.path.join(dirpath, f), ROOT))
    if flagged:
        print("\nreview these -- looks like superseded sprawl, delete or rename:")
        for f in flagged:
            print("  ?", f)


if __name__ == "__main__":
    main()
