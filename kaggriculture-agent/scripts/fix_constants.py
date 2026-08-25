with open('continuous_agent/water_fill.py', 'r') as f:
    text = f.read()

constants_start = text.find('CROPS = {')
constants_end = text.find('def ')
constants = text[constants_start:constants_end]

with open('continuous_agent/main_dynamic.py', 'r') as f:
    main_text = f.read()

main_text = constants + '\n' + main_text

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(main_text)
print("CONSTANTS INJECTED")
