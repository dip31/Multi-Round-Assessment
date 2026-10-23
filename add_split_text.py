with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\app\services\rag_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where to insert the _split_text method - after build_resume_index method
idx = content.find('def build_resume_index')
if idx != -1:
    # Find the next method definition after build_resume_index
    next_method = content.find('\n    def ', content.find('def build_resume_index') + 1)
    if next_method == -1:
        next_method = len(content)
    
    # Insert _split_text method before the next method
    method_code = '''
    def _split_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - overlap
            if start >= text_len:
                break
        
        return chunks

'''
    new_content = content[:next_method] + method_code + content[next_method:]
    
    with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\app\services\rag_service.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Added _split_text method')
else:
    print('Could not find build_resume_index method')