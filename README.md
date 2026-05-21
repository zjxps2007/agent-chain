# AgentChain

서로 다른 에이전트가 **코딩 → 검토 → (재코딩)** 사이클을 반복하는 범용 파이프라인 프레임워크입니다.

## 특징

- **구조적 인터페이스 기반 확장**: `run(context)`를 구현하면 특정 베이스 클래스 없이도 어떤 LLM/규칙 엔진이든 연동 가능
- **선언적 파이프라인**: YAML/JSON으로 에이전트 조합과 규칙을 정의, 코드 수정 없이 워크플로우 변경
- **자동 Retry**: 검토에서 수정 요청(`changes_requested`) 시 설정된 최대 횟수 내에서 자동 재시도
- **Context 공유**: 코드, 리뷰 결과, 히스토리가 한 객체에 누적되어 에이전트 간 상태 전달이 명확
- **CLI 지원**: 터미널에서 바로 실행 가능

## 빠른 시작

### 1. 프로젝트 초기화

```bash
python -m agent_chain init
```

`config.yaml`과 `custom_agents.py` 템플릿이 생성됩니다.

### 2. 파이프라인 실행

```bash
python -m agent_chain run "사용자 입력을 검증하는 함수를 작성해줘"
```

결과를 파일로 저장:

```bash
python -m agent_chain run -o result.py "JSON 파서 클래스를 작성해줘"
```

## CLI 사용법

```text
$ python -m agent_chain --help
usage: agent-chain [-h] {run,init} ...

positional arguments:
  {run,init}
    run       파이프라인을 실행합니다.
    init      프로젝트 초기화 파일을 생성합니다.

$ python -m agent_chain run --help
usage: agent-chain run [-h] [-c CONFIG] [-o OUTPUT] [-l LANGUAGE]
                       [-m MAX_ITERATIONS] [--json PATH]
                       request

options:
  -c, --config            설정 파일 (기본값: config.yaml)
  -o, --output            생성된 코드 저장 파일
  -l, --language          타겟 언어 (기본값: python)
  -m, --max-iterations    최대 반복 횟수 오버라이드
  --json PATH             전체 결과를 JSON으로 저장
```

### 예시

```bash
# 커스텀 설정 사용
python -m agent_chain run -c my-config.yaml -l python "API 클라이언트 작성"

# 반복 5회 허용
python -m agent_chain run -m 5 "복잡한 알고리즘 구현"

# 결과를 코드와 JSON 동시 저장
python -m agent_chain run -o src/solution.py --json result.json "데이터 처리 파이프라인"
```

## 설치 (선택)

`agent-chain` 명령어를 글로벌로 등록하려면:

```bash
pip install -e .
agent-chain run "요청문"
```

LLM 에이전트(`LLMCoderAgent`, `LLMReviewerAgent`)를 사용하려면 OpenAI SDK 선택 의존성을 설치하고
`OPENAI_API_KEY`를 설정하세요.

```bash
pip install -e ".[llm]"
```

개발/테스트 의존성:

```bash
pip install -e ".[dev]"
pytest
```

## 커스텀 에이전트 만들기

```python
from agent_chain.core import Context, ReviewResult

class MyLLMCoder:
    def __init__(self, name: str, config: dict | None = None) -> None:
        self.name = name
        self.config = config or {}

    def run(self, context: Context) -> str:
        # 이전 리뷰 접근
        if context.review:
            feedback = context.review.message
        # LLM 호출 또는 자체 로직
        return "...생성된 코드..."

class MyReviewer:
    def __init__(self, name: str, config: dict | None = None) -> None:
        self.name = name
        self.config = config or {}

    def run(self, context: Context) -> ReviewResult:
        return ReviewResult(status="approved", message="검토 통과")
```

만든 에이전트를 `config.yaml`에 등록하고, 플러그인 디렉토리 또는 `class: module.ClassName` 설정으로 동적 로드할 수 있습니다.

플러그인 디렉토리로 동적 로드되는 에이전트는 생성자 시그니처와 `run(context)` 시그니처를 검증합니다.
생성자는 `(name, config)`, `config` 단일 인자, 무인자 형태를 지원하며 필요한 경우 `name`과 `config` 속성을 자동 보강합니다.
`role`은 기본 입출력 추론용 메타데이터이며, 필요하면 step에 `output: code` 또는 `output: review`를 지정할 수 있습니다.

## LLM 에이전트 설정 예시

```yaml
max_iterations: 2

steps:
  - role: coder
    agent: llm_coder
  - role: reviewer
    agent: llm_reviewer

agent_configs:
  llm_coder:
    model: gpt-5.5
    target_file: src/generated.py
  llm_reviewer:
    model: gpt-5.5
    target_file: src/generated.py
```

## CLI 조합 예시

전용 어댑터가 없는 CLI는 `generic_cli_reviewer` 또는 `generic_cli_coder`로 연결할 수 있습니다.

```yaml
max_iterations: 2

steps:
  - role: coder
    agent: codex_coder
    output: code
  - role: reviewer
    agent: antigravity_reviewer
    output: review

agent_configs:
  codex_coder:
    model: gpt-5.4
    target_file: src/generated.py
  antigravity_reviewer:
    class: agent_chain.agents.cli.ConfigurableCLIReviewer
    target_file: src/generated.py
    command:
      - antigravity
      - --prompt
      - "{prompt}"
```

