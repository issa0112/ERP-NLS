from datetime import date
from decimal import Decimal


def simple_pdf(title, lines):
    # Minimal PDF generator for plain text documents (no external deps).
    content = []
    content.append(f"BT /F1 16 Tf 50 780 Td ({_escape(title)}) Tj ET")
    y = 750
    for line in lines:
        content.append(f"BT /F1 11 Tf 50 {y} Td ({_escape(line)}) Tj ET")
        y -= 16
        if y < 60:
            break

    stream = "\n".join(content)
    objects = []
    objects.append("1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj")
    objects.append("2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj")
    objects.append(
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj"
    )
    objects.append("4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj")
    objects.append(f"5 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj")

    xref_positions = []
    pdf = "%PDF-1.4\n"
    for obj in objects:
        xref_positions.append(len(pdf))
        pdf += obj + "\n"

    xref_start = len(pdf)
    pdf += "xref\n0 {0}\n0000000000 65535 f \n".format(len(objects) + 1)
    for pos in xref_positions:
        pdf += f"{pos:010d} 00000 n \n"
    pdf += (
        "trailer << /Size {0} /Root 1 0 R >>\nstartxref\n{1}\n%%EOF".format(len(objects) + 1, xref_start)
    )
    return pdf.encode("latin-1")


def _escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_invoice_lines(invoice, company, vat_rate, currency):
    vat_rate = Decimal(str(vat_rate))
    subtotal = Decimal("0")
    for line in invoice.lignes.all():
        subtotal += line.quantite * line.prix_unitaire
    tva = (subtotal * vat_rate).quantize(Decimal("0.01"))
    total_ttc = subtotal + tva

    lines = [
        f"Date: {date.today().strftime('%Y-%m-%d')}",
        f"Logo: {company.get('logo_text', '')}",
        f"Société: {company.get('name', '')}",
        f"Adresse: {company.get('address', '')}",
        f"NIF: {company.get('nif', '')}",
        f"Téléphone: {company.get('phone', '')}",
        f"Email: {company.get('email', '')}",
        f"Client: {invoice.client}",
        f"Statut: {invoice.get_statut_display()}",
        "",
        "Lignes:",
    ]
    for line in invoice.lignes.all():
        total = line.quantite * line.prix_unitaire
        lines.append(f"- {line.description} | {line.quantite} x {line.prix_unitaire} = {total} {currency}")
    lines.append("")
    lines.append(f"Sous-total: {subtotal} {currency}")
    lines.append(f"TVA ({vat_rate * 100}%): {tva} {currency}")
    lines.append(f"TOTAL TTC: {total_ttc} {currency}")
    lines.append("")
    lines.append("Signature client: ________________________")
    lines.append("Signature société: _______________________")
    return lines


def build_salary_lines(salary, company, currency):
    lines = [
        f"Date: {date.today().strftime('%Y-%m-%d')}",
        f"Logo: {company.get('logo_text', '')}",
        f"Société: {company.get('name', '')}",
        f"Adresse: {company.get('address', '')}",
        f"NIF: {company.get('nif', '')}",
        f"Téléphone: {company.get('phone', '')}",
        f"Email: {company.get('email', '')}",
        "",
        f"Employé: {salary.employee}",
        f"Période: {salary.periode_debut} -> {salary.periode_fin}",
        f"Statut: {salary.get_statut_display()}",
        "",
        f"Salaire de base: {salary.salaire_base} {currency}",
        f"Primes: {salary.primes} {currency}",
        f"Déductions: {salary.deductions} {currency}",
    ]
    if salary.contributions.exists():
        lines.append("Cotisations:")
        for contrib in salary.contributions.all():
            lines.append(f"- {contrib.contribution_type}: {contrib.montant} {currency}")
    lines.append("")
    lines.append(f"Net à payer: {salary.net} {currency}")
    lines.append("")
    lines.append("Signature employé: ________________________")
    lines.append("Signature société: _______________________")
    return lines
