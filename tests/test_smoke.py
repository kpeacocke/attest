from attest.cli import main

def test_version_exits_zero(capsys):
    rc = main(["version"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "attest" in out.lower()
