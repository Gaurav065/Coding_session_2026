import json

def inspect_obs():
    replay_path = r"C:\Users\LENOVO\Downloads\92023176.json"
    with open(replay_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # get an observation from step 10
    obs = data["steps"][10][0]["observation"]
    
    # print opponent's (player 1) farm
    farm = obs["farms"][1]
    
    # let's look at the tiles
    for row in farm["tiles"]:
        for t in row:
            if isinstance(t, dict):
                print(t)

if __name__ == "__main__":
    inspect_obs()
