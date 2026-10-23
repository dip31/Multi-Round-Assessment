with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\services\interviewService.js', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find the call_ready handler
search_str = "this.client.on('call_ready'"
start = content.find(search_str)
if start != -1:
    end = content.find('});', start)
    if end != -1:
        end += 2
        section = content[start:end]
        with open('D:/temp_call_ready.txt', 'w', encoding='utf-8', errors='replace') as f:
            f.write(section)
        print('Found call_ready handler at', start)
    else:
        print('Could not find end of call_ready handler')
else:
    print('Could not find call_ready handler')