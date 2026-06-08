"""Bank-format report generation.

Assembles a valuation's answers into the bank's heading structure (via
:class:`masters.models.ReportSetup`), renders an HTML template to PDF, stores it
in S3, and returns ``(key, presigned_url)``. WeasyPrint is preferred; if its
system libraries are unavailable we fall back to a minimal reportlab PDF so the
endpoint always produces a file.
"""

from __future__ import annotations

import logging

from django.template.loader import render_to_string

from masters.models import ReportSetup
from valuations import storage

logger = logging.getLogger("omen.ai")


def _assemble_sections(valuation) -> list[dict]:
    """Group the valuation's answers under the bank's report headings.

    Falls back to a single "All answers" section when no ReportSetup mapping
    exists for the case (e.g. early demo data).
    """
    wo = valuation.work_order
    answers = {a.question_id: a for a in valuation.answers.select_related("question").all()}

    setups = (
        ReportSetup.objects.filter(bank=wo.bank, service_type=wo.service_type)
        .select_related("heading", "question")
        .order_by("heading__sequence", "sequence")
    )

    if not setups.exists():
        rows = [
            {"label": a.question.text, "value": a.value, "confidence": a.confidence}
            for a in answers.values()
        ]
        return [{"heading": "All answers", "rows": rows}]

    grouped: dict[str, dict] = {}
    for setup in setups:
        bucket = grouped.setdefault(
            setup.heading_id,
            {"heading": setup.heading.title, "sequence": setup.heading.sequence, "rows": []},
        )
        ans = answers.get(setup.question_id)
        bucket["rows"].append(
            {
                "label": setup.question.text,
                "value": ans.value if ans else None,
                "confidence": ans.confidence if ans else "red",
            }
        )
    return sorted(grouped.values(), key=lambda s: s["sequence"])


def _render_pdf_bytes(html: str) -> bytes:
    """Render HTML to PDF bytes, with a reportlab fallback."""
    try:
        from weasyprint import HTML

        return HTML(string=html).write_pdf()
    except Exception:  # pragma: no cover - depends on system libs
        logger.warning("WeasyPrint unavailable; falling back to reportlab.")
        import io
        import re

        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        pdf = canvas.Canvas(buf, pagesize=A4)
        text = pdf.beginText(40, 800)
        plain = re.sub(r"<[^>]+>", " ", html)
        for line in plain.split("\n"):
            for chunk in (line[i : i + 100] for i in range(0, len(line) or 1, 100)):
                text.textLine(chunk.strip()[:100])
        pdf.drawText(text)
        pdf.showPage()
        pdf.save()
        return buf.getvalue()


def render_valuation_pdf(valuation) -> tuple[str, str]:
    """Render and store the report PDF. Returns ``(s3_key, presigned_url)``."""
    sections = _assemble_sections(valuation)
    html = render_to_string(
        "reports/valuation_report.html",
        {"valuation": valuation, "sections": sections},
    )
    pdf_bytes = _render_pdf_bytes(html)
    key = f"valuations/{valuation.id}/report/valuation_report.pdf"
    storage.put_bytes(key, pdf_bytes, mime="application/pdf")
    return key, storage.presign_get(key)
