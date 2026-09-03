import glob
import os
import csv

files = glob.glob(r"C:\Coding\kaggriculture_architecture\our_replays\*.json")
ids = []
for f in files:
    basename = os.path.basename(f)
    if basename.startswith("episode-") and basename.endswith("-replay.json"):
        ep_id = basename.split("-")[1]
        ids.append([ep_id])

with open(r"C:\Coding\kaggriculture_architecture\replay_ids.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["EpisodeId"])
    writer.writerows(ids)

print(f"Saved {len(ids)} episode IDs to replay_ids.csv")
