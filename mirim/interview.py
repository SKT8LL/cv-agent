# interview_demo.py
# 목적:
# - PASS된 자기소개서를 input으로 받아
# - 면접관 LLM이 질문 5개를 생성하는지 확인

import os
from typing import TypedDict
from dotenv import load_dotenv

# -----------------------------
# 0) 환경 변수 로드
# -----------------------------
load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("`.env`에 OPENAI_API_KEY가 설정되어 있지 않습니다.")

# -----------------------------
# 1) State 정의 (HR과 동일한 구조)
# -----------------------------
class AgentState(TypedDict):
    current_text: str
    retry_count: int


# -----------------------------
# 2) 면접관 Prompt
# -----------------------------
INTERVIEWER_PROMPT = """
당신은 채용 면접관입니다.
아래에 제공된 자기소개서를 바탕으로,
지원자가 실제로 해당 경험을 수행했는지,
그리고 그 경험이 직무 수행 역량으로 이어질 수 있는지를 검증하기 위한
면접 질문을 생성하십시오.

[INPUT]
{input}

────────────────────
[질문 생성 목적]
- 자기소개서에 작성된 내용이 사실인지, 깊이 이해하고 있는지,
  실제 행동과 판단을 수반한 경험인지 확인한다.
- “잘 썼는지”를 묻지 말고,
  “실제로 해봤는지”를 검증하는 질문을 만든다.
────────────────────

[질문 생성 원칙 – 반드시 준수]

1) 자기소개서에 **명시적으로 등장한 경험, 주장, 기술**에만 근거하여 질문하십시오.
   (자기소개서에 없는 새로운 경험이나 가정을 추가하지 마십시오.)

2) 질문은 단순 설명 요구가 아니라,
   다음 중 하나 이상을 검증해야 합니다.
   - 의사결정의 이유 (왜 그렇게 선택했는가?)
   - 문제 인식과 해결 과정 (어떤 문제를 어떻게 정의했는가?)
   - 대안 비교 (다른 선택지는 무엇이었고 왜 배제했는가?)
   - 결과에 대한 책임과 한계 (잘 안 된 점은 무엇이었는가?)

3) “무엇을 했나요?”로 끝나는 질문을 만들지 마십시오.
   반드시 사고 과정, 판단 기준, 행동의 맥락이 드러나도록 질문을 구성하십시오.

────────────────────
[질문 유형 분배 – 반드시 반영]

아래 유형을 균형 있게 포함하여 질문을 생성하십시오.

- 경험 검증 질문 (경험의 진위와 깊이 확인)
- 기술/설계 질문 (구현 방식과 선택의 타당성 확인)
- 문제 해결 질문 (문제 상황에서의 접근 방식 확인)
- 협업/의사소통 질문 (팀 내 역할과 상호작용 확인)
- 직무 연결 질문 (해당 경험이 지원 직무에 어떻게 활용되는지 확인)

────────────────────
[출력 형식 – 엄격]

- 번호가 매겨진 면접 질문 리스트로 출력하십시오.
- 질문 외의 설명, 해설, 머리말을 절대 출력하지 마십시오.
- 질문 개수는 정확히 5개로 하십시오.
""".strip()


# -----------------------------
# 3) Interview Agent (단일 def)
# -----------------------------
def interview_agent(state: AgentState) -> AgentState:
    """
    면접관 에이전트
    - input: PASS된 자기소개서 (state["current_text"])
    - output: 면접 질문 리스트
    """
    print("--- Interviewer Agent ---")

    from openai import OpenAI

    client = OpenAI(api_key=API_KEY)

    input_blob = state["current_text"]

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": INTERVIEWER_PROMPT},
            {"role": "user", "content": input_blob},
        ],
        temperature=0.2,  # 질문 다양성 약간 허용
    )

    # 응답 텍스트 추출 (SDK 버전 차이 대응)
    output_text = ""
    try:
        output_text = resp.output_text.strip()
    except Exception:
        parts = []
        for item in getattr(resp, "output", []) or []:
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    parts.append(getattr(c, "text", ""))
        output_text = "\n".join(parts).strip()

    return {
        "current_text": output_text,
        "retry_count": state["retry_count"],
    }


# -----------------------------
# 4) 단독 실행용 main
# -----------------------------
def main():
    # ✅ PASS된 자기소개서 예시 (HR 단계를 통과했다고 가정)
    demo_input = """
[자기소개서 문항 1]
지원 동기 및 직무 역량을 작성하시오.

저는 백엔드 개발자로 성장하기 위해 다양한 팀 프로젝트를 수행해왔습니다.
React와 FastAPI 기반 일정 추천 서비스 개발 프로젝트에서
API 설계와 비즈니스 로직 구현을 담당했습니다.

서비스 배포 이후 발생한 장애 상황에서
로그 분석을 통해 원인을 파악하고
비동기 처리 구조를 개선하여 응답 지연 문제를 해결했습니다.

이러한 경험을 바탕으로
귀사의 백엔드 직무에서 안정적인 서비스 운영에 기여하고 싶습니다.
""".strip()

    state: AgentState = {
        "current_text": demo_input,
        "retry_count": 0,
    }

    out_state = interview_agent(state)

    print("\n===== INTERVIEW QUESTIONS =====")
    print(out_state["current_text"])
    print("================================")


if __name__ == "__main__":
    main()