# blank.py
# 목적: 임의 input을 넣었을 때 HR 에이전트(OpenAI)가
# 1) [PASS] / [REVISE] 태그를 판단하고
# 2) [REVISE]면 "다음 생성용 작성 지시(message)"를 붙여서
# 결과를 출력하는지 빠르게 확인하는 단일 실행 스크립트

import os
from typing import TypedDict
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("`.env`에 OPENAI_API_KEY(또는 openai_api_key) 설정이 없습니다.")

# -----------------------------
# 1) State 정의
# -----------------------------
class AgentState(TypedDict):
    current_text: str
    retry_count: int


# -----------------------------
# 2) HR Prompt (입력 1개, 출력 1개)
# -----------------------------
HR_PROMPT = """
당신은 작성된 자기소개서를 HR 관점에서 평가하고,
다음 자기소개서 생성을 위한 '작성 지시(message)'를 재설계하는 평가관입니다.

[INPUT]
{input}

────────────────────
[평가 목적]
- 현재 자기소개서가 실제 채용 프로세스에서
  "면접 단계로 바로 넘겨도 되는 수준인지"를 판단한다.
- 부족할 경우, 평가 코멘트가 아니라
  다음 생성에서 반드시 반영되어야 할 '작성 지시(message)'로만 보완한다.
────────────────────

[평가 기준 – 아래 항목을 각각 독립적으로 검토하시오]

① 직무 적합성
- 자기소개서 내용이 지원 직무의 핵심 역할과 직접적으로 연결되어 있는가?
- 직무와 무관한 일반론적 서술(성실함, 열정 등)에 의존하지 않았는가?

② 경험의 구체성
- 실제 수행한 경험이 존재하는가?
- 역할, 행동, 사용 기술/방법, 맥락이 구체적으로 드러나는가?
- "했다 / 참여했다" 수준의 나열에 그치지 않았는가?

③ 근거의 명확성
- 주장(역량, 강점)에 대해 경험이라는 근거가 명확히 대응되는가?
- 근거 없는 자기평가 또는 추상적 표현이 반복되지 않는가?

④ 회사/직무 연결성
- 경험이 해당 회사 또는 직무에서
  어떻게 활용될 수 있는지 명확히 연결되어 있는가?
- 단순한 지원 동기 문장으로 끝나지 않았는가?

⑤ 서술 구조
- 문항의 요구사항에 맞는 구조를 갖추고 있는가?
- 하나의 문단에 여러 경험이 섞여 있지 않은가?
- 읽는 사람이 핵심을 빠르게 파악할 수 있는가?

────────────────────
[PASS 판정 기준 – 매우 엄격]

아래 조건을 **모두 만족하는 경우에만 [PASS]를 부여하십시오.**

- 다섯 가지 평가 기준(①~⑤) 중
  단 하나라도 명확히 충족되지 않으면 [PASS]를 부여하지 마십시오.
- 추가 설명이나 보완 지시 없이도
  면접에서 바로 검증 질문을 던질 수 있는 수준이어야 합니다.

────────────────────
[REVISE 판정 기준]

- 위 PASS 기준을 하나라도 충족하지 못한 경우
  반드시 [REVISE]를 부여하십시오.

[REVISE]인 경우 지켜야 할 규칙:
- 평가 이유를 설명하지 마십시오.
- 부족한 점을 "다음 생성에서 반드시 반영해야 할 작성 지시(message)"로 변환하십시오.
- 문항 제목([자기소개서 문항 n])과 '+' 형식의 지시는 유지하십시오.
- 지시는 추상적 표현을 피하고, 실행 가능한 수준으로 구체화하십시오.

(예: ❌ 경험을 더 구체적으로 쓰세요
     ⭕ 프로젝트에서 본인의 역할, 사용 기술, 문제 상황과 해결 과정을 단계적으로 서술하시오)

────────────────────
[출력 형식 – 반드시 준수]

- 첫 줄: [PASS] 또는 [REVISE] 중 하나만 출력
- [REVISE]일 때만, 다음 줄부터
  '수정된 자기소개서 문항 및 작성 지시(message)'를 출력
- [PASS]일 때는 첫 줄만 출력하고 다른 문장은 절대 출력하지 마십시오
""".strip()


