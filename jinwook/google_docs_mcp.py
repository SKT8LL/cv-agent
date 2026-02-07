import asyncio
from mcp.server import Server
from mcp.types import Tool, TextContent
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os
import pickle

# Google Docs API 스코프
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

class GoogleDocsMCPServer:
    def __init__(self):
        self.server = Server("google-docs-mcp")
        self.creds = None
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
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict):
            """도구 실행"""
            if name == "read_google_doc":
                return await self._read_google_doc(arguments["document_id"])
            else:
                raise ValueError(f"Unknown tool: {name}")
    
    async def _read_google_doc(self, document_id: str):
        """Google Docs 문서 읽기"""
        try:
            creds = self._get_credentials()
            service = build('docs', 'v1', credentials=creds)
            
            # 문서 가져오기
            document = service.documents().get(documentId=document_id).execute()
            
            # 텍스트 추출
            content = []
            for element in document.get('body', {}).get('content', []):
                if 'paragraph' in element:
                    for text_run in element['paragraph'].get('elements', []):
                        if 'textRun' in text_run:
                            content.append(text_run['textRun']['content'])
            
            full_text = ''.join(content)
            
            return [TextContent(
                type="text",
                text=f"문서 제목: {document.get('title', 'N/A')}\n\n{full_text}"
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
