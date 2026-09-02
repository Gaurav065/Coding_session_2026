import os
import sys

def create_submission(source_dir, out_file):
    with open(out_file, 'w', encoding='utf-8') as fout:
        fout.write("import sys\n")
        fout.write("import importlib\n")
        fout.write("from pathlib import Path\n")
        fout.write("import copy\n")
        fout.write("import json\n")
        
        # Write the tape
        with open("artifacts/e780_nator_tape/nator_x_seat0.py", encoding='utf-8') as f:
            fout.write(f.read() + "\n")
            
        # We need to write a mock structure or just run tar?
        # Actually, Kaggle submission is just a tar.gz!
        pass

# Let's just copy the build script and change paths!
