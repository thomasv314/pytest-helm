from __future__ import annotations

import pytest

import pytest_helm._cli as cli


def test_main_scaffolds_with_init_flag(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main(["--init"])

    assert exit_code == 0
    assert (tmp_path / "test" / "conftest.py").exists()
    assert (tmp_path / "test" / "test_deployments.py").exists()
    stdout = capsys.readouterr().out
    assert "Scaffolded files:" in stdout


def test_main_rejects_positional_subcommand() -> None:
    with pytest.raises(SystemExit):
        cli.main(["init"])


def test_main_fails_if_files_exist_without_force(monkeypatch, tmp_path, capsys) -> None:
    test_dir = tmp_path / "test"
    test_dir.mkdir(parents=True)
    existing_path = test_dir / "conftest.py"
    existing_path.write_text("original", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    exit_code = cli.main(["--init"])

    assert exit_code == 1
    assert existing_path.read_text(encoding="utf-8") == "original"
    stdout = capsys.readouterr().out
    assert "Refusing to overwrite existing files" in stdout


def test_main_overwrites_with_force(monkeypatch, tmp_path) -> None:
    test_dir = tmp_path / "test"
    test_dir.mkdir(parents=True)
    existing_path = test_dir / "conftest.py"
    existing_path.write_text("original", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    exit_code = cli.main(["--init", "--force"])

    assert exit_code == 0
    assert "manifest_fixture" in existing_path.read_text(encoding="utf-8")
