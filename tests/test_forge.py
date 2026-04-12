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


class TestPrismYamlEditing:
    def test_add_agent_with_repo(self, tmp_path):
        prism_yaml = tmp_path / "agents.yaml"
        prism_yaml.write_text(yaml.dump({"agents": {}}), encoding="utf-8")
        forge.add_agent_to_prism(
            str(prism_yaml),
            name="rpg",
            prism_port=3107,
            voice="google/en-US-Chirp3-HD-Puck",
            fallback_voice="en-US-GuyNeural",
            repo="rauriemo/rpg",
        )
        data = yaml.safe_load(prism_yaml.read_text(encoding="utf-8"))
        entry = data["agents"]["rpg"]
        assert entry["repo"] == "rauriemo/rpg"
        assert entry["endpoint"] == "ws://localhost:3107"
        assert entry["voice"] == "google/en-US-Chirp3-HD-Puck"
        assert entry["token_env"] == "PRISM_ANTHEM_TOKEN"

    def test_add_agent_without_repo(self, tmp_path):
        prism_yaml = tmp_path / "agents.yaml"
        prism_yaml.write_text(yaml.dump({"agents": {}}), encoding="utf-8")
        forge.add_agent_to_prism(
            str(prism_yaml),
            name="rpg",
            prism_port=3107,
            voice="google/en-US-Chirp3-HD-Puck",
            fallback_voice="en-US-GuyNeural",
        )
        data = yaml.safe_load(prism_yaml.read_text(encoding="utf-8"))
        entry = data["agents"]["rpg"]
        assert "repo" not in entry

    def test_idempotent(self, tmp_path):
        prism_yaml = tmp_path / "agents.yaml"
        prism_yaml.write_text(yaml.dump({"agents": {}}), encoding="utf-8")
        for _ in range(2):
            forge.add_agent_to_prism(
                str(prism_yaml),
                name="rpg",
                prism_port=3107,
                voice="google/en-US-Chirp3-HD-Puck",
                fallback_voice="en-US-GuyNeural",
                repo="rauriemo/rpg",
            )
        data = yaml.safe_load(prism_yaml.read_text(encoding="utf-8"))
        assert len(data["agents"]) == 1

    def test_creates_file_if_missing(self, tmp_path):
        prism_yaml = tmp_path / "agents.yaml"
        forge.add_agent_to_prism(
            str(prism_yaml),
            name="rpg",
            prism_port=3107,
            voice="google/en-US-Chirp3-HD-Puck",
            fallback_voice="en-US-GuyNeural",
            repo="rauriemo/rpg",
        )
        assert prism_yaml.exists()
        data = yaml.safe_load(prism_yaml.read_text(encoding="utf-8"))
        assert "rpg" in data["agents"]


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


class TestGetPrismToken:
    def test_reads_existing_token(self, tmp_path):
        path = tmp_path / "channels.yaml"
        path.write_text("prism:\n  token: prism-secret-456\n", encoding="utf-8")
        assert forge.get_prism_token(str(path)) == "prism-secret-456"

    def test_generates_token_if_missing(self, tmp_path):
        path = tmp_path / "channels.yaml"
        path.write_text("dispatch:\n  token: abc\n", encoding="utf-8")
        token = forge.get_prism_token(str(path))
        assert len(token) == 64  # 32 bytes = 64 hex chars
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["prism"]["token"] == token

    def test_missing_file_raises(self, tmp_path):
        path = tmp_path / "channels.yaml"
        with pytest.raises(FileNotFoundError):
            forge.get_prism_token(str(path))

    def test_idempotent_on_second_call(self, tmp_path):
        path = tmp_path / "channels.yaml"
        path.write_text("dispatch:\n  token: abc\n", encoding="utf-8")
        token1 = forge.get_prism_token(str(path))
        token2 = forge.get_prism_token(str(path))
        assert token1 == token2


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


