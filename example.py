"""AgentChain 사용 예시."""

from agent_chain import run_pipeline
from agent_chain.agents import SimpleCoderAgent, SimpleReviewerAgent


def main():
    # 1. 에이전트 등록
    agents = {
        "primary_coder": SimpleCoderAgent(
            "primary_coder",
            config={"style": "google"},
        ),
        "strict_reviewer": SimpleReviewerAgent(
            "strict_reviewer",
            config={
                "require_docstring": True,
                "max_line_length": 50,  # 일부러 짧게 설정해 1회차 반려 유도
            },
        ),
    }

    # 2. 파이프라인 설정
    pipeline_config = {
        "max_iterations": 3,
        "steps": [
            {"role": "coder", "agent": "primary_coder"},
            {"role": "reviewer", "agent": "strict_reviewer"},
        ],
    }

    # 3. 실행
    result = run_pipeline(
        agents=agents,
        config=pipeline_config,
        request="사용자 입력을 검증하는 파이썬 함수를 작성해줘",
        workspace=".",
        language="python",
    )

    # 4. 결과 확인
    print("\n========== 최종 결과 ==========")
    print(f"총 반복 횟수: {result.iteration}")
    print(f"최종 검토 상태: {result.review.status if result.review else 'N/A'}")
    print(f"검토 메시지: {result.review.message if result.review else 'N/A'}")
    print("\n--- 생성된 코드 ---")
    print(result.code)
    print("\n--- 전체 히스토리 ---")
    for entry in result.history:
        print(f"  Iter {entry['iteration']} | {entry['role']} | {entry['agent']}")


if __name__ == "__main__":
    main()
