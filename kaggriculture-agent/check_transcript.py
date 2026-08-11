import json
with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\3ece3814-c904-43e0-af13-65ccd1dd368c\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if '_sync_world_jobs' in line:
            print("Found _sync_world_jobs in a line")
            try:
                data = json.loads(line)
                if 'tool_calls' in data:
                    for call in data['tool_calls']:
                        print("Tool call:", call['name'])
                        if call['name'] in ['write_to_file', 'replace_file_content', 'multi_replace_file_content']:
                            if 'strategy.py' in str(call['args']):
                                print("Modifies strategy.py!")
                elif data.get('type') == 'TOOL_RESPONSE':
                    print("Tool response containing _sync_world_jobs!")
            except:
                pass
