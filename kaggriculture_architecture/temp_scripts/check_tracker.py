def simulate_tape_positions(max_steps=720):
    import sys
    sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
    from agents.e749a_niklita_consensus_network import SOURCE
    
    positions = {i: [4, 4] for i in range(5)} # Assuming shed is at 4,4
    history = {}
    
    for step in range(max_steps):
        if step < len(SOURCE.TRACE_ACTIONS):
            action = SOURCE.TRACE_ACTIONS[step]
        else:
            break
            
        hands = action.get("hands", [])
        for i in range(5):
            if i < len(hands):
                cmd = hands[i]
                if cmd:
                    if cmd[0] == "NORTH": positions[i][1] = (positions[i][1] + 1) % 15
                    elif cmd[0] == "SOUTH": positions[i][1] = (positions[i][1] - 1) % 15
                    elif cmd[0] == "EAST": positions[i][0] = (positions[i][0] + 1) % 15
                    elif cmd[0] == "WEST": positions[i][0] = (positions[i][0] - 1) % 15
        
        # Save positions at this step
        history[step] = {i: tuple(positions[i]) for i in range(5)}
        
    return history

history = simulate_tape_positions(10)
for k, v in history.items():
    print(k, v)
