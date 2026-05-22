# AgentChain 통합 파일

이 디렉터리는 Codex, Kimi, Antigravity 같은 외부 CLI 호스트에 AgentChain을 등록하기 위한 사전 생성 파일입니다.

기본 전제는 `agc` 실행 파일이 PATH에 등록되어 있다는 것입니다. 긴 명령 이름인 `agent-chain`도 계속 사용할 수 있습니다.

## 간단 설정

저장소 루트에서 호스트별 등록 명령을 확인하려면:

```powershell
agc setup codex
agc setup kimi
agc setup antigravity
agc setup all
```

Codex, Kimi, Antigravity 등록 명령을 바로 실행하려면:

```powershell
agc setup codex --apply
agc setup kimi --apply
agc setup antigravity --apply
```

파일을 다른 위치로 복사한 뒤 그 위치 기준의 등록 명령을 보고 싶으면:

```powershell
agc setup all --copy-to D:\Tools\agent-chain-integrations
```

## Codex

저장소 루트를 바로 Codex marketplace로 등록할 수 있습니다.

```powershell
codex plugin marketplace add <AGENT_CHAIN_ROOT>
codex plugin add agent-chain-wrapper@agent-chain
```

`integrations/codex`만 따로 복사해서 사용할 경우에는 해당 복사 위치를 marketplace로 등록하고 `agent-chain-wrapper@agent-chain-local`을 설치합니다.

## Kimi

Kimi에는 사전 생성된 플러그인 디렉터리를 설치합니다.

```powershell
kimi plugin install <AGENT_CHAIN_ROOT>\integrations\kimi
```

## Antigravity

Antigravity CLI는 `agy` 실행 파일을 사용합니다. 플러그인은 아래처럼 등록합니다.

```powershell
agy plugin validate <AGENT_CHAIN_ROOT>\integrations\antigravity
agy plugin install <AGENT_CHAIN_ROOT>\integrations\antigravity
```

Antigravity 실행 파일명이 `agy`가 아니면 `--coder-command` 또는 `--reviewer-command`로 실제 경로를 넘기세요.

## 자주 쓰는 실행

```powershell
agc review "요청문" -R kimi -t src/generated.py -w . --json .agent-chain-review.json
agc review "요청문" -R codex -t src/generated.py -w . --json .agent-chain-review.json
agc challenge "요청문" -R kimi -t src/generated.py -w . --focus "보안"
agc review "요청문" -R kimi -t src/generated.py -w . --background
agc status
agc result <job-id>
agc delegate "요청문" -C codex -R kimi -t src/generated.py -w .
```

일반적인 스킬/플러그인 흐름에서는 현재 호스트 CLI가 파일을 수정하고 `agc review`가 리뷰어만 호출합니다. AgentChain이 코더와 리뷰어 CLI를 모두 직접 실행해야 할 때만 `agc delegate` 또는 `agc p`를 사용하세요.
