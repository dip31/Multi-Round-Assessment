import zipfile
import xml.etree.ElementTree as ET
import sys

try:
    doc = zipfile.ZipFile(sys.argv[1])
    xml_content = doc.read('word/document.xml')
    tree = ET.XML(xml_content)
    WORD_NAMESPACE = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    
    with open('ui_spec.txt', 'w', encoding='utf-8') as f:
        for paragraph in tree.iter(WORD_NAMESPACE + 'p'):
            texts = [node.text for node in paragraph.iter(WORD_NAMESPACE + 't') if node.text]
            if texts:
                f.write(''.join(texts) + '\n')
except Exception as e:
    print('Error:', e)
