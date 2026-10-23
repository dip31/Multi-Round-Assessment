with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\RetellInterviewRoom.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

start = content.find('Live Transcript Display - Enhanced with better formatting')
map_start = content.find('{liveTranscript.map', start)
print('map_start:', map_start)

idx = map_start
brace_count = 0
in_string = False
string_char = None
for i in range(idx, len(content)):
    ch = content[i]
    if not in_string and (ch == '"' or ch == "'" or ch == '`'):
        in_string = True
        string_char = ch
    elif in_string and ch == string_char and content[i-1] != '\\':
        in_string = False
        string_char = None
    elif not in_string:
        if ch == '{':
            brace_count += 1
        elif ch == '}':
            brace_count -= 1
            if brace_count == 0:
                print('Found closing brace at:', i)
                print('Context:', repr(content[i:i+20]))
                break