class TestNormalizeRepoUrl:
    def test_owner_repo_shorthand(self):
        assert (
            forge.normalize_repo_url("felipeblassioli/oncall-roster")
            == "https://github.com/felipeblassioli/oncall-roster.git"
        )

    def test_owner_repo_with_dots(self):
        assert (
            forge.normalize_repo_url("my-org/my-lib.js")
            == "https://github.com/my-org/my-lib.js.git"
        )

    def test_https_url_unchanged(self):
        url = "https://github.com/user/repo.git"
        assert forge.normalize_repo_url(url) == url

    def test_https_url_without_dot_git_unchanged(self):
        url = "https://github.com/user/repo"
        assert forge.normalize_repo_url(url) == url

    def test_ssh_url_unchanged(self):
        url = "git@github.com:user/repo.git"
        assert forge.normalize_repo_url(url) == url

    def test_ssh_protocol_url_unchanged(self):
        url = "ssh://git@github.com/user/repo.git"
        assert forge.normalize_repo_url(url) == url

    def test_strips_whitespace(self):
        assert forge.normalize_repo_url("  owner/repo  ") == "https://github.com/owner/repo.git"

    def test_gitlab_https_unchanged(self):
        url = "https://gitlab.com/org/project.git"
        assert forge.normalize_repo_url(url) == url

    def test_relative_dot_slash_not_treated_as_shorthand(self):
        assert forge.normalize_repo_url("./repo") == "./repo"

    def test_relative_dotdot_slash_not_treated_as_shorthand(self):
        assert forge.normalize_repo_url("../repo") == "../repo"

    def test_nested_path_not_treated_as_shorthand(self):
        assert forge.normalize_repo_url("a/b/c") == "a/b/c"

    def test_http_url_unchanged(self):
        url = "http://github.com/user/repo.git"
        assert forge.normalize_repo_url(url) == url

    def test_git_protocol_url_unchanged(self):
        url = "git://github.com/user/repo.git"
        assert forge.normalize_repo_url(url) == url

    def test_single_segment_not_treated_as_shorthand(self):
        assert forge.normalize_repo_url("justrepo") == "justrepo"

    def test_shorthand_with_underscores(self):
        assert forge.normalize_repo_url("my_org/my_repo") == "https://github.com/my_org/my_repo.git"

    def test_shorthand_with_hyphens(self):
        assert forge.normalize_repo_url("my-org/my-repo") == "https://github.com/my-org/my-repo.git"


