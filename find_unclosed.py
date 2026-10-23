with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the unclosed single quote by tracking balance
balance = 0
for i, ch in enumerate(content):
    if ch == "'":
        balance += 1
    elif ch == '"':
        pass
    if balance % 2 == 1 and i > 100000:
        # Show context around the problematic area
        print(f'Potential issue at {i}: balance={balance}')
        print(repr(content[max(0,i-100):i+100]))
        break

# Also check from the end backwards
balance = 0
for i in range(len(content)-1, -1, -1):
    ch = content[i]
    if ch == "'":
        balance += 1
    if balance % 2 == 1 and i < len(content) - 1000:
        print(f'Potential issue from end at {i}: balance={balance}')
        print(repr(content[max(0,i-100):i+100]))
        break