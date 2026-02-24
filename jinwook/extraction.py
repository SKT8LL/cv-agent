import os
from pypdf import PdfReader # PDF 읽는 라이브러리 (pip install pypdf 필요)

# 1. 내 컴퓨터에 있는 PDF 파일 경로
file_path = r"C:\Users\username\Desktop\docs\introduce.pdf"

# 2. PDF 내용을 텍스트로 추출 (이 부분이 import os로는 안 되는 부분)
def extract_text_from_pdf(path):
    reader = PdfReader(path)
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"
    return full_text

# 3. 텍스트 추출 실행
if os.path.exists(file_path): # os는 파일이 있는지 확인하는 용도
    source_content = extract_text_from_pdf(file_path)
    print("PDF 내용 추출 완료!")
else:

    print("파일이 없습니다.")
