"""Tests for forge.py scaffolding helpers."""

from __future__ import annotations

import subprocess

import pytest
import yaml

import forge


class TestPortAllocation:
    def test_get_used_ports(self, agents_yaml_file):
        ports = forge.get_used_ports(agents_yaml_file)
        assert ports == [8081, 8082, 8083, 8084, 18789]

    def test_get_used_ports_empty_yaml(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("settings: {}\n", encoding="utf-8")
        assert forge.get_used_ports(str(path)) == []

    def test_next_available_port(self, agents_yaml_file):
        assert forge.next_available_port(agents_yaml_file) == 8085

    def test_next_available_port_with_gap(self, tmp_path):
        data = {
            "agents": {
                "a": {"endpoint": "ws://localhost:8085"},
                "b": {"endpoint": "ws://localhost:8087"},
            }
        }
        path = tmp_path / "agents.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")
        assert forge.next_available_port(str(path)) == 8086

    def test_next_available_port_empty(self, tmp_path):
        path = tmp_path / "agents.yaml"
        path.write_text("settings: {}\n", encoding="utf-8")
        assert forge.next_available_port(str(path)) == 8085


class TestVoiceAllocation:
    def test_get_used_voices(self, agents_yaml_file):
        voices = forge.get_used_voices(agents_yaml_file)
        assert "google/en-US-Chirp3-HD-Erinome" in voices
        assert "google/en-US-Chirp3-HD-Aoede" in voices
        assert len(voices) == 5

    def test_allocate_voice_returns_unused(self, agents_yaml_file):
        primary, fallback = forge.allocate_voice(agents_yaml_file)
        used = forge.get_used_voices(agents_yaml_file)
        assert primary not in used
        assert primary == "google/en-US-Chirp3-HD-Puck"
        assert fallback == "en-US-GuyNeural"

    def test_allocate_voice_pool_exhausted(self, tmp_path):
        all_voices = {v[0] for v in forge.VOICE_POOL}
        agents = {}
        for i, voice in enumerate(all_voices):
            agents[f"agent-{i}"] = {
                "endpoint": f"ws://localhost:{9000 + i}",
                "voice": voice,
            }
        data = {"agents": agents}
        path = tmp_path / "agents.yaml"
        path.write_text(yaml.dump(data), encoding="utf-8")
        with pytest.raises(RuntimeError, match="exhausted"):
            forge.allocate_voice(str(path))


class TestTokenGeneration:
    def test_token_length(self):
        token = forge.generate_token()
        assert len(token) == 64

    def test_token_hex_chars(self):
        token = forge.generate_token()
        assert all(c in "0123456789abcdef" for c in token)

    def test_token_uniqueness(self):
        tokens = {forge.generate_token() for _ in range(10)}
        assert len(tokens) == 10

    def test_custom_length(self):
        token = forge.generate_token(length=16)
        assert len(token) == 32


