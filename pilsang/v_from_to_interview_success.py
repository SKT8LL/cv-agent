import sys
import os
import asyncio
from dotenv import load_dotenv

# Add project root to sys.path to allow importing from sibling directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from jaebeom.rag import app as rag_app, setup_retriever
from mirim.hr_agent import hr_agent as mirim_hr_agent
from mirim.interview import interview_agent as mirim_interview_agent

# 1. 환경 설정
load_dotenv(override=True)
MY_GITHUB_ID = "yeop-sang"

# --- State 정의 ---
class AgentState(TypedDict):
    """
    워크플로우 상태 관리.
    resume_text: 자소서 텍스트 (RAG/MCP/HR에서 처리)
    question_text: 면접 질문 텍스트 (Interview에서 생성)
    retry_count: 재시도 횟수
    """
    resume_text: str
    question_text: Optional[str]
    retry_count: int

# --- 에이전트 노드 ---

def rag_agent(state: AgentState) -> AgentState:
    """
    RAG 에이전트: 검색 기반으로 초기 프롬프트를 생성합니다.
    """
    print("--- RAG Agent ---")
    
    # RAG 실행에 필요한 설정 (예시 URL/경로 사용 - 실제 사용시 조정 필요)
    # jaebeom/rag.py의 main 실행부에서 가져온 경로들
    target_url = "/home/sktll/projects/cv_mcp_project/data_for_rag/internship.html" 
    target_pdf = "/home/sktll/projects/cv_mcp_project/data_for_rag/questions.docx"
    
    try:
        # Retriever 생성
        print("Initializing Retriever...")
        retriever = setup_retriever(target_url, target_pdf)
        
        # RAG Workflow 실행
        rag_initial_state = {
            "messages": [HumanMessage(content="채용 공고 분석 및 자소서 가이드 시작해줘.")],
            "retriever": retriever
        }
        
        print("Invoking RAG App...")
        final_state = rag_app.invoke(rag_initial_state)
        
        # 결과 추출 (User Request: messages[1] + messages[2])
        # messages[0]: Human, messages[1]: AI(Analysis), messages[2]: AI(Strategy)
        part1 = final_state["messages"][1].content
        part2 = final_state["messages"][2].content
        
        combined_text = f"--- [Job Analysis] ---\n{part1}\n\n--- [Resume Strategy] ---\n{part2}"
        
        print("RAG Finished.")
        # RAG 결과는 resume_text에 들어갑니다.
        return {"resume_text": combined_text, "retry_count": state["retry_count"], "question_text": None}
        
    except Exception as e:
        print(f"RAG Agent Error: {e}")
        # 에러 발생 시 fallback
        return {"resume_text": f"RAG Failed: {e}", "retry_count": state["retry_count"], "question_text": None}

async def mcp_agent(state: AgentState) -> AgentState:
    """
    MCP Agent: GitHub 데이터를 기반으로 자소서를 작성하거나 수정합니다.
    """
    print(f"\n🔹 [MCP Agent 작동 시작] (Retry Count: {state['retry_count']})")
    
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
        print("   🔌 GitHub 서버 연결 중...")
        client = MultiServerMCPClient(server_config)
        tools = await client.get_tools()
        print(f"   ✅ 연결 성공! 사용 가능한 도구: {len(tools)}개")

        # LLM 설정
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        agent = create_react_agent(llm, tools)

        # 시스템 프롬프트 (내 아이디로만 검색하도록 강제)
        system_prompt = f"""
        당신은 사용자의 GitHub(`user:{MY_GITHUB_ID}`) 데이터를 근거로 자소서를 작성하는 에이전트입니다.
        없는 내용은 지어내지 말고, 반드시 검색된 코드나 커밋 내용을 근거로 작성하세요.
        각 항목별로 300자 이내로 작성해주세요.
        """

        # 입력 메시지 구성 (current_text -> resume_text)
        if state["retry_count"] == 0:
            user_msg = f"[CREATE]\n{state['resume_text']}"
            print("작업 모드: [CREATE] (초안 작성)")
        else:
            user_msg = f"[REVISE]\n{state['resume_text']}"
            print("작업 모드: [REVISE] (수정 보완)")

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg)
        ]

        # 3. 에이전트 실행
        print("에이전트가 생각 중입니다... (GitHub 검색 중)")
        response = await agent.ainvoke({"messages": messages})
        
        # 4. 결과 뽑기
        generated_text = response["messages"][-1].content
        return {"resume_text": generated_text, "retry_count": state["retry_count"]}

    except Exception as e:
        print(f"MCP 에러 발생: {e}")
        return {"resume_text": f"Error: {str(e)}", "retry_count": state["retry_count"]}

