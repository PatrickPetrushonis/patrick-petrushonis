#!/usr/bin/env python3
"""Static checks for the SCSS in <src>/styles and the markup that uses it.

Usage:
  python3 check_styles.py [SRC_DIR] --profile PROFILE.md
  python3 check_styles.py --self-test

SRC_DIR defaults to ../src relative to this script (scripts/check_styles.py).
--profile names the site's profile (guide §16). Site facts come from it: the
state-toggled selectors (§12.2), the markup hooks that have no rule (§12.3), the
contrast thresholds (§3.5.1) and the checker settings (§15.9). The checker also
compares the profile's tables to the code (rule 15.7).
--self-test runs the built-in fixtures (rule 15.6).

Output: one line per rule ID with the number of items checked and the number
of violations, then every ERROR and WARN line. ERROR exits 1; WARN does not.
Every message begins with the ID of the guide rule it enforces.
This does not compile Sass.
"""
import argparse
import glob
import os
import re
import shutil
import sys
import tempfile

# Site facts. load_profile() fills these from the profile (guide §16); nothing here names a site.
SCRIPT_TOGGLED = set()      # classes set by scripts or state (profile §12.2)
SCRIPT_ATTRS = set()        # attribute selectors set by scripts (profile §12.2)
NO_RULE_HOOKS = set()       # markup hooks that have no rule (profile §12.3)
THRESHOLDS = {}             # role -> minimum ratio against --surface; None: structural line (profile §3.5.1)
EXEMPT = set()              # (theme, role) pairs below their threshold by design (profile §15.9)
IMPORTANT_ALLOWED = set()   # files that may contain !important (profile §15.9)
MARKUP_EXT = ()             # markup file extensions (profile §15.9)
MARKUP_ROOTS = ()           # directories or files under SRC_DIR, searched for markup (profile §15.9)
THEME_KEY_FILES = ()        # file that reads the saved theme key, file that declares it (profile §15.9)
STACK = ''
# Core minimums for the roles every profile defines (guide 3.5.1); a profile may add roles.
CORE_MIN = {'text': 4.5, 'text-muted': 4.5, 'link': 4.5, 'focus': 3.0, 'border-strong': 3.0,
            'fill-strong': 3.0, 'border': None, 'border-subtle': None}
SCRIPT_EXT = ('.ts', '.tsx', '.js', '.jsx', '.mjs')
PROFILE_MARKERS = ('## 1.1 Layout', '## 2.2 Token reference', '## 3.2 Roles', '**3.5.1**',
                   '## 12.2 Script-affected selectors', '## 12.3 Components and hooks',
                   '## 15.9 Checker settings')
MAX_LINE = 100
BEM = re.compile(r'^[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?:__[a-z0-9]+(?:-[a-z0-9]+)*)?(?:--[a-z0-9]+(?:-[a-z0-9]+)*)?$')
KEBAB = re.compile(r'^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$')
CLASS_TOKEN = re.compile(r'^[a-z][\w-]*$')
# Properties that follow custom properties and precede the alphabetical rest, in this order (rule 8.1.4).
OFFSETS = ['position', 'top', 'right', 'bottom', 'left']
def profile_section(text, start):
    """Text after the marker `start` up to the next heading; '' when the marker is absent."""
    i = text.find(start)
    if i < 0:
        return ''
    rest = text[i + len(start):]
    m = re.search(r'\n#{1,6} ', rest)
    return rest[:m.start()] if m else rest


