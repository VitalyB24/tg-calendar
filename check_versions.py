"""What is installed here must satisfy what the repository asks for.

Dependabot answers a different question — "is there a newer release?" — and answers it in
the repository, as a pull request. This one asks about the machine: the ranges in
requirements-dev.txt say which tool versions the suite is actually run against, and an
environment below the floor is running checks nobody tested. The module itself needs
nothing outside the standard library — only the development tools are declared and checked.

Run it before you commit; CI runs it too, where it also proves the install matched the
ranges.
"""
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent
FILES = ('requirements-dev.txt',)


def requirements(path):
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.split('#', 1)[0].strip()
        if line:
            yield Requirement(line)


def check(path):
    findings = []
    for req in requirements(path):
        try:
            installed = version(req.name)
        except PackageNotFoundError:
            findings.append('%s is not installed (%s asks for %s)'
                            % (req.name, path.name, req.specifier or 'any version'))
            continue
        if req.specifier and not req.specifier.contains(installed, prereleases=True):
            findings.append('%s %s is installed, %s asks for %s'
                            % (req.name, installed, path.name, req.specifier))
    return findings


def main():
    findings = []
    for name in FILES:
        path = ROOT / name
        if not path.exists():
            findings.append('%s is missing' % name)
            continue
        findings.extend(check(path))

    if not findings:
        print()
        print('VERSION CHECK: OK - everything installed matches the repository')
        return 0
    print()
    print('VERSION CHECK: %d finding(s)' % len(findings))
    for line in findings:
        print('  %s' % line)
    print()
    print('  Bring this machine up to what the repository asks for:')
    print('    python -m pip install --upgrade -r requirements-dev.txt')
    return 1


if __name__ == '__main__':
    sys.exit(main())
