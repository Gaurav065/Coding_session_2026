import sys
import types
import os

def unpack_file(filepath, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(filepath, 'r', encoding='utf-8') as f:
        code = f.read()

    globs = {}
    exec(code, globs)
    print("Globals extracted from:", filepath)
    for k in sorted(globs.keys()):
        if not k.startswith('__'):
            val = globs[k]
            print(f"  {k}: type={type(val)}")
            if isinstance(val, dict):
                print(f"     keys: {list(val.keys())[:10]}")

    if '_V44_MODULES' in globs:
        mods = globs['_V44_MODULES']
        for mod_name, mod_src in mods.items():
            mod_path = os.path.join(out_dir, mod_name.replace('.', os.sep) + '.py')
            os.makedirs(os.path.dirname(mod_path), exist_ok=True)
            with open(mod_path, 'w', encoding='utf-8') as mf:
                mf.write(mod_src)
        print(f"Extracted {len(mods)} modules to {out_dir}")

    if 'agent' in globs:
        print("agent function found:", globs['agent'])

if __name__ == '__main__':
    unpack_file(r'C:\Users\GauravPatel\Downloads\main (2).py', r'C:\Coding\kaggriculture_architecture\unpacked_main2')
    unpack_file(r'C:\Coding\main.py', r'C:\Coding\kaggriculture_architecture\unpacked_main')
