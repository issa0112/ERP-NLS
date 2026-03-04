from django.contrib.auth import get_user_model
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

User = get_user_model()


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Site(TimeStampedModel):
    DEPOT = "depot"
    AGENCY = "agency"
    SITE_TYPE_CHOICES = [
        (DEPOT, "Dépôt"),
        (AGENCY, "Agence"),
    ]

    nom = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    site_type = models.CharField(max_length=20, choices=SITE_TYPE_CHOICES)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=80, blank=True)
    pays = models.CharField(max_length=80, default="Mali")
    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nom} ({self.code})"


class Client(TimeStampedModel):
    STATION = "station"
    INDUSTRIEL = "industriel"
    DEPOT = "depot"
    AUTRE = "autre"
    TYPE_CHOICES = [
        (STATION, "Station"),
        (INDUSTRIEL, "Industriel"),
        (DEPOT, "Dépôt"),
        (AUTRE, "Autre"),
    ]

    nom = models.CharField(max_length=150)
    client_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    nif = models.CharField(max_length=50, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=80, blank=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.nom


class FuelType(TimeStampedModel):
    nom = models.CharField(max_length=80)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.nom


class FuelBatch(TimeStampedModel):
    fuel_type = models.ForeignKey(FuelType, on_delete=models.PROTECT)
    batch_number = models.CharField(max_length=80)
    fournisseur = models.CharField(max_length=120, blank=True)
    quantite_litres = models.DecimalField(max_digits=14, decimal_places=2)
    recu_le = models.DateTimeField()
    site = models.ForeignKey(Site, on_delete=models.PROTECT)

    class Meta:
        unique_together = ("fuel_type", "batch_number")

    def __str__(self):
        return f"{self.fuel_type} - {self.batch_number}"


class Vehicle(TimeStampedModel):
    ACTIF = "actif"
    MAINTENANCE = "maintenance"
    HORS_SERVICE = "hors_service"
    STATUT_CHOICES = [
        (ACTIF, "Actif"),
        (MAINTENANCE, "Maintenance"),
        (HORS_SERVICE, "Hors service"),
    ]

    immatriculation = models.CharField(max_length=30, unique=True)
    marque = models.CharField(max_length=60, blank=True)
    modele = models.CharField(max_length=60, blank=True)
    capacite_litres = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    gps_device_id = models.CharField(max_length=80, blank=True)
    carte_grise_image = models.ImageField(upload_to="vehicles/carte_grise/", blank=True, null=True)
    assurance = models.CharField(max_length=120, blank=True)
    annee_fabrication = models.PositiveIntegerField(null=True, blank=True)
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default=ACTIF)
    motif_hors_service = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.statut == self.HORS_SERVICE and not (self.motif_hors_service or "").strip():
            raise ValidationError({"motif_hors_service": "Le motif est obligatoire si le camion est hors service."})

    def __str__(self):
        return self.immatriculation


class Tanker(TimeStampedModel):
    vehicle = models.OneToOneField(Vehicle, on_delete=models.PROTECT)
    adr_expires_at = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"Citerne {self.vehicle.immatriculation}"


class TankerCompartment(TimeStampedModel):
    tanker = models.ForeignKey(Tanker, on_delete=models.PROTECT, related_name="compartiments")
    numero = models.PositiveIntegerField()
    capacite_litres = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("tanker", "numero")

    def __str__(self):
        return f"{self.tanker} - {self.numero}"


