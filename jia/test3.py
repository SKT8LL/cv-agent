import os
import asyncio
from typing import TypedDict
from dotenv import load_dotenv

# LangChain / MCP 필수 임포트
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

# 1. 환경 설정
load_dotenv(override=True)
MY_GITHUB_ID = "yeop-sang" 

# State 정의
class AgentState(TypedDict):
    current_text: str
    retry_count: int

# ----------------------------------------------------------------
#수정한 MCP Agent 함수
# ----------------------------------------------------------------
async def mcp_agent(state: AgentState) -> AgentState:
    print(f"\n[MCP Agent 작동 시작] (Retry Count: {state['retry_count']})")
    
    # 1. GitHub 서버 설정
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

    try:
        # [수정 1] async with 제거! (최신 버전 호환성 해결)
        print("GitHub 서버 연결 중...")
        client = MultiServerMCPClient(server_config)
        tools = await client.get_tools()
        print(f"연결 성공. 사용 가능한 도구: {len(tools)}개")

        # LLM 설정
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        # [수정 2] 복잡한 옵션 제거 (state_modifier 등 삭제)
        agent = create_react_agent(llm, tools)

        # 시스템 프롬프트 (내 아이디로만 검색하도록 강제)
        system_prompt = f"""
        당신은 사용자의 GitHub(`user:{MY_GITHUB_ID}`) 데이터를 근거로 자소서를 작성하는 에이전트입니다.
        없는 내용은 지어내지 말고, 반드시 검색된 코드나 커밋 내용을 근거로 작성하세요.
        """

        # 입력 메시지 구성
        if state["retry_count"] == 0:
            user_msg = f"[CREATE]\n{state['current_text']}"
            print("작업 모드: [CREATE] (초안 작성)")
        else:
            user_msg = f"[REVISE]\n{state['current_text']}"
            print("작업 모드: [REVISE] (수정 보완)")

        # [수정 3] 시스템 프롬프트를 메시지 리스트에 직접 주입 (확실한 방법)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg)
        ]

        # 3. 에이전트 실행
        print("에이전트가 생각 중입니다 (GitHub 검색 중)")
        response = await agent.ainvoke({"messages": messages})
        
        # 4. 결과 뽑기
        generated_text = response["messages"][-1].content
        return {"current_text": generated_text, "retry_count": state["retry_count"]}

    except Exception as e:
        print(f"MCP 에러 발생: {e}")
        # 에러 내용을 텍스트에 포함시켜서 디버깅 돕기
        return {"current_text": f"Error: {str(e)}", "retry_count": state["retry_count"]}

# ----------------------------------------------------------------
# 🧪 테스트 실행 (Main)
# ----------------------------------------------------------------
async def main():
    fake_strategy_input ="""
    [자기소개서 문항 1]
    지원 동기 및 직무 역량을 작성하시오.

    [현재 작성된 자기소개서]
    저는 백엔드 개발자로 성장하기 위해 다양한 팀 프로젝트와 개인 프로젝트를 수행해왔습니다.
    React와 FastAPI를 활용한 일정 추천 서비스 개발 프로젝트에서
    API 설계와 비즈니스 로직 구현을 담당하며 실제 사용자 트래픽을 고려한 구조를 설계했습니다.

    서비스 배포 이후 발생한 장애 상황에서는
    로그를 기반으로 원인을 분석하고,
    비동기 처리 구조를 개선하여 응답 지연 문제를 해결한 경험이 있습니다.
    이 경험을 통해 서비스 안정성과 문제 해결 능력의 중요성을 깊이 체감했습니다.

    이러한 경험을 바탕으로,
    귀사의 백엔드 직무에서 안정적인 서비스 운영과
    지속적인 성능 개선에 기여하고 싶습니다.

    [직전 작성 지시(message)]
    + 백엔드 직무와 직접적으로 연결되는 핵심 역량 2~3가지를 먼저 명시하시오
    + 일정 추천 서비스 프로젝트에서 본인이 맡은 역할을 구체적으로 서술하시오
    + 장애 대응 경험을 문제–원인–해결–결과 구조로 정리하시오
    """.strip()
    
    test_state = AgentState(current_text=fake_strategy_input, retry_count=0)

    print("="*50)
    print("🚀 MCP 에이전트 단독 테스트 시작")
    print("="*50)

    result_state = await mcp_agent(test_state)

    print("\n" + "="*50)
    print("📄 [최종 결과 확인]")
    print("="*50)
    print(result_state["current_text"])

if __name__ == "__main__":
    asyncio.run(main())
