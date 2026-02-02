import os
import dotenv
from dotenv import load_dotenv
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader, BSHTMLLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

# API KEY 설정 (환경변수 또는 직접 입력)
load_dotenv()

# --- 1. State 정의 (MessageState 형식) ---
class AgentState(TypedDict):
    # add_messages: 기존 메시지 리스트에 새로운 메시지를 append 하는 리듀서
    messages: Annotated[list[BaseMessage], add_messages]
    # 문맥 공유를 위한 추가 필드
    retriever: object 

# --- 2. 문서 로드 및 VectorStore 생성 (Step 1) ---
def setup_retriever(input_source: str, file_path: str):
    """웹과 PDF를 로드하여 Retriever를 반환합니다."""

    # 1. Input Source 로드 (URL vs 로컬 파일 분기 처리)
    if input_source.startswith("http"):
        print(f"웹 사이트에서 로드 중: {input_source}")
        loader = WebBaseLoader(input_source)
    else:
        print(f"로컬 파일에서 로드 중: {input_source}")
        # open_encoding 옵션은 한글 깨짐 방지를 위해 종종 필요합니다.
        loader = BSHTMLLoader(input_source, open_encoding="utf-8")
    
    web_or_file_docs = loader.load()
    # 2. File Load (PDF vs DOCX 분기 처리)
    # 파일 확장자 확인
    _, file_extension = os.path.splitext(file_path)
    
    if file_extension.lower() == '.pdf':
        print(f"PDF 파일 로드: {file_path}")
        file_loader = PyPDFLoader(file_path)
        
    elif file_extension.lower() == '.docx':
        print(f"Word 파일 로드: {file_path}")
        # [핵심 변경] Docx2txtLoader 사용
        file_loader = Docx2txtLoader(file_path)
        
    else:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {file_extension}")
        
    file_docs = file_loader.load()
    
    # 3. Split
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_splits = text_splitter.split_documents(web_or_file_docs + file_docs)
    
    # 4. Indexing (In-memory Chroma)
    vectorstore = Chroma.from_documents(
        documents=all_splits, 
        embedding=OpenAIEmbeddings()
    )
    
    # MMR 검색 방식 사용하여 다양성 확보 (자소서 문항과 직무 내용이 섞여 있으므로)
    return vectorstore.as_retriever(search_type="mmr", search_kwargs={"k": 5})

# --- 3. Nodes 정의 ---

# LLM 초기화
llm = ChatOpenAI(model="gpt-5-nano", temperature=0)

def analyze_competency_node(state: AgentState):
    """Step 2: 직무 역량 분석"""
    retriever = state["retriever"]
    query = "이 회사의 해당 직무에 지원하기 위해 필요한 핵심 역량과 자격 요건을 자세히 알려줘."
    
    # RAG 수행
    retrieved_docs = retriever.invoke(query)
    context = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "당신은 채용 공고를 분석하는 HR 전문가입니다."),
        ("human", "채용 공고 내용: {context}\n\n질문: {query}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"context": context, "query": query})
    
    # 결과 메시지 저장
    return {"messages": [response]}

def strategize_resume_node(state: AgentState):
    """Step 3: 자소서 문항별 전략 수립"""
    retriever = state["retriever"]
    
    # 이전 단계(역량 분석)의 결과 가져오기
    competency_analysis = state["messages"][-1].content
    
    # 자소서 문항을 찾기 위한 검색 (Critique 반영: 구체적 쿼리 사용)
    query = "자기소개서 문항 질문 리스트"
    retrieved_docs = retriever.invoke(query)
    context_questions = "\n\n".join([doc.page_content for doc in retrieved_docs])
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "당신은 취업 컨설턴트입니다. 직무 역량 분석 결과와 자기소개서 문항을 바탕으로 조언해줍니다."),
        ("human", """
        [직무 역량 분석 결과]
        {competency_analysis}
        
        [자기소개서 관련 문서 내용]
        {context_questions}
        
        [요청사항]
        위의 '직무 역량'을 바탕으로, '자기소개서 관련 문서 내용'에 있는 **각 문항별로** 어떤 경험과 이력을 강조하여 작성해야 할지 구체적인 가이드라인을 제시해주세요.
        문항이 명시되어 있지 않다면 문서 내용에서 질문을 추론하세요.
        """)
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "competency_analysis": competency_analysis, 
        "context_questions": context_questions
    })
    
    return {"messages": [response]}

# --- 4. Graph 구성 ---

workflow = StateGraph(AgentState)

# 노드 추가
workflow.add_node("analyze_competency", analyze_competency_node)
workflow.add_node("strategize_resume", strategize_resume_node)

# 엣지 연결 (순차 실행)
workflow.add_edge(START, "analyze_competency")
workflow.add_edge("analyze_competency", "strategize_resume")
workflow.add_edge("strategize_resume", END)

# 컴파일
app = workflow.compile()

# --- 5. 실행 (Execution) ---

if __name__ == "__main__":
    # Input 설정
    target_url = "/home/sktll/projects/cv_mcp_project/data_for_rag/internship.html" # 예시 URL
    target_pdf = "/home/sktll/projects/cv_mcp_project/data_for_rag/questions.docx" # 예시 PDF 경로 (파일이 존재해야 함)
    
    # 실제 파일이 없으면 에러가 나므로, 여기서는 Retriever 생성 부분은 주석 처리하거나 
    # 실제 환경에 맞게 경로를 수정해야 합니다.
    print("--- 1. Retriever 생성 중 ---")
    retriever = setup_retriever(target_url, target_pdf)
    
    # 테스트를 위한 Mock Retriever (코드가 돌아가는 것을 보여주기 위함)
    # 실제 사용시에는 위 setup_retriever를 사용하세요.
    # class MockRetriever:
    #     def invoke(self, query):
    #         from langchain_core.documents import Document
    #         if "역량" in query:
    #             return [Document(page_content="주요 업무: Python 백엔드 개발, 대용량 트래픽 처리. 자격요건: Python 3년 이상, RAG 경험 우대.")]
    #         else:
    #             return [Document(page_content="1. 지원 동기\n2. 직무상 강점\n3. 실패 경험")]
    # retriever = MockRetriever()

    # 초기 상태 설정
    initial_state = {
        "messages": [HumanMessage(content="채용 공고 분석 및 자소서 작성해줘")],
        "retriever": retriever
    }
    
    print("--- 2. Agent 실행 중 ---")
    # Step 4: 결과는 자동으로 MessageState 형식(리스트)으로 누적되어 반환됨
    final_state = app.invoke(initial_state)
    
    print("\n--- [Step 2 결과: 직무 역량] ---")
    # 첫 번째 AI 응답 (analyze_competency_node 결과)
    print(final_state["messages"][1].content)
    
    print("\n--- [Step 3 결과: 자소서 가이드 (최종 Output)] ---")
    # 두 번째 AI 응답 (strategize_resume_node 결과)
    print(final_state["messages"][2].content)