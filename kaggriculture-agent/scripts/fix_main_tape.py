
import re
with open("main.py", "r") as f: code = f.read()
code = code.replace("tape_151k.json", "blind_hybrid_tape.json")
with open("main.py", "w") as f: f.write(code)

