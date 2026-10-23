with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\services\interviewService.js', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find the transcript handler
search_str = "this.client.on('transcript'"
start = content.find(search_str)
if start != -1:
    end = content.find('});', start)
    if end != -1:
        end += 2
        section = content[start:end]
        with open('D:/temp_transcript_handler.txt', 'w', encoding='utf-8', errors='replace') as f:
            f.write(section)
        print('Found transcript handler at', start)
        print(section[:300])