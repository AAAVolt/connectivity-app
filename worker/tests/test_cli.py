"""Tests for the worker CLI."""

from typer.testing import CliRunner

from worker.cli import app

runner = CliRunner()


def test_hello_default() -> None:
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello, world!" in result.output


def test_hello_with_name() -> None:
    result = runner.invoke(app, ["hello", "--name", "Bizkaia"])
    assert result.exit_code == 0
    assert "Bizkaia" in result.output
