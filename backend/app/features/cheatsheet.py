import re
import uuid
from typing import Dict, List, Set
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.engine import get_db
from app.db.models import User, Document, StudyNote, CheatSheet
from app.deps import get_current_user
from app.math.validator import validate_math_text

router = APIRouter(tags=["cheatsheet"])

COMMON_CBSE_CONSTANTS = [
    ("Permittivity of Free Space (\\varepsilon_0)", "8.854 \\times 10^{-12}", "\\mathrm{C^2 N^{-1} m^{-2}}"),
    ("Coulomb Constant (\\frac{1}{4\\pi\\varepsilon_0})", "9 \\times 10^9", "\\mathrm{N\\cdot m^2 C^{-2}}"),
    ("Elementary Charge (e)", "1.602 \\times 10^{-19}", "\\mathrm{C}"),
    ("Mass of Electron (m_e)", "9.109 \\times 10^{-31}", "\\mathrm{kg}"),
    ("Planck Constant (h)", "6.626 \\times 10^{-34}", "\\mathrm{J\\cdot s}"),
    ("Speed of Light (c)", "3 \\times 10^8", "\\mathrm{m/s}"),
    ("Universal Gas Constant (R)", "8.314", "\\mathrm{J\\cdot K^{-1} mol^{-1}}"),
    ("Faraday Constant (F)", "96485", "\\mathrm{C/mol}")
]

@router.post("/documents/{doc_id}/cheatsheet")
async def generate_cheatsheet(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    stmt = select(Document).where(Document.id == d_uuid, Document.user_id == user.id)
    doc = (await db.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Load all study notes for this document
    notes_stmt = select(StudyNote).where(StudyNote.document_id == d_uuid, StudyNote.user_id == user.id)
    notes = (await db.execute(notes_stmt)).scalars().all()

    # Extract all formula markdown tables or math spans from the notes
    formula_entries = []
    seen_latex: Set[str] = set()

    for n in notes:
        # Match table rows or equations
        for line in n.content_md.split("\n"):
            if "|" in line and "$" in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2 and not line.startswith("| :---"):
                    name = parts[0].replace("*", "")
                    eq = parts[1]
                    unit = parts[3] if len(parts) > 3 else "-"
                    canonical = re.sub(r'\s+', '', eq)
                    if canonical not in seen_latex and len(name) < 50:
                        seen_latex.add(canonical)
                        formula_entries.append((name, eq, unit))

    # If notes didn't have markdown table rows, extract standard equations
    if not formula_entries:
        formula_entries = [
            ("Coulomb's Law", "$F = \\frac{1}{4\\pi\\varepsilon_0}\\frac{q_1 q_2}{r^2}$", "$\\mathrm{N}$"),
            ("Electric Field Intensity", "$\\vec{E} = \\frac{\\vec{F}}{q_0}$", "$\\mathrm{N/C}$"),
            ("Dipole Moment", "$p = 2aq$", "$\\mathrm{C\\cdot m}$"),
            ("Axial Field of Dipole", "$E_{axial} = \\frac{2p}{4\\pi\\varepsilon_0 r^3}$", "$\\mathrm{N/C}$"),
            ("Torque on Dipole", "$\\vec{\\tau} = \\vec{p} \\times \\vec{E}$", "$\\mathrm{N\\cdot m}$"),
            ("Gauss's Law", "$\\oint \\vec{E} \\cdot d\\vec{A} = \\frac{q_{enc}}{\\varepsilon_0}$", "$\\mathrm{N\\cdot m^2/C}$"),
            ("Capacitance (Parallel Plate)", "$C = \\frac{\\varepsilon_0 A}{d}$", "$\\mathrm{F}$"),
            ("Energy Stored in Capacitor", "$U = \\frac{1}{2}CV^2 = \\frac{Q^2}{2C}$", "$\\mathrm{J}$")
        ]

    lines = [
        f"# {doc.title}: Rapid Revision Cheat Sheet\n",
        "> **Notice:** High-yield reference sheet formatted for two-column quick board revision and A4 print layout.\n",
        "## I. Essential Formulas\n",
        "| Concept / Law | Formula | SI Unit |",
        "| :--- | :--- | :--- |"
    ]

    for name, eq, unit in formula_entries:
        lines.append(f"| **{name}** | {eq} | {unit} |")

    lines.append("\n## II. Standard Board Constants\n")
    lines.append("| Constant Name | Symbol & Value | SI Unit |")
    lines.append("| :--- | :--- | :--- |")
    for c_name, c_val, c_unit in COMMON_CBSE_CONSTANTS:
        lines.append(f"| {c_name} | ${c_val}$ | ${c_unit}$ |")

    content_md = "\n".join(lines)
    ok, errs, _ = validate_math_text(content_md)

    cs = CheatSheet(
        id=uuid.uuid4(),
        user_id=user.id,
        document_id=doc.id,
        title=f"{doc.title} - Cheat Sheet",
        content_md=content_md,
        formula_count=len(formula_entries),
        math_invalid=not ok
    )
    db.add(cs)
    await db.commit()

    return {
        "id": str(cs.id),
        "document_id": str(doc.id),
        "title": cs.title,
        "formula_count": cs.formula_count,
        "math_invalid": cs.math_invalid
    }

@router.get("/documents/{doc_id}/cheatsheet")
async def get_cheatsheet(
    doc_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:
        d_uuid = uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")

    stmt = select(CheatSheet).where(
        CheatSheet.document_id == d_uuid,
        CheatSheet.user_id == user.id
    ).order_by(CheatSheet.created_at.desc())
    
    cs = (await db.execute(stmt)).scalars().first()
    if not cs:
        raise HTTPException(status_code=404, detail="Cheat sheet not found for this document")

    return {
        "id": str(cs.id),
        "title": cs.title,
        "content_md": cs.content_md,
        "formula_count": cs.formula_count,
        "math_invalid": cs.math_invalid,
        "created_at": cs.created_at.isoformat()
    }
