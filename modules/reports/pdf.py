import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from datetime import datetime

DISCLAIMER = (
    "This document is a DEMO. No real patient data. Not for clinical use.\n"
    "Results are simulated and for portfolio demonstration only."
)

def generate_report_pdf(out_dir: str, embryo_id: str, detail: dict) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"embryo_{embryo_id}_report.pdf")
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter

    # Watermark
    c.saveState()
    c.setFont("Helvetica-Bold", 50)
    c.setFillGray(0.90, 0.5)
    c.translate(width/2, height/2)
    c.rotate(30)
    c.drawCentredString(0, 0, "DEMO – NOT PHI")
    c.restoreState()

    # Header
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1*inch, 10*inch, "Embryo Risk Report (Demo)")
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, 9.75*inch, f"Embryo ID: {embryo_id}")
    c.drawString(1*inch, 9.55*inch, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    # Polygenic
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, 9.2*inch, "Polygenic Risk Estimates:")
    c.setFont("Helvetica", 11)
    y = 9.0*inch
    for cond, pct in detail.get("polygenic", {}).items():
        c.drawString(1.2*inch, y, f"- {cond}: {pct}%")
        y -= 0.2*inch

    # Monogenic
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, y - 0.2*inch, "Monogenic Findings:")
    y -= 0.4*inch
    c.setFont("Helvetica", 11)
    for gene, status in detail.get("monogenic", {}).items():
        c.drawString(1.2*inch, y, f"- {gene}: {status}")
        y -= 0.2*inch

    # Overall
    y -= 0.2*inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1*inch, y, f"Overall Score: {detail.get('overall_score', 'N/A')}/100")
    y -= 0.4*inch

    # Disclaimer + fake signature
    c.setFont("Helvetica", 9)
    for line in DISCLAIMER.split("\n"):
        c.drawString(1*inch, y, line); y -= 0.18*inch
    y -= 0.4*inch
    c.setFont("Helvetica-Oblique", 11)
    c.drawString(1*inch, y, "Reviewed by: Dr. Jane Doe, PhD (Demo)")

    c.showPage(); c.save()
    return path
