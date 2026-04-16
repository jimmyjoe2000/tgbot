from __future__ import annotations

import asyncio
from pathlib import Path

import paramiko

from app.core.config import settings


class SSHDeploymentService:
    def __init__(self) -> None:
        self.private_key_path = Path(settings.deploy_ssh_private_key_path)
        self.password = settings.deploy_ssh_password

    async def run_script(
        self,
        host: str,
        script: str,
        username: str | None = None,
        port: int | None = None,
    ) -> str:
        return await asyncio.to_thread(
            self._run_script_sync,
            host,
            script,
            username or settings.deploy_default_ssh_user,
            port or settings.deploy_default_ssh_port,
        )

    def _run_script_sync(self, host: str, script: str, username: str, port: int) -> str:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 15,
        }
        if self.private_key_path.exists():
            connect_kwargs["pkey"] = self._load_private_key()
        elif self.password:
            connect_kwargs["password"] = self.password
        else:
            raise FileNotFoundError(
                f"未找到 SSH 私钥且未配置密码认证: {self.private_key_path}"
            )

        client.connect(**connect_kwargs)
        try:
            _, stdout, stderr = client.exec_command(script)
            output = stdout.read().decode("utf-8", errors="ignore")
            error = stderr.read().decode("utf-8", errors="ignore")
            return "\n".join(part for part in [output.strip(), error.strip()] if part)
        finally:
            client.close()

    def _load_private_key(self) -> paramiko.PKey:
        loaders = [
            paramiko.Ed25519Key.from_private_key_file,
            paramiko.RSAKey.from_private_key_file,
            paramiko.ECDSAKey.from_private_key_file,
        ]
        for loader in loaders:
            try:
                return loader(str(self.private_key_path))
            except paramiko.PasswordRequiredException:
                raise
            except Exception:
                continue
        raise ValueError(f"无法识别 SSH 私钥类型: {self.private_key_path}")