class Driver(TimeStampedModel):
    ACTIF = "actif"
    SUSPENDU = "suspendu"
    STATUT_CHOICES = [
        (ACTIF, "Actif"),
        (SUSPENDU, "Suspendu"),
    ]

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    prenom = models.CharField(max_length=80)
    nom = models.CharField(max_length=80)
    telephone = models.CharField(max_length=30, blank=True)
    numero_permis = models.CharField(max_length=50)
    permis_image = models.ImageField(upload_to="drivers/permis/", blank=True, null=True)
    permis_expire_le = models.DateField()
    certificat_jaugeage_image = models.ImageField(upload_to="drivers/certificat_jaugeage/", blank=True, null=True)
    cahier_transport = models.FileField(upload_to="drivers/cahier_transport/", blank=True, null=True)
    date_embauche = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=ACTIF)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Apprentice(TimeStampedModel):
    ACTIF = "actif"
    INACTIF = "inactif"
    STATUT_CHOICES = [
        (ACTIF, "Actif"),
        (INACTIF, "Inactif"),
    ]

    chauffeur = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="apprentis")
    prenom = models.CharField(max_length=80)
    nom = models.CharField(max_length=80)
    telephone = models.CharField(max_length=30, blank=True)
    date_affectation = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=ACTIF)

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.chauffeur})"


class Employee(TimeStampedModel):
    ACTIF = "actif"
    SUSPENDU = "suspendu"
    DEMISSION = "demission"
    STATUT_CHOICES = [
        (ACTIF, "Actif"),
        (SUSPENDU, "Suspendu"),
        (DEMISSION, "Démission"),
    ]

    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    prenom = models.CharField(max_length=80)
    nom = models.CharField(max_length=80)
    fonction = models.CharField(max_length=120, blank=True)
    departement = models.CharField(max_length=120, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    date_embauche = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=ACTIF)

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class SalaryPayment(TimeStampedModel):
    BROUILLON = "brouillon"
    PAYE = "paye"
    STATUT_CHOICES = [
        (BROUILLON, "Brouillon"),
        (PAYE, "Payé"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="salaires")
    reference = models.CharField(max_length=80, unique=True)
    periode_debut = models.DateField()
    periode_fin = models.DateField()
    salaire_base = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    primes = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    paye_le = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=BROUILLON)
    commentaire = models.TextField(blank=True)

    def __str__(self):
        return f"Salaire {self.reference}"

    @property
    def total_contributions(self):
        return sum(contrib.montant for contrib in self.contributions.all())

    @property
    def net(self):
        return self.salaire_base + self.primes - self.deductions - self.total_contributions


class ContributionType(TimeStampedModel):
    nom = models.CharField(max_length=120)
    taux_pourcent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    montant_fixe = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.nom


class SalaryContribution(TimeStampedModel):
    salary = models.ForeignKey(SalaryPayment, on_delete=models.CASCADE, related_name="contributions")
    contribution_type = models.ForeignKey(ContributionType, on_delete=models.PROTECT)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    commentaire = models.CharField(max_length=200, blank=True)
    auto_generated = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.contribution_type} - {self.montant}"


class LeaveRequest(TimeStampedModel):
    EN_ATTENTE = "en_attente"
    APPROUVE = "approuve"
    REFUSE = "refuse"
    STATUT_CHOICES = [
        (EN_ATTENTE, "En attente"),
        (APPROUVE, "Approuvé"),
        (REFUSE, "Refusé"),
    ]

    CONGE = "conge"
    ABSENCE = "absence"
    MALADIE = "maladie"
    TYPE_CHOICES = [
        (CONGE, "Congé"),
        (ABSENCE, "Absence"),
        (MALADIE, "Maladie"),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="conges")
    type_absence = models.CharField(max_length=20, choices=TYPE_CHOICES, default=CONGE)
    date_debut = models.DateField()
    date_fin = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=EN_ATTENTE)
    motif = models.TextField(blank=True)

    def __str__(self):
        return f"{self.employee} - {self.get_type_absence_display()}"


class DriverCertification(TimeStampedModel):
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT, related_name="certifications")
    type_certification = models.CharField(max_length=120)
    delivree_le = models.DateField()
    expire_le = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.type_certification} - {self.driver}"


