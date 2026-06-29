from pathlib import Path

from backend.sandbox.docker_sandbox_executor import build_docker_command


def test_local_readonly_docker_command_has_isolation_flags(tmp_path: Path):
    command = build_docker_command(tmp_path, "local_readonly")
    command_text = " ".join(str(item) for item in command)

    assert "--network none" in command_text
    assert "--read-only" in command
    assert "--cap-drop ALL" in command_text
    assert "--security-opt no-new-privileges" in command_text
    assert "--pids-limit" in command
    assert "--memory" in command
    assert "--cpus" in command
    assert "agentguard-tool-sandbox:latest" in command


def test_strict_profile_does_not_mount_secret_or_private(tmp_path: Path):
    command = build_docker_command(tmp_path, "strict")
    command_text = " ".join(str(item).replace("\\", "/").lower() for item in command)

    assert "/workspace/public" in command_text
    assert "/workspace/course" not in command_text
    assert "/workspace/outbox" not in command_text
    assert "secret" not in command_text
    assert "private" not in command_text


def test_local_safe_write_mounts_outbox_as_writable(tmp_path: Path):
    command = build_docker_command(tmp_path, "local_safe_write")
    mount_values = [
        str(command[index + 1])
        for index, item in enumerate(command[:-1])
        if item == "--mount"
    ]

    outbox_mounts = [item for item in mount_values if "/workspace/outbox" in item.replace("\\", "/")]
    assert len(outbox_mounts) == 1
    assert "readonly" not in outbox_mounts[0]
