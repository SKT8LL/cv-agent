import asyncio
import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

# 환경변수 로드
load_dotenv(override=True)

async def main():
    print("🔎 Notion 연결 및 권한 확인 중...")
    
    # 우리가 만든 파이썬 서버 경로 (jia 폴더 안)
    script_path = os.path.abspath("jia/notion_server.py")
    
    # 파일이 진짜 있는지 확인
    if not os.path.exists(script_path):
        print(f"❌ 오류: 서버 파일({script_path})이 없습니다!")
        return

    server_config = {
        "notion": {
            "command": "python",
            "args": [script_path],
            "env": {
                "NOTION_API_KEY": os.getenv("NOTION_API_KEY"),
                "PYTHONUNBUFFERED": "1"
            }
        }
    }
    
    try:
        async with MultiServerMCPClient(server_config) as client:
            tools = await client.get_tools()
            notion_tool = next((t for t in tools if "search_notion" in t.name), None)
            
            if not notion_tool:
                print("❌ Notion 도구를 불러오지 못했습니다.")
                return

            print("✅ 도구 연결 성공! 봇이 접근 가능한 페이지가 있는지 확인합니다...")
            
            # [핵심] 검색어를 비워두면('') 노션이 "최근 페이지" 목록을 줍니다.
            # 이걸로 봇이 페이지를 볼 수 있는지(권한이 있는지) 테스트합니다.
            result = await notion_tool.ainvoke({"query": ""})
            
            print("\n" + "="*20 + " [봇이 볼 수 있는 페이지 목록] " + "="*20)
            print(result)
            print("="*60)
            
            if "검색 결과가 없습니다" in result:
                print("\n🚨 [진단 결과: 권한 없음]")
                print("봇은 연결됐지만, 볼 수 있는 페이지가 하나도 없습니다.")
                print("👉 해결법: Notion 페이지 우측 상단 '...' -> 'Connect to(연결)' -> 봇 이름 선택")
            else:
                print("\n✅ [진단 결과: 성공]")
                print("봇이 정상적으로 페이지를 읽고 있습니다! 이제 test3.py를 실행해도 됩니다.")

    except Exception as e:
        print(f"❌ 실행 중 에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())