class GarageServiceType(TimeStampedModel):
    PREVENTIF = "preventif"
    CORRECTIF = "correctif"
    DIAGNOSTIC = "diagnostic"
    CARROSSERIE = "carrosserie"
    PNEUMATIQUE = "pneumatique"
    CATEGORIE_CHOICES = [
        (PREVENTIF, "Preventif"),
        (CORRECTIF, "Correctif"),
        (DIAGNOSTIC, "Diagnostic"),
        (CARROSSERIE, "Carrosserie"),
        (PNEUMATIQUE, "Pneumatique"),
    ]

    code = models.CharField(max_length=40, unique=True)
    nom = models.CharField(max_length=120)
    categorie = models.CharField(max_length=30, choices=CATEGORIE_CHOICES, default=PREVENTIF)
    interval_km = models.PositiveIntegerField(null=True, blank=True)
    interval_jours = models.PositiveIntegerField(null=True, blank=True)
    duree_standard_heures = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cout_main_oeuvre_standard = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.nom}"


class GaragePart(TimeStampedModel):
    reference = models.CharField(max_length=60, unique=True)
    designation = models.CharField(max_length=160)
    categorie = models.CharField(max_length=80, blank=True)
    unite = models.CharField(max_length=20, default="piece")
    stock_actuel = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_min = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fournisseur = models.CharField(max_length=120, blank=True)
    actif = models.BooleanField(default=True)

    @property
    def en_alerte_stock(self):
        return self.stock_actuel <= self.stock_min

    def __str__(self):
        return f"{self.reference} - {self.designation}"


class GarageWorkOrder(TimeStampedModel):
    OUVERT = "ouvert"
    DIAGNOSTIC = "diagnostic"
    EN_ATTENTE_VALIDATION = "en_attente_validation"
    PLANIFIE = "planifie"
    EN_COURS = "en_cours"
    CONTROLE_QUALITE = "controle_qualite"
    TERMINE = "termine"
    ANNULE = "annule"
    STATUT_CHOICES = [
        (OUVERT, "Ouvert"),
        (DIAGNOSTIC, "Diagnostic"),
        (EN_ATTENTE_VALIDATION, "En attente validation"),
        (PLANIFIE, "Planifie"),
        (EN_COURS, "En cours"),
        (CONTROLE_QUALITE, "Controle qualite"),
        (TERMINE, "Termine"),
        (ANNULE, "Annule"),
    ]

    BASSE = "basse"
    NORMALE = "normale"
    HAUTE = "haute"
    CRITIQUE = "critique"
    PRIORITE_CHOICES = [
        (BASSE, "Basse"),
        (NORMALE, "Normale"),
        (HAUTE, "Haute"),
        (CRITIQUE, "Critique"),
    ]

    reference = models.CharField(max_length=80, unique=True)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="garage_workorders")
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name="garage_workorders")
    service_type = models.ForeignKey(
        GarageServiceType, on_delete=models.SET_NULL, null=True, blank=True, related_name="workorders"
    )
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default=OUVERT)
    priorite = models.CharField(max_length=20, choices=PRIORITE_CHOICES, default=NORMALE)
    ouvert_le = models.DateTimeField(default=timezone.now)
    planifie_debut = models.DateTimeField(null=True, blank=True)
    planifie_fin = models.DateTimeField(null=True, blank=True)
    debut_reel = models.DateTimeField(null=True, blank=True)
    fin_reel = models.DateTimeField(null=True, blank=True)
    km_entree = models.PositiveIntegerField(null=True, blank=True)
    km_sortie = models.PositiveIntegerField(null=True, blank=True)
    panne_signalee = models.TextField(blank=True)
    diagnostic = models.TextField(blank=True)
    travaux_realises = models.TextField(blank=True)
    cout_pieces = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    heures_main_oeuvre = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    taux_horaire = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    qualite_validee = models.BooleanField(default=False)
    signature_client_nom = models.CharField(max_length=120, blank=True)
    signature_client_image = models.ImageField(upload_to="garage/workorders/signatures/", blank=True, null=True)
    observations = models.TextField(blank=True)

    def clean(self):
        super().clean()
        if self.km_entree is not None and self.km_sortie is not None and self.km_sortie < self.km_entree:
            raise ValidationError({"km_sortie": "Le kilometrage de sortie doit etre >= au kilometrage d'entree."})
        if self.planifie_debut and self.planifie_fin and self.planifie_fin < self.planifie_debut:
            raise ValidationError({"planifie_fin": "La fin planifiee doit etre >= au debut planifie."})
        if self.debut_reel and self.fin_reel and self.fin_reel < self.debut_reel:
            raise ValidationError({"fin_reel": "La fin reelle doit etre >= au debut reel."})

    @property
    def cout_main_oeuvre(self):
        return self.heures_main_oeuvre * self.taux_horaire

    @property
    def cout_total(self):
        return self.cout_pieces + self.cout_main_oeuvre

    @property
    def sla_status(self):
        if not self.planifie_fin:
            return "non_planifie"
        reference_end = self.fin_reel or timezone.now()
        if reference_end > self.planifie_fin:
            return "retard"
        return "a_l_heure"

    @property
    def sla_delay_hours(self):
        if not self.planifie_fin:
            return 0
        reference_end = self.fin_reel or timezone.now()
        if reference_end <= self.planifie_fin:
            return 0
        delta = reference_end - self.planifie_fin
        return round(delta.total_seconds() / 3600, 1)

    def __str__(self):
        return f"{self.reference} - {self.vehicle.immatriculation}"


