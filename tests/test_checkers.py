"""Smoke stands for the repository's own gate scripts (repository-only, not distributed).

Each stand is a throwaway git repository under tmp_path holding a copy of
check_language.py plus planted files; the checker runs as a subprocess from the
stand, exactly the way the gate runs locally and in CI. The gate must fail
closed: a file it cannot read or parse is a finding, never a silent skip."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _stand(tmp_path):
    shutil.copy(REPO_ROOT / 'check_language.py', tmp_path / 'check_language.py')
    return tmp_path


def _run_checker(stand):
    subprocess.run(['git', 'init', '-q'], cwd=stand, check=True)  # noqa: S603, S607
    subprocess.run(['git', 'add', '-A'], cwd=stand, check=True)   # noqa: S603, S607
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    return subprocess.run([sys.executable, 'check_language.py'],  # noqa: S603
                          cwd=stand, capture_output=True, encoding='utf-8', env=env)


def test_undecodable_tracked_file_is_a_finding(tmp_path):
    """A tracked file that is not valid UTF-8 must fail the gate loudly,
    not be skipped into a green 'OK - 0 finding(s)'."""
    stand = _stand(tmp_path)
    (stand / 'bad_cp1251.py').write_bytes('# комментарий\nX = "Привет"\n'.encode('cp1251'))
    res = _run_checker(stand)
    assert res.returncode == 1
    assert 'bad_cp1251' in res.stdout


def test_unparseable_file_is_a_finding_and_scan_continues(tmp_path):
    """A tokenizer-breaking file must yield a 'cannot parse' finding (not a
    traceback) and must not abort the scan of the files after it."""
    stand = _stand(tmp_path)
    (stand / 'a_broken.py').write_text('# ремарка\nx = (\n', encoding='utf-8')
    (stand / 'zz_bad.py').write_text('# тоже по-русски\n', encoding='utf-8')
    res = _run_checker(stand)
    assert res.returncode == 1
    assert 'cannot parse' in res.stdout
    assert 'zz_bad' in res.stdout


def test_russian_message_in_human_raise_is_a_finding(tmp_path):
    """Even in a LITERALS_ARE_DATA module, a Russian message inside
    raise ValueError(...) is prose for a developer, not label data."""
    stand = _stand(tmp_path)
    (stand / 'tg_calendar.py').write_text(
        'def f():\n    raise ValueError("Сообщение по-русски")\n', encoding='utf-8')
    res = _run_checker(stand)
    assert res.returncode == 1
    assert 'message' in res.stdout


def test_clean_stand_passes(tmp_path):
    """Control: the checker alone in an otherwise empty stand stays green."""
    res = _run_checker(_stand(tmp_path))
    assert res.returncode == 0
    assert 'OK' in res.stdout
