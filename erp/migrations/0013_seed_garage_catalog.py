from django.db import migrations


def seed_garage_catalog(apps, schema_editor):
    GarageServiceType = apps.get_model("erp", "GarageServiceType")
    GaragePart = apps.get_model("erp", "GaragePart")

    services = [
        ("ENT-VIDANGE", "Entretien vidange moteur", "preventif", 10000, 180, 2.0, 30000),
        ("ENT-FILTRES", "Remplacement filtres (air/huile/carburant)", "preventif", 10000, 180, 1.5, 22000),
        ("ENT-GRAISS", "Graissage et controles generaux", "preventif", 5000, 90, 1.0, 15000),
        ("PNEU-CTRL", "Controle pression et usure pneus", "pneumatique", 3000, 30, 0.7, 10000),
        ("PNEU-ROT", "Rotation / permutation pneus", "pneumatique", 10000, 120, 1.0, 12000),
        ("PNEU-REMPL", "Remplacement pneu", "pneumatique", None, None, 1.0, 8000),
        ("MEC-FREINS", "Diagnostic et reparation freinage", "correctif", None, None, 3.0, 45000),
        ("MEC-EMBRAY", "Diagnostic embrayage / transmission", "diagnostic", None, None, 4.0, 55000),
        ("MEC-MOTEUR", "Diagnostic panne moteur", "diagnostic", None, None, 4.5, 60000),
        ("MEC-DIVERS", "Divers pannes mecaniques", "correctif", None, None, 2.5, 35000),
        ("ELEC-DIAG", "Diagnostic electrique", "diagnostic", None, None, 2.0, 30000),
        ("CARROSS-REP", "Reparation carrosserie", "carrosserie", None, None, 6.0, 90000),
    ]

    for code, nom, categorie, interval_km, interval_jours, duree_h, cout_std in services:
        GarageServiceType.objects.update_or_create(
            code=code,
            defaults={
                "nom": nom,
                "categorie": categorie,
                "interval_km": interval_km,
                "interval_jours": interval_jours,
                "duree_standard_heures": duree_h,
                "cout_main_oeuvre_standard": cout_std,
                "actif": True,
            },
        )

    parts = [
        ("PNEU-315-80R22", "Pneu 315/80 R22.5", "Pneumatique", "piece", 8, 4, 225000, "Fournisseur pneus"),
        ("CHAMBRE-AIR-22", "Chambre a air 22.5", "Pneumatique", "piece", 10, 4, 35000, "Fournisseur pneus"),
        ("FILTRE-HUILE", "Filtre a huile", "Entretien", "piece", 20, 8, 12000, "Fournisseur moteur"),
        ("FILTRE-AIR", "Filtre a air", "Entretien", "piece", 16, 6, 15000, "Fournisseur moteur"),
        ("FILTRE-CARB", "Filtre carburant", "Entretien", "piece", 18, 6, 18000, "Fournisseur carburant"),
        ("HUILE-15W40", "Huile moteur 15W40", "Lubrifiant", "litre", 200, 80, 4500, "Fournisseur lubrifiant"),
        ("PLAQUETTE-FR", "Plaquettes de frein", "Freinage", "jeu", 8, 3, 45000, "Fournisseur freins"),
        ("DISQUE-FR", "Disque de frein", "Freinage", "piece", 6, 2, 70000, "Fournisseur freins"),
        ("KIT-EMBRAY", "Kit embrayage", "Transmission", "kit", 4, 1, 180000, "Fournisseur transmission"),
        ("COURROIE-ALT", "Courroie alternateur", "Moteur", "piece", 8, 3, 22000, "Fournisseur moteur"),
    ]

    for reference, designation, categorie, unite, stock_actuel, stock_min, prix_unitaire, fournisseur in parts:
        GaragePart.objects.update_or_create(
            reference=reference,
            defaults={
                "designation": designation,
                "categorie": categorie,
                "unite": unite,
                "stock_actuel": stock_actuel,
                "stock_min": stock_min,
                "prix_unitaire": prix_unitaire,
                "fournisseur": fournisseur,
                "actif": True,
            },
        )


def unseed_garage_catalog(apps, schema_editor):
    GarageServiceType = apps.get_model("erp", "GarageServiceType")
    GaragePart = apps.get_model("erp", "GaragePart")
    GarageServiceType.objects.filter(
        code__in=[
            "ENT-VIDANGE",
            "ENT-FILTRES",
            "ENT-GRAISS",
            "PNEU-CTRL",
            "PNEU-ROT",
            "PNEU-REMPL",
            "MEC-FREINS",
            "MEC-EMBRAY",
            "MEC-MOTEUR",
            "MEC-DIVERS",
            "ELEC-DIAG",
            "CARROSS-REP",
        ]
    ).delete()
    GaragePart.objects.filter(
        reference__in=[
            "PNEU-315-80R22",
            "CHAMBRE-AIR-22",
            "FILTRE-HUILE",
            "FILTRE-AIR",
            "FILTRE-CARB",
            "HUILE-15W40",
            "PLAQUETTE-FR",
            "DISQUE-FR",
            "KIT-EMBRAY",
            "COURROIE-ALT",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("erp", "0012_garageworkorder_signature_client_image_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_garage_catalog, unseed_garage_catalog),
    ]
