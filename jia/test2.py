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
    # 2. MCP 서버 설정 (GitHub만 연결)
    server_config = {
        "github": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-github"],
            "env": {
                "GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_API_KEY"),
                "PATH": os.environ["PATH"]
            }
        }
    }

    print("🔌 GitHub MCP 서버에 연결 중...")
    try:
        client = MultiServerMCPClient(server_config)
        tools = await client.get_tools()
        print(f"✅ 연결 성공! 도구 {len(tools)}개를 가져왔습니다.")
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return

    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    # 3. 시스템 프롬프트
    system_prompt = f"""
    당신은 사용자의 GitHub 데이터를 근거로 자소서를 작성하는 에이전트입니다.
    
    [행동 지침]
    1. `[CREATE]` 태그: GitHub(`user:{MY_GITHUB_ID}`)를 검색하여 근거를 찾고, 초안을 작성하세요.
    2. `[REVISE]` 태그: 피드백을 반영하여 내용을 수정/보완하세요.
    
    [출력 규칙]
    - "분석 결과"나 "근거 요약" 같은 부가적인 말은 하지 마세요.
    - 오직 **완성된 자소서 텍스트**만 출력하세요.
    """

    # ------------------------------------------------------------------
    # [수정 포인트] state_modifier -> messages_modifier 로 변경!
    # ------------------------------------------------------------------
    agent = create_react_agent(llm, tools, messages_modifier=system_prompt)

    # 4. 테스트용 가짜 데이터 (입력)
    input_text = """
    [CREATE]
    문항 1: 지원 직무와 관련하여 가장 몰입했던 프로젝트 경험을 서술하시오.
    전략: GitHub에서 'Python' 또는 'Deep Learning'을 사용한 프로젝트를 검색해서, 
    어떤 문제를 해결했는지 구체적인 기술(라이브러리 이름 등)과 함께 작성할 것.
    """
    
    user_input = {"messages": [("user", input_text)]}
    
    # 5. 실행 및 결과 출력
    try:
        response = await agent.ainvoke(user_input)
        generated_draft = response["messages"][-1].content

        print("\n" + "="*30)
        print("📢 [입력된 요구사항]")
        print("="*30)
        print(input_text.strip())

        print("\n" + "="*30)
        print("📝 [생성된 자소서]")
        print("="*30)
        print(generated_draft)
        
    except Exception as e:
        print(f"\n❌ 실행 중 에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())