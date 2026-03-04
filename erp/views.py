import json
import re
from datetime import timedelta
from urllib.parse import quote

from django.contrib import messages
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from .forms import (
    ApprenticeForm,
    ClientForm,
    ContributionTypeForm,
    DeliveryNoteForm,
    DriverForm,
    DriverQuickForm,
    EmployeeForm,
    ExpenseForm,
    FuelTypeForm,
    GaragePartForm,
    GarageServiceTypeForm,
    GarageWorkOrderDocumentForm,
    GarageWorkOrderForm,
    GarageWorkOrderQuickForm,
    InvoiceCreateForm,
    LeaveRequestForm,
    SalaryContributionForm,
    SalaryPaymentForm,
    SiteForm,
    TransportOrderForm,
    VehicleForm,
)
from .models import (
    Apprentice,
    Client,
    ContributionType,
    CreditNote,
    DeliveryNote,
    Driver,
    Employee,
    Expense,
    FuelBatch,
    FuelType,
    GaragePart,
    GarageServiceType,
    GarageWorkOrder,
    GarageWorkOrderDocument,
    FuelMeasurement,
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
from .pdf import build_invoice_lines, build_salary_lines, simple_pdf

from .telematics import fetch_traccar_positions

FLUX_SCOPE_CHOICES = [
    ("7", "7 jours"),
    ("30", "30 jours"),
    ("90", "90 jours"),
    ("all", "Tout"),
]

CYCLE_CHOICES = [
    ("jour", "Jour"),
    ("semaine", "Semaine"),
    ("mois", "Mois"),
    ("trimestre", "Trimestre"),
    ("annee", "Annee"),
]


def _build_invoice_number():
    today = timezone.localdate().strftime("%Y%m%d")
    prefix = f"INV-{today}-"
    max_seq = 0
    for numero in Invoice.objects.filter(numero__startswith=prefix).values_list("numero", flat=True):
        try:
            seq = int(numero.split("-")[-1])
        except (ValueError, TypeError):
            continue
        if seq > max_seq:
            max_seq = seq
    return f"{prefix}{max_seq + 1:03d}"


def _build_workorder_reference():
    today = timezone.localdate().strftime("%Y%m%d")
    prefix = f"WO-{today}-"
    max_seq = 0
    for reference in GarageWorkOrder.objects.filter(reference__startswith=prefix).values_list("reference", flat=True):
        try:
            seq = int(reference.split("-")[-1])
        except (ValueError, TypeError):
            continue
        if seq > max_seq:
            max_seq = seq
    return f"{prefix}{max_seq + 1:03d}"


def _selected_badge_filters(request):
    flux_scope = (request.GET.get("flux_scope") or "30").strip()
    cycle = (request.GET.get("cycle") or "mois").strip()
    valid_flux = {v for v, _ in FLUX_SCOPE_CHOICES}
    valid_cycle = {v for v, _ in CYCLE_CHOICES}
    if flux_scope not in valid_flux:
        flux_scope = "30"
    if cycle not in valid_cycle:
        cycle = "mois"
    return flux_scope, cycle


def _window_start_for_scope(today, flux_scope):
    if flux_scope == "7":
        return today - timedelta(days=7)
    if flux_scope == "30":
        return today - timedelta(days=30)
    if flux_scope == "90":
        return today - timedelta(days=90)
    return None


def _cycle_label(today, cycle):
    if cycle == "jour":
        return f"Journalier {today.strftime('%d/%m/%Y')}"
    if cycle == "semaine":
        week, year = today.isocalendar().week, today.isocalendar().year
        return f"Semaine {week:02d}/{year}"
    if cycle == "trimestre":
        quarter = ((today.month - 1) // 3) + 1
        return f"Trimestre T{quarter}/{today.year}"
    if cycle == "annee":
        return f"Annuel {today.year}"
    return f"Mensuel {today.strftime('%m/%Y')}"


def _find_tariff_for_order(order, reference_date):
    if not order or not order.contract:
        return None
    rules = TariffRule.objects.filter(contract=order.contract).filter(effectif_du__lte=reference_date)
    if order.fuel_type:
        rules = rules.filter(fuel_type=order.fuel_type)
    rules = rules.filter(models.Q(effectif_au__isnull=True) | models.Q(effectif_au__gte=reference_date))
    return rules.order_by("-effectif_du").first()


def _build_auto_invoice_line(order, delivery, cleaned_data):
    today = timezone.localdate()
    reference_date = today
    if delivery and delivery.livre_le:
        reference_date = delivery.livre_le.date()
    elif order and order.date_prevue:
        reference_date = order.date_prevue

    tariff = _find_tariff_for_order(order, reference_date)
    description = cleaned_data.get("description")
    fuel_type = order.fuel_type if order else None

    if tariff and tariff.prix_par_litre:
        if delivery:
            quantite = delivery.quantite_livree_litres or 0
            default_desc = f"Transport carburant - Ordre {order.reference} - Livraison {delivery.pk} ({tariff.prix_par_litre}/L)"
        else:
            quantite = order.quantite_prevue_litres or 0
            default_desc = f"Transport carburant - Ordre {order.reference} ({tariff.prix_par_litre}/L)"
        return quantite, tariff.prix_par_litre, description or default_desc, fuel_type

    if tariff and tariff.prix_par_km and order and order.distance_km:
        default_desc = f"Transport carburant - Ordre {order.reference} ({tariff.prix_par_km}/km)"
        return order.distance_km, tariff.prix_par_km, description or default_desc, fuel_type

    if delivery:
        default_desc = f"Transport carburant - Ordre {order.reference} - Livraison {delivery.pk} (tarif a definir)"
        quantite = delivery.quantite_livree_litres or 0
    else:
        default_desc = f"Transport carburant - Ordre {order.reference} (tarif a definir)"
        quantite = order.quantite_prevue_litres or 0
    return quantite, 0, description or default_desc, fuel_type


def _recalculate_invoice_total(invoice):
    total = 0
    for line in invoice.lignes.all():
        total += line.quantite * line.prix_unitaire
    invoice.total = total
    invoice.save(update_fields=["total"])


def _normalize_phone(phone):
    digits = re.sub(r"\D+", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    return digits


def _build_whatsapp_share_url(request, invoice):
    phone = _normalize_phone(invoice.client.telephone)
    if not phone:
        return ""
    pdf_url = request.build_absolute_uri(reverse("erp:invoice_pdf", kwargs={"pk": invoice.pk}))
    text = (
        f"Bonjour {invoice.client.nom}, veuillez trouver votre facture {invoice.numero} "
        f"(emise le {invoice.emis_le}). PDF: {pdf_url}"
    )
    return f"https://wa.me/{phone}?text={quote(text)}"


class DashboardView(TemplateView):
    template_name = "erp/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["stats"] = {
            "clients": Client.objects.count(),
            "sites": Site.objects.count(),
            "fuel_types": FuelType.objects.count(),
            "vehicles": Vehicle.objects.count(),
            "drivers": Driver.objects.count(),
            "orders": TransportOrder.objects.count(),
            "deliveries": DeliveryNote.objects.count(),
        }
        context["recent_orders"] = TransportOrder.objects.select_related("client", "fuel_type").order_by("-created_at")[:5]
        context["recent_deliveries"] = DeliveryNote.objects.select_related("ordre").order_by("-livre_le")[:5]
        context["critical_incidents"] = (
            Incident.objects.select_related("trip")
            .filter(severite=Incident.GRAVE)
            .order_by("-date_incident")[:5]
        )
        context["permit_alerts"] = Driver.objects.order_by("permis_expire_le")[:5]
        context["loss_alerts"] = _loss_alerts()[:5]
        context["drop_alerts"] = _fuel_drop_alerts()[:5]
        return context


class OrdersModuleView(TemplateView):
    template_name = "erp/module_orders.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_orders"] = TransportOrder.objects.select_related("client", "fuel_type").order_by("-created_at")[:10]
        context["recent_trips"] = Trip.objects.select_related("ordre", "vehicle", "driver").order_by("-created_at")[:10]
        context["recent_incidents"] = Incident.objects.select_related("trip").order_by("-date_incident")[:10]
        context["status_counts"] = {
            "brouillon": TransportOrder.objects.filter(statut=TransportOrder.BROUILLON).count(),
            "planifie": TransportOrder.objects.filter(statut=TransportOrder.PLANIFIE).count(),
            "en_cours": TransportOrder.objects.filter(statut=TransportOrder.EN_COURS).count(),
            "livre": TransportOrder.objects.filter(statut=TransportOrder.LIVRE).count(),
        }
        return context


class DeliveriesModuleView(TemplateView):
    template_name = "erp/module_deliveries.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recent_deliveries"] = DeliveryNote.objects.select_related("ordre").order_by("-livre_le")[:10]
        context["recent_trips"] = Trip.objects.select_related("ordre", "vehicle").order_by("-created_at")[:10]
        context["recent_incidents"] = Incident.objects.select_related("trip").order_by("-date_incident")[:10]
        return context


