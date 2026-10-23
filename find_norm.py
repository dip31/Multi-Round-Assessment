with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\services\interviewService.js', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find the exact normalize function
search_str = "static _normalizeTranscript"
start = content.find(search_str)
if start != -1:
    section = content[start:start+600]
    with open('D:/temp_norm.txt', 'w', encoding='utf-8', errors='replace') as f:
        f.write(section)
    print('Found at position:', start)
    print('First 200 chars:', repr(content[start:start+200]))