`command`는 실제 CLI 문법에 맞게 바꾸면 됩니다. 리뷰어 CLI는 JSON(`status`, `message`, `suggestions`)을 출력하면 재시도 게이트로 동작합니다.

## Codex 플러그인/스킬 wrapper

이 repo에는 Codex에서 설치할 수 있는 로컬 플러그인 wrapper가 포함되어 있습니다.

```powershell
codex plugin marketplace add <AGENT_CHAIN_ROOT>
codex plugin add agent-chain-wrapper@agent-chain-local
```

설치 후 Codex가 `agent-chain` 스킬을 사용할 수 있고, 실제 실행은 wrapper 스크립트가 담당합니다.

```powershell
uv run python .\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "요청문" --config .\config.yaml --workspace .
```

다른 프로젝트를 대상으로 실행할 때는 해당 프로젝트 경로를 넘깁니다.

```powershell
uv run python <AGENT_CHAIN_ROOT>\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "요청문" --config <PROJECT_ROOT>\.agent-chain.yaml --workspace <PROJECT_ROOT>
```

Codex+Antigravity 기본 조합 템플릿은 `plugins/agent-chain-wrapper/configs/codex-antigravity.yaml`에 있습니다.

Codex/Kimi/Antigravity는 wrapper에서 바로 조합할 수도 있습니다.

```powershell
uv run python .\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "요청문" --coder-cli codex --reviewer-cli antigravity --target-file src/generated.py
uv run python .\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "요청문" --coder-cli kimi --reviewer-cli codex --target-file src/generated.py
uv run python .\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "요청문" --coder-cli antigravity --reviewer-cli kimi --target-file src/generated.py
```

지원하는 built-in CLI worker:

- `codex`
- `kimi`
- `antigravity`

내장 프로필:

- `codex-antigravity`
- `codex-kimi`
- `kimi-codex`
- `kimi-antigravity`
- `antigravity-codex`
- `antigravity-kimi`

예:

```powershell
uv run python .\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "요청문" --profile kimi-codex --workspace .
```

Kimi를 host CLI로 쓸 때는 같은 skill 디렉터리를 넘길 수 있습니다.

```powershell
kimi --skills-dir <AGENT_CHAIN_ROOT>\plugins\agent-chain-wrapper\skills --prompt "agent-chain skill로 이 요청을 처리해줘."
```

## 사전 생성 integration pack

배포용으로는 `integrations/` 아래의 미리 만들어진 파일을 사용할 수 있습니다. 이 방식은
`agent-chain` 실행 파일이 PATH에 있다고 가정하고, 각 CLI가 읽는 skill/plugin 파일만 등록합니다.

```text
integrations/
  codex/        # Codex local marketplace + plugin
  kimi/         # Kimi skills-dir
  antigravity/  # Antigravity skill/command templates
  common/       # 공통 profile config와 thin wrapper scripts
```

Codex:

```powershell
codex plugin marketplace add <AGENT_CHAIN_ROOT>\integrations\codex
codex plugin add agent-chain-wrapper@agent-chain-local
```

Kimi:

```powershell
kimi --skills-dir <AGENT_CHAIN_ROOT>\integrations\kimi\skills --prompt "agent-chain으로 이 요청을 처리해줘."
```

Antigravity:

```text
integrations/antigravity/skills
integrations/antigravity/commands
```

위 파일들을 Antigravity의 skill/custom-command 경로에 등록하면 됩니다. Antigravity 실행 파일명이 다르면
`--coder-command` 또는 `--reviewer-command`로 실제 경로를 넘기세요.

## 아키텍처

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Coder     │────▶│  Reviewer   │────▶│  Decision   │
│  (Agent)    │     │  (Agent)    │     │ (Pipeline)  │
└─────────────┘     └─────────────┘     └──────┬──────┘
       ▲                                         │
       └─────────────────────────────────────────┘
                    changes_requested
```

## 프로젝트 구조

```
agent_chain/
├── __init__.py
├── __main__.py       # python -m agent_chain 지원
├── cli.py            # CLI 진입점
├── core.py           # Context, Agent(ABC), Pipeline
├── llm.py            # OpenAI Responses API 헬퍼
├── pipeline.py       # run_pipeline() 헬퍼
├── registry.py       # 에이전트 로딩 및 인터페이스 검증
└── agents/
    ├── __init__.py
    ├── base.py       # BaseCoderAgent, BaseReviewerAgent
    ├── coder.py      # SimpleCoderAgent, LLMCoderAgent
    └── reviewer.py   # SimpleReviewerAgent, LLMReviewerAgent
tests/
├── test_core.py
├── test_llm_agents.py
└── test_registry.py
```

## 확장 아이디어

1. **멀티 리뷰어**: 보안 리뷰어, 성능 리뷰어, 스타일 리뷰어를 병렬/순차로 연결
2. **멀티 코더**: A 코더가 생성 → B 코더가 리팩토링 → 리뷰어가 검토
3. **MCP 연동**: Kimi CLI의 도구를 에이전트 낶부에서 호출하도록 `run()` 메서드에 통합
4. **웹 UI**: Streamlit/Gradio로 `run_pipeline()`을 감싸 시각화
