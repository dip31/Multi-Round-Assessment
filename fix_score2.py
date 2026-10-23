with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the getScoreColor template literal - use array join instead of template literal
old = '<span className={`text-3xl font-bold ${getScoreColor(questionScore)}`}>'
new = '<span className={["text-3xl font-bold", getScoreColor(questionScore)].join(" ")}>'

if old in content:
    content = content.replace(old, new)
    print('Replaced getScoreColor with array join')
else:
    print('Not found')

with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')