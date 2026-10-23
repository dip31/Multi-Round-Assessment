with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all template literals with function calls
import re
# Pattern: `...${...}...` where inside ${} there's a function call
for m in re.finditer(r'`[^`]*\$\{[^}]*\([^)]*\)[^}]*\}[^`]*`', content):
    idx = m.start()
    print(f'At {idx}: {repr(content[max(0,idx-30):idx+80])}')
    print('---')