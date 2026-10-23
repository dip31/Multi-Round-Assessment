with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Revert the getScoreColor change
old = '<span className={"text-3xl font-bold " + getScoreColor(questionScore)}>'
new = '<span className={`text-3xl font-bold ${getScoreColor(questionScore)}`}>'

if old in content:
    content = content.replace(old, new)
    print('Reverted getScoreColor')
else:
    print('Not found to revert')

with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')