"""Minimal S-expression reader/writer for KiCad files."""
import re

class Sym(str):
    """A bare symbol token (unquoted)."""
    __slots__ = ()

_tok = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))', re.S)

def parse(text):
    stack = [[]]
    pos = 0
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            break
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            lst = stack.pop()
            stack[-1].append(lst)
        elif m.group(3):
            s = m.group(3)[1:-1].replace('\\"', '"').replace("\\\\", "\\")
            stack[-1].append(s)
        elif m.group(4):
            stack[-1].append(Sym(m.group(4)))
    return stack[0]

def _fmt(x):
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int,)):
        return str(x)
    if isinstance(x, float):
        s = f"{x:.6f}".rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    if isinstance(x, str):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
    raise TypeError(type(x))

def dumps(node, indent=0):
    """Serialise a nested list preserving child order (KiCad parsers are order-sensitive)."""
    if not isinstance(node, list):
        return _fmt(node)
    if all(not isinstance(c, list) for c in node):
        return "(" + " ".join(_fmt(c) for c in node) + ")"
    pad = "  " * (indent + 1)
    out = "(" + _fmt(node[0]) if node else "("
    for c in node[1:]:
        if isinstance(c, list):
            out += "\n" + pad + dumps(c, indent + 1)
        else:
            out += " " + _fmt(c)
    return out + ")"

def find(node, key):
    """First child list whose head == key."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None

def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]

def S(*args):
    return list(args)

def sym(s):
    return Sym(s)
