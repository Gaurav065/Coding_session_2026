import sys
import traceback
try:
    import submission_phase_f
    print('Success!')
except Exception as e:
    traceback.print_exc()
