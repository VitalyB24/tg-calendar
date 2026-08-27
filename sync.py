"""Distributes the modules to the consumer directories listed in sync_targets.txt.

The repository is the single source of truth. Edit the modules HERE, run the gates, then
push the result out with --apply. A consumer copy that differs from the repository is a
finding either way: an edit made in the consumer bypassed the gates and belongs in the
repository first, and a stale copy simply needs the sync.

    python sync.py            # report drift, exit 1 if any target differs
    python sync.py --apply    # overwrite the targets with the repository copies

sync_targets.txt (one absolute directory per line, # comments allowed) is machine-specific
and deliberately untracked; without it the check is skipped with exit 0, which is what CI
sees. A listed directory that does not exist is a loud failure, not a skip — a renamed
consumer folder must not silently drop out of the sync. Line endings are ignored in the
comparison: git and editors may flip CRLF/LF, and an EOL-only difference changes nothing
for Python.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODULES = ('tg_calendar.py', 'tg_timepick.py')
TARGETS_FILE = ROOT / 'sync_targets.txt'


def targets():
    if not TARGETS_FILE.exists():
        return None
    dirs = []
    for raw in TARGETS_FILE.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if line:
            dirs.append(Path(line))
    return dirs


def _normalised(path):
    return path.read_bytes().replace(b'\r\n', b'\n')


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    apply = '--apply' in args
    dirs = targets()
    if dirs is None:
        print('SYNC: skipped — no sync_targets.txt on this machine, nothing to compare')
        return 0
    findings = []
    synced = 0
    for d in dirs:
        if not d.is_dir():
            findings.append('%s: target directory does not exist' % d)
            continue
        for name in MODULES:
            src, dst = ROOT / name, d / name
            if dst.exists() and _normalised(dst) == _normalised(src):
                continue
            if apply:
                dst.write_bytes(src.read_bytes())
                synced += 1
                print('synced %s' % dst)
            else:
                state = 'differs from the repository' if dst.exists() else 'is missing'
                findings.append('%s: %s' % (dst, state))
    if apply:
        print('\nSYNC APPLY: %d file(s) written, %d finding(s)' % (synced, len(findings)))
    else:
        for line in findings:
            print(line)
        print('\nSYNC CHECK: %s — %d finding(s)' % ('FAILED' if findings else 'OK', len(findings)))
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
