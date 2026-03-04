from django.contrib import admin

from .models import (
    Apprentice,
    Client,
    ContributionType,
    Contract,
    CreditNote,
    DeliveryNote,
    Driver,
    DriverCertification,
    Employee,
    Expense,
    FuelBatch,
    FuelMeasurement,
    FuelType,
    GaragePart,
    GarageServiceType,
    GarageWorkOrder,
    GarageWorkOrderDocument,
    Incident,
    Invoice,
    InvoiceLine,
    LeaveRequest,
    Payment,
    SalaryContribution,
    SalaryPayment,
    Site,
    Tanker,
    TankerCompartment,
    TariffRule,
    TransportOrder,
    Trip,
    Vehicle,
)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("nom", "code", "site_type", "ville", "actif")
    search_fields = ("nom", "code", "ville")
    list_filter = ("site_type", "actif")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nom", "client_type", "telephone", "ville", "actif")
    search_fields = ("nom", "nif", "telephone", "email")
    list_filter = ("client_type", "actif")


@admin.register(FuelType)
class FuelTypeAdmin(admin.ModelAdmin):
    list_display = ("nom", "code")
    search_fields = ("nom", "code")


@admin.register(FuelBatch)
class FuelBatchAdmin(admin.ModelAdmin):
    list_display = ("fuel_type", "batch_number", "quantite_litres", "recu_le", "site")
    search_fields = ("batch_number",)
    list_filter = ("fuel_type", "site")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "immatriculation",
        "marque",
        "modele",
        "annee_fabrication",
        "assurance",
        "statut",
        "gps_device_id",
    )
    search_fields = ("immatriculation", "marque", "modele", "assurance", "gps_device_id")
    list_filter = ("statut",)


@admin.register(Tanker)
class TankerAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "adr_expires_at", "actif")
    list_filter = ("actif",)


@admin.register(TankerCompartment)
class TankerCompartmentAdmin(admin.ModelAdmin):
    list_display = ("tanker", "numero", "capacite_litres")
    list_filter = ("tanker",)


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = (
        "prenom",
        "nom",
        "telephone",
        "numero_permis",
        "permis_expire_le",
        "statut",
    )
    search_fields = ("prenom", "nom", "telephone", "numero_permis")
    list_filter = ("statut",)


@admin.register(Apprentice)
class ApprenticeAdmin(admin.ModelAdmin):
    list_display = ("prenom", "nom", "chauffeur", "telephone", "date_affectation", "statut")
    search_fields = ("prenom", "nom", "telephone", "chauffeur__prenom", "chauffeur__nom")
    list_filter = ("statut", "chauffeur")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("prenom", "nom", "fonction", "departement", "telephone", "statut")
    search_fields = ("prenom", "nom", "fonction", "departement", "telephone", "email")
    list_filter = ("statut", "departement")


@admin.register(SalaryPayment)
class SalaryPaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "employee", "periode_debut", "periode_fin", "salaire_base", "statut")
    search_fields = ("reference", "employee__prenom", "employee__nom")
    list_filter = ("statut",)


@admin.register(ContributionType)
class ContributionTypeAdmin(admin.ModelAdmin):
    list_display = ("nom", "taux_pourcent", "montant_fixe", "actif")
    list_filter = ("actif",)


@admin.register(SalaryContribution)
class SalaryContributionAdmin(admin.ModelAdmin):
    list_display = ("salary", "contribution_type", "montant", "auto_generated")
    list_filter = ("contribution_type", "auto_generated")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "type_absence", "date_debut", "date_fin", "statut")
    list_filter = ("type_absence", "statut")


@admin.register(DriverCertification)
class DriverCertificationAdmin(admin.ModelAdmin):
    list_display = ("driver", "type_certification", "delivree_le", "expire_le")
    list_filter = ("type_certification",)


@admin.register(GarageServiceType)
class GarageServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "categorie", "interval_km", "interval_jours", "actif")
    search_fields = ("code", "nom")
    list_filter = ("categorie", "actif")


@admin.register(GaragePart)
class GaragePartAdmin(admin.ModelAdmin):
    list_display = ("reference", "designation", "categorie", "stock_actuel", "stock_min", "prix_unitaire", "actif")
    search_fields = ("reference", "designation", "categorie", "fournisseur")
    list_filter = ("actif", "categorie")


@admin.register(GarageWorkOrder)
class GarageWorkOrderAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "vehicle",
        "service_type",
        "statut",
        "priorite",
        "ouvert_le",
        "fin_reel",
        "qualite_validee",
    )
    search_fields = ("reference", "vehicle__immatriculation", "driver__prenom", "driver__nom")
    list_filter = ("statut", "priorite", "qualite_validee", "service_type")


@admin.register(GarageWorkOrderDocument)
class GarageWorkOrderDocumentAdmin(admin.ModelAdmin):
    list_display = ("workorder", "titre", "created_at")
    search_fields = ("workorder__reference", "titre")


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("reference", "client", "debut", "fin", "actif")
    search_fields = ("reference", "client__nom")
    list_filter = ("actif",)


@admin.register(TariffRule)
class TariffRuleAdmin(admin.ModelAdmin):
    list_display = ("contract", "fuel_type", "prix_par_litre", "prix_par_km", "effectif_du", "effectif_au")
    list_filter = ("contract", "fuel_type")


@admin.register(TransportOrder)
class TransportOrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "client", "fuel_type", "quantite_prevue_litres", "date_prevue", "statut")
    search_fields = ("reference", "client__nom")
    list_filter = ("statut", "fuel_type")


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("ordre", "vehicle", "driver", "depart_prevu", "arrivee_prevue", "statut")
    list_filter = ("statut",)


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(admin.ModelAdmin):
    list_display = ("ordre", "livre_le", "quantite_livree_litres", "ecart_litres")
    list_filter = ("livre_le",)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("trip", "type_incident", "date_incident", "severite")
    list_filter = ("severite",)


@admin.register(FuelMeasurement)
class FuelMeasurementAdmin(admin.ModelAdmin):
    list_display = ("trip", "compartment", "mesure_le", "niveau_litres", "source", "evenement")
    list_filter = ("source", "evenement")


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("numero", "client", "emis_le", "echeance_le", "statut", "total")
    search_fields = ("numero", "client__nom")
    list_filter = ("statut",)
    inlines = [InvoiceLineInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "montant", "paye_le", "methode")
    list_filter = ("methode",)


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = ("invoice", "montant", "raison", "emis_le")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("description", "categorie", "montant", "depense_le", "reference")
    list_filter = ("categorie",)
