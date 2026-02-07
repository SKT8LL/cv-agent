import sys
import os

# Add project root to sys.path to allow importing from sibling directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from typing import TypedDict, Literal, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage
from jaebeom.rag import app as rag_app, setup_retriever

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

# --- 에이전트 노드 (Placeholder) ---

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


def mcp_agent(state: AgentState) -> AgentState:
    """
    MCP 에이전트: 컨텍스트/도구를 기반으로 텍스트를 초안 작성하거나 수정합니다.
    """
    # TODO: 담당자 구현 부분 (MCP 도구 활용 및 텍스트 생성)
    print("--- MCP Agent ---")
    
    # 시뮬레이션: 변경 사항을 보여주기 위해 텍스트 추가
    new_text = state["resume_text"] + " -> MCP Processed"
    return {"resume_text": new_text, "retry_count": state["retry_count"]}

def hr_agent(state: AgentState) -> AgentState:
    """
    HR 에이전트: 내용을 검토하고 [PASS] 또는 [REVISE] 태그를 부여합니다.
    """
    # TODO: 담당자 구현 부분 (평가 로직 및 태그 부착)
    print("--- HR Agent ---")
    
    # 루프 테스트를 위한 시뮬레이션 로직:
    # retry_count가 3 미만이면 데모를 위해 강제로 REVISE를 설정합니다.
    # 실제 프로덕션에서는 실제 텍스트 품질에 따라 결정됩니다.
    current_count = state["retry_count"]
    if current_count < 3:
        feedback = "[REVISE]"
    else:
        feedback = "[PASS]"
        
    # 텍스트 앞에 피드백 추가
    reviewed_text = feedback + "\n" + state["resume_text"]
    
    # 참고: 여기서는 retry_count를 증가시키지 않습니다; 엣지/다음 단계에서 처리하거나 루프가 처리하게 합니다.
    # 요구사항: "루프가 발생할 때마다 retry_count를 1씩 증가시키는 로직을 포함하세요."
    return {"resume_text": reviewed_text, "retry_count": state["retry_count"]}

def interview_agent(state: AgentState) -> AgentState:
    """
    면접 에이전트: 최종 텍스트를 기반으로 면접 질문을 생성합니다.
    """
    # TODO: 담당자 구현 부분 (면접 질문 생성)
    print("--- Interview Agent ---")
    # Resume text는 건드리지 않고, Question text만 생성합니다.
    final_output = "\n\nGenerated Interview Questions based on Resume..."
    return {"question_text": final_output, "resume_text": state["resume_text"], "retry_count": state["retry_count"]}

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
    # HR 에이전트가 앞부분에 태그를 붙이므로 startswith를 사용하여 최신 태그를 확인합니다.
    if text.strip().startswith("[REVISE]") and count < 5:
        print(f"--> Looping back (Retry {count + 1})")
        return "mcp_agent"
    
    print("--> Proceeding to Interview")
    return "interview_agent"

# 재시도 카운트를 증가시키기 위한 헬퍼 함수
# StateGraph는 조건부 엣지 함수 내에서 상태 업데이트를 직접 지원하지 않을 수 있음
# 따라서 루프 진입 전 카운트를 증가시키는 명시적 노드를 추가함
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

if __name__ == "__main__":
    print("Initializing Workflow...")
    
    initial_state = AgentState(resume_text="", question_text=None, retry_count=0)
    
    # 그래프 실행
    for output in app.stream(initial_state):
        for key, value in output.items():
            print(f"Finished Node: {key}")
            # print(f"Current State: {value}") # 전체 상태 확인 시 주석 해제
            
    print("\nWorkflow Finished.")
