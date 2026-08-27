"""Guards the English-only rule: run it before committing, CI runs it on every push.

    python check_language.py

What it forbids, everywhere: non-Latin text in comments, docstrings and in anything said to
a human — assert messages, print(), SystemExit(), RuntimeError(), getpass() prompts.

What it allows:
  * README.ru.md — the Russian half of the bilingual documentation;
  * string literals in tg_calendar.py and tg_timepick.py — the button labels ARE Russian:
    month and weekday names, the quick-date footer, the picker titles, the marker and
    digit-style catalogues. They are the product's data, not prose; localising the modules
    means editing exactly these strings;
  * string literals inside tests/ — the fixtures pin the Russian labels and the figure-space
    padding, and translating them would leave the suite green while the keyboards regress;
  * the handful of strings listed in ALLOWED below, each with the reason it cannot be
    English.

Anything else is reported with its file and line, and the exit code is 1.
"""
import ast
import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NON_LATIN = re.compile(r'[^\x00-\x7F]')
CYRILLIC = re.compile(r'[Ѐ-ӿ]')

# Files that are Russian by design: the documentation speaks two languages.
ALLOWED_FILES = {'README.ru.md'}

# Strings that are data rather than prose. The reason is the point of each entry: without
# one, a string does not belong here.
ALLOWED = {
    'README.md': [('Русская версия', 'link to the Russian README')],
}

HUMAN_CALLS = {'print', 'SystemExit', 'RuntimeError', 'AssertionError', 'getpass'}

# Files whose string LITERALS are data rather than prose: the modules (their literals are
# the Russian UI labels), the fixtures under tests/, and this file, whose allowlist has to
# quote the very strings it permits. Their comments, docstrings and messages are held to the
# rule like everywhere else.
LITERALS_ARE_DATA = ('tests/', 'check_language.py', 'tg_calendar.py', 'tg_timepick.py')


def allowed(rel, text):
    return any(frag in text for frag, _why in ALLOWED.get(rel, ()))


def python_findings(rel, src):
    """Comments, docstrings and human-facing messages must be English; other literals may be
    data — and in this repository the data is deliberately Russian."""
    out = [(tok.start[0], 'comment', tok.string.strip())
           for tok in tokenize.generate_tokens(io.StringIO(src).readline)
           if tok.type == tokenize.COMMENT and CYRILLIC.search(tok.string)
           and not allowed(rel, tok.string)]
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, 'body', None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str) and CYRILLIC.search(body[0].value.value) \
                    and not allowed(rel, body[0].value.value):
                out.append((body[0].lineno, 'docstring', body[0].value.value.strip()[:60]))
        msgs = []
        if isinstance(node, ast.Assert) and node.msg is not None:
            msgs.append(node.msg)
        if isinstance(node, ast.Call) and _human(node.func):
            msgs += node.args
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and _human(node.exc.func):
            msgs += node.exc.args
        out += [(sub.lineno, 'message', sub.value.strip()[:60])
                for m in msgs for sub in ast.walk(m)
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                and CYRILLIC.search(sub.value) and not allowed(rel, sub.value)]
    if not rel.startswith(LITERALS_ARE_DATA):
        out += [(node.lineno, 'literal', node.value.strip()[:60])
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and CYRILLIC.search(node.value) and not allowed(rel, node.value)]
    return out


def _human(func):
    return (isinstance(func, ast.Name) and func.id in HUMAN_CALLS) or \
           (isinstance(func, ast.Attribute) and func.attr in HUMAN_CALLS)


COMMENTS = {
    '.js': [re.compile(r'//[^\n]*'), re.compile(r'/\*.*?\*/', re.S)],
    '.css': [re.compile(r'/\*.*?\*/', re.S)],
    '.html': [re.compile(r'\{#.*?#\}', re.S), re.compile(r'<!--.*?-->', re.S),
              re.compile(r'/\*.*?\*/', re.S)],
    '.yml': [re.compile(r'#[^\n]*')],
    '.toml': [re.compile(r'#[^\n]*')],
}


def text_findings(rel, src, ext):
    """Outside Python we can only tell comments apart reliably — and that is what the rule
    is mostly about. Markdown carries no code, so every line of it counts."""
    if ext == '.md':
        return [(i, 'text', line.strip()[:60])
                for i, line in enumerate(src.split('\n'), 1)
                if CYRILLIC.search(line) and not allowed(rel, line)]
    return [(src[:m.start()].count('\n') + 1, 'comment', m.group(0).strip()[:60])
            for rx in COMMENTS.get(ext, ()) for m in rx.finditer(src)
            if CYRILLIC.search(m.group(0)) and not allowed(rel, m.group(0))]


def tracked_files():
    """The names every scan below walks, straight from git, verbatim.

    -z with core.quotepath=off hands each name over NUL-separated and unescaped: under the
    default quotepath git octal-escapes non-ASCII names and wraps them in quotes, and a
    whitespace split would drop exactly those files before the extension filter ever saw
    them.

    A listing that failed, or came back empty, is a loud stop rather than an "OK — 0
    finding(s)": a run that scanned nothing has not checked anything, and its green would
    read as proof the rule holds."""
    # NB: S603/S607 — a fixed argument list (no shell) and `git` without a full path,
    # deliberately: it is resolved from PATH so the check runs the same on Windows and Linux.
    listed = subprocess.run(['git', '-c', 'core.quotepath=off', 'ls-files', '-z'],  # noqa: S603, S607
                            cwd=ROOT, capture_output=True, encoding='utf-8')
    if listed.returncode != 0:
        raise SystemExit('LANGUAGE CHECK: FAILED — git ls-files exited %s, nothing was scanned'
                         % listed.returncode)
    files = [name for name in listed.stdout.split('\0') if name]
    if not files:
        raise SystemExit('LANGUAGE CHECK: FAILED — git ls-files listed no files, nothing was scanned')
    return files


def main():
    bad = 0
    for rel in tracked_files():
        if rel in ALLOWED_FILES:
            continue
        path = ROOT / rel
        ext = path.suffix.lower()
        if ext not in {'.py', '.js', '.css', '.html', '.yml', '.toml', '.md'}:
            continue
        try:
            src = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        if not NON_LATIN.search(src):
            continue
        try:
            found = python_findings(rel, src) if ext == '.py' else text_findings(rel, src, ext)
        except SyntaxError as e:
            print(f'{rel}: cannot parse ({e})')
            bad += 1
            continue
        for line, kind, text in sorted(set(found)):
            print(f'{rel}:{line}: non-English {kind} — {text}')
            bad += 1
    print(f'\nLANGUAGE CHECK: {"FAILED" if bad else "OK"} — {bad} finding(s)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
