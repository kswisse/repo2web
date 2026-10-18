"""Unit tests for Docker daemon URL detection (no daemon required)."""

import pytest

from app.runtime import docker as docker_module


@pytest.mark.parametrize("system", ["Linux", "Darwin"])
def test_non_windows_uses_unix_socket(monkeypatch, system):
    monkeypatch.setattr(docker_module.platform, "system", lambda: system)
    assert docker_module._detect_docker_url() == "unix:///var/run/docker.sock"


def test_windows_prefers_answering_pipe(monkeypatch):
    monkeypatch.setattr(docker_module.platform, "system", lambda: "Windows")

    pinging = {"npipe:////./pipe/dockerDesktopLinuxEngine"}

    class FakeClient:
        def __init__(self, base_url):
            self.base_url = base_url

        def ping(self):
            if self.base_url not in pinging:
                raise RuntimeError("no pipe")

        def close(self):
            pass

    monkeypatch.setattr(docker_module.docker, "DockerClient", FakeClient)
    assert (
        docker_module._detect_docker_url()
        == "npipe:////./pipe/dockerDesktopLinuxEngine"
    )


def test_windows_falls_back_to_legacy_pipe_when_none_answer(monkeypatch):
    monkeypatch.setattr(docker_module.platform, "system", lambda: "Windows")

    class DeadClient:
        def __init__(self, base_url):
            pass

        def ping(self):
            raise RuntimeError("no daemon")

        def close(self):
            pass

    monkeypatch.setattr(docker_module.docker, "DockerClient", DeadClient)
    assert docker_module._detect_docker_url() == "npipe:////./pipe/docker_engine"
