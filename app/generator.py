from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas


def generate_certificate_pdf(
    output_path: Path,
    recipient_name: str,
    event_name: str,
    issue_date: str,
    certificate_id: str,
    custom_title: str | None = None,
) -> Path:
    """
    Renders an elegant, high-resolution vector PDF certificate based on
    a predefined professional landscape template using ReportLab.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Dimensions in landscape (792 x 612 pt)
    page_width, page_height = landscape(letter)

    c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))
    c.setTitle(f"Certificate - {recipient_name}")

    # Color Palette
    navy = colors.HexColor("#0f172a")        # Deep Slate Navy
    gold = colors.HexColor("#c29d38")        # Refined Gold
    gold_light = colors.HexColor("#fef3c7")  # Warm Light Accent
    slate_subtle = colors.HexColor("#475569") # Muted Charcoal
    border_gray = colors.HexColor("#e2e8f0")

    # --- Decorative Background & Borders ---
    # Outer Margin Box
    c.setStrokeColor(navy)
    c.setLineWidth(5)
    c.rect(28, 28, page_width - 56, page_height - 56)

    # Inner Gold Inset Box
    c.setStrokeColor(gold)
    c.setLineWidth(1.8)
    c.rect(36, 36, page_width - 72, page_height - 72)

    # Corner Accents (Gold corner brackets)
    corner_len = 24
    c.setLineWidth(3)
    c.setStrokeColor(gold)
    # Bottom Left
    c.line(42, 42, 42 + corner_len, 42)
    c.line(42, 42, 42, 42 + corner_len)
    # Bottom Right
    c.line(page_width - 42, 42, page_width - 42 - corner_len, 42)
    c.line(page_width - 42, 42, page_width - 42, 42 + corner_len)
    # Top Left
    c.line(42, page_height - 42, 42 + corner_len, page_height - 42)
    c.line(42, page_height - 42, 42, page_height - 42 - corner_len)
    # Top Right
    c.line(page_width - 42, page_height - 42, page_width - 42 - corner_len, page_height - 42)
    c.line(page_width - 42, page_height - 42, page_width - 42, page_height - 42 - corner_len)

    center_x = page_width / 2.0

    # --- Header Title ---
    c.setFillColor(gold)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(center_x, page_height - 88, "OFFICIAL CERTIFICATE OF ACHIEVEMENT")

    c.setStrokeColor(gold)
    c.setLineWidth(1)
    c.line(center_x - 140, page_height - 96, center_x + 140, page_height - 96)

    # --- Subtitle ---
    c.setFillColor(slate_subtle)
    c.setFont("Helvetica", 12)
    c.drawCentredString(center_x, page_height - 145, "THIS IS PROUDLY PRESENTED TO")

    # --- Recipient Name ---
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 32)
    c.drawCentredString(center_x, page_height - 200, recipient_name)

    # Subtle decorative line under name
    c.setStrokeColor(gold)
    c.setLineWidth(1.5)
    c.line(center_x - 180, page_height - 215, center_x + 180, page_height - 215)

    # Optional Custom Title / Role
    curr_y = page_height - 245
    if custom_title:
        c.setFillColor(gold)
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(center_x, curr_y, custom_title.upper())
        curr_y -= 25

    # --- Statement of Completion ---
    c.setFillColor(slate_subtle)
    c.setFont("Helvetica", 13)
    c.drawCentredString(center_x, curr_y, "for successfully participating in and completing")

    curr_y -= 40
    # --- Event / Course Name ---
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(center_x, curr_y, event_name)

    # --- Bottom Footer Section ---
    footer_y = 100

    # Left: Issue Date
    c.setStrokeColor(border_gray)
    c.setLineWidth(1)
    c.line(100, footer_y + 20, 260, footer_y + 20)
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(180, footer_y + 25, issue_date)
    c.setFillColor(slate_subtle)
    c.setFont("Helvetica", 10)
    c.drawCentredString(180, footer_y + 5, "DATE OF ISSUANCE")

    # Center: Certificate ID & Verification
    c.setFillColor(slate_subtle)
    c.setFont("Helvetica", 8)
    c.drawCentredString(center_x, footer_y + 10, f"Certificate ID: {certificate_id}")
    c.drawCentredString(center_x, footer_y - 2, "Verified by Bulk Certificate Generator")

    # Right: Signature line
    c.setStrokeColor(border_gray)
    c.setLineWidth(1)
    c.line(page_width - 260, footer_y + 20, page_width - 100, footer_y + 20)
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(page_width - 180, footer_y + 25, "Authorized Signatory")
    c.setFillColor(slate_subtle)
    c.setFont("Helvetica", 10)
    c.drawCentredString(page_width - 180, footer_y + 5, "DIRECTOR / CHAIR")

    c.showPage()
    c.save()
    return output_path
