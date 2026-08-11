import json

content = ""
successes = 0
failures = 0

with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\3ece3814-c904-43e0-af13-65ccd1dd368c\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            data = json.loads(line)
            if 'tool_calls' in data:
                for call in data['tool_calls']:
                    if 'strategy.py' in call['args'].get('TargetFile', ''):
                        if call['name'] == 'write_to_file':
                            content = call['args']['CodeContent']
                            successes += 1
                        elif call['name'] == 'replace_file_content':
                            target = call['args']['TargetContent']
                            replacement = call['args']['ReplacementContent']
                            if target in content:
                                content = content.replace(target, replacement)
                                successes += 1
                            else:
                                failures += 1
                                print(f'Failed to replace: {target[:50]}...')
                        elif call['name'] == 'multi_replace_file_content':
                            for chunk in call['args']['ReplacementChunks']:
                                target = chunk['TargetContent']
                                replacement = chunk['ReplacementContent']
                                if target in content:
                                    content = content.replace(target, replacement)
                                    successes += 1
                                else:
                                    failures += 1
                                    print(f'Failed to multi_replace: {target[:50]}...')
        except Exception as e:
            pass

print(f'Successes: {successes}, Failures: {failures}')
with open(r'C:\Coding\kaggriculture-agent\strategy.py', 'w', encoding='utf-8') as f:
    f.write(content)
