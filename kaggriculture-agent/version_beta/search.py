with open("out.txt", "r", encoding="utf-16") as f:
    for i, line in enumerate(f):
        if "starv" in line.lower() or "panic" in line.lower():
            print(f"Line {i+1}: {line.strip()}")