class TestAgentFileParsing:
    def test_parse_valid_file(self, tmp_path):
        p = tmp_path / "agent.md"
        p.write_text(
            "---\nname: Test\ndescription: A test agent\nrole: reviewer\n---\n\nBody text here.\n",
            encoding="utf-8",
        )
        fm, body = forge.parse_agent_file(str(p))
        assert fm["name"] == "Test"
        assert fm["description"] == "A test agent"
        assert fm["role"] == "reviewer"
        assert "Body text here." in body

    def test_parse_minimal_file(self, tmp_path):
        p = tmp_path / "agent.md"
        p.write_text("---\nname: Min\n---\n\nHello.\n", encoding="utf-8")
        fm, body = forge.parse_agent_file(str(p))
        assert fm["name"] == "Min"
        assert "description" not in fm
        assert "Hello." in body

    def test_parse_extra_unknown_fields(self, tmp_path):
        p = tmp_path / "agent.md"
        p.write_text("---\nname: X\nfuture_field: hello\n---\n\nBody.\n", encoding="utf-8")
        fm, _body = forge.parse_agent_file(str(p))
        assert fm["future_field"] == "hello"
        assert fm["name"] == "X"

    def test_parse_missing_delimiters_raises(self, tmp_path):
        p = tmp_path / "agent.md"
        p.write_text("name: Test\nNo delimiters here.\n", encoding="utf-8")
        with pytest.raises(ValueError, match="delimiter"):
            forge.parse_agent_file(str(p))

    def test_parse_empty_file_raises(self, tmp_path):
        p = tmp_path / "agent.md"
        p.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="Empty"):
            forge.parse_agent_file(str(p))

    def test_write_then_parse_roundtrip(self, tmp_path):
        p = tmp_path / "agent.md"
        fm_in = {"name": "Roundtrip", "description": "Test roundtrip", "role": "tester"}
        body_in = "This is the body.\n\nWith multiple paragraphs.\n"
        forge.write_agent_file(str(p), fm_in, body_in)
        fm_out, body_out = forge.parse_agent_file(str(p))
        assert fm_out["name"] == fm_in["name"]
        assert fm_out["description"] == fm_in["description"]
        assert fm_out["role"] == fm_in["role"]
        assert body_out == body_in

    def test_write_preserves_body_verbatim(self, tmp_path):
        p = tmp_path / "agent.md"
        body = "Line one.\n  Indented line.\n\n- Bullet\n- List\n"
        forge.write_agent_file(str(p), {"name": "V"}, body)
        _, body_out = forge.parse_agent_file(str(p))
        assert body_out == body

    def test_parse_body_with_horizontal_rule(self, tmp_path):
        p = tmp_path / "agent.md"
        p.write_text(
            "---\nname: Test\n---\n\nBefore rule\n\n---\n\nAfter rule\n",
            encoding="utf-8",
        )
        fm, body = forge.parse_agent_file(str(p))
        assert fm["name"] == "Test"
        assert "Before rule" in body
        assert "After rule" in body

    def test_parse_body_with_multiple_horizontal_rules(self, tmp_path):
        p = tmp_path / "agent.md"
        p.write_text(
            "---\nname: Multi\n---\n\nSection A\n\n---\n\nSection B\n\n---\n\nSection C\n",
            encoding="utf-8",
        )
        fm, body = forge.parse_agent_file(str(p))
        assert fm["name"] == "Multi"
        assert "Section A" in body
        assert "Section B" in body
        assert "Section C" in body


class TestCloudContentHash:
    def test_deterministic(self):
        fm = {"name": "A", "description": "B"}
        body = "Body"
        h1 = forge.compute_cloud_content_hash(fm, body)
        h2 = forge.compute_cloud_content_hash(fm, body)
        assert h1 == h2

    def test_different_description(self):
        body = "Same"
        h1 = forge.compute_cloud_content_hash({"name": "A", "description": "B"}, body)
        h2 = forge.compute_cloud_content_hash({"name": "A", "description": "C"}, body)
        assert h1 != h2

    def test_different_model(self):
        body = "Same"
        h1 = forge.compute_cloud_content_hash({"name": "A", "model": "opus"}, body)
        h2 = forge.compute_cloud_content_hash({"name": "A", "model": "sonnet"}, body)
        assert h1 != h2

    def test_prism_voice_change_no_effect(self):
        body = "Same"
        h1 = forge.compute_cloud_content_hash({"name": "A", "voice": "v1"}, body)
        h2 = forge.compute_cloud_content_hash({"name": "A", "voice": "v2"}, body)
        assert h1 == h2

    def test_prism_extra_context_no_effect(self):
        body = "Same"
        h1 = forge.compute_cloud_content_hash({"name": "A", "extra_context": "x"}, body)
        h2 = forge.compute_cloud_content_hash({"name": "A", "extra_context": "y"}, body)
        assert h1 == h2

    def test_prism_role_change_no_effect(self):
        body = "Same"
        h1 = forge.compute_cloud_content_hash({"name": "A", "role": "reviewer"}, body)
        h2 = forge.compute_cloud_content_hash({"name": "A", "role": "designer"}, body)
        assert h1 == h2

    def test_prism_icon_change_no_effect(self):
        body = "Same"
        h1 = forge.compute_cloud_content_hash({"name": "A", "icon": "🎨"}, body)
        h2 = forge.compute_cloud_content_hash({"name": "A", "icon": "🔧"}, body)
        assert h1 == h2

    def test_prism_fallback_voice_change_no_effect(self):
        body = "Same"
        h1 = forge.compute_cloud_content_hash({"name": "A", "fallback_voice": "v1"}, body)
        h2 = forge.compute_cloud_content_hash({"name": "A", "fallback_voice": "v2"}, body)
        assert h1 == h2

    def test_body_change_affects_hash(self):
        fm = {"name": "A"}
        h1 = forge.compute_cloud_content_hash(fm, "Body 1")
        h2 = forge.compute_cloud_content_hash(fm, "Body 2")
        assert h1 != h2

    def test_field_order_no_effect(self):
        body = "Same"
        h1 = forge.compute_cloud_content_hash(
            {"name": "A", "description": "B", "model": "opus"},
            body,
        )
        h2 = forge.compute_cloud_content_hash(
            {"model": "opus", "name": "A", "description": "B"},
            body,
        )
        assert h1 == h2

    def test_hash_format(self):
        h = forge.compute_cloud_content_hash({"name": "A"}, "body")
        assert h.startswith("sha256:")
        assert len(h) == 7 + 64  # "sha256:" + 64 hex chars


