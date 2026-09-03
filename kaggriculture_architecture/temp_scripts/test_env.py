import sys
import kaggle_environments
import traceback

env = kaggle_environments.make("kaggriculture")
agent_f = "submission_phase_f.py"
agent_orig = "extracted_notebook_agent/main.py"

trainer = env.train([None, agent_orig])
obs = trainer.reset()
try:
    for i in range(10):
        action = trainer.step(None)
    print("Trainer stepped 10 times successfully.")
except Exception as e:
    traceback.print_exc()
