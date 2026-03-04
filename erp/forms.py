from django import forms
from django.utils import timezone


class BaseModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field, forms.DateField) and not isinstance(field, forms.DateTimeField):
                field.widget = forms.DateInput(attrs={"type": "date"})
            elif isinstance(field, forms.DateTimeField):
                field.widget = forms.DateTimeInput(attrs={"type": "datetime-local"})

from .models import (
    Apprentice,
    Client,
    ContributionType,
    DeliveryNote,
    Driver,
    Employee,
    Expense,
    FuelType,
    GaragePart,
    GarageServiceType,
    GarageWorkOrder,
    GarageWorkOrderDocument,
    LeaveRequest,
    Invoice,
    SalaryContribution,
    SalaryPayment,
    Site,
    TransportOrder,
    Vehicle,
)


class ClientForm(BaseModelForm):
    class Meta:
        model = Client
        fields = [
            "nom",
            "client_type",
            "nif",
            "telephone",
            "email",
            "adresse",
            "ville",
            "actif",
        ]


class SiteForm(BaseModelForm):
    class Meta:
        model = Site
        fields = ["nom", "code", "site_type", "adresse", "ville", "pays", "actif"]


class FuelTypeForm(BaseModelForm):
    class Meta:
        model = FuelType
        fields = ["nom", "code"]


class VehicleForm(BaseModelForm):
    def clean(self):
        cleaned_data = super().clean()
        statut = cleaned_data.get("statut")
        motif = (cleaned_data.get("motif_hors_service") or "").strip()
        if statut == Vehicle.HORS_SERVICE and not motif:
            self.add_error("motif_hors_service", "Le motif est obligatoire si le camion est hors service.")
        return cleaned_data

    class Meta:
        model = Vehicle
        fields = [
            "immatriculation",
            "marque",
            "modele",
            "annee_fabrication",
            "capacite_litres",
            "assurance",
            "carte_grise_image",
            "gps_device_id",
            "statut",
            "motif_hors_service",
        ]
        widgets = {
            "carte_grise_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "motif_hors_service": forms.Textarea(attrs={"rows": 3}),
        }


class DriverForm(BaseModelForm):
    class Meta:
        model = Driver
        fields = [
            "user",
            "prenom",
            "nom",
            "telephone",
            "numero_permis",
            "permis_image",
            "permis_expire_le",
            "certificat_jaugeage_image",
            "cahier_transport",
            "date_embauche",
            "statut",
        ]
        widgets = {
            "permis_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "certificat_jaugeage_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
            "cahier_transport": forms.ClearableFileInput(attrs={"accept": ".pdf,image/*"}),
        }


class DriverQuickForm(BaseModelForm):
    class Meta:
        model = Driver
        fields = [
            "prenom",
            "nom",
            "telephone",
            "numero_permis",
            "permis_expire_le",
            "statut",
        ]


class ApprenticeForm(BaseModelForm):
    class Meta:
        model = Apprentice
        fields = [
            "chauffeur",
            "prenom",
            "nom",
            "telephone",
            "date_affectation",
            "statut",
        ]


class EmployeeForm(BaseModelForm):
    class Meta:
        model = Employee
        fields = [
            "user",
            "prenom",
            "nom",
            "fonction",
            "departement",
            "telephone",
            "email",
            "date_embauche",
            "statut",
        ]


class SalaryPaymentForm(BaseModelForm):
    class Meta:
        model = SalaryPayment
        fields = [
            "employee",
            "reference",
            "periode_debut",
            "periode_fin",
            "salaire_base",
            "primes",
            "deductions",
            "paye_le",
            "statut",
            "commentaire",
        ]


class ContributionTypeForm(BaseModelForm):
    class Meta:
        model = ContributionType
        fields = ["nom", "taux_pourcent", "montant_fixe", "actif"]


class SalaryContributionForm(BaseModelForm):
    class Meta:
        model = SalaryContribution
        fields = ["salary", "contribution_type", "montant", "commentaire", "auto_generated"]


