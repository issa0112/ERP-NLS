from datetime import date

from django.db import models, transaction

from .models import Invoice, InvoiceLine, TariffRule, TransportOrder


def _build_invoice_number(order_id: int) -> str:
    today = date.today().strftime("%Y%m%d")
    return f"INV-{today}-{order_id}"


@transaction.atomic
def _find_tariff(order, reference_date):
    if not order.contract:
        return None
    rules = (
        TariffRule.objects.filter(contract=order.contract)
        .filter(effectif_du__lte=reference_date)
        .order_by("-effectif_du")
    )
    if order.fuel_type:
        rules = rules.filter(fuel_type=order.fuel_type)
    rules = rules.filter(models.Q(effectif_au__isnull=True) | models.Q(effectif_au__gte=reference_date))
    return rules.first()


def _build_pricing(order, delivery, tariff):
    if not tariff:
        return 0, 0, "Transport carburant - Ordre {ref} (tarif à définir)"

    if tariff.prix_par_litre:
        quantite = delivery.quantite_livree_litres or 0
        prix_unitaire = tariff.prix_par_litre
        desc = "Transport carburant - Ordre {ref} ({prix}/L)"
        return quantite, prix_unitaire, desc

    if tariff.prix_par_km and order.distance_km:
        quantite = order.distance_km
        prix_unitaire = tariff.prix_par_km
        desc = "Transport carburant - Ordre {ref} ({prix}/km)"
        return quantite, prix_unitaire, desc

    return 0, 0, "Transport carburant - Ordre {ref} (tarif incomplet)"


def create_or_update_invoice_for_delivery(delivery):
    order = delivery.ordre
    if not order:
        return None

    numero = _build_invoice_number(order.id)
    invoice, created = Invoice.objects.get_or_create(
        numero=numero,
        defaults={
            "client": order.client,
            "emis_le": date.today(),
            "statut": Invoice.BROUILLON,
        },
    )

    if created:
        # Reset total for new invoice.
        invoice.total = 0
        invoice.save(update_fields=["total"])

    # Avoid duplicate lines for the same delivery/order.
    existing = (
        InvoiceLine.objects.filter(invoice=invoice, order=order, description__icontains=delivery.ordre.reference)
        .first()
    )
    if existing:
        return invoice

    tariff = _find_tariff(order, delivery.livre_le.date() if delivery.livre_le else date.today())
    quantite, prix_unitaire, desc_template = _build_pricing(order, delivery, tariff)
    description = desc_template.format(ref=order.reference, prix=prix_unitaire)
    InvoiceLine.objects.create(
        invoice=invoice,
        order=order,
        fuel_type=order.fuel_type,
        description=description,
        quantite=quantite,
        prix_unitaire=prix_unitaire,
    )

    # Recalculate total
    total = 0
    for line in invoice.lignes.all():
        total += line.quantite * line.prix_unitaire
    invoice.total = total
    invoice.save(update_fields=["total"])
    return invoice
