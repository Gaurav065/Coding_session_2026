import json

calls = []
with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\3ece3814-c904-43e0-af13-65ccd1dd368c\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    if 'strategy.py' in call['args'].get('TargetFile', ''):
                        calls.append((call['name'], call['args']))
        except Exception as e:
            pass

print(f'Found {len(calls)} edits to strategy.py')
