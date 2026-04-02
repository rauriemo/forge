"""Tests for forge.py scaffolding helpers."""

from __future__ import annotations

import json
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
        )
        with open(agents_yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert "rpg" in data["agents"]
        entry = data["agents"]["rpg"]
        assert entry["type"] == "anthem"
        assert entry["endpoint"] == "ws://localhost:8085"
        assert entry["wake_word"] == "assets/hey-rpg.ppn"
        assert entry["voice"] == "google/en-US-Chirp3-HD-Puck"

    def test_preserves_existing_agents(self, agents_yaml_file):
        forge.add_agent_to_dispatch(
            agents_yaml_file,
            name="rpg",
            port=8085,
            token_env="RPG_ANTHEM_TOKEN",
            voice="google/en-US-Chirp3-HD-Puck",
            fallback_voice="en-US-GuyNeural",
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


class TestGetDispatchToken:
    def test_reads_shared_token(self, tmp_path):
        path = tmp_path / "channels.yaml"
        path.write_text("dispatch:\n  token: shared-secret-123\n", encoding="utf-8")
        assert forge.get_dispatch_token(str(path)) == "shared-secret-123"

    def test_missing_file_raises(self, tmp_path):
        path = tmp_path / "channels.yaml"
        with pytest.raises(FileNotFoundError):
            forge.get_dispatch_token(str(path))

    def test_missing_token_raises(self, tmp_path):
        path = tmp_path / "channels.yaml"
        path.write_text("slack:\n  bot_token: xoxb\n", encoding="utf-8")
        with pytest.raises(ValueError, match=r"No dispatch\.token"):
            forge.get_dispatch_token(str(path))


class TestSettings:
    def test_defaults_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(forge, "SETTINGS_PATH", tmp_path / "settings.json")
        settings = forge.load_settings()
        assert settings == {"repo_visibility": "public"}

    def test_save_and_load(self, tmp_path, monkeypatch):
        path = tmp_path / "settings.json"
        monkeypatch.setattr(forge, "SETTINGS_PATH", path)
        forge.save_settings({"repo_visibility": "private"})
        assert path.exists()
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["repo_visibility"] == "private"
        assert forge.load_settings() == {"repo_visibility": "private"}

    def test_set_visibility_public(self, tmp_path, monkeypatch):
        monkeypatch.setattr(forge, "SETTINGS_PATH", tmp_path / "settings.json")
        result = forge.set_repo_visibility("public")
        assert result["repo_visibility"] == "public"

    def test_set_visibility_private(self, tmp_path, monkeypatch):
        monkeypatch.setattr(forge, "SETTINGS_PATH", tmp_path / "settings.json")
        result = forge.set_repo_visibility("private")
        assert result["repo_visibility"] == "private"

    def test_set_visibility_persists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(forge, "SETTINGS_PATH", tmp_path / "settings.json")
        forge.set_repo_visibility("private")
        assert forge.load_settings()["repo_visibility"] == "private"
        forge.set_repo_visibility("public")
        assert forge.load_settings()["repo_visibility"] == "public"

    def test_set_visibility_invalid(self, tmp_path, monkeypatch):
        monkeypatch.setattr(forge, "SETTINGS_PATH", tmp_path / "settings.json")
        with pytest.raises(ValueError, match="Invalid visibility"):
            forge.set_repo_visibility("internal")


class TestCreateGithubRepo:
    def test_creates_public_repo(self, tmp_path, monkeypatch):
        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        url = forge.create_github_repo(str(tmp_path), "my-app")

        assert url == "https://github.com/rauriemo/my-app"
        assert calls[0] == ["git", "add", "."]
        assert calls[1][0:2] == ["git", "commit"]
        gh_call = calls[2]
        assert "gh" in gh_call
        assert "--public" in gh_call
        assert "rauriemo/my-app" in gh_call

    def test_creates_private_repo(self, tmp_path, monkeypatch):
        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        forge.create_github_repo(str(tmp_path), "secret-proj", private=True)

        gh_call = calls[2]
        assert "--private" in gh_call
        assert "--public" not in gh_call

    def test_passes_cwd(self, tmp_path, monkeypatch):
        cwds = []

        def mock_run(cmd, **kwargs):
            cwds.append(kwargs.get("cwd"))
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        forge.create_github_repo(str(tmp_path), "test")

        assert all(c == str(tmp_path) for c in cwds)

    def test_gh_failure_propagates(self, tmp_path, monkeypatch):
        call_count = 0

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise subprocess.CalledProcessError(1, cmd)
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        with pytest.raises(subprocess.CalledProcessError):
            forge.create_github_repo(str(tmp_path), "dup-repo")


class TestScaffold:
    def _setup_scaffold_env(self, tmp_path, monkeypatch, agents_yaml_file):
        """Common setup: mock DISPATCH_PATH, channels.yaml, settings, and subprocess."""
        import shutil

        monkeypatch.setattr(forge, "DISPATCH_PATH", str(tmp_path / "dispatch"))
        monkeypatch.setattr(forge, "SETTINGS_PATH", tmp_path / "settings.json")
        dispatch_dir = tmp_path / "dispatch"
        dispatch_dir.mkdir()
        shutil.copy(agents_yaml_file, dispatch_dir / "agents.yaml")

        channels_dir = tmp_path / "anthem_home"
        channels_dir.mkdir()
        monkeypatch.setattr("pathlib.Path.home", staticmethod(lambda: channels_dir))
        anthem_dir = channels_dir / ".anthem"
        anthem_dir.mkdir()
        (anthem_dir / "channels.yaml").write_text(
            "dispatch:\n  token: shared-test-token\n", encoding="utf-8"
        )

        calls = []

        def mock_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        return calls, dispatch_dir

    def test_scaffold_creates_project(self, tmp_path, monkeypatch, agents_yaml_file):
        calls, dispatch_dir = self._setup_scaffold_env(tmp_path, monkeypatch, agents_yaml_file)

        result = forge.scaffold_project(
            base_path=str(tmp_path / "projects"),
            name="My RPG",
        )

        assert result["port"] == 8085
        assert result["voice"] == "google/en-US-Chirp3-HD-Puck"
        assert result["wake_phrase"] == "hey my-rpg"
        assert result["token_env"] == "MY_RPG_ANTHEM_TOKEN"
        assert result["repo"] == "https://github.com/rauriemo/my-rpg"

        project_dir = tmp_path / "projects" / "my-rpg"
        assert project_dir.exists()
        assert (project_dir / "WORKFLOW.md").exists()
        assert (project_dir / ".gitignore").exists()

        workflow = (project_dir / "WORKFLOW.md").read_text(encoding="utf-8")
        assert 'repo: "rauriemo/my-rpg"' in workflow
        assert "localhost:8085" in workflow

        assert any("git" in str(c) and "init" in str(c) for c in calls)
        assert any("anthem" in str(c) for c in calls)
        assert any("git" in str(c) and "add" in str(c) for c in calls)
        assert any("git" in str(c) and "commit" in str(c) for c in calls)
        assert any("gh" in str(c) and "repo" in str(c) for c in calls)

        gh_call = next(c for c in calls if "gh" in str(c))
        assert "--public" in gh_call

        env_content = (dispatch_dir / ".env").read_text(encoding="utf-8")
        assert "MY_RPG_ANTHEM_TOKEN=shared-test-token" in env_content

        agents_data = yaml.safe_load((dispatch_dir / "agents.yaml").read_text(encoding="utf-8"))
        assert agents_data["agents"]["my-rpg"]["wake_word"] == "assets/hey-my-rpg.ppn"

    def test_scaffold_with_repo_url(self, tmp_path, monkeypatch, agents_yaml_file):
        calls, _ = self._setup_scaffold_env(tmp_path, monkeypatch, agents_yaml_file)

        forge.scaffold_project(
            base_path=str(tmp_path / "projects"),
            name="test",
            repo_url="https://github.com/user/repo.git",
        )

        assert any("clone" in str(c) for c in calls)

    def test_scaffold_respects_private_setting(self, tmp_path, monkeypatch, agents_yaml_file):
        calls, _ = self._setup_scaffold_env(tmp_path, monkeypatch, agents_yaml_file)
        forge.set_repo_visibility("private")

        result = forge.scaffold_project(
            base_path=str(tmp_path / "projects"),
            name="secret",
        )

        assert result["repo"] == "https://github.com/rauriemo/secret"
        gh_call = next(c for c in calls if "gh" in str(c))
        assert "--private" in gh_call


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
