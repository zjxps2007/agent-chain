# AgentChain

서로 다른 에이전트가 **코딩 → 검토 → (재코딩)** 사이클을 반복하는 범용 파이프라인 프레임워크입니다.

## 특징

- **구조적 인터페이스 기반 확장**: `run(context)`를 구현하면 특정 베이스 클래스 없이도 어떤 LLM/규칙 엔진이든 연동 가능
- **선언적 파이프라인**: YAML/JSON으로 에이전트 조합과 규칙을 정의, 코드 수정 없이 워크플로우 변경
- **자동 재시도**: 검토에서 수정 요청(`changes_requested`) 시 설정된 최대 횟수 내에서 자동 재시도
- **컨텍스트 공유**: 코드, 리뷰 결과, 히스토리가 한 객체에 누적되어 에이전트 간 상태 전달이 명확
- **CLI 지원**: 터미널에서 바로 실행 가능

## 빠른 시작

### 1. 설치

로컬 체크아웃에서 바로 테스트할 때:

```bash
pip install -e .
```

GitHub 저장소에서 전역 명령으로 설치할 때:

```bash
uv tool install git+https://github.com/zjxps2007/agent-chain.git
```

`uv tool install` 대신 `pipx install git+https://github.com/zjxps2007/agent-chain.git`를 사용해도 됩니다. 어떤 방식을 쓰든 `agc` 명령이 PATH에서 실행되어야 합니다.

### 2. Codex 플러그인 등록

로컬 체크아웃에서 등록할 때:

```powershell
codex plugin marketplace add .
codex plugin add agent-chain-wrapper@agent-chain
```

GitHub 저장소를 직접 등록할 때:

```powershell
codex plugin marketplace add zjxps2007/agent-chain
codex plugin add agent-chain-wrapper@agent-chain
```

등록 후 Codex 세션에서 `agent-chain` 스킬을 사용하면 현재 Codex가 코딩하고, AgentChain이 선택한 리뷰어 CLI를 호출합니다.

### 3. 프로젝트 초기화

```bash
agc i
```

`config.yaml`과 `custom_agents.py` 템플릿이 생성됩니다.

### 4. 파이프라인 실행

```bash
agc r "사용자 입력을 검증하는 함수를 작성해줘"
```

결과를 파일로 저장:

```bash
agc r -o result.py "JSON 파서 클래스를 작성해줘"
```

## CLI 사용법

```text
$ agc --help
usage: agc [-h] {run,r,pair,p,init,i} ...

positional arguments:
  {run,r,pair,p,init,i}
    run (r)       파이프라인을 실행합니다.
    pair (p)      CLI 코더/리뷰어 쌍을 짧게 실행합니다.
    init (i)      프로젝트 초기화 파일을 생성합니다.

$ agc p --help
usage: agc pair [-h] [-c CONFIG] [--profile PROFILE]
               [--coder-cli CLI] [--reviewer-cli CLI] [--target-file PATH]
               [-o OUTPUT] [-l LANGUAGE] [-m MAX_ITERATIONS]
               [--workspace WORKSPACE] [--json PATH] request

options:
  -c, --config            설정 파일 (기본값: config.yaml)
  -C, --coder-cli         코더 CLI
  -R, --reviewer-cli      리뷰어 CLI
  -P, --profile           내장 CLI 조합 프로필
  -t, --target-file       생성/리뷰 대상 파일
  -w, --workspace         작업 디렉토리
  -o, --output            생성된 코드 저장 파일
  -l, --language          타겟 언어 (기본값: python)
  -m, --max-iterations    최대 반복 횟수 오버라이드
  --json PATH             전체 결과를 JSON으로 저장
```

### 예시

```bash
# 커스텀 설정 사용
agc r -c my-config.yaml -l python "API 클라이언트 작성"

# 반복 5회 허용
agc r -m 5 "복잡한 알고리즘 구현"

# 결과를 코드와 JSON 동시 저장
agc r -o src/solution.py --json result.json "데이터 처리 파이프라인"
```

## 수동 설치와 개발 환경

소스 체크아웃에서 개발 모드로 설치하려면:

```bash
pip install -e .
agc r "요청문"
agc p "요청문" -C codex -R kimi -t src/generated.py
agc ui
```

PowerShell 내장 alias와 충돌하지 않도록 AgentChain의 짧은 명령은 `agc`만 사용합니다.

```powershell
agc ui
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

## CLI 스킬/플러그인 설정

`agc setup`은 호스트별 등록 명령을 확인하거나, Kimi/Antigravity용 스킬 파일을 다른 위치로 복사할 때 사용합니다. 모든 호스트의 기본 흐름은 현재 CLI 세션이 코드를 작성하고, AgentChain은 `agc review`로 리뷰어만 호출하는 방식입니다.

```powershell
agc setup codex
agc setup kimi
agc setup antigravity
agc setup all
```

Codex, Kimi, Antigravity는 자동 등록까지 실행할 수 있습니다.

```powershell
agc setup codex --apply
agc setup kimi --apply
agc setup antigravity --apply
```

`--apply`는 Codex에 대해 `codex plugin marketplace add`와 `codex plugin add`를 실행하고, Kimi에 대해 `kimi plugin install`, Antigravity에 대해 `agy plugin validate`와 `agy plugin install`을 실행합니다.

미리 만들어 둔 파일을 다른 위치로 먼저 복사하려면:

```powershell
agc setup all --copy-to D:\Tools\agent-chain-integrations
```

완전 위임 실행은 `agc delegate` 또는 `agc p`로 사용할 수 있습니다. AgentChain이 코더 CLI와 리뷰어 CLI를 모두 직접 실행해야 할 때만 이 방식을 사용하세요.

## 실시간 웹 UI

`agc ui`는 리뷰 중심 화면입니다. 현재 CLI 세션이 직접 코딩하고, UI는 외부 리뷰어 CLI 호출과 그 결과만 실시간으로 보여줍니다.

로컬 웹 대시보드를 실행하면 리뷰 실행 상황을 이벤트 스트림으로 볼 수 있습니다.

```powershell
agc ui
```

기본 주소는 `http://127.0.0.1:8787`입니다.

