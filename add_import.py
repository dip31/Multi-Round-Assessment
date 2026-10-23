with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\InterviewReport.jsx', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Add import for QuestionWiseAnalysis
import_line = "import { QuestionWiseAnalysis } from '../components/QuestionWiseAnalysis';\n"

# Find the last import line
import_end = content.rfind('import PageSkeleton from')
if import_end != -1:
    # Find the end of that import line
    line_end = content.find('\n', import_end)
    if line_end != -1:
        new_content = content[:line_end+1] + "import { QuestionWiseAnalysis } from '../components/QuestionWiseAnalysis';\n" + content[line_end+1:]
        with open(r'D:\Projects\EDI 4\Multi-Round-Assesment-v8n\frontend\src\pages\InterviewReport.jsx', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print('Added import for QuestionWiseAnalysis')
    else:
        print('Could not find end of import line')
else:
    print('Could not find PageSkeleton import')