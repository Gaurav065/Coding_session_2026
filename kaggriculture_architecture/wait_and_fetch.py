import subprocess
import time
import sys

while True:
    res = subprocess.run(["kaggle", "kernels", "status", "gaurav06520/kaggriculture-hrl-training"], capture_output=True, text=True)
    out = res.stdout.strip()
    print("Status:", out)
    if "COMPLETE" in out or "ERROR" in out:
        break
    time.sleep(10)

print("Fetching output...")
subprocess.run(["kaggle", "kernels", "output", "gaurav06520/kaggriculture-hrl-training", "-p", "./kaggle_output_debug"])
print("Done")