웹 UI에서 볼 수 있는 항목:

- 리뷰어 실행 상태
- 리뷰 상태, 메시지, 제안
- 라인 코멘트와 리뷰 JSON
- 외부 리뷰어 CLI stdout/stderr 스트림

포트를 바꿀 때:

```powershell
agc ui --port 8790
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
      - agy
      - --prompt
      - "{prompt}"
```

`command`는 실제 CLI 문법에 맞게 바꾸면 됩니다. 리뷰어 CLI는 JSON(`status`, `message`, `suggestions`)을 출력하면 재시도 게이트로 동작합니다.

## 현재 CLI 세션을 코더로 쓰기

Codex, Kimi, Antigravity 같은 호스트 CLI가 이미 파일을 직접 수정하는 세션이라면 AgentChain이 코더 CLI를 다시 실행할 필요가 없습니다.
이때는 호스트 CLI가 코딩하고, AgentChain은 외부 리뷰어만 호출합니다.

```powershell
agc review "요청문" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
```

권장 루프:

1. 현재 CLI 세션이 직접 파일을 수정합니다.
2. `agc review ... -R kimi`로 Kimi 리뷰를 실행합니다.
3. `.agent-chain-review.json`의 `status`가 `changes_requested`이면 `message`와 `suggestions`를 반영해 다시 수정합니다.
4. `approved`이면 종료합니다.

파일 대신 stdin으로 코드를 넘길 수도 있습니다.

```powershell
Get-Content src/generated.py -Raw | agc review "요청문" -R kimi --stdin --json .agent-chain-review.json
```

## Codex 플러그인/스킬 래퍼

이 저장소 루트는 Codex 플러그인 marketplace로 바로 등록할 수 있습니다.

```powershell
codex plugin marketplace add <AGENT_CHAIN_ROOT>
codex plugin add agent-chain-wrapper@agent-chain
```

또는 AgentChain이 직접 등록 명령을 실행하게 할 수 있습니다.

```powershell
agc setup codex --apply
```

설치 후 Codex가 `agent-chain` 스킬을 사용할 수 있고, 실제 실행은 래퍼 스크립트가 담당합니다.

패키지를 설치한 환경에서는 짧은 명령을 바로 사용할 수 있습니다.

```powershell
agc p "요청문" -C codex -R kimi -t src/generated.py -w .
```

래퍼 스크립트를 직접 호출해야 하는 경우에는 해당 프로젝트 경로를 넘깁니다.

```powershell
uv run python <AGENT_CHAIN_ROOT>\plugins\agent-chain-wrapper\scripts\agent_chain_wrapper.py "요청문" --config <PROJECT_ROOT>\.agent-chain.yaml --workspace <PROJECT_ROOT>
```

Codex+Antigravity 기본 조합 템플릿은 `plugins/agent-chain-wrapper/configs/codex-antigravity.yaml`에 있습니다.

Codex/Kimi/Antigravity는 래퍼에서 바로 조합할 수도 있습니다.

```powershell
agc p "요청문" -C codex -R antigravity -t src/generated.py
agc p "요청문" -C kimi -R codex -t src/generated.py
agc p "요청문" -C antigravity -R kimi -t src/generated.py
```

지원하는 내장 CLI 워커:

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
agc p "요청문" -P kimi-codex -w .
```

Kimi를 호스트 CLI로 쓸 때는 플러그인으로 등록할 수 있습니다.

```powershell
kimi plugin install <AGENT_CHAIN_ROOT>\integrations\kimi
```

## 사전 생성 통합 패키지

배포용으로는 `integrations/` 아래의 미리 만들어진 파일을 사용할 수 있습니다. 이 방식은
`agent-chain` 실행 파일이 PATH에 있다고 가정하고, 각 CLI가 읽는 스킬/플러그인 파일만 등록합니다.

```text
integrations/
  codex/        # Codex 로컬 마켓플레이스와 플러그인
  kimi/         # Kimi 스킬 디렉터리
  antigravity/  # Antigravity 스킬/명령 템플릿
  common/       # 공통 프로필 설정과 얇은 래퍼 스크립트
```

Codex는 저장소 루트를 바로 등록하는 방식을 권장합니다.

```powershell
codex plugin marketplace add <AGENT_CHAIN_ROOT>
codex plugin add agent-chain-wrapper@agent-chain
```

Kimi:

```powershell
kimi plugin install <AGENT_CHAIN_ROOT>\integrations\kimi
```

Antigravity CLI는 `agy` 실행 파일을 사용합니다.

```powershell
agy plugin validate <AGENT_CHAIN_ROOT>\integrations\antigravity
agy plugin install <AGENT_CHAIN_ROOT>\integrations\antigravity
```

위 명령으로 AgentChain 플러그인을 Antigravity에 등록할 수 있습니다. Antigravity 실행 파일명이 `agy`가 아니면
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
├── web.py            # 실시간 웹 UI / SSE 서버
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
3. **MCP 연동**: Kimi CLI의 도구를 에이전트 내부에서 호출하도록 `run()` 메서드에 통합
4. **멀티 실행 큐**: 여러 AgentChain run을 큐잉하고 웹 UI에서 비교
