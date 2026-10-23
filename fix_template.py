with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the CONNECTING block's p className (at 56330)
old_p = "<p className={`text-sm leading-relaxed ${isUser ? 'text-blue-200' : 'text-purple-200'} break-words`}>"
new_p = '<p className={messageClassName}>'

if old_p in content:
    content = content.replace(old_p, new_p)
    print('Replaced CONNECTING p')
else:
    print('Not found exact')
    print(repr(content[56330:56450]))

# Also fix the stableKey line in CONNECTING block
# Find the exact whitespace
idx = content.find('const stableKey = utt.turn_id', 52000)
idx2 = content.find('return (', idx)
print('Exact old:', repr(content[idx:idx2+10]))

old_stable = content[idx:idx2+10]
new_stable = old_stable.replace(
    'const stableKey = utt.turn_id || `${utt.speaker}-${idx}`;\n                                                    return (',
    'const stableKey = utt.turn_id || `${utt.speaker}-${idx}`;\n                                                    const messageClassName = `text-sm leading-relaxed ${isUser ? "text-blue-200" : "text-purple-200"} break-words`;\n                                                    return ('
)

content = content.replace(old_stable, new_stable)
print('Replaced stableKey')

with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')