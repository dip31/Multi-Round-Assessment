with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\services\interviewService.js', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find the actual handler for agent_start_talking
search_str = "this.client.on('agent_start_talking'"
start = content.find(search_str)
if start != -1:
    end = content.find('});', start)
    if end != -1:
        end += 2
        section = content[start:end]
        with open('D:/temp_agent_start_handler.txt', 'w', encoding='utf-8', errors='replace') as f:
            f.write(section)
        print('Found handler at', start)
    else:
        print('Could not find end of handler')
else:
    print('Could not find handler')