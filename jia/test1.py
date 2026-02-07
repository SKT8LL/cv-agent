import os
import asyncio
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# 1. 환경 변수 로드
load_dotenv(override=True)
MY_GITHUB_ID = "ujia0220" 

async def main():
    # 2. MCP 서버 설정 (변경 없음 - 고정)
    server_config = {
        "github": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_API_KEY"),
                "PATH": os.environ["PATH"]
            }
        },
        #"notion": {
        #    "transport": "stdio",
        #    "command": "npx",
        #    "args": ["-y", "@modelcontextprotocol/server-notion"],
        #    "env": {
        #        "NOTION_API_KEY": os.getenv("NOTION_API_KEY"),
        #        "PATH": os.environ["PATH"]
        #    }
        #}
    }

    # 연결 (변경 없음)
    print("🔌 GitHub와 Notion MCP 서버에 연결 중...")
    try:
        client = MultiServerMCPClient(server_config)
        tools = await client.get_tools()
        print(f"✅ 연결 성공! 도구 {len(tools)}개를 가져왔습니다.")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    # ------------------------------------------------------------------
    # [수정] 시스템 프롬프트: 분석 내용은 빼고, 오직 '자소서 본문'만 출력하도록 지시
    # ------------------------------------------------------------------
    system_prompt = f"""
    당신은 사용자의 GitHub/Notion 데이터를 근거로 자소서를 작성하는 에이전트입니다.
    
    [행동 지침]
    1. `[CREATE]` 태그: GitHub(`user:{MY_GITHUB_ID}`)와 Notion을 검색하여 근거를 찾고, 초안을 작성하세요.
    2. `[REVISE]` 태그: 피드백을 반영하여 내용을 수정/보완하세요.
    
    [출력 규칙]
    - "분석 결과"나 "근거 요약" 같은 부가적인 말은 하지 마세요.
    - 오직 **완성된 자소서 텍스트**만 출력하세요.
    """

    agent = create_react_agent(llm, tools, state_modifier=system_prompt)

    # ------------------------------------------------------------------
    # [Input] 상황에 따라 주석을 풀어 사용하세요
    # ------------------------------------------------------------------
    
    # [상황 1: 초기 생성]
    input_text = """
    [CREATE]
    문항 1: 직무와 관련된 프로젝트 경험 서술.
    전략: GitHub에 있는 Python 데이터 분석 프로젝트 중 성과가 좋았던 것을 골라 구체적 수치와 함께 작성.
    """

    # [상황 2: 수정 (피드백 반영)]
    # input_text = """
    # [REVISE]
    # 이전 자소서 내용: (생략)
    # 피드백: "어떤 라이브러리를 썼는지 구체적인 이름이 빠져있습니다. Pandas인지 NumPy인지 명시해주세요."
    # """
    
    user_input = {"messages": [("user", input_text)]}
    
    # 실행
    response = await agent.ainvoke(user_input)
    generated_draft = response["messages"][-1].content

    # ------------------------------------------------------------------
    # [Output] 요청하신 대로 '요구사항'과 '자소서'만 딱 출력
    # ------------------------------------------------------------------
    print("\n" + "="*30)
    print("📢 [입력된 요구사항 (Requirements)]")
    print("="*30)
    print(input_text.strip())

    print("\n" + "="*30)
    print("📝 [생성된 자소서 (Draft)]")
    print("="*30)
    print(generated_draft)

if __name__ == "__main__":
    asyncio.run(main())