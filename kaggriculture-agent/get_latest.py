import json
latest_content = None
with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\3ece3814-c904-43e0-af13-65ccd1dd368c\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    if call['name'] == 'write_to_file' and 'strategy.py' in str(call['args']):
                        if '_sync_world_jobs' in call['args']['CodeContent']:
                            latest_content = call['args']['CodeContent']
        except:
            pass

if latest_content:
    with open(r'C:\Coding\kaggriculture-agent\strategy_latest_write.py', 'w', encoding='utf-8') as f:
        f.write(latest_content)
    print("Saved to strategy_latest_write.py")