def hr_agent(state: AgentState) -> AgentState:
    """
    HR 에이전트: 실제 LLM 기반 검토 수행 및 태그 부착.
    """
    print("--- HR Agent ---")
    
    # mirim/hr_agent.py 호출을 위한 상태 변환 (resume_text -> current_text)
    mirim_state = {
        "current_text": state["resume_text"],
        "retry_count": state["retry_count"]
    }
    
    try:
        # 실제 HR 에이전트 로직 실행
        result_state = mirim_hr_agent(mirim_state)
        # 결과 매핑 (current_text -> resume_text)
        reviewed_text = result_state["current_text"]
        print(f"HR Feedback Tag: {reviewed_text.splitlines()[0]}")
    except Exception as e:
        print(f"HR Agent Error: {e}")
        reviewed_text = f"[REVISE]\n{e}\n{state['resume_text']}"
    
    print(reviewed_text)
    return {"resume_text": reviewed_text, "retry_count": state["retry_count"]}

def interview_agent(state: AgentState) -> AgentState:
    """
    면접 에이전트: 최종 텍스트를 기반으로 면접 질문을 생성합니다.
    """
    print("--- Interview Agent ---")
    
    # resume_text가 [PASS] 태그를 포함하고 있을 수 있으니, 태그 제거 후 전달하거나 그대로 전달
    # mirim/interview.py는 input 전체를 읽어서 질문 생성하므로 그대로 전달.
    
    mirim_state = {
        "current_text": state["resume_text"],
        "retry_count": state["retry_count"]
    }
    
    try:
        result_state = mirim_interview_agent(mirim_state)
        # 결과는 질문 리스트임
        questions = result_state["current_text"]
    except Exception as e:
        print(f"Interview Agent Error: {e}")
        questions = "Error generating questions."
    print(questions)
    return {"question_text": questions, "resume_text": state["resume_text"], "retry_count": state["retry_count"]}

def docs_agent(state: AgentState) -> AgentState:
    """
    문서 에이전트: 최종 문서화 및 포맷팅.
    """
    # TODO: 담당자 구현 부분 (최종 문서화 저장/변환)
    print("--- Docs Agent ---")
    print(f"Final Resume Length: {len(state.get('resume_text', ''))}")
    print(f"Final Questions Length: {len(state.get('question_text', ''))}")
    
    # 최종 결과물 링크 시뮬레이션
    final_link = "[Link to Generated PDF]"
    print(final_link)
    
    return {"resume_text": state["resume_text"], "question_text": state["question_text"], "retry_count": state["retry_count"]}

# --- 라우팅 로직 ---

def route_logic(state: AgentState) -> Literal["mcp_agent", "interview_agent"]:
    """
    HR 에이전트의 출력에 따라 다음 단계를 결정합니다.
    - [REVISE]이고 retry_count < 5이면 -> mcp_agent
    - [PASS]이거나 retry_count >= 5이면 -> interview_agent
    """
    text = state["resume_text"]
    count = state["retry_count"]
    
    # 생성된 텍스트가 [REVISE]로 시작하는지 확인합니다.
    if text.strip().startswith("[REVISE]") and count < 5:
        print(f"--> Looping back (Retry {count + 1})")
        return "mcp_agent"
    
    print("--> Proceeding to Interview")
    return "interview_agent"

# 재시도 카운트를 증가시키기 위한 헬퍼 함수
def prepare_retry(state: AgentState) -> AgentState:
    return {"retry_count": state["retry_count"] + 1, "resume_text": state["resume_text"]}


# --- 그래프 구성 ---

workflow = StateGraph(AgentState)

# 노드 추가
workflow.add_node("rag_agent", rag_agent)
workflow.add_node("mcp_agent", mcp_agent)
workflow.add_node("hr_agent", hr_agent)
workflow.add_node("prepare_retry", prepare_retry) # 카운팅을 위한 헬퍼 노드
workflow.add_node("interview_agent", interview_agent)
workflow.add_node("docs_agent", docs_agent)

# 시작점 설정
workflow.set_entry_point("rag_agent")

# 엣지 정의
workflow.add_edge("rag_agent", "mcp_agent")
workflow.add_edge("mcp_agent", "hr_agent")

# HR 에이전트로부터의 조건부 엣지
workflow.add_conditional_edges(
    "hr_agent",
    route_logic,
    {
        "mcp_agent": "prepare_retry", # 재시도 시, 카운트 증가를 위해 prepare_retry로 이동
        "interview_agent": "interview_agent"
    }
)

# prepare_retry에서 mcp_agent로 다시 연결
workflow.add_edge("prepare_retry", "mcp_agent")

workflow.add_edge("interview_agent", "docs_agent")
workflow.add_edge("docs_agent", END)

# 컴파일
app = workflow.compile()

# --- 실행 ---

async def main():
    print("Initializing Workflow...")
    
    initial_state = AgentState(resume_text="", question_text=None, retry_count=0)
    
    # 그래프 실행 (Async)
    async for output in app.astream(initial_state):
        for key, value in output.items():
            print(f"Finished Node: {key}")
            # print(f"Current State: {value}")
            
    print("\nWorkflow Finished.")

if __name__ == "__main__":
    asyncio.run(main())
