import pytest
import sys
from unittest.mock import patch
from transpiler.cli.main import main


def test_cli_missing_file(capsys):
    with patch.object(sys, "argv", ["transpiler", "nonexistent.py", "--to", "python"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

    out, err = capsys.readouterr()
    assert "Error: File 'nonexistent.py' not found." in err


def test_cli_unsupported_extension(tmp_path, capsys):
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")

    with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", "python"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

    out, err = capsys.readouterr()
    assert "Error: Unsupported source file extension '.txt'" in err


def test_cli_valid_transpile(tmp_path, capsys):
    test_file = tmp_path / "test.py"
    test_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")

    with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", "python"]):
        main()

    out, err = capsys.readouterr()
    assert err == ""
    assert "def add(a: int, b: int) -> int:" in out
    assert "return (a + b)" in out


def test_cli_frontend_error(tmp_path, capsys):
    # Depending on how the parser handles it, we want to test the try-except
    test_file = tmp_path / "test.py"
    test_file.write_text("def def def invalid syntax")

    with patch.object(sys, "argv", ["transpiler", str(test_file), "--to", "python"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1

    out, err = capsys.readouterr()
    assert "Frontend Error" in err