class LeaveRequestForm(BaseModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["employee", "type_absence", "date_debut", "date_fin", "statut", "motif"]


class ExpenseForm(BaseModelForm):
    class Meta:
        model = Expense
        fields = ["categorie", "description", "montant", "depense_le", "reference", "commentaire"]


class TransportOrderForm(BaseModelForm):
    class Meta:
        model = TransportOrder
        fields = [
            "reference",
            "client",
            "contract",
            "fuel_type",
            "batch",
            "site_depart",
            "adresse_livraison",
            "quantite_prevue_litres",
            "distance_km",
            "date_prevue",
            "statut",
        ]
        labels = {
            "contract": "Contrat",
            "fuel_type": "Type de carburant",
            "batch": "Lot",
        }


class DeliveryNoteForm(BaseModelForm):
    class Meta:
        model = DeliveryNote
        fields = [
            "ordre",
            "trip",
            "livre_le",
            "quantite_livree_litres",
            "ecart_litres",
            "recepteur_nom",
            "commentaire",
        ]
        labels = {
            "trip": "Trajet",
    
        }


class GarageServiceTypeForm(BaseModelForm):
    class Meta:
        model = GarageServiceType
        fields = [
            "code",
            "nom",
            "categorie",
            "interval_km",
            "interval_jours",
            "duree_standard_heures",
            "cout_main_oeuvre_standard",
            "actif",
        ]


class GaragePartForm(BaseModelForm):
    class Meta:
        model = GaragePart
        fields = [
            "reference",
            "designation",
            "categorie",
            "unite",
            "stock_actuel",
            "stock_min",
            "prix_unitaire",
            "fournisseur",
            "actif",
        ]


class GarageWorkOrderForm(BaseModelForm):
    class Meta:
        model = GarageWorkOrder
        fields = [
            "reference",
            "vehicle",
            "driver",
            "service_type",
            "statut",
            "priorite",
            "ouvert_le",
            "planifie_debut",
            "planifie_fin",
            "debut_reel",
            "fin_reel",
            "km_entree",
            "km_sortie",
            "panne_signalee",
            "diagnostic",
            "travaux_realises",
            "cout_pieces",
            "heures_main_oeuvre",
            "taux_horaire",
            "qualite_validee",
            "signature_client_nom",
            "signature_client_image",
            "observations",
        ]
        labels = {
            "service_type": "Type de service",
        }
        widgets = {
            "panne_signalee": forms.Textarea(attrs={"rows": 3}),
            "diagnostic": forms.Textarea(attrs={"rows": 3}),
            "travaux_realises": forms.Textarea(attrs={"rows": 3}),
            "observations": forms.Textarea(attrs={"rows": 3}),
            "signature_client_image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }


class GarageWorkOrderQuickForm(BaseModelForm):
    class Meta:
        model = GarageWorkOrder
        fields = [
            "vehicle",
            "driver",
            "service_type",
            "priorite",
            "panne_signalee",
        ]
        labels = {
            "service_type": "Type de service",
        }
        widgets = {
            "panne_signalee": forms.Textarea(attrs={"rows": 3, "placeholder": "Panne ou besoin d'entretien"}),
        }


class GarageWorkOrderDocumentForm(BaseModelForm):
    class Meta:
        model = GarageWorkOrderDocument
        fields = ["workorder", "titre", "fichier"]


class InvoiceCreateForm(forms.Form):
    SOURCE_MANUAL = "manual"
    SOURCE_ORDER = "order"
    SOURCE_DELIVERY = "delivery"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Saisie manuelle"),
        (SOURCE_ORDER, "Depuis un ordre"),
        (SOURCE_DELIVERY, "Depuis une livraison"),
    ]

    source_type = forms.ChoiceField(choices=SOURCE_CHOICES, initial=SOURCE_DELIVERY, label="Source")
    client = forms.ModelChoiceField(queryset=Client.objects.order_by("nom"), required=False)
    order = forms.ModelChoiceField(queryset=TransportOrder.objects.order_by("-date_prevue"), required=False, label="Ordre")
    delivery = forms.ModelChoiceField(queryset=DeliveryNote.objects.order_by("-livre_le"), required=False, label="Livraison")
    numero = forms.CharField(max_length=80, required=False, label="Numero facture")
    emis_le = forms.DateField(initial=timezone.localdate, label="Date d'emission")
    echeance_le = forms.DateField(required=False, label="Date d'echeance")
    statut = forms.ChoiceField(choices=Invoice.STATUT_CHOICES, initial=Invoice.EMIS)
    description = forms.CharField(max_length=200, required=False, help_text="Laisse vide pour description automatique.")
    quantite = forms.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0)
    prix_unitaire = forms.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["emis_le"].widget = forms.DateInput(attrs={"type": "date"})
        self.fields["echeance_le"].widget = forms.DateInput(attrs={"type": "date"})

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("source_type")
        client = cleaned.get("client")
        order = cleaned.get("order")
        delivery = cleaned.get("delivery")
        emis_le = cleaned.get("emis_le")
        echeance_le = cleaned.get("echeance_le")

        if echeance_le and emis_le and echeance_le < emis_le:
            self.add_error("echeance_le", "La date d'echeance doit etre >= a la date d'emission.")

        if source == self.SOURCE_MANUAL:
            if not client:
                self.add_error("client", "Le client est obligatoire en saisie manuelle.")
            if cleaned.get("quantite") is None:
                self.add_error("quantite", "La quantite est obligatoire en saisie manuelle.")
            if cleaned.get("prix_unitaire") is None:
                self.add_error("prix_unitaire", "Le prix unitaire est obligatoire en saisie manuelle.")
        elif source == self.SOURCE_ORDER:
            if not order:
                self.add_error("order", "Selectionne un ordre.")
            elif client and client != order.client:
                self.add_error("client", "Le client doit correspondre au client de l'ordre selectionne.")
        elif source == self.SOURCE_DELIVERY:
            if not delivery:
                self.add_error("delivery", "Selectionne une livraison.")
            elif not delivery.ordre:
                self.add_error("delivery", "Cette livraison n'est liee a aucun ordre.")
            elif client and client != delivery.ordre.client:
                self.add_error("client", "Le client doit correspondre au client de la livraison selectionnee.")
        return cleaned
