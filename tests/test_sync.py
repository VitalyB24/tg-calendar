"""The sync tool: drift is loud, --apply repairs it, EOL noise is not drift."""
import pytest

import sync


def _repo(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    for name in sync.FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'print("canon %s")\n' % name.encode())
    monkeypatch.setattr(sync, 'ROOT', root)
    monkeypatch.setattr(sync, 'TARGETS_FILE', root / 'sync_targets.txt')
    return root


def test_no_targets_file_is_a_clean_skip(tmp_path, monkeypatch, capsys):
    _repo(tmp_path, monkeypatch)
    assert sync.main([]) == 0
    assert 'skipped' in capsys.readouterr().out


def test_drift_and_missing_copies_fail_and_apply_repairs_all(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    bot = tmp_path / 'bot'
    bot.mkdir()
    (bot / sync.FILES[0]).write_bytes(b'edited in the consumer\n')   # drift
    # every other file, the tests/ subdirectory included, is absent entirely
    sync.TARGETS_FILE.write_text(str(bot) + '\n', encoding='utf-8')
    assert sync.main([]) == 1
    out = capsys.readouterr().out
    assert 'differs from the repository' in out and 'is missing' in out
    assert sync.main(['--apply']) == 0
    for name in sync.FILES:
        assert (bot / name).read_bytes() == (root / name).read_bytes()
    assert sync.main([]) == 0


def test_a_vanished_target_directory_is_loud_not_skipped(tmp_path, monkeypatch):
    _repo(tmp_path, monkeypatch)
    sync.TARGETS_FILE.write_text(str(tmp_path / 'renamed-bot') + '\n', encoding='utf-8')
    assert sync.main([]) == 1
    # --apply must not paper over it either
    assert sync.main(['--apply']) == 1


def test_line_ending_only_difference_is_not_drift(tmp_path, monkeypatch):
    root = _repo(tmp_path, monkeypatch)
    bot = tmp_path / 'bot'
    bot.mkdir()
    for name in sync.FILES:
        path = bot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root / name).read_bytes().replace(b'\n', b'\r\n'))
    sync.TARGETS_FILE.write_text(str(bot) + '\n', encoding='utf-8')
    assert sync.main([]) == 0


def test_apply_prints_finding_lines_not_just_the_counter(tmp_path, monkeypatch, capsys):
    """--apply must name a vanished target, not bury it in '1 finding(s)'."""
    _repo(tmp_path, monkeypatch)
    good = tmp_path / 'good_bot'
    good.mkdir()
    missing = tmp_path / 'missing_bot'          # never created
    sync.TARGETS_FILE.write_text(str(good) + '\n' + str(missing) + '\n', encoding='utf-8')
    assert sync.main(['--apply']) == 1
    assert 'missing_bot' in capsys.readouterr().out


def test_targets_file_with_utf8_bom_is_read_cleanly(tmp_path, monkeypatch):
    """A PowerShell redirect prepends a BOM; it must not corrupt the first path."""
    root = _repo(tmp_path, monkeypatch)
    bot = tmp_path / 'bot'
    bot.mkdir()
    for name in sync.FILES:
        path = bot / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((root / name).read_bytes())
    sync.TARGETS_FILE.write_bytes(b'\xef\xbb\xbf' + str(bot).encode('utf-8') + b'\n')
    assert sync.main([]) == 0


def test_relative_target_line_is_a_loud_refusal(tmp_path, monkeypatch):
    """A relative line must abort before anything is compared or written —
    resolving it against the CWD would silently write to the wrong place."""
    _repo(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    sync.TARGETS_FILE.write_text('rel_target\n', encoding='utf-8')
    with pytest.raises(SystemExit) as exc:
        sync.main([])
    assert 'rel_target' in str(exc.value)
    assert not (tmp_path / 'rel_target').exists()


def test_targets_parsing_comments_and_blank_lines(tmp_path, monkeypatch):
    """Full-line comments, inline comments, empty and whitespace-only lines
    are not targets."""
    _repo(tmp_path, monkeypatch)
    bot = tmp_path / 'bot'
    bot.mkdir()
    sync.TARGETS_FILE.write_text(
        '# full-line comment\n\n   \n' + str(bot) + '   # inline comment\n',
        encoding='utf-8')
    assert sync.targets() == [bot]


def test_apply_does_not_resurrect_a_vanished_target(tmp_path, monkeypatch):
    """--apply must report a vanished directory, not recreate it and write
    into the void."""
    _repo(tmp_path, monkeypatch)
    missing = tmp_path / 'renamed-bot'
    sync.TARGETS_FILE.write_text(str(missing) + '\n', encoding='utf-8')
    assert sync.main(['--apply']) == 1
    assert not missing.exists()
