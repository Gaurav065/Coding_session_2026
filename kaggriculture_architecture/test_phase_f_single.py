from kaggle_environments import make
env = make("kaggriculture", debug=True)
try:
    steps = env.run([r"C:\Coding\kaggriculture_architecture\submission_phase_f.py", "random"])
    print("Test passed! Phase F runs successfully from single file.")
except Exception as e:
    import traceback
    traceback.print_exc()