def load_profile(path):
    """Fill the site settings from the profile at path; exit when it is missing a required section."""
    global SCRIPT_TOGGLED, SCRIPT_ATTRS, NO_RULE_HOOKS, THRESHOLDS, EXEMPT, IMPORTANT_ALLOWED
    global MARKUP_EXT, MARKUP_ROOTS, THEME_KEY_FILES, STACK
    if not os.path.isfile(path):
        sys.exit(f'ERROR: [16.2] profile file not found: {path}')
    text = open(path).read()
    for marker in PROFILE_MARKERS:
        if marker not in text:
            sys.exit(f'ERROR: [16.2] profile {path} has no "{marker}" section')

    SCRIPT_TOGGLED, SCRIPT_ATTRS = set(), set()
    for row in profile_section(text, '## 12.2 Script-affected selectors').splitlines():
        m = re.match(r'\|\s*`([.\[][^`|]+)`', row)
        if m and m.group(1).startswith('.'):
            SCRIPT_TOGGLED.add(m.group(1)[1:])
        elif m:
            SCRIPT_ATTRS.add(m.group(1).strip('[]').split('=')[0])

    NO_RULE_HOOKS = set()
    for line in profile_section(text, '## 12.3 Components and hooks').splitlines():
        if line.startswith('Markup hook'):
            NO_RULE_HOOKS = {t[1:] for t in re.findall(r'`([^`]+)`', line) if t.startswith('.')}

    THRESHOLDS = {}
    for row in profile_section(text, '**3.5.1**').splitlines():
        m = re.match(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|', row)
        if not m:
            continue
        required = re.match(r'\d+(?:\.\d+)?', m.group(2))
        for role in re.findall(r'`([\w-]+)`', m.group(1)):
            THRESHOLDS[role] = float(required.group(0)) if required else None

    settings = {}
    for row in profile_section(text, '## 15.9 Checker settings').splitlines():
        m = re.match(r'\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*$', row)
        if m:
            settings[m.group(1)] = m.group(2)
    for key in ('stack', 'markup extensions', 'markup roots', 'theme key files', 'exempt roles',
                '!important files'):
        if key not in settings:
            sys.exit(f'ERROR: [16.3] profile {path} §15.9 has no "{key}" row')
    STACK = settings['stack']
    MARKUP_EXT = tuple(re.findall(r'`(\.\w+)`', settings['markup extensions']))
    MARKUP_ROOTS = tuple(re.findall(r'`([^`]+)`', settings['markup roots']))
    THEME_KEY_FILES = tuple(re.findall(r'`([^`]+)`', settings['theme key files']))
    if len(THEME_KEY_FILES) not in (0, 2):
        sys.exit(f'ERROR: [16.3] profile {path} §15.9 "theme key files" lists {len(THEME_KEY_FILES)} files; expected 2 or none')
    EXEMPT = set(re.findall(r'`(light|dark):([\w-]+)`', settings['exempt roles']))
    IMPORTANT_ALLOWED = set(re.findall(r'`([^`]+)`', settings['!important files']))


class Report:
    """Findings plus, per rule ID, how many items were checked and how many failed."""

    def __init__(self):
        self.errors, self.warnings = [], []
        self.checked, self.violations = {}, {}

    def count(self, rule, n=1):
        self.checked[rule] = self.checked.get(rule, 0) + n

    def error(self, rule, msg):
        self.errors.append(f'[{rule}] {msg}')
        self.violations[rule] = self.violations.get(rule, 0) + 1

    def warn(self, rule, msg):
        self.warnings.append(f'[{rule}] {msg}')
        self.violations[rule] = self.violations.get(rule, 0) + 1

    def hit(self):
        return {m[1:m.index(']')] for m in self.errors + self.warnings}


def declaration_key(prop):
    """Sort key for rule 8.1.4: custom properties, then position, top, right, bottom, left, then A-Z."""
    if prop.startswith('--'):
        return (0, 0, prop)
    if prop in OFFSETS:
        return (1, OFFSETS.index(prop), '')
    return (2, 0, prop)


def strip_comments(text):
    """Text with // and /* */ comments removed (a // after a colon, as in a URL, stays)."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'(?<!:)//.*', '', text)


def parse(text):
    """Statements of comment-free SCSS as ('stmt'|'block', head, children|None) tuples.

    Interpolation (#{...}) and parentheses stay inside the surrounding statement.
    """
    items, i, n, buf = [], 0, len(text), ''
    while i < n:
        c = text[i]
        if c in '#(' and (c == '(' or text[i:i + 2] == '#{'):
            opener, closer = ('(', ')') if c == '(' else ('{', '}')
            depth = 0
            while i < n:
                buf += text[i]
                if text[i] == opener:
                    depth += 1
                elif text[i] == closer:
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                i += 1
            continue
        if c == ';':
            if buf.strip():
                items.append(('stmt', buf.strip(), None))
            buf, i = '', i + 1
            continue
        if c == '{':
            depth, j = 1, i + 1
            while j < n and depth:
                depth += (text[j] == '{') - (text[j] == '}')
                j += 1
            items.append(('block', buf.strip(), parse(text[i + 1:j - 1])))
            buf, i = '', j
            continue
        buf += c
        i += 1
    if buf.strip():
        items.append(('stmt', buf.strip(), None))
    return items


def kind(item):
    """Statement kind: M leading include, D declaration, N nested selector, B breakpoint, X other."""
    k, head, _ = item
    if k == 'block':
        if head.startswith('@include breakpoint'):
            return 'B'
        return 'X' if head.startswith('@') else 'N'
    if head.startswith('@include'):
        return 'M'
    return 'X' if head.startswith(('@', '$')) else 'D'


def luminance(hexval):
    """WCAG relative luminance of a #rrggbb color."""
    h = hexval.lstrip('#')
    ch = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a, b):
    """WCAG contrast ratio of two #rrggbb colors."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def block_after(text, marker):
    """Body of the first {...} after marker, matching nested braces; None if absent."""
    start = text.find(marker)
    if start < 0:
        return None
    open_at = text.find('{', start)
    depth = 0
    for i in range(open_at, len(text)):
        depth += (text[i] == '{') - (text[i] == '}')
        if depth == 0:
            return text[open_at + 1:i]
    return None


def literal_tokens(text):
    """Class-like words from every string literal in text, and the prefixes of template literals.

    A template literal such as `a--${x}` yields the prefix `a--`, which stands for
    every class that starts with it.
    """
    tokens, prefixes = set(), set()
    for m in re.finditer(r"'([^'\n]*)'|\"([^\"\n]*)\"|`([^`]*)`", text):
        single, double, template = m.groups()
        if template is not None:
            parts = re.split(r'\$\{[^}]*\}', template)
            for index, part in enumerate(parts):
                words = part.split()
                if index < len(parts) - 1 and words and not part.endswith(' '):
                    last = words.pop()
                    if last.endswith('-'):
                        prefixes.add(last)
                    else:
                        words.append(last)
                tokens.update(w for w in words if CLASS_TOKEN.match(w))
        else:
            text = single if single is not None else double
            tokens.update(w for w in text.split() if CLASS_TOKEN.match(w))
    return tokens, prefixes


def class_attribute_tokens(text):
    """Class words and template prefixes from every class=, className= and class:list= in text."""
    tokens, prefixes = set(), set()
    attr = r'class(?:Name)?(?::list)?'
    for m in re.finditer(attr + r'\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', text):
        tokens.update(w for w in (m.group(1) or m.group(2)).split() if CLASS_TOKEN.match(w))
    for m in re.finditer(attr + r'\s*=\s*\{', text):
        depth, i = 1, m.end()
        while i < len(text) and depth:
            depth += (text[i] == '{') - (text[i] == '}')
            i += 1
        found, pre = literal_tokens(text[m.end():i - 1])
        tokens |= found
        prefixes |= pre
    for m in re.finditer(r'classList\.(?:add|toggle|remove)\(\s*[\'"]([\w-]+)[\'"]', text):
        tokens.add(m.group(1))
    return tokens, prefixes


class Project:
    """Parsed view of <root>/styles and the markup under <root>."""

    def __init__(self, root):
        self.root = root
        self.styles = os.path.join(root, 'styles')
        self.scss = sorted(glob.glob(os.path.join(self.styles, '**', '*.scss'), recursive=True))
        self.raw = {f: open(f).read() for f in self.scss}
        self.code = {f: strip_comments(t) for f, t in self.raw.items()}
        self.all_code = '\n'.join(self.code.values())
        self.variables_file = os.path.join(self.styles, 'utilities', '_variables.scss')
        self.themes_file = os.path.join(self.styles, 'utilities', '_themes.scss')
        self.helpers_file = os.path.join(self.styles, 'utilities', '_helpers.scss')
        self.main_file = os.path.join(self.styles, 'main.scss')
        self.palette = self._palette()
        self.roles = self._roles()
        self.markup = []
        for entry in MARKUP_ROOTS:
            target = os.path.normpath(os.path.join(root, entry))
            if os.path.isdir(target):
                self.markup += [x for x in glob.glob(os.path.join(target, '**', '*'), recursive=True)
                                if x.endswith(MARKUP_EXT) and os.path.isfile(x)]
            elif os.path.isfile(target):
                self.markup.append(target)
        self.markup = sorted(set(self.markup))

    def rel(self, path):
        """Path relative to styles/, with forward slashes."""
        return os.path.relpath(path, self.styles).replace(os.sep, '/')

    def _palette(self):
        text = self.code.get(self.variables_file)
        if not text or '$color-map:' not in text:
            return {}
        body = text.split('$color-map:')[1].split(');')[0] + ')'
        return {g: dict(re.findall(r'(\w+)\s*:\s*(#[0-9a-fA-F]{3,6})', inner))
                for g, inner in re.findall(r'(\w+)\s*:\s*\(([^()]*)\)', body)}

    def _roles(self):
        roles = {'light': {}, 'dark': {}}
        text = self.code.get(self.themes_file, '')
        for theme in roles:
            body = block_after(text, f'@mixin theme-{theme}')
            for role, g, tone in re.findall(
                    r'--([\w-]+)\s*:\s*#\{color\(\s*(\w+)\s*,\s*(\w+)\s*\)\}', body or ''):
                roles[theme][role] = (g, tone)
        return roles

    def variables(self):
        """Names and values of the variables defined in _variables.scss."""
        text = self.code.get(self.variables_file, '')
        return {n: v.strip() for n, v in re.findall(r'^\s*\$([\w-]+)\s*:\s*([^;]+);', text, re.M)}

    def nesting_mixins(self):
        """Names of mixins whose output contains a nested rule, directly or through another mixin."""
        if not hasattr(self, '_nesting'):
            bodies = {}
            for f in self.scss:
                for k, head, body in parse(self.code[f]):
                    if k == 'block' and head.startswith('@mixin'):
                        bodies[re.match(r'@mixin\s+([\w-]+)', head).group(1)] = body
            found, changed = set(), True
            while changed:
                changed = False
                for name, body in bodies.items():
                    if name in found:
                        continue
                    for k, head, _ in body:
                        included = re.match(r'@include\s+([\w-]+)', head)
                        if (k == 'block' and (not head.startswith('@') or head.startswith(('@media', '@include breakpoint')))) \
                                or (included and included.group(1) in found):
                            found.add(name)
                            changed = True
                            break
            self._nesting = found
        return self._nesting

    def classes_in(self, f):
        """Every class name that appears in a selector in one file."""
        t = re.sub(r'url\([^)]*\)', '', self.code[f])
        t = re.sub(r'\b(?:map|math|list|string|meta)\.[\w-]+', '', t)
        return {c for c in re.findall(r'\.([A-Za-z_][\w-]*)', t) if not c.endswith('-')}

    def top_classes(self, f):
        """Classes that head a top-level rule in one file."""
        found = set()
        for k, head, _ in parse(self.code[f]):
            if k == 'block' and head.startswith('.'):
                found.update(re.findall(r'^\s*\.([\w-]+)', head, re.M) +
                             [m for m in re.findall(r',\s*\.([\w-]+)', head)])
        return found


def check_preconditions(root, rep):
    """Rule 1.1.1: the styles directory and entry file exist. Exits when they do not."""
    if not os.path.isdir(os.path.join(root, 'styles')):
        sys.exit(f'ERROR: [1.1.1] {root}/styles does not exist; pass the src directory as the first argument')
    rep.count('1.1.1')


def check_syntax_and_modules(p, rep):
    """Rules syntax, 1.1.1, 1.2.1-1.2.8."""
    for f, t in p.code.items():
        rep.count('syntax')
        for a, b in (('{', '}'), ('(', ')'), ('[', ']')):
            if t.count(a) != t.count(b):
                rep.error('syntax', f'{p.rel(f)}: unbalanced {a}{b} ({t.count(a)}/{t.count(b)})')

    def resolves(frm, path):
        if path.startswith('sass:'):
            return True
        base = os.path.normpath(os.path.join(os.path.dirname(frm), path))
        d, n = os.path.split(base)
        return any(os.path.exists(c) for c in (
            base + '.scss', os.path.join(d, '_' + n + '.scss'), os.path.join(base, '_index.scss')))

    for f, t in p.code.items():
        rep.count('1.2.7')
        if re.search(r'@import\b', t):
            rep.error('1.2.7', f'{p.rel(f)}: @import is not used; load modules with @use')
        for m in re.finditer(r'@(?:use|forward)\s+[\'"]([^\'"]+)[\'"]', t):
            rep.count('1.2.8')
            if not resolves(f, m.group(1)):
                rep.error('1.2.8', f'{p.rel(f)}: cannot resolve module {m.group(1)}')
            if '/utilities/' in f.replace(os.sep, '/') and not m.group(1).startswith('sass:'):
                rep.count('1.2.4')
                if '/' in m.group(1):
                    rep.error('1.2.4', f'{p.rel(f)}: utilities partials load siblings by bare name, not {m.group(1)}')

    for needed, label in ((p.variables_file, 'utilities/_variables.scss'),
                          (p.themes_file, 'utilities/_themes.scss'), (p.main_file, 'main.scss')):
        rep.count('1.1.1')
        if not os.path.exists(needed):
            rep.error('1.1.1', f'{label} not found')

    if os.path.exists(p.main_file):
        uses = re.findall(r"@use\s+'([^']+)'", p.code[p.main_file])
        rep.count('1.2.1', len(uses))
        for dup in sorted({u for u in uses if uses.count(u) > 1}):
            rep.error('1.2.1', f'main.scss loads {dup} more than once')
        rep.count('1.2.2')
        if uses and uses[0] != 'utilities/themes':
            rep.error('1.2.2', 'main.scss: first @use must be utilities/themes')
        if uses and uses[-1] != 'utilities/helpers':
            rep.error('1.2.2', 'main.scss: last @use must be utilities/helpers')
        loaded = set()
        for u in uses:
            d, n = os.path.split(os.path.normpath(os.path.join(p.styles, u)))
            loaded.add(os.path.join(d, '_' + n + '.scss'))
        support = {'_functions.scss', '_mixins.scss', '_variables.scss', '_index.scss'}
        for f in p.scss:
            if f != p.main_file and os.path.basename(f) not in support:
                rep.count('1.2.8')
                if f not in loaded:
                    rep.error('1.2.8', f'{p.rel(f)}: not loaded from main.scss')

    for f in p.scss:
        r = p.rel(f)
        if r.startswith(('base/', 'components/')):
            rep.count('1.2.3')
            uses = [u for u in re.findall(r"@use\s+'([^']+)'", p.raw[f]) if not u.startswith('sass:')]
            if not uses or uses[0] != '../utilities' or "@use '../utilities' as *;" not in p.raw[f]:
                rep.warn('1.2.3', f"{r}: first project module is not @use '../utilities' as *;")
            rep.count('1.2.6')
            if any(u.startswith(('../base', '../components')) for u in uses):
                rep.error('1.2.6', f'{r}: loads another base/ or components/ partial')
    index = os.path.join(p.styles, 'utilities', '_index.scss')
    if os.path.exists(index):
        rep.count('1.2.5')
        forwarded = sorted(re.findall(r"@forward\s+'([^']+)'", p.raw[index]))
        if forwarded != ['functions', 'mixins', 'variables']:
            rep.error('1.2.5', f'utilities/_index.scss forwards {forwarded}; expected functions, mixins, variables')


def check_tokens_and_roles(p, rep):
    """Rules 2.1.1, 3.1.1, 3.3.1, 3.3.3, 3.4.2-3.4.5, 3.4.8, 4.2.1."""
    for f, t in p.code.items():
        for g, tone in re.findall(r'(?<![\w-])color\(\s*(\w+)\s*,\s*(\w+)\s*\)', t):
            rep.count('3.1.1')
            if tone not in p.palette.get(g, {}):
                rep.error('3.1.1', f'{p.rel(f)}: color({g}, {tone}) is not in $color-map')

    text = p.code.get(p.themes_file, '')
    if text:
        for theme in ('light', 'dark'):
            body = block_after(text, f'@mixin theme-{theme}')
            rep.count('3.3.1')
            if body is None:
                rep.error('3.3.1', f'_themes.scss: @mixin theme-{theme} not found')
                continue
            rep.count('3.4.3')
            if 'color-scheme' not in body:
                rep.error('3.4.3', f'_themes.scss: theme-{theme} does not set color-scheme')
        if set(p.roles['light']) != set(p.roles['dark']):
            rep.error('3.3.1', f'_themes.scss: roles differ between themes: '
                               f'{sorted(set(p.roles["light"]) ^ set(p.roles["dark"]))}')
        for token in (':root {', ":root[data-theme='dark']", ':root:not([data-theme])', 'prefers-color-scheme: dark'):
            rep.count('3.4.8')
            if token not in text:
                rep.error('3.4.8', f'_themes.scss: missing {token}')
    used_roles = set(re.findall(r'(?<![\w-])theme\(\s*([\w-]+)\s*\)', p.all_code))
    for f, t in p.code.items():
        for role in re.findall(r'(?<![\w-])theme\(\s*([\w-]+)\s*\)', t):
            rep.count('3.3.1')
            if role not in p.roles['light']:
                rep.error('3.3.1', f'{p.rel(f)}: theme({role}) has no definition in _themes.scss')
    for role in sorted(set(p.roles['light']) - used_roles):
        rep.warn('3.3.1', f'role --{role} is defined but never read with theme()')
    for theme in ('light', 'dark'):
        for role in p.roles[theme]:
            rep.count('3.3.3')
            if role not in THRESHOLDS and role != 'surface':
                rep.warn('3.3.3', f'role --{role} has no row in the profile §3.5.1 table')
    for f, t in p.code.items():
        for m in re.finditer(r'(--[\w-]+)\s*:\s*([^;]*);', t):
            rep.count('3.4.4')
            if ('$' in m.group(2) or 'color(' in m.group(2)) and '#{' not in m.group(2):
                rep.error('3.4.4', f'{p.rel(f)}: {m.group(1)} uses a Sass value without interpolation')
        for k, head, body in parse(t):
            if k == 'block' and re.search(r'(?:^|,)\s*(?:html|body|\.main-container)\s*(?:,|$)', head):
                rep.count('3.4.5')
                if any(kind(i) == 'D' and i[1].startswith('transition') for i in body):
                    rep.error('3.4.5', f'{p.rel(f)}: {head} declares transition')

    variables = p.variables()
    for f, t in p.code.items():
        local = (set(re.findall(r'\$([\w-]+)\s*:', t)) | set(re.findall(r'[(,]\s*\$([\w-]+)', t))
                 | set(re.findall(r'@(?:for|each)\s+\$([\w-]+)', t)))
        for v in set(re.findall(r'\$([\w-]+)', t)):
            rep.count('2.1.1')
            if v not in variables and v not in local:
                rep.error('2.1.1', f'{p.rel(f)}: ${v} is not defined')
    outside = '\n'.join(t for f, t in p.code.items() if f != p.variables_file)
    for v in sorted(variables):
        rep.count('2.1.1')
        if not re.search(r'\$' + re.escape(v) + r'\b', outside):
            rep.warn('2.1.1', f'${v} is defined in _variables.scss but never used')
    for f, t in p.code.items():
        for name in re.findall(r'(?:^|\s)\$([\w-]+)\s*:', t):
            rep.count('4.2.1')
            if not KEBAB.match(name):
                rep.warn('4.2.1', f'{p.rel(f)}: ${name} is not kebab-case')
        for name in re.findall(r'@(?:mixin|function)\s+([\w-]+)', t) + re.findall(r'%([\w-]+)\s*\{', t):
            rep.count('4.2.1')
            if not KEBAB.match(name):
                rep.warn('4.2.1', f'{p.rel(f)}: {name} is not kebab-case')

    if len(THEME_KEY_FILES) == 2:
        reader, writer = (os.path.normpath(os.path.join(p.root, x)) for x in THEME_KEY_FILES)
        rep.count('3.4.2')
        missing = [x for x in THEME_KEY_FILES if not os.path.exists(os.path.normpath(os.path.join(p.root, x)))]
        for x in missing:
            rep.error('3.4.2', f'{x} is listed in the profile §15.9 as a theme key file and does not exist')
        if not missing:
            a = re.search(r"getItem\('([^']+)'\)", open(reader).read())
            b = re.search(r"STORAGE_KEY\s*=\s*'([^']+)'", open(writer).read())
            if not a or not b or a.group(1) != b.group(1):
                rep.error('3.4.2', f'theme storage key differs between {THEME_KEY_FILES[0]} and {THEME_KEY_FILES[1]}')


def check_forbidden(p, rep):
    """Rules 3.1.3, 3.3.4, 5.1.2, 5.1.3, 5.3.1, 5.4.4, 6.2, 6.5, 9.1.4."""
    for f, t in p.code.items():
        r = p.rel(f)
        rep.count('3.1.3')
        if f != p.variables_file and re.search(r'#[0-9a-fA-F]{3,8}\b', re.sub(r'#\{', '', t)):
            rep.error('3.1.3', f'{r}: hex color outside _variables.scss')
        if re.search(r'\b(?:rgba?|hsla?)\(', t):
            rep.error('3.1.3', f'{r}: rgb()/hsl() literal; add a palette token or theme role instead')
        if re.search(r':\s*[^;{]*\b(?:white|black)\b[^;]*;', t):
            rep.error('3.1.3', f'{r}: named color white/black; use color() or theme()')
        rep.count('3.3.4')
        if re.search(r'\b(?:rgba?|darken|lighten|mix|transparentize|opacify|adjust-color|scale-color)\([^)]*theme\(', t):
            rep.error('3.3.4', f'{r}: Sass color function applied to a theme() value')
        rep.count('5.3.1')
        if r not in IMPORTANT_ALLOWED and '!important' in t:
            rep.error('5.3.1', f'{r}: !important outside {sorted(IMPORTANT_ALLOWED)}')
        rep.count('5.1.3')
        if re.search(r'\[\s*class\s*[\^\*\$]=', t):
            rep.error('5.1.3', f'{r}: attribute selector on class; use a placeholder or mixin')
        rep.count('5.1.2')
        if f != p.variables_file and re.search(r'(?:^|[\s,>+~])#[A-Za-z_-][\w-]*\s*[{,]', t, re.M):
            rep.error('5.1.2', f'{r}: ID selector')
        rep.count('6.2')
        if r != 'utilities/_mixins.scss' and re.search(r'@media[^{]*(?:min|max)-width', t):
            rep.error('6.2', f'{r}: raw width @media; use @include breakpoint($variable)')
        if re.search(r'breakpoint\(\s*\d', t):
            rep.error('6.2', f'{r}: breakpoint() argument must be a breakpoint variable')
        rep.count('6.5')
        for m in re.finditer(r'@media([^{]*)\{', t):
            q = m.group(1).strip()
            if not (q in ('(prefers-color-scheme: dark)', '(prefers-reduced-motion: reduce)')
                    or (r == 'utilities/_mixins.scss' and 'min-width' in q)) \
                    and 'min-width' not in q and 'max-width' not in q:
                rep.error('6.5', f'{r}: @media {q} is not permitted')
        rep.count('5.4.4')
        if re.search(r'@extend\s+\.', t):
            rep.error('5.4.4', f'{r}: @extend of a class; extend a placeholder')
        rep.count('9.1.4')
        if 'text-shadow' in t:
            rep.error('9.1.4', f'{r}: text-shadow')


def walk(items, path, f, p, rep):
    """Rules 5.2.3, 8.1.4, 8.4.1, 13.6 on one block's statements, then its nested blocks."""
    rep.count('5.2.3')
    nesting = p.nesting_mixins()

    def classify(i):
        included = re.match(r'@include\s+([\w-]+)', i[1])
        if kind(i) == 'M' and included and included.group(1) in nesting:
            return 'Q'
        return kind(i)

    seq = ''.join(classify(i) for i in items if classify(i) != 'X')
    if not re.fullmatch(r'M*D*[NQ]*B*', seq):
        rep.warn('5.2.3', f'{p.rel(f)}: {path}: order is {seq}; expected declaration includes (M), declarations (D), '
                          f'nested selectors and nesting includes (N, Q), breakpoint (B)')
    rep.count('8.1.4')
    props = [i[1].split(':', 1)[0].strip() for i in items if kind(i) == 'D' and ':' in i[1]]
    expected = sorted(props, key=declaration_key)
    if props != expected:
        rep.warn('8.1.4', f'{p.rel(f)}: {path}: declaration order {props}; expected {expected}')
    rep.count('8.4.1')
    decl = {i[1].split(':', 1)[0].strip(): i[1].split(':', 1)[1].strip()
            for i in items if kind(i) == 'D' and ':' in i[1]}
    if decl.get('opacity') == '0' and decl.get('visibility') != 'hidden' \
            and 'display' not in decl and 'input' not in path:
        rep.warn('8.4.1', f'{p.rel(f)}: {path}: opacity: 0 without visibility: hidden')
    rep.count('13.6')
    if not items:
        rep.warn('13.6', f'{p.rel(f)}: {path}: empty rule block')
    for i in items:
        if i[0] == 'block' and kind(i) in ('N', 'B'):
            walk(i[2], (path + ' > ' if path else '') + i[1][:40], f, p, rep)


def check_structure(p, rep):
    """Rules 5.2.1, 5.2.3, 8.1.4, 8.4.1, 13.6 and 8.1.3 / 12.1.2."""
    for f in p.scss:
        for k, head, body in parse(p.code[f]):
            if k == 'block' and (head.startswith(('.', '%', ':', 'html', 'body', '*', '@mixin', '@for', '@each'))
                                 or re.match(r'[a-z]', head)):
                walk(body, head[:60], f, p, rep)
            elif k == 'block' and head.startswith('@media'):
                for k2, h2, b2 in body:
                    if k2 == 'block':
                        walk(b2, f'{head[:20]} > {h2[:40]}', f, p, rep)
        depth = peak = 0
        for c in p.code[f]:
            depth += (c == '{') - (c == '}')
            peak = max(peak, depth)
        rep.count('5.2.1')
        if peak > 3:
            rep.warn('5.2.1', f'{p.rel(f)}: nesting depth {peak}; limit is 3')
        r = p.rel(f)
        if r.startswith(('base/', 'components/')):
            comments = ' '.join(re.findall(r'//[^\n]*', p.raw[f]))
            for name in sorted(SCRIPT_TOGGLED):
                if re.search(r'\.' + re.escape(name) + r'\b', p.code[f]):
                    rep.count('8.1.3')
                    if '.' + name not in comments:
                        rep.warn('8.1.3', f'{r}: styles .{name} (set by a script) but no comment names it')
            for attr in sorted(SCRIPT_ATTRS):
                if attr in p.code[f]:
                    rep.count('8.1.3')
                    if attr not in comments:
                        rep.warn('8.1.3', f'{r}: styles [{attr}] (set by a script) but no comment names it')


def check_formatting(p, rep):
    """Rules 2.3.1, 14.1, 14.2, 14.6-14.9."""
    values = sorted({v[:-2] for n, v in p.variables().items()
                     if n.startswith('space-') and re.fullmatch(r'\d+(?:\.\d+)?px', v)}, key=float)
    steps = r'(?:' + '|'.join(re.escape(v) for v in values) + r')px' if values else ''
    for f in p.scss:
        r = p.rel(f)
        lines = p.raw[f].splitlines()
        rep.count('14.1', len(lines))
        tabs = sum(1 for l in lines if l.startswith('\t'))
        if tabs:
            rep.warn('14.1', f'{r}: indented with tabs ({tabs} lines); use 2 spaces per level')
        depth, bad = 0, []
        for n, line in enumerate(p.code[f].splitlines(), 1):
            if not line.strip() or line.startswith('\t'):
                continue
            closers = len(re.match(r'[})\]]*', line.strip()).group(0))
            if len(line) - len(line.lstrip(' ')) != 2 * max(depth - closers, 0):
                bad.append(n)
            depth += sum(line.count(c) for c in '{([') - sum(line.count(c) for c in '})]')
        if bad:
            rep.warn('14.1', f'{r}: {len(bad)} lines not indented 2 spaces per level (first: line {bad[0]})')
        rep.count('14.9', len(lines))
        long_lines = [n for n, l in enumerate(lines, 1) if len(l) > MAX_LINE]
        if long_lines:
            rep.warn('14.9', f'{r}: {len(long_lines)} lines over {MAX_LINE} characters (first: line {long_lines[0]})')
        rep.count('14.2')
        dq = re.findall(r'"[^"]*"', p.code[f])
        if dq:
            rep.warn('14.2', f'{r}: double-quoted strings {dq}; use single quotes')
        rep.count('14.6')
        for m in re.finditer(r'(?<![\w.])0(?:px|em|rem|%)(?![\w])|\b\d+(?:\.\d+)?rem\b', p.code[f]):
            rep.warn('14.6', f'{r}: unit {m.group(0)}; use px, ch, em, or a unitless 0')
        rep.count('14.7')
        if re.search(r'#[0-9a-fA-F]*[A-F][0-9a-fA-F]*\b', re.sub(r'#\{', '', p.code[f])):
            rep.warn('14.7', f'{r}: uppercase hex')
        rep.count('14.8')
        for m in re.finditer(r'calc\(([^;]*)\)', p.code[f]):
            if '$' in re.sub(r'#\{[^}]*\}', '', m.group(0)):
                rep.warn('14.8', f'{r}: calc() with a variable outside interpolation: {m.group(0)[:60]}')
        if f != p.variables_file and steps:
            rep.count('2.3.1')
            for m in re.finditer(r'(?:margin|padding|gap)[a-z-]*\s*:[^;]*?\b' + steps
                                 + r'|calc\([^)]*\b' + steps, p.code[f]):
                rep.warn('2.3.1', f'{r}: spacing literal in "{m.group(0).strip()}"; use a $space-* token')


def comments_of(text):
    """Text of every // line comment, /* */ block comment and <!-- --> comment in text."""
    found = re.findall(r'(?<!:)//([^\n]*)', text)
    found += re.findall(r'/\*(.*?)\*/', text, re.S)
    found += re.findall(r'<!--(.*?)-->', text, re.S)
    return found


def check_classes_and_comments(p, rep):
    """Rules 4.1.1, 4.1.4, 13.2, 13.5, 12.1.1."""
    in_attribute, in_literal, prefixes = set(), set(), set()
    for path in p.markup:
        t = open(path, errors='ignore').read()
        script = path.endswith(SCRIPT_EXT)
        code = strip_comments(t) if script else t
        found, pre = class_attribute_tokens(code)
        in_attribute |= found
        prefixes |= pre
        if script:
            found, pre = literal_tokens(code)
            in_literal |= found
            prefixes |= pre
        if path.endswith(('.tsx', '.jsx', '.astro')):
            rep.count('12.1.1')
            if re.search(r'\sstyle\s*=\s*[{"\']', code):
                rep.error('12.1.1', f'{os.path.relpath(path, p.root)}: inline style attribute')
    used = in_attribute | in_literal
    rules = {c for f in p.scss for c in p.classes_in(f)}
    n = re.search(r'\$grid-columns\s*:\s*(\d+)', p.code.get(p.variables_file, ''))
    generated = {f'flex__{k}--{i}' for k in ('small', 'large') for i in range(1, int(n.group(1)) + 1)} if n else set()
    helpers = set(re.findall(r'\.([A-Za-z_][\w-]*)', p.code.get(p.helpers_file, '')))
    helpers |= {f'{a}-{s}-0' for a in ('marg', 'pad') for s in ('top', 'right', 'bottom', 'left')}
    for c in sorted(rules - generated):
        rep.count('4.1.1')
        if not BEM.match(c):
            rep.warn('4.1.1', f'.{c} does not follow block__element--modifier kebab-case')
    for c in sorted(in_attribute - rules - generated - NO_RULE_HOOKS):
        rep.count('4.1.4')
        rep.warn('4.1.4', f'class "{c}" is used in markup but has no rule')
    for c in sorted(rules - used - SCRIPT_TOGGLED - generated - helpers - {'jpg', 'svg', 'webp'}):
        rep.count('4.1.4')
        if not any(c.startswith(pre) for pre in prefixes):
            rep.warn('4.1.4', f'.{c} has a rule but no markup uses it')
    names = {os.path.basename(x) for x in glob.glob(os.path.join(p.root, '**', '*'), recursive=True)}
    names |= set(os.listdir(os.path.dirname(p.root)))
    history = r'\b(?:previously|formerly|used to|no longer|old version|was changed|replaces the|yet)\b'
    sources = {p.rel(f): t for f, t in p.raw.items()}
    for path in p.markup:
        sources[os.path.relpath(path, p.root)] = open(path, errors='ignore').read()
    for label, t in sources.items():
        for text in comments_of(t):
            rep.count('13.5')
            for fn in re.findall(r'[\w.\[\]-]+\.(?:astro|scss|js|jsx|ts|tsx|html|md|mdx)\b', text):
                if fn not in names:
                    rep.error('13.5', f'{label}: comment names {fn}, which does not exist')
            rep.count('13.2')
            if re.search(history, text, re.I):
                rep.warn('13.2', f'{label}: comment describes history or a pending state: {" ".join(text.split())[:90]}')


def contrast_rows(p):
    """(theme, role, color, surface, ratio, minimum) for every role against --surface."""
    rows = []
    for theme in ('light', 'dark'):
        if 'surface' not in p.roles[theme]:
            continue
        sg, st = p.roles[theme]['surface']
        surface = p.palette[sg][st]
        for role, minimum in THRESHOLDS.items():
            if role in p.roles[theme]:
                g, tone = p.roles[theme][role]
                rows.append((theme, role, p.palette[g][tone], surface, ratio(p.palette[g][tone], surface), minimum))
    return rows


def check_contrast(p, rep):
    """Rule 3.5.1."""
    for theme, role, color, surface, value, minimum in contrast_rows(p):
        rep.count('3.5.1')
        if minimum and value < minimum and (theme, role) not in EXEMPT:
            rep.warn('3.5.1', f'{theme}: --{role} {color} on surface {surface} is {value:.2f}:1, below {minimum}:1')


def check_profile(p, rep, profile_path):
    """Rule 15.7: the profile's tables match the code."""
    g = open(profile_path).read()

    def section(start):
        return profile_section(g, start)

    def mismatch(msg):
        rep.count('15.7')
        rep.error('15.7', msg)

    tree = section('## 1.1 Layout')
    listed = set(re.findall(r'_[\w-]+\.scss', tree)) | {'main.scss'}
    actual = {os.path.basename(f) for f in p.scss}
    rep.count('15.7')
    for n in sorted(listed - actual):
        mismatch(f'profile §1.1 lists {n}; no such file')
    for n in sorted(actual - listed):
        mismatch(f'{n} exists; profile §1.1 does not list it')

    variables = p.variables()
    table = section('## 2.2 Token reference')
    names = re.findall(r'`\$([\w-]+)`', table)
    for name, val in re.findall(r'`\$([\w-]+)`\s+(\d+(?:\.\d+)?(?:px|ch)?)', table):
        rep.count('15.7')
        if name not in variables:
            mismatch(f'profile §2.2: ${name} is not in _variables.scss')
        elif variables[name] != val:
            mismatch(f'profile §2.2: ${name} is {val}; code has {variables[name]}')
    for name in names:
        if name not in variables and name != 'color-map':
            mismatch(f'profile §2.2: ${name} is not in _variables.scss')
    for name in variables:
        if name not in names:
            mismatch(f'${name} is in _variables.scss; profile §2.2 does not list it')

    table = section('## 3.2 Roles')
    rows = {}
    for row in table.splitlines():
        m = re.match(r'\|\s*`([\w-]+)`\s*\|[^|]*\|\s*([\w-]+)-(\w+) `(#[0-9a-f]{6})`\s*\|'
                     r'\s*([\w-]+)-(\w+) `(#[0-9a-f]{6})`\s*\|', row)
        if m:
            rows[m.group(1)] = {'light': m.groups()[1:4], 'dark': m.groups()[4:7]}
    for role in sorted(set(rows) | set(p.roles['light'])):
        rep.count('15.7')
        if role not in rows:
            mismatch(f'--{role} is in _themes.scss; profile §3.2 does not list it')
        elif role not in p.roles['light']:
            mismatch(f'profile §3.2: --{role} is not in _themes.scss')
        else:
            for theme in ('light', 'dark'):
                gg, gt, gh = rows[role][theme]
                cg, ct = p.roles[theme][role]
                if (gg, gt) != (cg, ct) or p.palette[cg][ct].lower() != gh:
                    mismatch(f'profile §3.2: --{role} {theme} is {gg}-{gt} {gh}; code has {cg}-{ct} {p.palette[cg][ct]}')

    for role, minimum in CORE_MIN.items():
        if role in THRESHOLDS:
            rep.count('15.7')
            if THRESHOLDS[role] != minimum:
                mismatch(f'profile §3.5.1: --{role} requires {THRESHOLDS[role]}; guide 3.5.1 requires {minimum}')
    table = section('**3.5.1**')
    computed = {(t, r): v for t, r, _, _, v, _ in contrast_rows(p)}
    for row in table.splitlines():
        m = re.match(r'\|\s*([^|]+?)\s*\|[^|]*\|\s*([\d.,\s]+)\|\s*([\d.,\s*]+)\|', row)
        if not m:
            continue
        names = re.findall(r'`([\w-]+)`', m.group(1))
        for theme, cell in (('light', m.group(2)), ('dark', m.group(3))):
            for name, val in zip(names, re.findall(r'[\d.]+', cell.replace('*', ''))):
                rep.count('15.7')
                got = computed.get((theme, name))
                if got is None or abs(got - float(val)) > 0.006:
                    mismatch(f'profile §3.5.1: {theme} {name} is {val}; computed '
                             f'{"n/a" if got is None else format(got, ".2f")}')

    table = section('## 12.2 Script-affected selectors')
    for row in table.splitlines():
        m = re.match(r'\|\s*`([.\[][^`|]+)`[^|]*\|([^|]*)\|[^|]*\|([^|]*)\|', row)
        if not m:
            continue
        sel = m.group(1)
        key = sel.strip('.[]').split(']')[0]
        for fn in re.findall(r'`([\w./-]+\.\w+)`', m.group(2)):
            if not fn.endswith(MARKUP_EXT):
                continue
            rep.count('15.7')
            hits = [x for x in p.markup if x.replace(os.sep, '/').endswith('/' + fn)]
            if not hits or key not in open(hits[0]).read():
                mismatch(f'profile §12.2: {fn} does not contain {key}')
        for part in re.findall(r'`([\w/.-]*_[\w-]+\.scss)`', m.group(3)):
            rep.count('15.7')
            hits = [f for f in p.scss if f.replace(os.sep, '/').endswith(part)]
            if not hits or key not in p.code[hits[0]]:
                mismatch(f'profile §12.2: {part} does not style {sel}')

    table = section('## 12.3 Components and hooks')
    owners = {}
    for f in p.scss:
        for c in p.top_classes(f):
            owners.setdefault(c, set()).add(f)
    for row in table.splitlines():
        m = re.match(r'\|\s*`(_[\w-]+)`\s*\|([^|]*)\|', row)
        if not m:
            continue
        hits = [f for f in p.scss if os.path.basename(f) == m.group(1) + '.scss']
        rep.count('15.7')
        if not hits:
            mismatch(f'profile §12.3: {m.group(1)} is not a partial')
            continue
        f = hits[0]
        expected, previous = set(), ''
        for tok in re.findall(r'`([^`]+)`', m.group(2)):
            if tok.startswith('--'):
                expected.add(previous + tok)
            elif tok.startswith('.') and 'N' not in tok and '{' not in tok:
                previous = tok[1:]
                expected.add(previous)
        actual_classes = p.classes_in(f)
        for c in sorted(expected - actual_classes):
            mismatch(f'profile §12.3: {m.group(1)} lists .{c}; the partial does not define it')
        for c in sorted(actual_classes - expected - SCRIPT_TOGGLED):
            if re.match(r'(?:flex__|marg-|pad-)', c) or c in ('jpg', 'svg', 'webp'):
                continue
            if f not in owners.get(c, set()) and owners.get(c):
                continue
            mismatch(f'{p.rel(f)} defines .{c}; profile §12.3 does not list it')


def run(root, profile):
    """Load the profile, run every check against <root>, and return the Report."""
    load_profile(profile)
    rep = Report()
    check_preconditions(root, rep)
    p = Project(root)
    check_syntax_and_modules(p, rep)
    check_tokens_and_roles(p, rep)
    check_forbidden(p, rep)
    check_structure(p, rep)
    check_formatting(p, rep)
    check_classes_and_comments(p, rep)
    check_contrast(p, rep)
    check_profile(p, rep, profile)
    return rep, p


def print_report(rep, p):
    """Contrast table, per-rule ledger, then findings."""
    print(f'Profile stack: {STACK}')
    print('Contrast of each role against --surface')
    print(f'{"theme":6} {"role":14} {"color":8} {"surface":8} {"ratio":>6}  required')
    for theme, role, color, surface, value, minimum in contrast_rows(p):
        required = 'n/a' if not minimum else (f'{minimum} (exempt, 3.5.3)' if (theme, role) in EXEMPT and value < minimum else minimum)
        print(f'{theme:6} {role:14} {color:8} {surface:8} {value:6.2f}  {required}')
    print('\nRules checked (items checked / violations)')
    for rule in sorted(rep.checked, key=lambda r: [int(x) if x.isdigit() else 0 for x in r.split('.')]):
        print(f'  [{rule}] {rep.checked[rule]} / {rep.violations.get(rule, 0)}')
    print()
    for e in rep.errors:
        print('ERROR:', e)
    for w in rep.warnings:
        print('WARN: ', w)
    print(f'\n{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)')


# ---------------------------------------------------------------- self-test
FIXTURE = {
    'styles/main.scss': "@use 'utilities/themes';\n\n@use 'base/base';\n\n@use 'components/widget';\n\n@use 'utilities/helpers';\n",
    'styles/utilities/_index.scss': "@forward 'functions';\n@forward 'mixins';\n@forward 'variables';\n",
    'styles/utilities/_variables.scss': (
        "$color-map: (\n  primary: (\n    light: #009bff,\n    mild: #006cb2,\n    mid: #005d99,\n    dark: #002e4c\n  ),\n"
        "  gray: (\n    light: #f5f5f5,\n    mild: #bdbdbd,\n    mid: #616161,\n    dark: #424242,\n    jet: #212121\n  )\n);\n\n"
        "$small-screen: 768px;\n$space-sm: 11px;\n$space-md: 22px;\n$transition: all 0.3s ease-out;\n"),
    'styles/utilities/_functions.scss': (
        "@use 'variables' as *;\n@use 'sass:map';\n\n@function color($color, $tone: 'light') {\n"
        "  @return map.get(map.get($color-map, $color), $tone);\n}\n\n@function theme($role) {\n  @return var(--#{$role});\n}\n"),
    'styles/utilities/_mixins.scss': (
        "@use 'variables' as *;\n\n@mixin breakpoint($point) {\n  @media screen and (min-width: $point) { @content; }\n}\n\n"
        "@mixin lift-on-hover {\n  transition: $transition;\n\n  &:hover { transform: translateY(-4px); }\n}\n"),
    'styles/utilities/_themes.scss': (
        "@use 'functions' as *;\n\n@mixin theme-light {\n  --border: #{color(gray, mid)};\n  --border-strong: #{color(gray, mid)};\n"
        "  --border-subtle: #{color(gray, mild)};\n  --fill-strong: #{color(gray, jet)};\n  --focus: #{color(primary, mild)};\n"
        "  --link: #{color(primary, mild)};\n  --surface: #{color(gray, light)};\n  --text: #{color(gray, jet)};\n"
        "  --text-muted: #{color(gray, mid)};\n  color-scheme: light;\n}\n\n"
        "@mixin theme-dark {\n  --border: #{color(gray, mid)};\n  --border-strong: #{color(gray, mild)};\n"
        "  --border-subtle: #{color(gray, dark)};\n  --fill-strong: #{color(gray, mild)};\n  --focus: #{color(primary, light)};\n"
        "  --link: #{color(primary, light)};\n  --surface: #{color(gray, jet)};\n  --text: #{color(gray, light)};\n"
        "  --text-muted: #{color(gray, mild)};\n  color-scheme: dark;\n}\n\n:root { @include theme-light; }\n\n"
        ":root[data-theme='dark'] { @include theme-dark; }\n\n@media (prefers-color-scheme: dark) {\n"
        "  :root:not([data-theme]) { @include theme-dark; }\n}\n"),
    'styles/utilities/_helpers.scss': (
        "@use 'mixins' as *;\n@use 'variables' as *;\n\n.mobile-only {\n  @include breakpoint($small-screen) { display: none; }\n}\n"),
    'styles/base/_base.scss': (
        "@use '../utilities' as *;\n\nhtml {\n  background-color: theme(surface);\n}\n\n:focus-visible {\n"
        "  outline: 2px solid theme(focus);\n  outline-offset: 2px;\n}\n\n.main-container {\n  background-color: theme(surface);\n"
        "  color: theme(text);\n}\n\n@media (prefers-reduced-motion: reduce) {\n  *,\n  *::before,\n  *::after {\n"
        "    transition-duration: 0.01ms !important;\n  }\n}\n"),
    'styles/components/_widget.scss': (
        "@use '../utilities' as *;\n\n// Widget: fixture component.\n// Script-toggled: .is-open on .widget (set by Widget.tsx).\n"
        ".widget {\n  border: 1px solid theme(border);\n  color: theme(text-muted);\n  padding: $space-md;\n  transition: $transition;\n\n"
        "  &.is-open {\n    background-color: theme(fill-strong);\n    border-color: theme(border-strong);\n  }\n\n  a {\n"
        "    color: theme(link);\n  }\n\n  @include breakpoint($small-screen) {\n    padding: $space-sm;\n  }\n}\n\n"
        ".widget__title {\n  border-bottom: 1px solid theme(border-subtle);\n}\n\n"
        ".widget__note { margin: 0; }\n\n.widget__note--high { color: theme(link); }\n"),
    '../index.html': (
        "<!doctype html>\n<html lang=\"en\">\n  <head>\n    <script>\n      let theme = localStorage.getItem('theme');\n"
        "    </script>\n  </head>\n  <body>\n    <div id=\"root\" class=\"main-container shell\"></div>\n  </body>\n</html>\n"),
    'utils/theme.ts': "const STORAGE_KEY = 'theme';\n\nexport const key = STORAGE_KEY;\n",
    'components/Widget.tsx': (
        "interface WidgetProps {\n  open: boolean;\n  tone: string;\n}\n\n// Widget: fixture component.\n"
        "export function Widget({ open, tone }: WidgetProps) {\n  const empty = '';\n  return (\n    <div className={open ? 'widget is-open' : 'widget'}>\n"
        "      <h2 className=\"widget__title\">Title</h2>\n      <p className={`widget__note widget__note--${tone}`}>Note</p>\n"
        "      <a href=\"/\" title={empty}>Link</a>\n    </div>\n  );\n}\n"),
}

# (name, expected rule, edits). An edit is ('append'|'replace'|'create'|'delete', path, ...).
W = 'styles/components/_widget.scss'
V = 'styles/utilities/_variables.scss'
T = 'styles/utilities/_themes.scss'
M = 'styles/main.scss'
X = 'components/Widget.tsx'
CASES = [
    ('missing themes file', '1.1.1', [('delete', T)]),
    ('duplicate @use', '1.2.1', [('replace', M, "@use 'components/widget';", "@use 'components/widget';\n@use 'components/widget';")]),
    ('first @use not themes', '1.2.2', [('replace', M, "@use 'utilities/themes';\n\n", '')]),
    ('missing utilities @use', '1.2.3', [('replace', W, "@use '../utilities' as *;\n", '')]),
    ('relative path in utilities', '1.2.4', [('replace', 'styles/utilities/_helpers.scss', "@use 'mixins' as *;", "@use '../utilities/mixins' as *;")]),
    ('extra forward', '1.2.5', [('append', 'styles/utilities/_index.scss', "@forward 'themes';\n")]),
    ('partial loads partial', '1.2.6', [('replace', W, "@use '../utilities' as *;", "@use '../utilities' as *;\n@use '../base/base';")]),
    ('@import', '1.2.7', [('append', W, "@import 'x';\n")]),
    ('orphan partial', '1.2.8', [('create', 'styles/components/_orphan.scss', "@use '../utilities' as *;\n")]),
    ('undefined variable', '2.1.1', [('append', W, "\n.widget__a {\n  padding: $nope;\n}\n")]),
    ('spacing literal', '2.3.1', [('append', W, "\n.widget__a {\n  margin: 22px;\n}\n")]),
    ('bad color tone', '3.1.1', [('append', W, "\n.widget__a {\n  color: color(gray, nope);\n}\n")]),
    ('hex outside variables', '3.1.3', [('append', W, "\n.widget__a {\n  color: #ff0000;\n}\n")]),
    ('undefined role', '3.3.1', [('append', W, "\n.widget__a {\n  color: theme(nonexistent);\n}\n")]),
    ('role without threshold', '3.3.3', [('replace', T, "  --surface: #{color(gray, light)};", "  --surface: #{color(gray, light)};\n  --extra: #{color(gray, mild)};"),
                                         ('replace', T, "  --surface: #{color(gray, jet)};", "  --surface: #{color(gray, jet)};\n  --extra: #{color(gray, mild)};")]),
    ('color function on role', '3.3.4', [('append', W, "\n.widget__a {\n  color: rgba(theme(surface), 0.5);\n}\n")]),
    ('storage key mismatch', '3.4.2', [('replace', 'utils/theme.ts', "'theme'", "'other'")]),
    ('missing color-scheme', '3.4.3', [('replace', T, "  color-scheme: light;\n", '')]),
    ('no interpolation', '3.4.4', [('replace', T, "--surface: #{color(gray, light)};", "--surface: color(gray, light);")]),
    ('transition on html', '3.4.5', [('append', 'styles/base/_base.scss', "\nhtml {\n  transition: $transition;\n}\n")]),
    ('missing no-JS block', '3.4.8', [('replace', T, "@media (prefers-color-scheme: dark) {\n  :root:not([data-theme]) { @include theme-dark; }\n}\n", '')]),
    ('low contrast', '3.5.1', [('replace', T, "  --text: #{color(gray, light)};", "  --text: #{color(gray, dark)};")]),
    ('bad class name', '4.1.1', [('append', W, "\n.BadName {\n  padding: $space-sm;\n}\n")]),
    ('unused rule', '4.1.4', [('append', W, "\n.widget__unused {\n  padding: $space-sm;\n}\n")]),
    ('tsx class without a rule', '4.1.4', [('replace', X, 'className="widget__title"', 'className="widget__title space-x-1"')]),
    ('html class without a rule', '4.1.4', [('replace', '../index.html', 'class="main-container shell"', 'class="main-container shell nope"')]),
    ('bad variable name', '4.2.1', [('append', V, "$BadVar: 1px;\n")]),
    ('ID selector', '5.1.2', [('append', W, "\n#thing {\n  padding: $space-sm;\n}\n")]),
    ('class attribute selector', '5.1.3', [('append', W, "\n[class^='a'] {\n  padding: $space-sm;\n}\n")]),
    ('nesting depth', '5.2.1', [('append', W, "\n.widget__a {\n  &:hover {\n    &:focus {\n      &:active {\n        padding: $space-sm;\n      }\n    }\n  }\n}\n")]),
    ('breakpoint before nested', '5.2.3', [('append', W, "\n.widget__a {\n  padding: $space-sm;\n\n  @include breakpoint($small-screen) {\n    padding: $space-md;\n  }\n\n  &:hover {\n    color: theme(text);\n  }\n}\n")]),
    ('declaration after nesting include', '5.2.3', [('append', W, "\n.widget__b {\n  @include lift-on-hover;\n  padding: $space-sm;\n}\n")]),
    ('!important', '5.3.1', [('append', W, "\n.widget__a {\n  padding: $space-sm !important;\n}\n")]),
    ('@extend class', '5.4.4', [('append', W, "\n.widget__a {\n  @extend .widget;\n}\n")]),
    ('raw width media', '6.2', [('append', W, "\n@media (min-width: 700px) {\n  .widget {\n    padding: $space-sm;\n  }\n}\n")]),
    ('other media', '6.5', [('append', W, "\n@media print {\n  .widget {\n    padding: $space-sm;\n  }\n}\n")]),
    ('toggled class not named', '8.1.3', [('append', 'styles/base/_base.scss', "\n.is-open {\n  padding: $space-sm;\n}\n")]),
    ('astro class without a rule', '4.1.4', [('create', 'components/Card.astro', '<div class="widget__title nope-astro"></div>\n')]),
    ('astro inline style', '12.1.1', [('create', 'components/Card.astro', '<div style="color: red" class="widget__title"></div>\n')]),
    ('classList class without a rule', '4.1.4', [('create', 'utils/dom.ts', "export const mark = (e: Element) => e.classList.add('nope-list');\n")]),
    ('declaration order', '8.1.4', [('append', W, "\n.widget__a {\n  padding: $space-sm;\n  color: theme(text);\n}\n")]),
    ('position after alphabetical', '8.1.4', [('append', W, "\n.widget__a {\n  color: theme(text);\n  position: relative;\n}\n")]),
    ('offsets not clockwise', '8.1.4', [('append', W, "\n.widget__a {\n  position: absolute;\n  left: 0;\n  top: 0;\n}\n")]),
    ('custom property after declaration', '8.1.4', [('append', W, "\n.widget__a {\n  color: theme(text);\n  --x: 1px;\n}\n")]),
    ('opacity without visibility', '8.4.1', [('append', W, "\n.widget__a {\n  opacity: 0;\n}\n")]),
    ('text-shadow', '9.1.4', [('append', W, "\n.widget__a {\n  text-shadow: 0 0 1px theme(text);\n}\n")]),
    ('tsx inline style', '12.1.1', [('replace', X, '<a href', '<a style={{ color: "red" }} href')]),
    ('history comment', '13.2', [('append', W, "// previously 16px\n")]),
    ('tsx history comment', '13.2', [('append', X, "// previously a div\n")]),
    ('comment names missing file', '13.5', [('append', W, "// set by Missing.tsx\n")]),
    ('tsx comment names missing file', '13.5', [('append', X, "// see Missing.tsx\n")]),
    ('empty block', '13.6', [('append', W, "\n.widget__a {\n}\n")]),
    ('tabs', '14.1', [('replace', W, "\n  border-bottom: 1px", "\n\tborder-bottom: 1px")]),
    ('double quotes', '14.2', [('append', W, "\n.widget__a {\n  content: \"x\";\n}\n")]),
    ('zero with unit', '14.6', [('append', W, "\n.widget__a {\n  margin: 0px;\n}\n")]),
    ('uppercase hex', '14.7', [('replace', V, '#f5f5f5', '#F5F5F5')]),
    ('calc without interpolation', '14.8', [('append', W, "\n.widget__a {\n  width: calc(100% - $space-sm);\n}\n")]),
    ('long line', '14.9', [('append', W, '// ' + 'x' * 120 + '\n')]),
    ('unbalanced braces', 'syntax', [('append', W, "\n.widget__a {\n")]),
]


PROFILE_FIXTURE = '''## 1.1 Layout

_index.scss _variables.scss _functions.scss _mixins.scss _themes.scss _helpers.scss _base.scss _widget.scss main.scss

## 2.2 Token reference

| Group | Tokens |
|---|---|
| Palette | `$color-map` |
| Breakpoints | `$small-screen` 768px |
| Spacing | `$space-sm` 11px, `$space-md` 22px |
| Motion | `$transition` (`all 0.3s ease-out`) |

## 3.2 Roles

| Role | Purpose | Light | Dark |
|---|---|---|---|
| `surface` | Page | gray-light `#f5f5f5` | gray-jet `#212121` |
| `text` | Body | gray-jet `#212121` | gray-light `#f5f5f5` |
| `text-muted` | Secondary | gray-mid `#616161` | gray-mild `#bdbdbd` |
| `link` | Links | primary-mild `#006cb2` | primary-light `#009bff` |
| `focus` | Focus | primary-mild `#006cb2` | primary-light `#009bff` |
| `border` | Lines | gray-mid `#616161` | gray-mid `#616161` |
| `border-subtle` | Dividers | gray-mild `#bdbdbd` | gray-dark `#424242` |
| `border-strong` | State | gray-mid `#616161` | gray-mild `#bdbdbd` |
| `fill-strong` | Fills | gray-jet `#212121` | gray-mild `#bdbdbd` |

## 3.5 Contrast

**3.5.1** Each role meets its threshold against `surface`:

| Role | Required | Light | Dark |
|---|---|---|---|
| `text`, `text-muted`, `link` | 4.5 | 14.77, 5.68, 5.09 | 14.77, 8.57, 5.47 |
| `focus`, `border-strong`, `fill-strong` | 3 | 5.09, 5.68, 14.77 | 5.47, 8.57, 8.57 |
| `border`, `border-subtle` | none (structural) | 5.68, 1.72 | 2.60, 1.60 |

## 12.2 Script-affected selectors

| Selector | Set by | On | Styled in |
|---|---|---|---|
| `.is-open` | `Widget.tsx` | `.widget` | `_widget.scss` |

## 12.3 Components and hooks

| Partial | Classes | Appearance |
|---|---|---|
| `_widget` | `.widget`, `.widget__title`, `.widget__note`, `.widget__note--high` | Themed |
| `_base` | element rules, `.main-container` | Themed |
| `_helpers` | `.mobile-only` | None |

Markup hooks with no rule: `.shell`.

## 15.9 Checker settings

| Key | Value |
|---|---|
| `stack` | fixture |
| `markup extensions` | `.tsx`, `.ts`, `.html`, `.astro` |
| `markup roots` | `.`, `../index.html` |
| `theme key files` | `../index.html`, `utils/theme.ts` |
| `exempt roles` | `dark:fill-strong` |
| `!important files` | `base/_base.scss`, `utilities/_helpers.scss` |
'''

# (name, text to replace, replacement, rule); each must make the checker report that rule.
PROFILE_CASES = [
    ('profile lists a missing file', '_widget.scss main.scss', '_widget.scss _ghost.scss main.scss', '15.7'),
    ('profile token value', '`$small-screen` 768px', '`$small-screen` 800px', '15.7'),
    ('profile role value', '| `link` | Links | primary-mild `#006cb2`', '| `link` | Links | primary-mild `#006cb3`', '15.7'),
    ('profile contrast value', '14.77, 5.68, 5.09', '14.77, 5.68, 6.09', '15.7'),
    ('profile weaker than the core minimum', '| `focus`, `border-strong`, `fill-strong` | 3 |',
     '| `focus`, `border-strong`, `fill-strong` | 2 |', '15.7'),
    ('profile registry class', '`.widget__title`, `.widget__note`', '`.widget__title`, `.widget__ghost`, `.widget__note`', '15.7'),
    ('profile unlisted class', '`.widget__note`, `.widget__note--high`', '`.widget__note`', '15.7'),
    ('profile 12.2 file', '`Widget.tsx` | `.widget`', '`Ghost.tsx` | `.widget`', '15.7'),
    ('profile hook removed', 'Markup hooks with no rule: `.shell`.', 'Markup hooks with no rule: none.', '4.1.4'),
    ('profile theme key file missing', '`utils/theme.ts` |', '`utils/ghost.ts` |', '3.4.2'),
]


def build_tree(work, name, files=None):
    """Write the fixture tree under <work>/<name>/src and its profile beside it; return the src path."""
    root = os.path.join(work, name, 'src')
    for rel_path, text in (files or FIXTURE).items():
        path = os.path.normpath(os.path.join(root, rel_path))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w').write(text)
    open(profile_of(root), 'w').write(PROFILE_FIXTURE)
    return root


def profile_of(root):
    """Path of the fixture profile that build_tree writes beside src."""
    return os.path.join(os.path.dirname(root), 'profile.md')


def edit_file(root, edit):
    """Apply one ('append'|'replace'|'create'|'delete', path, ...) edit under root."""
    path = os.path.normpath(os.path.join(root, edit[1]))
    if edit[0] == 'append':
        open(path, 'a').write(edit[2])
    elif edit[0] == 'replace':
        text = open(path).read()
        assert edit[2] in text, f'{edit[2]!r} not in {edit[1]}'
        open(path, 'w').write(text.replace(edit[2], edit[3], 1))
    elif edit[0] == 'create':
        open(path, 'w').write(edit[2])
    elif edit[0] == 'delete':
        os.remove(path)


def self_test():
    """Rule 15.6: the fixture tree is clean and every case triggers its rule."""
    failures, total = 0, 0
    work = tempfile.mkdtemp()

    def report(ok, label):
        nonlocal failures, total
        total += 1
        failures += not ok
        print(f'{"PASS" if ok else "FAIL"}  {label}')

    def check(root):
        return run(root, profile_of(root))[0]

    try:
        rep = check(build_tree(work, 'clean'))
        report(not rep.errors and not rep.warnings, 'clean fixture reports nothing')
        for line in rep.errors + rep.warnings:
            print('      ', line)

        for i, (name, rule, edits) in enumerate(CASES):
            root = build_tree(work, f'case{i}')
            for edit in edits:
                edit_file(root, edit)
            try:
                hit = rule in check(root).hit()
            except SystemExit:
                hit = rule == '1.1.1'
            report(hit, f'[{rule}] {name}')

        root = build_tree(work, 'exempt')
        edit_file(root, ('replace', T, '  --fill-strong: #{color(gray, mild)};', '  --fill-strong: #{color(gray, mid)};'))
        report('3.5.1' not in check(root).hit(), '[3.5.1] dark fill-strong is exempt when the profile lists it (3.5.3)')
        root = build_tree(work, 'exempt-off')
        edit_file(root, ('replace', T, '  --fill-strong: #{color(gray, mild)};', '  --fill-strong: #{color(gray, mid)};'))
        text = open(profile_of(root)).read()
        open(profile_of(root), 'w').write(text.replace('`dark:fill-strong`', 'none', 1))
        report('3.5.1' in check(root).hit(), '[3.5.1] the same role is reported once the profile stops listing it')
        root = build_tree(work, 'exempt-other')
        edit_file(root, ('replace', T, '  --focus: #{color(primary, light)};', '  --focus: #{color(gray, dark)};'))
        report('3.5.1' in check(root).hit(), '[3.5.1] another dark role below its threshold is reported')

        root = build_tree(work, 'prefix')
        edit_file(root, ('replace', X, '`widget__note widget__note--${tone}`', "'widget__note'"))
        report('4.1.4' in check(root).hit(), '[4.1.4] a modifier rule is unused once the template prefix is gone')

        root = build_tree(work, 'noprofile')
        try:
            run(root, os.path.join(work, 'missing.md'))
            stopped = False
        except SystemExit:
            stopped = True
        report(stopped, '[16.2] a missing profile file stops with a message, not a traceback')

        root = build_tree(work, 'noprofile-section')
        text = open(profile_of(root)).read()
        open(profile_of(root), 'w').write(text.replace('## 12.3 Components and hooks', '## 12.3 Other', 1))
        try:
            check(root)
            stopped = False
        except SystemExit:
            stopped = True
        report(stopped, '[16.2] a profile without a required section stops with a message')

        root = build_tree(work, 'onekeyfile')
        text = open(profile_of(root)).read()
        open(profile_of(root), 'w').write(text.replace('`../index.html`, `utils/theme.ts`', '`utils/theme.ts`', 1))
        try:
            check(root)
            stopped = False
        except SystemExit:
            stopped = True
        report(stopped, '[16.3] a profile that lists one theme key file stops with a message')

        root = build_tree(work, 'nosetting')
        text = open(profile_of(root)).read()
        open(profile_of(root), 'w').write(text.replace('| `exempt roles` | `dark:fill-strong` |\n', '', 1))
        try:
            check(root)
            stopped = False
        except SystemExit:
            stopped = True
        report(stopped, '[16.3] a profile without a §15.9 row stops with a message')

        root = build_tree(work, 'profile')
        report(not check(root).errors, 'clean fixture matches its profile fixture')
        for name, old, new, rule in PROFILE_CASES:
            assert old in PROFILE_FIXTURE, f'{name}: {old!r} not in profile fixture'
            open(profile_of(root), 'w').write(PROFILE_FIXTURE.replace(old, new, 1))
            report(rule in check(root).hit(), f'[{rule}] {name}')
    finally:
        shutil.rmtree(work)
    covered = {c[1] for c in CASES} | {c[3] for c in PROFILE_CASES} | {'3.5.1', '16.2', '16.3'}
    print(f'\n{total - failures} of {total} fixtures passed; {len(covered)} rule IDs covered')
    return failures


def main():
    ap = argparse.ArgumentParser(description='Static checks for src/styles.')
    ap.add_argument('src', nargs='?', default=os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')))
    ap.add_argument('--profile', help="the site's profile (guide §16); required unless --self-test")
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        sys.exit(1 if self_test() else 0)
    if not args.profile:
        ap.error('--profile is required (guide 15.2)')
    rep, p = run(args.src, args.profile)
    print_report(rep, p)
    sys.exit(1 if rep.errors else 0)


if __name__ == '__main__':
    main()
