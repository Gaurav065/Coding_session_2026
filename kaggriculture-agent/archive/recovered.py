python -c "
import json
with open(r'C:\Users\GauravPatel\.gemini\antigravity\brain\a4ab4dc5-5b88-48a4-bc75-ba3e8146c3f5\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for line in reversed(lines):
    data = json.loads(line)
    if 'tool_calls' in data:
        for tc in data['tool_calls']:
            if 'water_fill_allocate' in str(tc['args']):
                print('FOUND water_fill_allocate!')
                with open('recovered.txt', 'w') as out:
                    out.write(json.dumps(tc['args'], indent=2))
                import sys; sys.exit(0)
"