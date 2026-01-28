# test_github.py
import asyncio
import os
from dotenv import load_dotenv
from langchain_mcp_adapters.tools import load_mcp_tools

# .env 파일 로딩
load_dotenv()

async def test_github():
    print("🚀 GitHub MCP 서버에 연결을 시도합니다...")
    
    try:
        # MCP 도구 로드 (npx로 공식 서버 실행)
        tools = await load_mcp_tools(
            server_params={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {
                    "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN"),
                    "PATH": os.environ["PATH"] # npx 실행을 위해 경로 전달
                }
            }
        )
        
        print(f"✅ 연결 성공! 가져온 도구 개수: {len(tools)}개")
        
        # 도구 이름들만 출력해보기
        print("\n[사용 가능한 GitHub 도구 목록]")
        for tool in tools:
            print(f"- {tool.name}")
            
    except Exception as e:
        print(f"❌ 연결 실패... 에러 내용을 확인하세요:\n{e}")

if __name__ == "__main__":
    asyncio.run(test_github())