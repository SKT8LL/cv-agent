from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END

# --- State Definition ---
class AgentState(TypedDict):
    """
    Workflow state management.
    """
    current_text: str
    retry_count: int

# --- Agent Nodes (Placeholders) ---

def rag_agent(state: AgentState) -> AgentState:
    """
    RAG Agent: Generates initial prompts based on retrieval.
    """
    # TODO: 담당자 구현 부분 (RAG 기반 검색 및 프롬프트 구성)
    print("--- RAG Agent ---")

    
    
    return {"current_text": "RAG Initial Draft", "retry_count": state["retry_count"]}

def mcp_agent(state: AgentState) -> AgentState:
    """
    MCP Agent: Drafts or modifies the text based on context/tools.
    """
    # TODO: 담당자 구현 부분 (MCP 도구 활용 및 텍스트 생성)
    print("--- MCP Agent ---")
    
    # Simulation: Just appending something to show change
    new_text = state["current_text"] + " -> MCP Processed"
    return {"current_text": new_text, "retry_count": state["retry_count"]}

def hr_agent(state: AgentState) -> AgentState:
    """
    HR Agent: Reviews the content and assigns [PASS] or [RETRY] tag.
    """
    # TODO: 담당자 구현 부분 (평가 로직 및 태그 부착)
    print("--- HR Agent ---")
    
    # Simulation logic for testing the loop:
    # If retry_count is less than 3, we force a RETRY for demonstration.
    # In production, this would be based on actual text quality.
    current_count = state["retry_count"]
    if current_count < 3:
        feedback = "[RETRY] Needs more detail."
    else:
        feedback = "[PASS] Looks good."
        
    # Prepend feedback to the text
    reviewed_text = feedback + "\n" + state["current_text"]
    
    return {"current_text": reviewed_text, "retry_count": state["retry_count"]}

def interview_agent(state: AgentState) -> AgentState:
    """
    Interview Agent: Generates interview questions based on the finalized text.
    """
    # TODO: 담당자 구현 부분 (면접 질문 생성)
    print("--- Interview Agent ---")
    final_output = state["current_text"] + "\n\nGenerated Interview Questions..."
    return {"current_text": final_output, "retry_count": state["retry_count"]}

def docs_agent(state: AgentState) -> AgentState:
    """
    Docs Agent: Final documentation and formatting.
    """
    # TODO: 담당자 구현 부분 (최종 문서화 저장/변환)
    print("--- Docs Agent ---")
    final_doc = state["current_text"] + "\n[FINAL DOC GENERATED]"
    return {"current_text": final_doc, "retry_count": state["retry_count"]}

# --- Routing Logic ---

def route_logic(state: AgentState) -> Literal["mcp_agent", "interview_agent"]:
    """
    Determines the next step based on HR Agent's output.
    - If [RETRY] and retry_count < 5 -> mcp_agent
    - If [PASS] or retry_count >= 5 -> interview_agent
    """
    text = state["current_text"]
    count = state["retry_count"]
    
    # Check if the generated text starts with [RETRY]
    # We use startswith (or check the first few chars) to likely catch the latest tag 
    # since HR agent prepends it.
    if text.strip().startswith("[RETRY]") and count < 5:
        print(f"--> Looping back (Retry {count + 1})")
        return "mcp_agent"
    
    print("--> Proceeding to Interview")
    return "interview_agent"

def prepare_retry(state: AgentState) -> AgentState:
    return {"retry_count": state["retry_count"] + 1, "current_text": state["current_text"]}


# --- Graph Construction ---

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("rag_agent", rag_agent)
workflow.add_node("mcp_agent", mcp_agent)
workflow.add_node("hr_agent", hr_agent)
workflow.add_node("prepare_retry", prepare_retry) # Helper for counting
workflow.add_node("interview_agent", interview_agent)
workflow.add_node("docs_agent", docs_agent)

# Set Entry Point
workflow.set_entry_point("rag_agent")

# Define Edges
workflow.add_edge("rag_agent", "mcp_agent")
workflow.add_edge("mcp_agent", "hr_agent")

# Conditional Edge from HR Agent
workflow.add_conditional_edges(
    "hr_agent",
    route_logic,
    {
        "mcp_agent": "prepare_retry",
        "interview_agent": "interview_agent"
    }
)

# Edge from prepare_retry back to mcp_agent
workflow.add_edge("prepare_retry", "mcp_agent")

workflow.add_edge("interview_agent", "docs_agent")
workflow.add_edge("docs_agent", END)

# Compile
app = workflow.compile()

# --- Execution ---

if __name__ == "__main__":
    print("Initializing Workflow...")
    
    initial_state = AgentState(current_text="", retry_count=0)
    
    # Run the graph
    for output in app.stream(initial_state):
        for key, value in output.items():
            print(f"Finished Node: {key}")
            # print(f"Current State: {value}") 
            
    print("\nWorkflow Finished.")
