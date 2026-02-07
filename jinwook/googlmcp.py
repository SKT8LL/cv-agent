import asyncio
import os
import pickle
from mcp.server import Server
from mcp.types import Tool, TextContent
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from openai import OpenAI
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Google Docs API 스코프 (쓰기 권한 포함)
SCOPES = ['https://www.googleapis.com/auth/documents']

class GoogleDocsMCPServer:
    def __init__(self):
        self.server = Server("google-docs-mcp")
        self.creds = None
        self.openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self._setup_handlers()
    
    def _get_credentials(self):
        """Google API 인증 처리"""
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.creds = pickle.load(token)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError(
                        "credentials.json 파일이 필요합니다. "
                        "Google Cloud Console에서 다운로드하세요."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.creds, token)
        
        return self.creds
    
    def _read_google_doc(self, document_id: str):
        """Google Docs 문서 읽기"""
        creds = self._get_credentials()
        service = build('docs', 'v1', credentials=creds)
        
        document = service.documents().get(documentId=document_id).execute()
        
        # 텍스트 추출
        content = []
        for element in document.get('body', {}).get('content', []):
            if 'paragraph' in element:
                for text_run in element['paragraph'].get('elements', []):
                    if 'textRun' in text_run:
                        content.append(text_run['textRun']['content'])
        
        full_text = ''.join(content)
        return full_text
    
    def _create_google_doc(self, title: str, content: str):
        """Google Docs 문서 생성"""
        creds = self._get_credentials()
        service = build('docs', 'v1', credentials=creds)
        
        # 새 문서 생성
        document = service.documents().create(body={'title': title}).execute()
        document_id = document.get('documentId')
        
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
    
    def _fill_form_with_ai(self, form_template: str, user_prompt: str):
        """OpenAI GPT로 양식 채우기"""
        prompt = f"""
다음은 양식 템플릿입니다:

{form_template}

사용자 요청: {user_prompt}

위 양식을 사용자 요청에 맞게 채워주세요. 양식의 구조를 유지하면서 내용을 작성해주세요.
"""
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 양식을 채우는 전문가입니다."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content
    
    def _generate_interview_prep(self, base_content: str, user_prompt: str):
        """기존 자기소개서를 바탕으로 면접 준비 자료 생성"""
        prompt = f"""
다음은 작성된 자기소개서입니다:

{base_content}

사용자 요청: {user_prompt}

위 자기소개서를 바탕으로 사용자 요청에 맞는 면접 준비 자료를 작성해주세요.
"""
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "당신은 면접 준비를 도와주는 커리어 코치입니다."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content
    
    def _setup_handlers(self):
        """MCP 서버 핸들러 설정"""
        
        @self.server.list_tools()
        async def list_tools():
            """사용 가능한 도구 목록"""
            return [
                Tool(
                    name="read_google_doc",
                    description="Google Docs 문서의 내용을 읽어옵니다",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "string",
                                "description": "Google Docs 문서 ID (URL의 /d/ 뒤 부분)"
                            }
                        },
                        "required": ["document_id"]
                    }
                ),
                Tool(
                    name="create_documents",
                    description="양식 템플릿과 프롬프트를 바탕으로 자기소개서와 면접 준비 자료를 생성합니다",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "form_template": {
                                "type": "string",
                                "description": "양식 템플릿 내용 (PDF에서 추출한 텍스트)"
                            },
                            "cover_letter_prompt": {
                                "type": "string",
                                "description": "자기소개서 작성을 위한 프롬프트"
                            },
                            "interview_prep_prompt": {
                                "type": "string",
                                "description": "면접 준비 자료 작성을 위한 프롬프트"
                            },
                            "interview_prep_prompt": {
                                "type": "string",
                                "description": "면접 준비 자료 작성을 위한 프롬프트"
                            },
                            "doc_title": {
                                "type": "string",
                                "description": "문서 제목 (선택사항)",
                                "default": "자기소개서 및 면접 준비 자료"
                            }
                        },
                        "required": ["form_template", "cover_letter_prompt", "interview_prep_prompt"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """도구 실행"""
            if name == "read_google_doc":
                return await self._handle_read_google_doc(arguments["document_id"])
            elif name == "create_documents":
                return await self._handle_create_documents(
                    arguments["form_template"],
                    arguments["cover_letter_prompt"],
                    arguments["interview_prep_prompt"],
                    arguments.get("doc_title", "자기소개서 및 면접 준비 자료")
                )
            else:
                raise ValueError(f"Unknown tool: {name}")
    
    async def _handle_read_google_doc(self, document_id: str):
        """Google Docs 문서 읽기 핸들러"""
        try:
            full_text = self._read_google_doc(document_id)
            
            return [TextContent(
                type="text",
                text=full_text
            )]
        
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"오류 발생: {str(e)}"
            )]
    
    async def _handle_create_documents(self, form_template: str, cover_letter_prompt: str, 
                                      interview_prep_prompt: str, doc_title: str):
        """자기소개서 + 면접 준비 자료 생성 핸들러 (단일 문서)"""
        try:
            # 1단계: 자기소개서 생성
            cover_letter = self._fill_form_with_ai(form_template, cover_letter_prompt)
            
            # 2단계: 면접 준비 자료 생성
            interview_prep = self._generate_interview_prep(cover_letter, interview_prep_prompt)
            
            # 3단계: 내용 통합
            final_content = f"""[자기소개서]
{cover_letter}

==================================================

[면접 대비 질문 리스트]
{interview_prep}
"""
            # 4단계: Google Doc 생성
            doc_id = self._create_google_doc(doc_title, final_content)
            
            result_text = f"""
✅ 문서 생성 완료!

📄 통합 문서 (자기소개서 + 면접 질문)
- 제목: {doc_title}
- URL: https://docs.google.com/document/d/{doc_id}/edit
- 문서 ID: {doc_id}
"""
            
            return [TextContent(
                type="text",
                text=result_text
            )]
        
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"오류 발생: {str(e)}"
            )]
    
    async def run(self):
        """서버 실행"""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )

if __name__ == "__main__":
    server = GoogleDocsMCPServer()
    asyncio.run(server.run())