class TestScaffoldAgents:
    def test_game_stack(self, tmp_path):
        slugs = forge.scaffold_agents_directory(str(tmp_path), "Unity game")
        assert slugs == ["orchestrator"]
        assert (tmp_path / "agents" / "orchestrator.md").exists()

    def test_web_stack(self, tmp_path):
        slugs = forge.scaffold_agents_directory(str(tmp_path), "React web app")
        assert slugs == ["orchestrator"]

    def test_api_stack(self, tmp_path):
        slugs = forge.scaffold_agents_directory(str(tmp_path), "FastAPI backend")
        assert slugs == ["orchestrator"]

    def test_default_fallback(self, tmp_path):
        slugs = forge.scaffold_agents_directory(str(tmp_path), "something unusual")
        assert slugs == ["orchestrator"]

    def test_case_insensitive(self, tmp_path):
        slugs = forge.scaffold_agents_directory(str(tmp_path), "WEB APP")
        assert slugs == ["orchestrator"]

    def test_valid_yaml_frontmatter(self, tmp_path):
        forge.scaffold_agents_directory(str(tmp_path), "game")
        for md in (tmp_path / "agents").iterdir():
            fm, _body = forge.parse_agent_file(str(md))
            assert "name" in fm
            assert "description" in fm

    def test_non_empty_body(self, tmp_path):
        forge.scaffold_agents_directory(str(tmp_path), "web")
        for md in (tmp_path / "agents").iterdir():
            _, body = forge.parse_agent_file(str(md))
            assert body.strip()

    def test_creates_agents_dir(self, tmp_path):
        forge.scaffold_agents_directory(str(tmp_path), "general")
        assert (tmp_path / "agents").is_dir()

    def test_existing_agents_dir(self, tmp_path):
        (tmp_path / "agents").mkdir()
        (tmp_path / "agents" / "existing.md").write_text("kept", encoding="utf-8")
        slugs = forge.scaffold_agents_directory(str(tmp_path), "general")
        assert slugs == ["orchestrator"]
        assert (tmp_path / "agents" / "existing.md").read_text(encoding="utf-8") == "kept"

    def test_scaffold_creates_orchestrator_md(self, tmp_path):
        forge.scaffold_agents_directory(str(tmp_path), "general")
        orch_path = tmp_path / "agents" / "orchestrator.md"
        assert orch_path.exists()
        fm, body = forge.parse_agent_file(str(orch_path))
        assert fm["role"] == "orchestrator"
        assert "name" in fm

    def test_scaffold_orchestrator_has_project_name(self, tmp_path):
        project_dir = tmp_path / "my-cool-project"
        project_dir.mkdir()
        forge.scaffold_agents_directory(str(project_dir), "general")
        fm, _body = forge.parse_agent_file(str(project_dir / "agents" / "orchestrator.md"))
        assert fm["name"] == "My Cool Project"

    def test_scaffold_no_default_guest_agents(self, tmp_path):
        forge.scaffold_agents_directory(str(tmp_path), "Unity game")
        agents_dir = tmp_path / "agents"
        md_files = list(agents_dir.glob("*.md"))
        assert len(md_files) == 1
        assert md_files[0].name == "orchestrator.md"