class GarageWorkOrderDocument(TimeStampedModel):
    workorder = models.ForeignKey(GarageWorkOrder, on_delete=models.CASCADE, related_name="documents")
    titre = models.CharField(max_length=120, blank=True)
    fichier = models.FileField(upload_to="garage/workorders/documents/")

    def __str__(self):
        return self.titre or f"Document {self.workorder.reference}"


class Contract(TimeStampedModel):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="contrats")
    reference = models.CharField(max_length=80, unique=True)
    debut = models.DateField()
    fin = models.DateField(null=True, blank=True)
    conditions = models.TextField(blank=True)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return self.reference


class TariffRule(TimeStampedModel):
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="tarifs")
    fuel_type = models.ForeignKey(FuelType, on_delete=models.PROTECT, null=True, blank=True)
    prix_par_litre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    prix_par_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    devise = models.CharField(max_length=10, default="XOF")
    effectif_du = models.DateField()
    effectif_au = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Tarif {self.contract.reference}"


class TransportOrder(TimeStampedModel):
    BROUILLON = "brouillon"
    PLANIFIE = "planifie"
    EN_COURS = "en_cours"
    LIVRE = "livre"
    ANNULE = "annule"
    STATUT_CHOICES = [
        (BROUILLON, "Brouillon"),
        (PLANIFIE, "Planifié"),
        (EN_COURS, "En cours"),
        (LIVRE, "Livré"),
        (ANNULE, "Annulé"),
    ]

    reference = models.CharField(max_length=80, unique=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    contract = models.ForeignKey(Contract, on_delete=models.SET_NULL, null=True, blank=True)
    fuel_type = models.ForeignKey(FuelType, on_delete=models.PROTECT)
    batch = models.ForeignKey(FuelBatch, on_delete=models.SET_NULL, null=True, blank=True)
    site_depart = models.ForeignKey(Site, on_delete=models.PROTECT, related_name="ordres_depart")
    adresse_livraison = models.TextField()
    quantite_prevue_litres = models.DecimalField(max_digits=12, decimal_places=2)
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    date_prevue = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=BROUILLON)

    def __str__(self):
        return self.reference


class Trip(TimeStampedModel):
    PLANIFIE = "planifie"
    EN_COURS = "en_cours"
    TERMINE = "termine"
    STATUT_CHOICES = [
        (PLANIFIE, "Planifié"),
        (EN_COURS, "En cours"),
        (TERMINE, "Terminé"),
    ]

    ordre = models.ForeignKey(TransportOrder, on_delete=models.PROTECT, related_name="tournees")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT)
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT)
    depart_prevu = models.DateTimeField(null=True, blank=True)
    arrivee_prevue = models.DateTimeField(null=True, blank=True)
    depart_reel = models.DateTimeField(null=True, blank=True)
    arrivee_reelle = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=PLANIFIE)

    def __str__(self):
        return f"{self.ordre.reference} - {self.vehicle}"


