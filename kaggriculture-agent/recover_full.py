import json

content = ''
with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\3ece3814-c904-43e0-af13-65ccd1dd368c\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    if call['name'] == 'write_to_file' and 'strategy.py' in call['args'].get('TargetFile', ''):
                        content = call['args']['CodeContent']
                    elif call['name'] == 'replace_file_content' and 'strategy.py' in call['args'].get('TargetFile', ''):
                        target = call['args']['TargetContent']
                        replacement = call['args']['ReplacementContent']
                        if target in content:
                            content = content.replace(target, replacement)
        except Exception as e:
            pass

with open(r'C:\Coding\kaggriculture-agent\strategy_recovered_full.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Recovered full with replacements')