class FuelModuleView(TemplateView):
    template_name = "erp/module_fuel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["fuel_types"] = FuelType.objects.all().order_by("nom")
        context["batches"] = FuelBatch.objects.select_related("fuel_type", "site").order_by("-recu_le")[:10]
        context["measurements"] = FuelMeasurement.objects.select_related("trip", "compartment").order_by("-mesure_le")[:10]
        context["drop_alerts"] = _fuel_drop_alerts()[:10]
        return context


class AccountingModuleView(TemplateView):
    template_name = "erp/module_accounting.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        flux_scope, cycle = _selected_badge_filters(self.request)
        window_start = _window_start_for_scope(today, flux_scope)

        context["stats"] = {
            "factures": Invoice.objects.count(),
            "encaissements": Payment.objects.count(),
            "avoirs": CreditNote.objects.count(),
            "depenses": Expense.objects.count(),
            "personnel": Employee.objects.count(),
            "salaires": SalaryPayment.objects.count(),
            "cotisations": SalaryContribution.objects.count(),
        }
        context["recent_invoices"] = Invoice.objects.select_related("client").order_by("-emis_le")[:6]
        context["recent_expenses"] = Expense.objects.order_by("-depense_le")[:6]

        invoice_activity = Invoice.objects.all()
        payment_activity = Payment.objects.all()
        expense_activity = Expense.objects.all()
        if window_start:
            invoice_activity = invoice_activity.filter(emis_le__gte=window_start)
            payment_activity = payment_activity.filter(paye_le__gte=window_start)
            expense_activity = expense_activity.filter(depense_le__gte=window_start)
        recent_activity = invoice_activity.count() + payment_activity.count() + expense_activity.count()

        flux_thresholds = {"7": 3, "30": 10, "90": 25, "all": 50}
        if recent_activity >= flux_thresholds.get(flux_scope, 10):
            flux_label = "Operationnel"
            flux_level = "good"
        elif recent_activity > 0:
            flux_label = "Modere"
            flux_level = "warn"
        else:
            flux_label = "Faible"
            flux_level = "danger"

        pending_controls = (
            Invoice.objects.filter(statut=Invoice.BROUILLON).count()
            + SalaryPayment.objects.filter(statut=SalaryPayment.BROUILLON).count()
        )
        if pending_controls == 0:
            controle_label = "Actif"
            controle_level = "good"
        elif pending_controls <= 5:
            controle_label = "A surveiller"
            controle_level = "warn"
        else:
            controle_label = "Charge elevee"
            controle_level = "danger"

        context["badges"] = {
            "flux_label": flux_label,
            "flux_level": flux_level,
            "cycle_label": _cycle_label(today, cycle),
            "controle_label": controle_label,
            "controle_level": controle_level,
        }
        context["badge_filters"] = {
            "flux_scope": flux_scope,
            "cycle": cycle,
            "flux_scope_choices": FLUX_SCOPE_CHOICES,
            "cycle_choices": CYCLE_CHOICES,
        }
        return context


class HRModuleView(TemplateView):
    template_name = "erp/module_hr.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["drivers"] = Driver.objects.order_by("nom")[:10]
        context["apprentices"] = Apprentice.objects.select_related("chauffeur").order_by("nom")[:10]
        context["permit_alerts"] = Driver.objects.order_by("permis_expire_le")[:10]
        context["employees"] = Employee.objects.order_by("nom")[:10]
        context["recent_salaries"] = SalaryPayment.objects.select_related("employee").order_by("-periode_fin")[:10]
        context["leave_requests"] = LeaveRequest.objects.select_related("employee").order_by("-date_debut")[:10]
        return context


class FleetModuleView(TemplateView):
    template_name = "erp/module_fleet.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["vehicles"] = Vehicle.objects.order_by("immatriculation")[:10]
        context["tankers"] = Tanker.objects.select_related("vehicle").order_by("vehicle__immatriculation")[:10]
        context["compartments"] = TankerCompartment.objects.select_related("tanker").order_by("tanker__vehicle__immatriculation")[:10]
        return context


