"""에이전트가 작업 디렉토리를 조작할 수 있는 도구 집합."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union


@dataclass
class ShellResult:
    """셸 명령 실행 결과."""
    returncode: int
    stdout: str
    stderr: str


class Environment:
    """파일 시스템, Git, 셸에 대한 안전한 접근 인터페이스.

    Codex CLI의 sandbox 개념을 차용하여, 리뷰어는 read-only,
    코더는 read-write로 동작하도록 제어할 수 있습니다.
    """

    def __init__(self, workspace: Path, *, read_only: bool = False) -> None:
        self.workspace = Path(workspace).resolve()
        self.read_only = read_only

    def _resolve(self, path: str) -> Path:
        """상대 경로를 workspace 기준으로 절대 경로로 변환.

        workspace 밖의 경로에 대한 접근을 차단하여 path traversal을 방지합니다.
        """
        p = Path(path)
        if not p.is_absolute():
            p = self.workspace / p
        resolved = p.resolve()
        if not resolved.is_relative_to(self.workspace):
            raise PermissionError(
                f"workspace 밖의 경로에 접근할 수 없습니다: {resolved}"
            )
        return resolved

    def read_file(self, path: str) -> str:
        """파일 내용을 읽어 문자열로 반환."""
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {target}")
        return target.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        """파일에 내용을 씁니다. read_only 모드에서는 차단됩니다."""
        if self.read_only:
            raise PermissionError("현재 Environment는 read-only 모드입니다.")
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def run_shell(self, command: Union[str, List[str]]) -> ShellResult:
        """셸 명령을 실행합니다.

        read_only 모드에서는 셸 명령 실행이 차단됩니다.

        Args:
            command: 문자열이든 리스트든 안전하게 shell=False로 실행합니다.
        """
        if self.read_only:
            raise PermissionError(
                "현재 Environment는 read-only 모드입니다. "
                "셸 명령을 실행할 수 없습니다."
            )

        kwargs = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "cwd": self.workspace,
        }
        if isinstance(command, str):
            cmd_list = shlex.split(command, posix=(os.name != "nt"))
        else:
            cmd_list = list(command)

        if cmd_list:
            executable = shutil.which(str(cmd_list[0]))
            if executable:
                cmd_list[0] = executable

        result = subprocess.run(cmd_list, shell=False, **kwargs)
        return ShellResult(
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    def git_diff(self, base: str = "HEAD") -> str:
        """Git diff 결과를 문자열로 반환. Git 저장소가 아니면 빈 문자열."""
        result = self.run_shell(f"git diff {base}")
        if result.returncode != 0:
            return ""
        return result.stdout

    def list_files(self, pattern: str = "*") -> List[str]:
        """workspace 내 파일 목록을 반환."""
        return [str(p.relative_to(self.workspace)) for p in self.workspace.rglob(pattern) if p.is_file()]

    def exists(self, path: str) -> bool:
        """파일/디렉토리 존재 여부."""
        return self._resolve(path).exists()
