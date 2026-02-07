# notion_server.py
from mcp.server.fastmcp import FastMCP
import httpx
import os

# 1. 서버 이름 정의
mcp = FastMCP("MyNotionServer")

# 2. 도구 만들기: Notion 검색 기능
@mcp.tool()
async def search_notion(query: str) -> str:
    """
    Notion 전체에서 페이지를 검색합니다. 
    프로젝트 이름, 성과, 문서 내용을 찾을 때 사용하세요.
    """
    api_key = os.getenv("NOTION_API_KEY")
    if not api_key:
        return "Error: NOTION_API_KEY가 환경변수에 없습니다."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    payload = {
        "query": query,
        "page_size": 5, # 상위 5개만 검색
        "sort": {"direction": "descending", "timestamp": "last_edited_time"}
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post("https://api.notion.com/v1/search", headers=headers, json=payload)
            
            if resp.status_code != 200:
                return f"Notion API Error ({resp.status_code}): {resp.text}"
            
            data = resp.json()
            results = []
            
            # 검색 결과 예쁘게 정리
            for page in data.get("results", []):
                title = "제목 없음"
                # Notion의 복잡한 제목 구조 파싱
                if "properties" in page:
                    for prop in page["properties"].values():
                        if prop["id"] == "title" or prop["type"] == "title":
                            if prop.get("title"):
                                title = prop["title"][0]["plain_text"]
                            break
                
                url = page.get("url", "")
                results.append(f"- [문서] {title}\n  URL: {url}")
            
            if not results:
                return "검색 결과가 없습니다."
                
            return "\n".join(results)

    except Exception as e:
        return f"검색 중 에러 발생: {str(e)}"

# 3. 서버 실행
if __name__ == "__main__":
    mcp.run()