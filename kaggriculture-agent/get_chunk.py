import json
latest_content = None
with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\3ece3814-c904-43e0-af13-65ccd1dd368c\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    if 'strategy.py' in str(call['args']):
                        if '_calc_purchases' in str(call['args']):
                            if call['name'] == 'write_to_file':
                                latest_content = call['args']['CodeContent']
                            elif call['name'] == 'replace_file_content':
                                latest_content = call['args']['ReplacementContent']
                            elif call['name'] == 'multi_replace_file_content':
                                latest_content = call['args']['ReplacementChunks'][0]['ReplacementContent']
        except:
            pass

if latest_content:
    with open(r'C:\Coding\kaggriculture-agent\recovered_chunk.py', 'w', encoding='utf-8') as f:
        f.write(latest_content)
    print("Saved to recovered_chunk.py")
