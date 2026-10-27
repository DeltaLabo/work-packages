import os
from pathlib import Path

import pandas as pd
from pandas.errors import EmptyDataError
from pylatex import (
    Document,
    NoEscape,
    Package,
)
from pylatex.utils import escape_latex


ROOT = Path(__file__).resolve().parent.parent
DATA_CSV = ROOT / "data" / "work_packages.csv"
OUTPUT_PDF_DIR = ROOT / "output" / "pdf"
OUTPUT_TEX_DIR = ROOT / "output" / "tex"
TEC_LOGO = ROOT / "assets" / "images" / "logo.jpg"
DELTA_LOGO = ROOT / "assets" / "images" / "logo_pdf.png"

REQUIRED_FIELDS = [
    "id",
    "title",
    "description",
    "objectives",
    "tasks",
    "equipment",
    "deliverables",
    "work breakdown",
    "payment",
    "supervisor",
    "professor",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names for resilient matching."""
    normalized = {
        col: " ".join(str(col).strip().lower().split())
        for col in df.columns
    }
    return df.rename(columns=normalized)


def parse_args() -> object:
    import argparse
    parser = argparse.ArgumentParser(description="Generate a work package PDF from data/work_packages.csv.")
    parser.add_argument("id", nargs="?", help="Work package id to generate, for example 012026.")
    return parser.parse_args()


def load_row(csv_path: Path, work_package_id: str | None = None) -> dict:
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    try:
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding="latin-1", dtype=str, keep_default_na=False)
    except EmptyDataError as exc:
        raise ValueError(
            f"The CSV is empty: {csv_path}. Add headers and at least one row in data/work_packages.csv."
        ) from exc

    if df.empty:
        raise ValueError(
            f"The CSV is empty: {csv_path}. Add at least one row in data/work_packages.csv."
        )

    df = normalize_columns(df)
    missing = [field for field in REQUIRED_FIELDS if field not in df.columns]
    if missing:
        raise ValueError(
            "Missing required columns in data/work_packages.csv: "
            + ", ".join(missing)
        )

    if work_package_id:
        selected_rows = df[df["id"].astype(str).str.strip() == work_package_id.strip()]
        if selected_rows.empty:
            raise ValueError(f"Work package id not found in data/work_packages.csv: {work_package_id}")
        row = selected_rows.iloc[-1].to_dict()
    else:
        row = df.iloc[-1].to_dict()
    return {field: ("" if pd.isna(row[field]) else str(row[field])) for field in REQUIRED_FIELDS}


def build_header(doc: Document) -> None:
    tec_logo = os.path.relpath(TEC_LOGO, OUTPUT_TEX_DIR).replace('\\', '/') if TEC_LOGO.exists() else ''
    delta_logo = os.path.relpath(DELTA_LOGO, OUTPUT_TEX_DIR).replace('\\', '/') if DELTA_LOGO.exists() else ''
    header = rf"""
\begin{{minipage}}[c]{{0.24\textwidth}}
    \includegraphics[width=\linewidth]{{{tec_logo}}}
\end{{minipage}}
\begin{{minipage}}[c]{{0.50\textwidth}}
    \centering
    {{\Large\textbf{{Work Package Overview}}}}
\end{{minipage}}
\begin{{minipage}}[c]{{0.24\textwidth}}
    \raggedleft
    \includegraphics[width=0.62\linewidth]{{{delta_logo}}}
\end{{minipage}}
\vspace{{0.6cm}}
"""
    doc.append(NoEscape(header))


def as_items(text: str) -> list[str]:
    return [item.strip() for item in text.split(";") if item.strip()]


def build_bullets(doc: Document, title: str, values: list[str]) -> None:
    doc.append(NoEscape(rf"\textbf{{{escape_latex(title)}}}"))
    doc.append(NoEscape(r"\begin{itemize}[leftmargin=*,itemsep=2pt,topsep=0pt,parsep=0pt,partopsep=0pt]"))
    for value in values:
        doc.append(NoEscape(rf"\item {escape_latex(value)}"))
    doc.append(NoEscape(r"\end{itemize}"))


def build_content(doc: Document, data: dict) -> None:
    title = escape_latex(data["title"])
    opp_id = escape_latex(data["id"])
    description = escape_latex(data["description"])

    doc.append(NoEscape(rf"\begin{{center}}\LARGE\textbf{{{title}}}\\[2pt]\large [ID {opp_id}]\end{{center}}"))
    doc.append(NoEscape(r"\vspace{4pt}"))
    doc.append(NoEscape(rf"\noindent {description}"))
    doc.append(NoEscape(r"\vspace{6pt}"))

    objectives = as_items(data["objectives"])
    tasks = as_items(data["tasks"])
    equipment = as_items(data["equipment"])
    deliverables = as_items(data["deliverables"])
    work_breakdown = as_items(data["work breakdown"])
    payment = data["payment"].strip()
    supervisor = data["supervisor"].strip()
    professor = data["professor"].strip()

    doc.append(NoEscape(r"\vspace{4pt}\hrule\vspace{8pt}"))

    if objectives:
        build_bullets(doc, "Objectives", objectives)
    if tasks:
        build_bullets(doc, "Tasks", tasks)
    if equipment:
        build_bullets(doc, "Equipment", equipment)
    if deliverables:
        build_bullets(doc, "Deliverables", deliverables)
    if work_breakdown:
        build_bullets(doc, "Work Breakdown", work_breakdown)

    doc.append(NoEscape(r"\vspace{6pt}\hrule\vspace{8pt}"))
    doc.append(NoEscape(rf"\textbf{{Payment:}} {escape_latex(payment)}\\[4pt]"))
    doc.append(NoEscape(rf"\textbf{{Supervisor:}} {escape_latex(supervisor)}\\[2pt]"))
    doc.append(NoEscape(rf"\textbf{{Professor:}} {escape_latex(professor)}"))


def generate_pdf(work_package_id: str | None = None) -> Path:
    OUTPUT_PDF_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_TEX_DIR.mkdir(parents=True, exist_ok=True)
    latest = load_row(DATA_CSV, work_package_id)

    doc = Document(
        documentclass="article",
        geometry_options={
            "margin": "1.8cm",
            "letterpaper": True,
        },
    )

    doc.packages.append(Package("graphicx"))
    doc.packages.append(Package("xcolor"))
    doc.packages.append(Package("array"))
    doc.packages.append(Package("enumitem"))
    doc.packages.append(Package("parskip"))

    build_header(doc)
    build_content(doc, latest)

    output_id = latest["id"].strip()
    if not output_id:
        raise ValueError("The selected work package row is missing an id.")
    safe_output_id = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in output_id)

    pdf_stem = OUTPUT_PDF_DIR / safe_output_id
    tex_path = (OUTPUT_TEX_DIR / safe_output_id).with_suffix(".tex")
    doc.generate_pdf(str(pdf_stem), clean_tex=False, compiler="lualatex")
    generated_tex = pdf_stem.with_suffix(".tex")
    if generated_tex.exists():
        generated_tex.replace(tex_path)
    tex_path.write_text(doc.dumps(), encoding="utf-8")
    return pdf_stem.with_suffix(".pdf")


if __name__ == "__main__":
    try:
        args = parse_args()
        pdf_path = generate_pdf(args.id)
        print(f"PDF generated: {pdf_path}")
    except Exception as exc:
        raise SystemExit(f"Error: {exc}")