class TestYamlEditing:
    def test_add_agent(self, agents_yaml_file):
        forge.add_agent_to_dispatch(
            agents_yaml_file,
            name="rpg",
            port=8085,
            token_env="RPG_ANTHEM_TOKEN",
            voice="google/en-US-Chirp3-HD-Puck",
            fallback_voice="en-US-GuyNeural",
            wake_phrase="hey rpg",
        )
        with open(agents_yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "rpg" in data["agents"]
        entry = data["agents"]["rpg"]
        assert entry["type"] == "anthem"
        assert entry["endpoint"] == "ws://localhost:8085"
        assert entry["wake_phrase"] == "hey rpg"
        assert entry["voice"] == "google/en-US-Chirp3-HD-Puck"

    def test_preserves_existing_agents(self, agents_yaml_file):
        forge.add_agent_to_dispatch(
            agents_yaml_file,
            name="rpg",
            port=8085,
            token_env="RPG_ANTHEM_TOKEN",
            voice="google/en-US-Chirp3-HD-Puck",
            fallback_voice="en-US-GuyNeural",
            wake_phrase="hey rpg",
        )
        with open(agents_yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "navi" in data["agents"]
        assert "anthem" in data["agents"]
        assert len(data["agents"]) == 6

    def test_idempotent(self, agents_yaml_file):
        for _ in range(2):
            forge.add_agent_to_dispatch(
                agents_yaml_file,
                name="rpg",
                port=8085,
                token_env="RPG_ANTHEM_TOKEN",
                voice="google/en-US-Chirp3-HD-Puck",
                fallback_voice="en-US-GuyNeural",
                wake_phrase="hey rpg",
            )
        with open(agents_yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert len(data["agents"]) == 6


class TestEnvEditing:
    def test_append_key(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("EXISTING=foo\n", encoding="utf-8")
        forge.add_token_to_env(str(env), "NEW_KEY", "bar")
        content = env.read_text(encoding="utf-8")
        assert "NEW_KEY=bar" in content
        assert "EXISTING=foo" in content

    def test_no_duplicate(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("MY_KEY=abc\n", encoding="utf-8")
        forge.add_token_to_env(str(env), "MY_KEY", "xyz")
        assert env.read_text(encoding="utf-8").count("MY_KEY=") == 1

    def test_creates_file_if_missing(self, tmp_path):
        env = tmp_path / ".env"
        forge.add_token_to_env(str(env), "TOKEN", "secret")
        assert env.exists()
        assert "TOKEN=secret" in env.read_text(encoding="utf-8")


class TestChannelsYaml:
    def test_add_entry(self, tmp_path):
        path = tmp_path / "channels.yaml"
        path.write_text("dispatch:\n  token: abc\n", encoding="utf-8")
        forge.add_token_to_channels_yaml(str(path), "rpg", "tok123")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["rpg"]["token"] == "tok123"
        assert data["dispatch"]["token"] == "abc"

    def test_creates_file_if_missing(self, tmp_path):
        path = tmp_path / "channels.yaml"
        forge.add_token_to_channels_yaml(str(path), "rpg", "tok123")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["rpg"]["token"] == "tok123"

    def test_idempotent(self, tmp_path):
        path = tmp_path / "channels.yaml"
        path.write_text("", encoding="utf-8")
        forge.add_token_to_channels_yaml(str(path), "rpg", "tok1")
        forge.add_token_to_channels_yaml(str(path), "rpg", "tok2")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["rpg"]["token"] == "tok1"


class TestScaffold:
    def test_scaffold_creates_project(self, tmp_path, monkeypatch, agents_yaml_file):
        monkeypatch.setattr(forge, "DISPATCH_PATH", str(tmp_path / "dispatch"))
        dispatch_dir = tmp_path / "dispatch"
        dispatch_dir.mkdir()

        # Copy agents.yaml into the mock dispatch dir
        import shutil

        shutil.copy(agents_yaml_file, dispatch_dir / "agents.yaml")

        channels_dir = tmp_path / "anthem_home"
        channels_dir.mkdir()
        monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: channels_dir))
        (channels_dir / ".anthem").mkdir()

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = forge.scaffold_project(
            base_path=str(tmp_path / "projects"),
            name="My RPG",
            repo_url=None,
            tech_stack="python",
        )

        assert result["port"] == 8085
        assert result["voice"] == "google/en-US-Chirp3-HD-Puck"
        assert result["wake_phrase"] == "hey my-rpg"
        assert result["token_env"] == "MY_RPG_ANTHEM_TOKEN"

        project_dir = tmp_path / "projects" / "my-rpg"
        assert project_dir.exists()
        assert (project_dir / "WORKFLOW.md").exists()
        assert (project_dir / ".gitignore").exists()

        # Verify git init was called
        assert any("git" in str(c) for c in calls)
        assert any("anthem" in str(c) for c in calls)

    def test_scaffold_with_repo_url(self, tmp_path, monkeypatch, agents_yaml_file):
        monkeypatch.setattr(forge, "DISPATCH_PATH", str(tmp_path / "dispatch"))
        dispatch_dir = tmp_path / "dispatch"
        dispatch_dir.mkdir()

        import shutil

        shutil.copy(agents_yaml_file, dispatch_dir / "agents.yaml")

        channels_dir = tmp_path / "anthem_home"
        channels_dir.mkdir()
        monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: channels_dir))
        (channels_dir / ".anthem").mkdir()

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)

        forge.scaffold_project(
            base_path=str(tmp_path / "projects"),
            name="test",
            repo_url="https://github.com/user/repo.git",
            tech_stack="go",
        )

        assert any("clone" in str(c) for c in calls)


class TestValidation:
    def test_sanitize_spaces(self):
        assert forge.validate_project_name("My Project") == "my-project"

    def test_sanitize_special_chars(self):
        assert forge.validate_project_name("hello@world!") == "helloworld"

    def test_sanitize_casing(self):
        assert forge.validate_project_name("MyProject") == "myproject"

    def test_reject_empty(self):
        with pytest.raises(ValueError, match="empty"):
            forge.validate_project_name("@@@")

    def test_reject_reserved(self):
        with pytest.raises(ValueError, match="Reserved"):
            forge.validate_project_name("forge")

    def test_validate_port_free(self, agents_yaml_file):
        assert forge.validate_port_free(9999, agents_yaml_file) is True
        assert forge.validate_port_free(8081, agents_yaml_file) is False
