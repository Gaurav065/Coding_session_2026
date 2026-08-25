import sys
sys.path.insert(0, r'C:\Coding\project_doppelganger')

from kaggle_environments import make
from main import agent as doppelganger_agent

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1}, debug=True)
env.run([doppelganger_agent, "starter"])

for idx, s in enumerate(env.steps):
    m0 = s[0]['observation']['farms'][0]['money']
    if m0 == 0:
        print(f"First 0 money step: {idx}")
        # Print preceding 5 steps
        for p in range(max(0, idx-5), idx+5):
            st = env.steps[p][0]
            print(f"Step {p:03d}: Act={st.get('action')} | Money={st['observation']['farms'][0]['money']} | Shed={st['observation']['private']['shed']}")
        break
