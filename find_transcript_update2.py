with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\services\interviewService.js', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find the transcript_update handler
search_str = "this.client.on('transcript_update'"
start = content.find(search_str)
if start != -1:
    end = content.find('});', start)
    if end != -1:
        end += 2
        section = content[start:end]
        with open('D:/temp_transcript_update_handler.txt', 'w', encoding='utf-8', errors='replace') as f:
            f.write(section)
        print('Found transcript_update handler at', start)
        # Print first 300 chars to ASCII file
        with open('D:/temp_transcript_update_handler2.txt', 'w', encoding='ascii', errors='replace') as f:
            f.write(section[:300])
    else:
        print('Could not find end of transcript_update handler')
else:
    print('Could not find transcript_update handler')