class DeliveryNote(TimeStampedModel):
    ordre = models.ForeignKey(TransportOrder, on_delete=models.PROTECT, related_name="livraisons")
    trip = models.ForeignKey(Trip, on_delete=models.SET_NULL, null=True, blank=True)
    livre_le = models.DateTimeField()
    quantite_livree_litres = models.DecimalField(max_digits=12, decimal_places=2)
    ecart_litres = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    recepteur_nom = models.CharField(max_length=120, blank=True)
    commentaire = models.TextField(blank=True)

    def __str__(self):
        return f"BL {self.ordre.reference}"


class Incident(TimeStampedModel):
    LEGER = "leger"
    MOYEN = "moyen"
    GRAVE = "grave"
    SEVERITE_CHOICES = [
        (LEGER, "Léger"),
        (MOYEN, "Moyen"),
        (GRAVE, "Grave"),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.PROTECT, related_name="incidents")
    type_incident = models.CharField(max_length=120)
    date_incident = models.DateTimeField()
    description = models.TextField()
    severite = models.CharField(max_length=20, choices=SEVERITE_CHOICES, default=LEGER)

    def __str__(self):
        return f"{self.type_incident} - {self.trip}"


class FuelMeasurement(TimeStampedModel):
    CAPTEUR = "capteur"
    MANUEL = "manuel"
    SOURCE_CHOICES = [
        (CAPTEUR, "Capteur"),
        (MANUEL, "Manuel"),
    ]

    CHARGEMENT = "chargement"
    DECHARGEMENT = "dechargement"
    EN_ROUTE = "en_route"
    EVENT_CHOICES = [
        (CHARGEMENT, "Chargement"),
        (DECHARGEMENT, "Déchargement"),
        (EN_ROUTE, "En route"),
    ]

    trip = models.ForeignKey(Trip, on_delete=models.PROTECT, related_name="mesures_carburant")
    compartment = models.ForeignKey(TankerCompartment, on_delete=models.SET_NULL, null=True, blank=True)
    mesure_le = models.DateTimeField()
    niveau_litres = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=CAPTEUR)
    evenement = models.CharField(max_length=20, choices=EVENT_CHOICES)

    def __str__(self):
        return f"{self.trip} - {self.niveau_litres} L"


class Invoice(TimeStampedModel):
    BROUILLON = "brouillon"
    EMIS = "emis"
    PAYE = "paye"
    STATUT_CHOICES = [
        (BROUILLON, "Brouillon"),
        (EMIS, "Émis"),
        (PAYE, "Payé"),
    ]

    client = models.ForeignKey(Client, on_delete=models.PROTECT)
    numero = models.CharField(max_length=80, unique=True)
    emis_le = models.DateField()
    echeance_le = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default=BROUILLON)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def __str__(self):
        return self.numero


class InvoiceLine(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lignes")
    order = models.ForeignKey(TransportOrder, on_delete=models.SET_NULL, null=True, blank=True)
    fuel_type = models.ForeignKey(FuelType, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=200)
    quantite = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return self.description

    @property
    def total(self):
        return self.quantite * self.prix_unitaire


class Payment(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="paiements")
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    paye_le = models.DateField()
    methode = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.invoice.numero} - {self.montant}"


class CreditNote(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="avoirs")
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    raison = models.CharField(max_length=200)
    emis_le = models.DateField()

    def __str__(self):
        return f"Avoir {self.invoice.numero}"


class Expense(TimeStampedModel):
    categorie = models.CharField(max_length=120, blank=True)
    description = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=14, decimal_places=2)
    depense_le = models.DateField()
    reference = models.CharField(max_length=80, blank=True)
    commentaire = models.TextField(blank=True)

    def __str__(self):
        return self.description