# -----------------------------
# 3) HR Agent (OpenAI가 여기서 태그/수정지시 생성)
# -----------------------------
def hr_agent(state: AgentState) -> AgentState:
    """
    input: state["current_text"]  (하나)
    output: state["current_text"] (하나) -> 첫 줄 [PASS] 또는 [REVISE]
    retry_count 증가는 이 함수에서 하지 않음(외부에서 루프 발생 시 올림)
    """
    print("--- HR Agent ---")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("환경변수 OPENAI_API_KEY가 없습니다. 먼저 설정하세요.")

    # OpenAI 호출 (Responses API)
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError(
            "openai 패키지가 없습니다. 먼저 설치하세요: pip install openai"
        ) from e

    client = OpenAI(api_key=api_key)

    # [수정] retry_count가 3 이상이면 강제로 PASS 처리
    # (무한 루프 방지 및 빠른 진행을 위함)
    if state["retry_count"] >= 3:
        print(f"⚠️ Retry limit reached ({state['retry_count']}). Forcing [PASS].")
        return {"current_text": "[PASS]", "retry_count": state["retry_count"]}

    input_blob = state["current_text"]

    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {
                "role": "system",
                "content": HR_PROMPT,
            },
            {
                "role": "user",
                "content": input_blob,
            },
        ],
        temperature=0.0,
    )

    # 응답 텍스트 추출(가장 일반적인 경로)
    # SDK 버전에 따라 구조가 다를 수 있어 방어적으로 처리
    hr_out = ""
    try:
        hr_out = resp.output_text.strip()
    except Exception:
        # fallback: output 배열에서 텍스트 조합
        parts = []
        for item in getattr(resp, "output", []) or []:
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    parts.append(getattr(c, "text", ""))
        hr_out = "\n".join(parts).strip()

    # 방어 로직: 태그가 깨지면 강제 REVISE
    if not hr_out:
        hr_out = "[REVISE]\n문항 제목([자기소개서 문항 n])과 '+' 형식을 유지하여 작성 지시(message)만 재설계하십시오."
    else:
        first_line = hr_out.splitlines()[0].strip()
        if first_line not in ("[PASS]", "[REVISE]"):
            hr_out = (
                "[REVISE]\n"
                "첫 줄은 [PASS] 또는 [REVISE]여야 합니다.\n"
                "문항 제목([자기소개서 문항 n])과 '+' 형식을 유지하여 작성 지시(message)만 재설계하십시오."
            )

    return {"current_text": hr_out, "retry_count": state["retry_count"]}


# -----------------------------
# 4) 로컬 테스트용 실행
# -----------------------------
def main():
    # ✅ 여기 input을 네가 임의로 바꾸면서 테스트하면 됨 (입력은 딱 1개 텍스트 덩어리)
    # 권장: 참고정보/자소서/기존지시를 한 덩어리로 넣기
    demo_input = """
    [자기소개서 문항 1]
    지원 동기 및 직무 역량을 작성하시오.

    [현재 작성된 자기소개서]
    서비스 배포 이후 발생한 장애 상황에서는
    로그를 기반으로 원인을 분석하고,
    비동기 처리 구조를 개선하여 응답 지연 문제를 해결한 경험이 있습니다.
    이 경험을 통해 서비스 안정성과 문제 해결 능력의 중요성을 깊이 체감했습니다.

    [직전 작성 지시(message)]
    + 백엔드 직무와 직접적으로 연결되는 핵심 역량 2~3가지를 먼저 명시하시오
    + 일정 추천 서비스 프로젝트에서 본인이 맡은 역할을 구체적으로 서술하시오
    + 장애 대응 경험을 문제–원인–해결–결과 구조로 정리하시오
    """.strip()


    state: AgentState = {"current_text": demo_input, "retry_count": 0}

    # 1회 실행
    out_state = hr_agent(state)

    print("\n===== HR OUTPUT =====")
    print(out_state["current_text"])
    print("=====================\n")

    # 태그 확인(분기 확인용)
    tag_line = out_state["current_text"].splitlines()[0].strip()
    if tag_line == "[REVISE]":
        print("결론: REVISE → (이 출력의 아래 부분을) 다음 MCP 입력(message)로 보내면 됨.")
    elif tag_line == "[PASS]":
        print("결론: PASS → 면접관 단계로 넘기면 됨.")
    else:
        print("결론: 태그 파싱 실패(방어 로직이 REVISE로 강제했어야 하는데 확인 필요).")


if __name__ == "__main__":
    main()