class GarageModuleView(TemplateView):
    template_name = "erp/module_garage.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        flux_scope, cycle = _selected_badge_filters(self.request)
        window_start = _window_start_for_scope(today, flux_scope)
        open_statuses = [
            GarageWorkOrder.OUVERT,
            GarageWorkOrder.DIAGNOSTIC,
            GarageWorkOrder.EN_ATTENTE_VALIDATION,
            GarageWorkOrder.PLANIFIE,
            GarageWorkOrder.EN_COURS,
            GarageWorkOrder.CONTROLE_QUALITE,
        ]
        workorders = GarageWorkOrder.objects.select_related("vehicle", "driver", "service_type")
        stock_alerts = GaragePart.objects.filter(actif=True, stock_actuel__lte=models.F("stock_min")).order_by(
            "stock_actuel"
        )
        context["stats"] = {
            "workorders_open": workorders.filter(statut__in=open_statuses).count(),
            "workorders_critical": workorders.filter(priorite=GarageWorkOrder.CRITIQUE).count(),
            "workorders_done_month": workorders.filter(
                statut=GarageWorkOrder.TERMINE,
                fin_reel__year=today.year,
                fin_reel__month=today.month,
            ).count(),
            "parts_alert": stock_alerts.count(),
            "parts_count": GaragePart.objects.count(),
            "services_count": GarageServiceType.objects.count(),
        }
        context["recent_workorders"] = workorders.order_by("-created_at")[:12]
        context["stock_alerts"] = stock_alerts[:12]
        context["documents"] = GarageWorkOrderDocument.objects.select_related("workorder").order_by("-created_at")[:8]
        context["preventive_alerts"] = _garage_preventive_alerts()[:12]

        recent_activity_qs = workorders
        if window_start:
            recent_activity_qs = recent_activity_qs.filter(created_at__date__gte=window_start)
        recent_activity = recent_activity_qs.count()

        flux_thresholds = {"7": 2, "30": 8, "90": 20, "all": 40}
        if recent_activity >= flux_thresholds.get(flux_scope, 8):
            flux_label = "Operationnel"
            flux_level = "good"
        elif recent_activity > 0:
            flux_label = "Modere"
            flux_level = "warn"
        else:
            flux_label = "Faible"
            flux_level = "danger"

        pending_control = workorders.filter(statut=GarageWorkOrder.CONTROLE_QUALITE, qualite_validee=False).count()
        if pending_control == 0:
            controle_label = "Actif"
            controle_level = "good"
        elif pending_control <= 3:
            controle_label = "A surveiller"
            controle_level = "warn"
        else:
            controle_label = "Charge elevee"
            controle_level = "danger"

        context["badges"] = {
            "flux_label": flux_label,
            "flux_level": flux_level,
            "cycle_label": _cycle_label(today, cycle),
            "controle_label": controle_label,
            "controle_level": controle_level,
        }
        context["badge_filters"] = {
            "flux_scope": flux_scope,
            "cycle": cycle,
            "flux_scope_choices": FLUX_SCOPE_CHOICES,
            "cycle_choices": CYCLE_CHOICES,
        }
        return context


class TelematicsView(TemplateView):
    template_name = "erp/module_telematics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["telematics"] = fetch_traccar_positions()
        context["vehicles"] = Vehicle.objects.exclude(gps_device_id="").order_by("immatriculation")
        context["traccar_iframe_url"] = getattr(settings, "TRACCAR_IFRAME_URL", "")
        context["osm_device"] = _pick_osm_device(context["telematics"].positions)
        context["positions_json"] = json.dumps(
            [
                {
                    "name": item.get("name"),
                    "lat": (item.get("position") or {}).get("latitude"),
                    "lon": (item.get("position") or {}).get("longitude"),
                    "speed": (item.get("position") or {}).get("speed"),
                }
                for item in context["telematics"].positions
            ]
        )
        return context


class InvoiceDetailView(TemplateView):
    template_name = "erp/invoice_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = get_object_or_404(Invoice, pk=kwargs["pk"])
        today = timezone.localdate()
        payment_terms_days = None
        days_to_due = None
        if invoice.echeance_le:
            days_to_due = (invoice.echeance_le - today).days
            payment_terms_days = (invoice.echeance_le - invoice.emis_le).days
        context["invoice"] = invoice
        context["today"] = today
        context["payment_terms_days"] = payment_terms_days
        context["days_to_due"] = days_to_due
        context["whatsapp_share_url"] = _build_whatsapp_share_url(self.request, invoice)
        return context


class InvoiceListView(ListView):
    template_name = "erp/invoice_list.html"
    context_object_name = "items"
    paginate_by = 20

    def get_queryset(self):
        qs = Invoice.objects.select_related("client").order_by("-emis_le")
        qs = _apply_date_filters(self.request, qs, "emis_le")
        query = self.request.GET.get("q")
        if query:
            qs = qs.filter(models.Q(numero__icontains=query) | models.Q(client__nom__icontains=query))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Factures"
        context["query"] = self.request.GET.get("q", "")
        context["filters"] = _filters_from_request(self.request)
        context["today"] = timezone.localdate()
        return context


class InvoiceCreateView(FormView):
    template_name = "erp/invoice_create.html"
    form_class = InvoiceCreateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nouvelle facture"
        return context

    def form_valid(self, form):
        source = form.cleaned_data["source_type"]
        order = form.cleaned_data.get("order")
        delivery = form.cleaned_data.get("delivery")
        client = form.cleaned_data.get("client")
        emis_le = form.cleaned_data["emis_le"]
        echeance_le = form.cleaned_data.get("echeance_le")
        statut = form.cleaned_data["statut"]
        numero = form.cleaned_data.get("numero") or _build_invoice_number()

        if Invoice.objects.filter(numero=numero).exists():
            form.add_error("numero", "Ce numero de facture existe deja.")
            return self.form_invalid(form)

        if source == InvoiceCreateForm.SOURCE_ORDER and order:
            client = order.client
        if source == InvoiceCreateForm.SOURCE_DELIVERY and delivery and delivery.ordre:
            order = delivery.ordre
            client = order.client

        invoice = Invoice.objects.create(
            client=client,
            numero=numero,
            emis_le=emis_le,
            echeance_le=echeance_le,
            statut=statut,
            total=0,
        )

        if source == InvoiceCreateForm.SOURCE_MANUAL:
            description = form.cleaned_data.get("description") or f"Facturation client {client}"
            quantite = form.cleaned_data["quantite"]
            prix_unitaire = form.cleaned_data["prix_unitaire"]
            InvoiceLine.objects.create(
                invoice=invoice,
                description=description,
                quantite=quantite,
                prix_unitaire=prix_unitaire,
            )
        else:
            quantite, prix_unitaire, description, fuel_type = _build_auto_invoice_line(order, delivery, form.cleaned_data)
            InvoiceLine.objects.create(
                invoice=invoice,
                order=order,
                fuel_type=fuel_type,
                description=description,
                quantite=quantite,
                prix_unitaire=prix_unitaire,
            )

        _recalculate_invoice_total(invoice)
        return redirect("erp:invoice_detail", pk=invoice.pk)


class SalaryDetailView(TemplateView):
    template_name = "erp/salary_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        salary = get_object_or_404(SalaryPayment, pk=kwargs["pk"])
        context["salary"] = salary
        context["settings"] = settings
        return context


