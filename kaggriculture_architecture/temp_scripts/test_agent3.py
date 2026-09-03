import sys
try:
    import submission_phase_f
    action = submission_phase_f.agent({
        "step": 0,
        "player": 1,
        "farms": [{"tiles": [], "farmer": [4,4], "hands": []}, {"tiles": [[None]*10 for _ in range(10)], "farmer": [4,4], "hands": []}],
        "private": {"seeds": {}}
    })
    print("Action returned:", action)
except Exception as e:
    import traceback
    traceback.print_exc()
