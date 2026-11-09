"""LaTeX -> OMML, so the displayed equations are real Word equations.

Rendering an equation as plain text forces ASCII stand-ins: n_(best) for a
subscript, (a)/(b) for a fraction. Word has a native maths format (OMML), and
Office ships the MathML -> OMML stylesheet that converts into it, so the chain
is

    LaTeX  --latex2mathml-->  MathML  --MML2OMML.XSL-->  OMML

which gives stacked fractions and true sub- and superscripts with no "_", "^"
or "/" anywhere in the text.

Both dependencies are checked at import: if either is missing, `available()`
returns False and the caller falls back to the plain-text renderer.
"""
import os
import re
import glob

NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"

_XSL_CANDIDATES = [
    r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL",
    r"C:\Program Files (x86)\Microsoft Office\root\Office16\MML2OMML.XSL",
]
_transform = None
_convert = None
_why = ""


def _find_xsl():
    for p in _XSL_CANDIDATES:
        if os.path.exists(p):
            return p
    for pat in (r"C:\Program Files\Microsoft Office\root\Office*\MML2OMML.XSL",
                r"C:\Program Files (x86)\Microsoft Office\root\Office*\MML2OMML.XSL"):
        hit = glob.glob(pat)
        if hit:
            return hit[0]
    return None


def _init():
    global _transform, _convert, _why
    if _transform is not None or _why:
        return
    try:
        from lxml import etree
        import latex2mathml.converter as conv
    except ImportError as e:
        _why = "missing dependency: %s" % e
        return
    xsl = _find_xsl()
    if xsl is None:
        _why = "Office MML2OMML.XSL not found"
        return
    _transform = etree.XSLT(etree.parse(xsl))
    _convert = conv.convert


def available():
    _init()
    return _transform is not None


def why_unavailable():
    _init()
    return _why


# LaTeX the converter does not need to see
_STRIP = (
    (re.compile(r"\\tag\{([^}]*)\}"), ""),
    (re.compile(r"\\qquad"), r"\\quad"),
    (re.compile(r"\\!"), ""),
)


def split_tag(latex):
    """Return (latex without its \\tag, tag text or None)."""
    m = re.search(r"\\tag\{([^}]*)\}", latex)
    return re.sub(r"\\tag\{[^}]*\}", "", latex).strip(), (m.group(1) if m else None)


MML = "http://www.w3.org/1998/Math/MathML"
_CLOSE = {"(": ")", "[": "]", "{": "}"}


def _fence_pairs_to_mfenced(root):
    """Rewrite a \\left ... \\right pair into <mfenced>.

    latex2mathml emits the two delimiters as free-standing <mo fence="true">
    operators. The MathML-to-OMML stylesheet only recognises <mfenced>, so
    without this the brackets arrive in Word as ordinary characters that do
    not grow with their contents: a full-height fraction ends up beside a
    single-line parenthesis, which reads as a gap in the equation.
    """
    from lxml import etree
    changed = True
    while changed:
        changed = False
        for parent in list(root.iter()):
            kids = list(parent)
            for i, k in enumerate(kids):
                if etree.QName(k).localname != "mo":
                    continue
                if k.get("fence") != "true" or k.get("form") != "prefix":
                    continue
                opening = (k.text or "").strip()
                want = _CLOSE.get(opening)
                if want is None:
                    continue
                depth, j = 0, None
                for n in range(i + 1, len(kids)):
                    o = kids[n]
                    if etree.QName(o).localname != "mo" or o.get("fence") != "true":
                        continue
                    if o.get("form") == "prefix":
                        depth += 1
                    elif o.get("form") == "postfix":
                        if depth == 0 and (o.text or "").strip() == want:
                            j = n
                            break
                        depth -= 1
                if j is None:
                    continue
                fenced = etree.SubElement(parent, "{%s}mfenced" % MML)
                fenced.set("open", opening)
                fenced.set("close", want)
                row = etree.SubElement(fenced, "{%s}mrow" % MML)
                for o in kids[i + 1:j]:
                    row.append(o)
                parent.remove(kids[i])
                parent.remove(kids[j])
                parent.insert(i, fenced)
                changed = True
                break
            if changed:
                break
    return root


def to_omml(latex):
    """LaTeX string -> an lxml <m:oMath> element, or None if unavailable."""
    if not available():
        return None
    from lxml import etree
    body = latex.strip()
    if body.startswith("$$"):
        body = body.strip("$").strip()
    body, _tag = split_tag(body)
    for rx, sub in _STRIP:
        body = rx.sub(sub, body)
    mathml = _convert(body)
    doc = _fence_pairs_to_mfenced(etree.fromstring(mathml.encode("utf-8")))
    tree = _transform(doc)
    root = tree.getroot()
    if root is None:
        return None
    # the stylesheet returns <m:oMathPara> or <m:oMath>; we want the oMath
    if root.tag == "{%s}oMathPara" % NS_M:
        kids = root.findall("{%s}oMath" % NS_M)
        return kids[0] if kids else None
    return root
