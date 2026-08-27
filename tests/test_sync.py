"""The sync tool: drift is loud, --apply repairs it, EOL noise is not drift."""
import sync


def _repo(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    for name in sync.MODULES:
        (root / name).write_bytes(b'print("canon %s")\n' % name.encode())
    monkeypatch.setattr(sync, 'ROOT', root)
    monkeypatch.setattr(sync, 'TARGETS_FILE', root / 'sync_targets.txt')
    return root


def test_no_targets_file_is_a_clean_skip(tmp_path, monkeypatch, capsys):
    _repo(tmp_path, monkeypatch)
    assert sync.main([]) == 0
    assert 'skipped' in capsys.readouterr().out


def test_drift_and_missing_copy_fail_and_apply_repairs_both(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path, monkeypatch)
    bot = tmp_path / 'bot'
    bot.mkdir()
    (bot / sync.MODULES[0]).write_bytes(b'edited in the consumer\n')   # drift
    # MODULES[1] is absent entirely
    sync.TARGETS_FILE.write_text(str(bot) + '\n', encoding='utf-8')
    assert sync.main([]) == 1
    out = capsys.readouterr().out
    assert 'differs from the repository' in out and 'is missing' in out
    assert sync.main(['--apply']) == 0
    for name in sync.MODULES:
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
    for name in sync.MODULES:
        (bot / name).write_bytes((root / name).read_bytes().replace(b'\n', b'\r\n'))
    sync.TARGETS_FILE.write_text(str(bot) + '\n', encoding='utf-8')
    assert sync.main([]) == 0