class TestScaffold:
    def _setup_scaffold_env(self, tmp_path, monkeypatch, agents_yaml_file):
        """Common setup: mock DISPATCH_PATH, PRISM_PATH, channels.yaml, settings, and subprocess."""
        import shutil

        monkeypatch.setattr(forge, "DISPATCH_PATH", str(tmp_path / "dispatch"))
        monkeypatch.setattr(forge, "PRISM_PATH", str(tmp_path / "prism"))
        monkeypatch.setattr(forge, "SETTINGS_PATH", tmp_path / "settings.json")
        dispatch_dir = tmp_path / "dispatch"
        dispatch_dir.mkdir()
        shutil.copy(agents_yaml_file, dispatch_dir / "agents.yaml")

        prism_backend = tmp_path / "prism" / "backend"
        prism_backend.mkdir(parents=True)
        (prism_backend / "agents.yaml").write_text("agents: {}\n", encoding="utf-8")

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
        assert result["prism_port"] == 3101
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
        assert "localhost:3101" in workflow

        agents_dir = project_dir / "agents"
        assert agents_dir.is_dir()
        assert (agents_dir / "orchestrator.md").exists()

        assert (project_dir / "CLAUDE.md").exists()
        claude = (project_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert "My Rpg" in claude

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

        prism_agents = yaml.safe_load(
            (tmp_path / "prism" / "backend" / "agents.yaml").read_text(encoding="utf-8")
        )
        assert "my-rpg" in prism_agents["agents"]
        assert prism_agents["agents"]["my-rpg"]["endpoint"] == "ws://localhost:3101"
        assert prism_agents["agents"]["my-rpg"]["token_env"] == "PRISM_ANTHEM_TOKEN"

    def test_scaffold_with_https_url(self, tmp_path, monkeypatch, agents_yaml_file):
        calls, _ = self._setup_scaffold_env(tmp_path, monkeypatch, agents_yaml_file)

        forge.scaffold_project(
            base_path=str(tmp_path / "projects"),
            name="test",
            repo_url="https://github.com/user/repo.git",
        )

        clone_call = next(c for c in calls if "clone" in str(c))
        assert clone_call == ["git", "clone", "https://github.com/user/repo.git", "."]

    def test_scaffold_with_shorthand(self, tmp_path, monkeypatch, agents_yaml_file):
        calls, _ = self._setup_scaffold_env(tmp_path, monkeypatch, agents_yaml_file)

        forge.scaffold_project(
            base_path=str(tmp_path / "projects"),
            name="test-short",
            repo_url="user/repo",
        )

        clone_call = next(c for c in calls if "clone" in str(c))
        assert clone_call == ["git", "clone", "https://github.com/user/repo.git", "."]

    def test_scaffold_with_ssh_url(self, tmp_path, monkeypatch, agents_yaml_file):
        calls, _ = self._setup_scaffold_env(tmp_path, monkeypatch, agents_yaml_file)

        forge.scaffold_project(
            base_path=str(tmp_path / "projects"),
            name="test-ssh",
            repo_url="git@github.com:user/repo.git",
        )

        clone_call = next(c for c in calls if "clone" in str(c))
        assert clone_call == ["git", "clone", "git@github.com:user/repo.git", "."]

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
