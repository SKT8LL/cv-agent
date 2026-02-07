import os
from dotenv import load_dotenv
from openai import OpenAI
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle

# 환경 변수 로드
load_dotenv()

# Google Docs API 스코프 (쓰기 권한 포함)
SCOPES = ['https://www.googleapis.com/auth/documents']

class FormFiller:
    def __init__(self):
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.google_creds = None
    
    def get_google_credentials(self):
        """Google API 인증"""
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.google_creds = pickle.load(token)
        
        if not self.google_creds or not self.google_creds.valid:
            if self.google_creds and self.google_creds.expired and self.google_creds.refresh_token:
                self.google_creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                self.google_creds = flow.run_local_server(port=0)
            
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.google_creds, token)
        
        return self.google_creds
    
    def generate_interview_prep(self, self_intro_content, custom_prompt=None):
        """자기소개서를 바탕으로 면접 준비 자료 생성"""
        default_prompt = """
너는 기술 기반 인턴 채용을 담당하는 면접관이다.
제공된 자기소개서 내용을 면밀히 분석하여, 지원자를 검증하고 깊이 있는 대화를 나누기 위한 **면접 대비 질문 리스트**를 작성하라.
질문은 다음 카테고리로 나누어 작성하라:
1. 기술 검증 질문 (구체적인 기술 스택 및 경험 관련)
2. 인성 및 가치관 질문
3. 문제 해결 능력 검증 질문 (프로젝트 경험 기반)
4. 회사/직무 적합성 질문

각 질문에 대해 모범 답안의 방향성도 간단히 코멘트하라.
"""
        prompt = custom_prompt if custom_prompt else default_prompt
        
        full_prompt = f"""
[자기소개서 전문]
{self_intro_content}

[요청 사항]
{prompt}
"""
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "당신은 전문 채용 면접관입니다."},
                {"role": "user", "content": full_prompt}
            ]
        )
        
        return response.choices[0].message.content
    
    def create_google_doc(self, title, content):
        """Google Docs 문서 생성"""
        creds = self.get_google_credentials()
        service = build('docs', 'v1', credentials=creds)
        
        # 새 문서 생성
        document = service.documents().create(body={'title': title}).execute()
        document_id = document.get('documentId')
        
        print(f'문서 생성됨: https://docs.google.com/document/d/{document_id}/edit')
        
        # 내용 추가
        requests = [
            {
                'insertText': {
                    'location': {
                        'index': 1,
                    },
                    'text': content
                }
            }
        ]
        
        service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()
        
        return document_id
    
    def process(self, self_intro_content, interview_prompt=None, doc_title="자기소개서 및 면접 준비 자료"):
        """
        전체 프로세스:
        1. 입력받은 자기소개서 내용 확인
        2. 자기소개서 바탕으로 면접 질문 생성
        3. 하나의 Google Doc에 통합하여 저장
        """
        print("\n" + "="*60)
        print("📝 자기소개서 처리 및 면접 질문 생성 시작")
        print("="*60)
        
        # 1. 면접 질문 생성
        print("1. AI로 면접 준비 자료 생성 중...")
        interview_content = self.generate_interview_prep(self_intro_content, interview_prompt)
        
        # 2. 내용 통합
        print("2. 문서 내용 통합 중...")
        final_content = f"""[자기소개서]
{self_intro_content}

==================================================

[면접 대비 질문 리스트]
{interview_content}
"""
        
        # 3. Google Docs 생성
        print("3. Google Docs에 작성 중...")
        doc_id = self.create_google_doc(doc_title, final_content)
        
        print("\n" + "="*60)
        print("🎉 프로세스 완료!")
        print("="*60)
        print(f"문서 링크: https://docs.google.com/document/d/{doc_id}/edit")
        
        return doc_id

# 사용 예시
if __name__ == "__main__":
    # 테스트용 더미 데이터
    dummy_intro = "안녕하세요. 저는 백엔드 개발자입니다. Python과 Django를 잘 다룹니다."
    
    filler = FormFiller()
    filler.process(dummy_intro)

