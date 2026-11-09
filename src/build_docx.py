"""Convert manuscript.md into a formatted Word document (.docx) with embedded
figures and native Word tables. Uses python-docx."""
import os, re
import _env
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

MD = os.path.join(_env.PROJECT, "manuscript.md")
OUT = os.path.join(_env.PROJECT, "manuscript.docx")
FIGDIR = os.path.join(_env.OUTPUTS, "figures")
FIG_FILES = {
    "0": ("fig0_workflow.png", 6.4),
    "1": ("fig1_europe_manning.png", 6.2),
    "2": ("fig2_national_boxplot.png", 4.8),
    "3": ("fig3_comparison.png", 6.2),
    "4": ("fig4_validation.png", 6.4),
    "A": ("figA_hydraulic.png", 6.4),
    "C": ("figC_confusion.png", 6.4),
    "D": ("figD_uncertainty.png", 6.4),
    "E": ("figE_greece.png", 5.2),
}

INLINE = re.compile(r"\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`")


def latex_to_text(s):
    """Light LaTeX -> readable Unicode for equations rendered as plain text."""
    s = re.sub(r"\\tag\{([^}]*)\}", r"    (\1)", s).replace("\\qquad", "    ").replace("\\quad", "   ")
    s = s.replace("\\tfrac", "\\frac").replace("\\dfrac", "\\frac")
    # resolve inner braces first so \frac arguments become brace-free
    s = re.sub(r"\\(?:text|mathrm|bar|overline|mathbf)\{([^{}]*)\}", r"\1", s)
    for _ in range(4):
        s = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", s)
        s = re.sub(r"_\{([^{}]*)\}", r"_(\1)", s)
    for _ in range(4):
        s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"sqrt(\1)", s)
    s = re.sub(r"\\big[lr]?|\\Big[lr]?", "", s)
    reps = {"\\sum": "Σ", "\\times": "×", "\\partial": "∂", "\\Delta": "Δ", "\\rho": "ρ",
            "\\sim": "~", "\\in": "∈", "\\dots": "…", "\\,": " ", "\\;": " ", "\\!": "",
            "\\left": "", "\\right": "", "\\cdot": "·", "{": "", "}": "", "$": ""}
    for k, v in reps.items():
        s = s.replace(k, v)
    return s.strip()


def add_runs(p, text):
    text = text.replace(r"\*", "✱").replace("$", "")  # protect escaped *, drop $
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            p.add_run(text[pos:m.start()].replace("✱", "*"))
        b, i, c = m.group(1), m.group(2), m.group(3)
        if b is not None:
            r = p.add_run(b.replace("✱", "*")); r.bold = True
        elif i is not None:
            r = p.add_run(i.replace("✱", "*")); r.italic = True
        else:
            r = p.add_run(c.replace("✱", "*")); r.font.name = "Consolas"
        pos = m.end()
    if pos < len(text):
        p.add_run(text[pos:].replace("✱", "*"))


def flush_table(doc, rows):
    # rows: list of list[str]; first row is header, drop separator row
    rows = [r for r in rows if not re.match(r"^\s*:?-{2,}", r[0].strip())]
    if not rows:
        return
    ncol = len(rows[0])
    t = doc.add_table(rows=0, cols=ncol)
    t.style = "Light Grid Accent 1"
    for ri, cells in enumerate(rows):
        wr = t.add_row().cells
        for ci in range(ncol):
            txt = cells[ci].strip() if ci < len(cells) else ""
            wr[ci].text = ""
            p = wr[ci].paragraphs[0]
            add_runs(p, txt)
            for run in p.runs:
                run.font.size = Pt(8)
                if ri == 0:
                    run.bold = True
            if ci > 0:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph()


def main():
    doc = Document()
    # base style
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"; normal.font.size = Pt(11)

    lines = open(MD, encoding="utf-8").read().splitlines()
    table_buf = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            table_buf.append(cells)
            i += 1
            continue
        elif table_buf:
            flush_table(doc, table_buf); table_buf = []

        s = ln.strip()
        if not s:
            i += 1; continue
        if s == "---":
            i += 1; continue
        if s.startswith("$$"):
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(latex_to_text(s)); r.italic = True; r.font.name = "Cambria Math"
            i += 1; continue
        if s.startswith("# "):
            h = doc.add_heading(s[2:].strip(), level=0)
        elif s.startswith("## "):
            doc.add_heading(s[3:].strip(), level=1)
        elif s.startswith("### "):
            doc.add_heading(s[4:].strip(), level=2)
        elif s.startswith("#### "):
            doc.add_heading(s[5:].strip(), level=3)
        else:
            # figure caption -> embed image above caption
            mfig = re.match(r"\*\*Figure (\w)\.\*\*", s)
            if mfig and mfig.group(1) in FIG_FILES:
                fn, win = FIG_FILES[mfig.group(1)]
                fp = os.path.join(FIGDIR, fn)
                if os.path.exists(fp):
                    pim = doc.add_paragraph(); pim.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    pim.add_run().add_picture(fp, width=Inches(win))
            p = doc.add_paragraph()
            add_runs(p, s)
        i += 1
    if table_buf:
        flush_table(doc, table_buf)

    doc.save(OUT)
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
