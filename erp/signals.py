from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ContributionType, DeliveryNote, SalaryContribution, SalaryPayment
from .services import create_or_update_invoice_for_delivery


@receiver(post_save, sender=DeliveryNote)
def auto_invoice_on_delivery(sender, instance, created, **kwargs):
    if not created:
        return
    create_or_update_invoice_for_delivery(instance)


@receiver(post_save, sender=SalaryPayment)
def auto_salary_contributions(sender, instance, created, **kwargs):
    # Auto-create contributions based on active types and salary base.
    salary = instance
    active_types = ContributionType.objects.filter(actif=True)
    for ctype in active_types:
        montant = None
        if ctype.taux_pourcent is not None:
            montant = (salary.salaire_base * ctype.taux_pourcent) / 100
        elif ctype.montant_fixe is not None:
            montant = ctype.montant_fixe
        if montant is None:
            continue
        contribution, was_created = SalaryContribution.objects.get_or_create(
            salary=salary,
            contribution_type=ctype,
            defaults={"montant": montant, "auto_generated": True},
        )
        if not was_created and contribution.auto_generated:
            contribution.montant = montant
            contribution.save(update_fields=["montant"])