def invoice_pdf_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    company = {
        "name": getattr(settings, "COMPANY_NAME", ""),
        "address": getattr(settings, "COMPANY_ADDRESS", ""),
        "nif": getattr(settings, "COMPANY_NIF", ""),
        "phone": getattr(settings, "COMPANY_PHONE", ""),
        "email": getattr(settings, "COMPANY_EMAIL", ""),
        "logo_text": getattr(settings, "COMPANY_LOGO_TEXT", ""),
    }
    vat_rate = getattr(settings, "VAT_RATE", 0)
    currency = getattr(settings, "COMPANY_CURRENCY", "XOF")
    lines = build_invoice_lines(invoice, company, vat_rate, currency)
    pdf_bytes = simple_pdf(f"Facture {invoice.numero}", lines)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="facture-{invoice.numero}.pdf"'
    return response


def invoice_send_whatsapp_view(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("client"), pk=pk)
    whatsapp_url = _build_whatsapp_share_url(request, invoice)
    if not whatsapp_url:
        messages.error(request, "Impossible d'envoyer par WhatsApp: numero client manquant.")
        return redirect("erp:invoice_detail", pk=invoice.pk)
    return redirect(whatsapp_url)


def invoice_send_email_view(request, pk):
    if request.method != "POST":
        return redirect("erp:invoice_detail", pk=pk)

    invoice = get_object_or_404(Invoice.objects.select_related("client"), pk=pk)
    if not invoice.client.email:
        messages.error(request, "Impossible d'envoyer par email: adresse email client manquante.")
        return redirect("erp:invoice_detail", pk=invoice.pk)

    company = {
        "name": getattr(settings, "COMPANY_NAME", ""),
        "address": getattr(settings, "COMPANY_ADDRESS", ""),
        "nif": getattr(settings, "COMPANY_NIF", ""),
        "phone": getattr(settings, "COMPANY_PHONE", ""),
        "email": getattr(settings, "COMPANY_EMAIL", ""),
        "logo_text": getattr(settings, "COMPANY_LOGO_TEXT", ""),
    }
    vat_rate = getattr(settings, "VAT_RATE", 0)
    currency = getattr(settings, "COMPANY_CURRENCY", "XOF")
    lines = build_invoice_lines(invoice, company, vat_rate, currency)
    pdf_bytes = simple_pdf(f"Facture {invoice.numero}", lines)

    subject = f"Facture {invoice.numero} - {company.get('name') or 'Nouvelle Logistique'}"
    body = (
        f"Bonjour {invoice.client.nom},\n\n"
        f"Veuillez trouver en piece jointe votre facture {invoice.numero} "
        f"emise le {invoice.emis_le}.\n\n"
        "Cordialement."
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or company.get("email") or "no-reply@example.com"
    message = EmailMessage(subject, body, from_email, [invoice.client.email])
    message.attach(f"facture-{invoice.numero}.pdf", pdf_bytes, "application/pdf")

    try:
        message.send(fail_silently=False)
    except Exception:
        messages.error(
            request,
            "Echec envoi email. Configure EMAIL_HOST/EMAIL_PORT/EMAIL_HOST_USER/EMAIL_HOST_PASSWORD et DEFAULT_FROM_EMAIL.",
        )
        return redirect("erp:invoice_detail", pk=invoice.pk)

    messages.success(request, f"Facture envoyee par email a {invoice.client.email}.")
    return redirect("erp:invoice_detail", pk=invoice.pk)


def salary_pdf_view(request, pk):
    salary = get_object_or_404(SalaryPayment, pk=pk)
    company = {
        "name": getattr(settings, "COMPANY_NAME", ""),
        "address": getattr(settings, "COMPANY_ADDRESS", ""),
        "nif": getattr(settings, "COMPANY_NIF", ""),
        "phone": getattr(settings, "COMPANY_PHONE", ""),
        "email": getattr(settings, "COMPANY_EMAIL", ""),
        "logo_text": getattr(settings, "COMPANY_LOGO_TEXT", ""),
    }
    currency = getattr(settings, "COMPANY_CURRENCY", "XOF")
    lines = build_salary_lines(salary, company, currency)
    pdf_bytes = simple_pdf(f"Fiche de paie {salary.reference}", lines)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="fiche-paie-{salary.reference}.pdf"'
    return response


def invoice_export_csv_view(request):
    qs = Invoice.objects.select_related("client").order_by("-emis_le")
    query = request.GET.get("q")
    if query:
        qs = qs.filter(models.Q(numero__icontains=query) | models.Q(client__nom__icontains=query))
    rows = [
        "Numero,Client,Emis le,Statut,Total",
    ]
    for invoice in qs:
        rows.append(
            f"{invoice.numero},{invoice.client},{invoice.emis_le},{invoice.get_statut_display()},{invoice.total}"
        )
    data = "\n".join(rows)
    response = HttpResponse(data, content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=factures.csv"
    return response


def telematics_positions_json_view(request):
    data = fetch_traccar_positions()
    payload = []
    for item in data.positions:
        pos = item.get("position") or {}
        payload.append(
            {
                "name": item.get("name"),
                "status": item.get("status"),
                "lat": pos.get("latitude"),
                "lon": pos.get("longitude"),
                "speed": pos.get("speed"),
                "device_time": pos.get("deviceTime"),
            }
        )
    return JsonResponse({"ok": data.ok, "message": data.message, "positions": payload})


def _loss_alerts():
    threshold = getattr(settings, "LOSS_ALERT_LITERS", 50)
    alerts = []
    for delivery in DeliveryNote.objects.select_related("ordre").order_by("-livre_le")[:200]:
        if abs(delivery.ecart_litres) >= threshold:
            alerts.append(delivery)
    return alerts


def _fuel_drop_alerts():
    threshold = getattr(settings, "FUEL_DROP_ALERT_LITERS", 100)
    recent = FuelMeasurement.objects.select_related("trip", "compartment").order_by("-mesure_le")[:200]
    alerts = []
    last_by_key = {}
    for measurement in recent:
        key = (measurement.trip_id, measurement.compartment_id)
        last = last_by_key.get(key)
        if last:
            drop = last.niveau_litres - measurement.niveau_litres
            if drop >= threshold:
                alerts.append(
                    {
                        "trip": measurement.trip,
                        "compartment": measurement.compartment,
                        "drop_liters": drop,
                        "from_level": last.niveau_litres,
                        "to_level": measurement.niveau_litres,
                        "mesure_le": measurement.mesure_le,
                    }
                )
        last_by_key[key] = measurement
    return alerts


def _pick_osm_device(positions):
    for item in positions:
        pos = item.get("position") or {}
        lat = pos.get("latitude")
        lon = pos.get("longitude")
        if lat is not None and lon is not None:
            delta = 0.02
            bbox = f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}"
            return {"name": item.get("name"), "lat": lat, "lon": lon, "bbox": bbox}
    return None


def _garage_preventive_alerts():
    alerts = []
    today = timezone.localdate()
    active_services = GarageServiceType.objects.filter(actif=True).exclude(
        interval_km__isnull=True, interval_jours__isnull=True
    )
    vehicles = Vehicle.objects.order_by("immatriculation")

    for vehicle in vehicles:
        # Approximate current odometer with last recorded km_sortie in garage orders.
        current_km = (
            GarageWorkOrder.objects.filter(vehicle=vehicle, km_sortie__isnull=False)
            .order_by("-fin_reel", "-updated_at")
            .values_list("km_sortie", flat=True)
            .first()
        )

        for service in active_services:
            last_wo = (
                GarageWorkOrder.objects.filter(
                    vehicle=vehicle,
                    service_type=service,
                    statut=GarageWorkOrder.TERMINE,
                )
                .order_by("-fin_reel", "-updated_at")
                .first()
            )

            if not last_wo:
                continue

            due_reason = []
            due_level = "ok"
            days_remaining = None
            km_remaining = None

            if service.interval_jours:
                base_date = (last_wo.fin_reel.date() if last_wo.fin_reel else last_wo.updated_at.date())
                due_date = base_date + timedelta(days=service.interval_jours)
                days_remaining = (due_date - today).days
                if days_remaining <= 0:
                    due_reason.append("Echeance date depassee")
                    due_level = "danger"
                elif days_remaining <= 15:
                    due_reason.append("Echeance proche")
                    if due_level != "danger":
                        due_level = "warning"

            if service.interval_km and current_km is not None and last_wo.km_sortie is not None:
                due_km = last_wo.km_sortie + service.interval_km
                km_remaining = due_km - current_km
                if km_remaining <= 0:
                    due_reason.append("Echeance km depassee")
                    due_level = "danger"
                elif km_remaining <= 500:
                    due_reason.append("Echeance km proche")
                    if due_level != "danger":
                        due_level = "warning"

            if due_level != "ok":
                alerts.append(
                    {
                        "vehicle": vehicle,
                        "service": service,
                        "last_wo": last_wo,
                        "due_level": due_level,
                        "days_remaining": days_remaining,
                        "km_remaining": km_remaining,
                        "reason": ", ".join(due_reason) or "Alerte preventive",
                    }
                )

    # Critical alerts first.
    alerts.sort(key=lambda a: 0 if a["due_level"] == "danger" else 1)
    return alerts


def _filters_from_request(request):
    return {
        "day": request.GET.get("day", ""),
        "month": request.GET.get("month", ""),
        "year": request.GET.get("year", ""),
    }


def _apply_date_filters(request, qs, field_name):
    day = request.GET.get("day")
    month = request.GET.get("month")
    year = request.GET.get("year")
    if day:
        qs = qs.filter(**{field_name: day})
    if month:
        parts = month.split("-")
        if len(parts) == 2:
            qs = qs.filter(**{f"{field_name}__year": parts[0], f"{field_name}__month": parts[1]})
    if year:
        qs = qs.filter(**{f"{field_name}__year": year})
    return qs


def _build_finance_series(payments, expenses, salary_paid, salary_pending, credit_notes):
    series = {}

    def add_point(key, income=0, out=0):
        data = series.setdefault(key, {"income": 0, "out": 0})
        data["income"] += income
        data["out"] += out

    for p in payments:
        key = p.paye_le.strftime("%Y-%m")
        add_point(key, income=p.montant)

    for e in expenses:
        key = e.depense_le.strftime("%Y-%m")
        add_point(key, out=e.montant)

    for s in salary_paid:
        key = s.paye_le.strftime("%Y-%m")
        add_point(key, out=s.net)

    for s in salary_pending:
        key = s.periode_fin.strftime("%Y-%m")
        add_point(key, out=s.net)

    for c in credit_notes:
        key = c.emis_le.strftime("%Y-%m")
        add_point(key, out=c.montant)

    labels = sorted(series.keys())
    income = [series[k]["income"] for k in labels]
    out = [series[k]["out"] for k in labels]
    return {"labels": labels, "income": income, "out": out}


class GenericListView(ListView):
    template_name = "erp/generic_list.html"
    context_object_name = "items"
    title = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class GenericCreateView(CreateView):
    template_name = "erp/generic_form.html"
    title = ""
    success_url = reverse_lazy("erp:dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class GenericUpdateView(UpdateView):
    template_name = "erp/generic_form.html"
    title = ""
    success_url = reverse_lazy("erp:dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class GenericDeleteView(DeleteView):
    template_name = "erp/generic_confirm_delete.html"
    title = ""
    success_url = reverse_lazy("erp:dashboard")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class ClientList(GenericListView):
    model = Client
    title = "Clients"


class ClientCreate(GenericCreateView):
    model = Client
    form_class = ClientForm
    title = "Nouveau client"
    success_url = reverse_lazy("erp:client_list")


class ClientUpdate(GenericUpdateView):
    model = Client
    form_class = ClientForm
    title = "Modifier client"
    success_url = reverse_lazy("erp:client_list")


class ClientDelete(GenericDeleteView):
    model = Client
    title = "Supprimer client"
    success_url = reverse_lazy("erp:client_list")


class SiteList(GenericListView):
    model = Site
    title = "Sites / Dépôts"


class SiteCreate(GenericCreateView):
    model = Site
    form_class = SiteForm
    title = "Nouveau site"
    success_url = reverse_lazy("erp:site_list")


class SiteUpdate(GenericUpdateView):
    model = Site
    form_class = SiteForm
    title = "Modifier site"
    success_url = reverse_lazy("erp:site_list")


class SiteDelete(GenericDeleteView):
    model = Site
    title = "Supprimer site"
    success_url = reverse_lazy("erp:site_list")


class FuelTypeList(GenericListView):
    model = FuelType
    title = "Types de carburant"


class FuelTypeCreate(GenericCreateView):
    model = FuelType
    form_class = FuelTypeForm
    title = "Nouveau type de carburant"
    success_url = reverse_lazy("erp:fueltype_list")


class FuelTypeUpdate(GenericUpdateView):
    model = FuelType
    form_class = FuelTypeForm
    title = "Modifier type de carburant"
    success_url = reverse_lazy("erp:fueltype_list")


class FuelTypeDelete(GenericDeleteView):
    model = FuelType
    title = "Supprimer type de carburant"
    success_url = reverse_lazy("erp:fueltype_list")


class VehicleList(GenericListView):
    model = Vehicle
    title = "Camions"
    template_name = "erp/vehicle_list.html"

    def get_queryset(self):
        return Vehicle.objects.order_by("immatriculation")


class VehicleCreate(GenericCreateView):
    model = Vehicle
    form_class = VehicleForm
    title = "Nouveau camion"
    success_url = reverse_lazy("erp:vehicle_list")


class VehicleUpdate(GenericUpdateView):
    model = Vehicle
    form_class = VehicleForm
    title = "Modifier camion"
    success_url = reverse_lazy("erp:vehicle_list")


class VehicleDelete(GenericDeleteView):
    model = Vehicle
    title = "Supprimer camion"
    success_url = reverse_lazy("erp:vehicle_list")


class GarageWorkOrderList(ListView):
    model = GarageWorkOrder
    template_name = "erp/garage_workorder_list.html"
    context_object_name = "items"
    paginate_by = 30

    def get_queryset(self):
        qs = GarageWorkOrder.objects.select_related("vehicle", "driver", "service_type").order_by("-created_at")
        statut = self.request.GET.get("statut", "").strip()
        priorite = self.request.GET.get("priorite", "").strip()
        if statut:
            qs = qs.filter(statut=statut)
        if priorite:
            qs = qs.filter(priorite=priorite)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Ordres atelier"
        context["selected_statut"] = self.request.GET.get("statut", "")
        context["selected_priorite"] = self.request.GET.get("priorite", "")
        context["statut_choices"] = GarageWorkOrder.STATUT_CHOICES
        context["priorite_choices"] = GarageWorkOrder.PRIORITE_CHOICES
        return context


class GarageWorkOrderCreate(GenericCreateView):
    model = GarageWorkOrder
    form_class = GarageWorkOrderQuickForm
    title = "Nouvel ordre atelier (saisie rapide)"
    success_url = reverse_lazy("erp:garage_workorder_list")

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.reference = _build_workorder_reference()
        self.object.statut = GarageWorkOrder.OUVERT
        if not self.object.priorite:
            self.object.priorite = GarageWorkOrder.NORMALE
        self.object.save()
        return redirect(self.success_url)


class GarageWorkOrderUpdate(GenericUpdateView):
    model = GarageWorkOrder
    form_class = GarageWorkOrderForm
    title = "Modifier ordre atelier"
    success_url = reverse_lazy("erp:garage_workorder_list")


class GarageWorkOrderDelete(GenericDeleteView):
    model = GarageWorkOrder
    title = "Supprimer ordre atelier"
    success_url = reverse_lazy("erp:garage_workorder_list")


class GarageServiceTypeList(GenericListView):
    model = GarageServiceType
    title = "Catalogue services garage"
    template_name = "erp/garage_service_list.html"

    def get_queryset(self):
        return GarageServiceType.objects.order_by("code")


class GarageServiceTypeCreate(GenericCreateView):
    model = GarageServiceType
    form_class = GarageServiceTypeForm
    title = "Nouveau service garage"
    success_url = reverse_lazy("erp:garage_service_list")


class GarageServiceTypeUpdate(GenericUpdateView):
    model = GarageServiceType
    form_class = GarageServiceTypeForm
    title = "Modifier service garage"
    success_url = reverse_lazy("erp:garage_service_list")


class GarageServiceTypeDelete(GenericDeleteView):
    model = GarageServiceType
    title = "Supprimer service garage"
    success_url = reverse_lazy("erp:garage_service_list")


class GaragePartList(GenericListView):
    model = GaragePart
    title = "Stock pieces garage"
    template_name = "erp/garage_part_list.html"

    def get_queryset(self):
        return GaragePart.objects.order_by("designation")


class GaragePartCreate(GenericCreateView):
    model = GaragePart
    form_class = GaragePartForm
    title = "Nouvelle piece garage"
    success_url = reverse_lazy("erp:garage_part_list")


class GaragePartUpdate(GenericUpdateView):
    model = GaragePart
    form_class = GaragePartForm
    title = "Modifier piece garage"
    success_url = reverse_lazy("erp:garage_part_list")


class GaragePartDelete(GenericDeleteView):
    model = GaragePart
    title = "Supprimer piece garage"
    success_url = reverse_lazy("erp:garage_part_list")


class GarageWorkOrderDocumentList(GenericListView):
    model = GarageWorkOrderDocument
    title = "Documents atelier"

    def get_queryset(self):
        return GarageWorkOrderDocument.objects.select_related("workorder").order_by("-created_at")


class GarageWorkOrderDocumentCreate(GenericCreateView):
    model = GarageWorkOrderDocument
    form_class = GarageWorkOrderDocumentForm
    title = "Nouveau document atelier"
    success_url = reverse_lazy("erp:garage_document_list")


class GarageWorkOrderDocumentUpdate(GenericUpdateView):
    model = GarageWorkOrderDocument
    form_class = GarageWorkOrderDocumentForm
    title = "Modifier document atelier"
    success_url = reverse_lazy("erp:garage_document_list")


class GarageWorkOrderDocumentDelete(GenericDeleteView):
    model = GarageWorkOrderDocument
    title = "Supprimer document atelier"
    success_url = reverse_lazy("erp:garage_document_list")


class GaragePlanningView(TemplateView):
    template_name = "erp/garage_planning.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        workorders = GarageWorkOrder.objects.select_related("vehicle", "service_type").exclude(
            statut__in=[GarageWorkOrder.TERMINE, GarageWorkOrder.ANNULE]
        )
        columns = [
            (GarageWorkOrder.OUVERT, "Ouvert"),
            (GarageWorkOrder.DIAGNOSTIC, "Diagnostic"),
            (GarageWorkOrder.EN_ATTENTE_VALIDATION, "Attente validation"),
            (GarageWorkOrder.PLANIFIE, "Planifie"),
            (GarageWorkOrder.EN_COURS, "En cours"),
            (GarageWorkOrder.CONTROLE_QUALITE, "Controle qualite"),
        ]
        context["columns"] = [
            {"value": value, "label": label, "items": workorders.filter(statut=value).order_by("-priorite", "created_at")}
            for value, label in columns
        ]
        return context


@require_POST
def garage_workorder_move_status_view(request, pk):
    workorder = get_object_or_404(GarageWorkOrder, pk=pk)
    new_status = (request.POST.get("statut") or "").strip()
    valid_status = {v for v, _ in GarageWorkOrder.STATUT_CHOICES}
    if new_status not in valid_status:
        return JsonResponse({"ok": False, "message": "Statut invalide."}, status=400)
    workorder.statut = new_status
    if new_status == GarageWorkOrder.EN_COURS and not workorder.debut_reel:
        workorder.debut_reel = timezone.now()
    if new_status == GarageWorkOrder.TERMINE and not workorder.fin_reel:
        workorder.fin_reel = timezone.now()
    workorder.save(update_fields=["statut", "debut_reel", "fin_reel", "updated_at"])
    return JsonResponse({"ok": True, "statut": workorder.get_statut_display()})


def garage_workorder_pdf_view(request, pk):
    workorder = get_object_or_404(
        GarageWorkOrder.objects.select_related("vehicle", "driver", "service_type"),
        pk=pk,
    )
    currency = getattr(settings, "COMPANY_CURRENCY", "XOF")
    lines = [
        f"Date: {timezone.localdate()}",
        f"Ordre atelier: {workorder.reference}",
        f"Camion: {workorder.vehicle.immatriculation}",
        f"Chauffeur: {workorder.driver or '-'}",
        f"Service: {workorder.service_type or '-'}",
        f"Priorite: {workorder.get_priorite_display()}",
        f"Statut: {workorder.get_statut_display()}",
        f"Ouvert le: {workorder.ouvert_le}",
        f"Planifie: {workorder.planifie_debut or '-'} -> {workorder.planifie_fin or '-'}",
        f"Reel: {workorder.debut_reel or '-'} -> {workorder.fin_reel or '-'}",
        f"KM entree/sortie: {workorder.km_entree or '-'} / {workorder.km_sortie or '-'}",
        "",
        f"Panne signalee: {workorder.panne_signalee or '-'}",
        f"Diagnostic: {workorder.diagnostic or '-'}",
        f"Travaux realises: {workorder.travaux_realises or '-'}",
        f"Cout pieces: {workorder.cout_pieces} {currency}",
        f"Main d'oeuvre: {workorder.heures_main_oeuvre} h x {workorder.taux_horaire} = {workorder.cout_main_oeuvre} {currency}",
        f"Total: {workorder.cout_total} {currency}",
        "",
        f"Signature client (nom): {workorder.signature_client_nom or '-'}",
        "Signature client: ___________________________",
        "Signature atelier: __________________________",
    ]
    pdf_bytes = simple_pdf(f"Ordre Atelier {workorder.reference}", lines)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="ordre-atelier-{workorder.reference}.pdf"'
    return response


class DriverList(GenericListView):
    model = Driver
    title = "Chauffeurs"
    template_name = "erp/driver_list.html"

    def get_queryset(self):
        return Driver.objects.prefetch_related("apprentis").order_by("nom", "prenom")


class DriverCreate(GenericCreateView):
    model = Driver
    form_class = DriverQuickForm
    title = "Nouveau chauffeur (saisie rapide)"
    success_url = reverse_lazy("erp:driver_list")


class DriverUpdate(GenericUpdateView):
    model = Driver
    form_class = DriverForm
    title = "Modifier chauffeur"
    success_url = reverse_lazy("erp:driver_list")


class DriverDelete(GenericDeleteView):
    model = Driver
    title = "Supprimer chauffeur"
    success_url = reverse_lazy("erp:driver_list")


class ApprenticeList(GenericListView):
    model = Apprentice
    title = "Apprentis"
    template_name = "erp/apprentice_list.html"

    def get_queryset(self):
        return Apprentice.objects.select_related("chauffeur").order_by("nom", "prenom")


class ApprenticeCreate(GenericCreateView):
    model = Apprentice
    form_class = ApprenticeForm
    title = "Nouvel apprenti"
    success_url = reverse_lazy("erp:apprentice_list")


class ApprenticeUpdate(GenericUpdateView):
    model = Apprentice
    form_class = ApprenticeForm
    title = "Modifier apprenti"
    success_url = reverse_lazy("erp:apprentice_list")


class ApprenticeDelete(GenericDeleteView):
    model = Apprentice
    title = "Supprimer apprenti"
    success_url = reverse_lazy("erp:apprentice_list")


class EmployeeList(GenericListView):
    model = Employee
    title = "Personnel"
    template_name = "erp/employee_list.html"

    def get_queryset(self):
        return Employee.objects.order_by("nom", "prenom")


class EmployeeCreate(GenericCreateView):
    model = Employee
    form_class = EmployeeForm
    title = "Nouveau personnel"
    success_url = reverse_lazy("erp:employee_list")


class EmployeeUpdate(GenericUpdateView):
    model = Employee
    form_class = EmployeeForm
    title = "Modifier personnel"
    success_url = reverse_lazy("erp:employee_list")


class EmployeeDelete(GenericDeleteView):
    model = Employee
    title = "Supprimer personnel"
    success_url = reverse_lazy("erp:employee_list")


class SalaryPaymentList(GenericListView):
    model = SalaryPayment
    title = "Salaires"
    template_name = "erp/salary_list.html"

    def get_queryset(self):
        qs = SalaryPayment.objects.select_related("employee").order_by("-periode_fin")
        qs = _apply_date_filters(self.request, qs, "periode_fin")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filters"] = _filters_from_request(self.request)
        return context


class SalaryPaymentCreate(GenericCreateView):
    model = SalaryPayment
    form_class = SalaryPaymentForm
    title = "Nouveau salaire"
    success_url = reverse_lazy("erp:salary_list")


class SalaryPaymentUpdate(GenericUpdateView):
    model = SalaryPayment
    form_class = SalaryPaymentForm
    title = "Modifier salaire"
    success_url = reverse_lazy("erp:salary_list")


class SalaryPaymentDelete(GenericDeleteView):
    model = SalaryPayment
    title = "Supprimer salaire"
    success_url = reverse_lazy("erp:salary_list")


class PaymentListView(ListView):
    template_name = "erp/payment_list.html"
    context_object_name = "items"

    def get_queryset(self):
        qs = Payment.objects.select_related("invoice", "invoice__client").order_by("-paye_le")
        qs = _apply_date_filters(self.request, qs, "paye_le")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Encaissements"
        context["filters"] = _filters_from_request(self.request)
        return context


class CreditNoteListView(ListView):
    template_name = "erp/creditnote_list.html"
    context_object_name = "items"

    def get_queryset(self):
        qs = CreditNote.objects.select_related("invoice", "invoice__client").order_by("-emis_le")
        qs = _apply_date_filters(self.request, qs, "emis_le")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Avoirs"
        context["filters"] = _filters_from_request(self.request)
        return context


class ExpenseList(GenericListView):
    model = Expense
    title = "Dépenses"
    template_name = "erp/expense_list.html"

    def get_queryset(self):
        qs = Expense.objects.order_by("-depense_le")
        qs = _apply_date_filters(self.request, qs, "depense_le")
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filters"] = _filters_from_request(self.request)
        return context


class ExpenseCreate(GenericCreateView):
    model = Expense
    form_class = ExpenseForm
    title = "Nouvelle dépense"
    success_url = reverse_lazy("erp:expense_list")


class ExpenseUpdate(GenericUpdateView):
    model = Expense
    form_class = ExpenseForm
    title = "Modifier dépense"
    success_url = reverse_lazy("erp:expense_list")


class ExpenseDelete(GenericDeleteView):
    model = Expense
    title = "Supprimer dépense"
    success_url = reverse_lazy("erp:expense_list")


class FinanceReportView(TemplateView):
    template_name = "erp/finance_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = _filters_from_request(self.request)

        payments = _apply_date_filters(self.request, Payment.objects.all(), "paye_le")
        credit_notes = _apply_date_filters(self.request, CreditNote.objects.all(), "emis_le")
        expenses = _apply_date_filters(self.request, Expense.objects.all(), "depense_le")

        salary_paid = _apply_date_filters(
            self.request, SalaryPayment.objects.filter(paye_le__isnull=False), "paye_le"
        )
        salary_pending = _apply_date_filters(
            self.request, SalaryPayment.objects.filter(paye_le__isnull=True), "periode_fin"
        )

        total_income = sum(p.montant for p in payments)
        total_credit_notes = sum(c.montant for c in credit_notes)
        total_expenses = sum(e.montant for e in expenses)
        total_salaries = sum(s.net for s in salary_paid) + sum(s.net for s in salary_pending)
        total_out = total_expenses + total_salaries + total_credit_notes
        net = total_income - total_out

        context["filters"] = filters
        context["totals"] = {
            "income": total_income,
            "expenses": total_expenses,
            "salaries": total_salaries,
            "credit_notes": total_credit_notes,
            "out": total_out,
            "net": net,
        }
        context["series"] = _build_finance_series(payments, expenses, salary_paid, salary_pending, credit_notes)
        return context


def finance_report_csv_view(request):
    payments = _apply_date_filters(request, Payment.objects.all(), "paye_le")
    credit_notes = _apply_date_filters(request, CreditNote.objects.all(), "emis_le")
    expenses = _apply_date_filters(request, Expense.objects.all(), "depense_le")
    salary_paid = _apply_date_filters(request, SalaryPayment.objects.filter(paye_le__isnull=False), "paye_le")
    salary_pending = _apply_date_filters(request, SalaryPayment.objects.filter(paye_le__isnull=True), "periode_fin")

    rows = ["Date,Type,Description,Montant"]
    for p in payments:
        rows.append(f"{p.paye_le},Encaissement,Facture {p.invoice.numero},{p.montant}")
    for e in expenses:
        rows.append(f"{e.depense_le},Dépense,{e.description},{e.montant}")
    for s in salary_paid:
        rows.append(f"{s.paye_le},Salaire,{s.employee},{s.net}")
    for s in salary_pending:
        rows.append(f"{s.periode_fin},Salaire (période),{s.employee},{s.net}")
    for c in credit_notes:
        rows.append(f"{c.emis_le},Avoir,{c.raison},{c.montant}")

    data = "\n".join(rows)
    response = HttpResponse(data, content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=rapport-financier.csv"
    return response

class ContributionTypeList(GenericListView):
    model = ContributionType
    title = "Types de cotisations"


class ContributionTypeCreate(GenericCreateView):
    model = ContributionType
    form_class = ContributionTypeForm
    title = "Nouveau type de cotisation"
    success_url = reverse_lazy("erp:contribution_type_list")


class ContributionTypeUpdate(GenericUpdateView):
    model = ContributionType
    form_class = ContributionTypeForm
    title = "Modifier type de cotisation"
    success_url = reverse_lazy("erp:contribution_type_list")


class ContributionTypeDelete(GenericDeleteView):
    model = ContributionType
    title = "Supprimer type de cotisation"
    success_url = reverse_lazy("erp:contribution_type_list")


class SalaryContributionList(GenericListView):
    model = SalaryContribution
    title = "Cotisations"


class SalaryContributionCreate(GenericCreateView):
    model = SalaryContribution
    form_class = SalaryContributionForm
    title = "Nouvelle cotisation"
    success_url = reverse_lazy("erp:salary_contribution_list")


class SalaryContributionUpdate(GenericUpdateView):
    model = SalaryContribution
    form_class = SalaryContributionForm
    title = "Modifier cotisation"
    success_url = reverse_lazy("erp:salary_contribution_list")


class SalaryContributionDelete(GenericDeleteView):
    model = SalaryContribution
    title = "Supprimer cotisation"
    success_url = reverse_lazy("erp:salary_contribution_list")


class LeaveRequestList(GenericListView):
    model = LeaveRequest
    title = "Congés"


class LeaveRequestCreate(GenericCreateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    title = "Nouveau congé"
    success_url = reverse_lazy("erp:leave_list")


class LeaveRequestUpdate(GenericUpdateView):
    model = LeaveRequest
    form_class = LeaveRequestForm
    title = "Modifier congé"
    success_url = reverse_lazy("erp:leave_list")


class LeaveRequestDelete(GenericDeleteView):
    model = LeaveRequest
    title = "Supprimer congé"
    success_url = reverse_lazy("erp:leave_list")


class LeaveCalendarView(TemplateView):
    template_name = "erp/leave_calendar.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leaves = LeaveRequest.objects.select_related("employee").all()
        context["leave_json"] = json.dumps(
            [
                {
                    "employee": str(leave.employee),
                    "type": leave.get_type_absence_display(),
                    "status": leave.get_statut_display(),
                    "start": leave.date_debut.isoformat(),
                    "end": leave.date_fin.isoformat(),
                }
                for leave in leaves
            ]
        )
        return context
class TransportOrderList(GenericListView):
    model = TransportOrder
    title = "Ordres de transport"


class TransportOrderCreate(GenericCreateView):
    model = TransportOrder
    form_class = TransportOrderForm
    title = "Nouvel ordre de transport"
    success_url = reverse_lazy("erp:order_list")


class TransportOrderUpdate(GenericUpdateView):
    model = TransportOrder
    form_class = TransportOrderForm
    title = "Modifier ordre de transport"
    success_url = reverse_lazy("erp:order_list")


class TransportOrderDelete(GenericDeleteView):
    model = TransportOrder
    title = "Supprimer ordre de transport"
    success_url = reverse_lazy("erp:order_list")


class DeliveryNoteList(GenericListView):
    model = DeliveryNote
    title = "Bons de livraison"


class DeliveryNoteCreate(GenericCreateView):
    model = DeliveryNote
    form_class = DeliveryNoteForm
    title = "Nouveau bon de livraison"
    success_url = reverse_lazy("erp:delivery_list")


class DeliveryNoteUpdate(GenericUpdateView):
    model = DeliveryNote
    form_class = DeliveryNoteForm
    title = "Modifier bon de livraison"
    success_url = reverse_lazy("erp:delivery_list")


class DeliveryNoteDelete(GenericDeleteView):
    model = DeliveryNote
    title = "Supprimer bon de livraison"
    success_url = reverse_lazy("erp:delivery_list")




