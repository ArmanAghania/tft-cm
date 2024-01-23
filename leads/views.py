import logging
import datetime
from typing import Any
from django.contrib import messages
from django.core.mail import send_mail
from django.http.response import JsonResponse
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.views import generic, View
from agents.mixins import OrganisorAndLoginRequiredMixin
from .models import (
    Lead,
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
    UserProfile,
    TelegramMessage,
)
from .forms import (
    LeadModelForm,
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
    AssignLeadsForm,
    RegisterAgentModelForm,
    LeadAgentForm,
)
from .serializers import (
    LeadSerializer,
    AgentPerformanceSerializer,
    DailyPerformanceSerializer,
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
from django.forms import modelformset_factory, formset_factory
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
from django.http import HttpResponseNotFound
from django.http import StreamingHttpResponse
from django import forms
from django.db.models import (
    Q,
    Count,
    Case,
    When,
    IntegerField,
    Avg,
    F,
    Value,
    BooleanField,
)
from django.db import connection
from django.db.models.functions import TruncDate, TruncMonth, TruncYear, TruncDay
from django.utils.timezone import now
from jalali_date import datetime2jalali
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST
from collections import Counter, defaultdict
from django.utils.dateformat import DateFormat
from django.contrib.auth.views import LoginView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets, status
import io

logger = logging.getLogger(__name__)

# CRUD+L - Create, Retrieve, Update and Delete + List


class SignupView(generic.CreateView):
    template_name = "registration/signup.html"
    form_class = CustomUserCreationForm

    def get_success_url(self):
        return reverse("login")


class CustomLoginView(LoginView):
    template_name = "registration/login.html"  # Specify your login template here

    def get_redirect_url(self):
        url = super().get_redirect_url()
        if self.request.user.is_authenticated:
            if self.request.user.is_register_agent:
                return reverse("leads:recent-sales")  # Change to your recent sales URL
            else:
                return reverse("leads:lead-list")  # Change to your lead list URL
        return url


class LandingPageView(generic.TemplateView):
    template_name = "landing.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if request.user.is_register_agent:
                return redirect("leads:recent-sale")
            else:
                return redirect("leads:lead-list")
        return super().dispatch(request, *args, **kwargs)


class LeadStatsAPIView(APIView):
    def get(self, request, organisation_id):
        user = self.request.user
        organisation = user.userprofile

        # Get current Jalali date
        jalali_today = khayyam.JalaliDate.today()
        first_day_of_jalali_month = khayyam.JalaliDate(
            jalali_today.year, jalali_today.month, 1
        ).todate()

        # Fetching Total Leads and Converted Leads
        total_leads = Lead.objects.filter(organisation=organisation).count()
        converted_leads = Lead.objects.filter(
            organisation=organisation, total_sale__gt=0
        ).count()

        # Fetching Current Jalali Month Leads and Converted Leads
        monthly_leads = Lead.objects.filter(
            organisation=organisation, date_assigned__gte=first_day_of_jalali_month
        ).count()
        monthly_converted = Lead.objects.filter(
            organisation=organisation,
            total_sale__gt=0,
            date_assigned__gte=first_day_of_jalali_month,
        ).count()

        data = {
            "total_stats": {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "conversion_rate": (converted_leads / total_leads) * 100
                if total_leads
                else 0,
            },
            "monthly_stats": {
                "total_leads": monthly_leads,
                "converted_leads": monthly_converted,
                "conversion_rate": (monthly_converted / monthly_leads) * 100
                if monthly_leads
                else 0,
            },
        }
        return Response(data)


class AgeDistributionAPIView(OrganisorAndLoginRequiredMixin, APIView):
    def get(self, request, organisation_id):
        organisation = UserProfile.objects.get(pk=organisation_id)
        age_distribution = self.get_age_distribution_of_sales(organisation)
        return Response(age_distribution)

    def get_age_distribution_of_sales(self, organisation):
        age_distribution = defaultdict(int)
        converted_leads = Lead.objects.filter(
            organisation=organisation, age__isnull=False, total_sale__gt=0
        )

        for lead in converted_leads:
            age = lead.age
            if age >= 100:
                age_group = "100+"
            else:
                age_group = f"{(age // 10) * 10}-{(age // 10) * 10 + 9}"
            age_distribution[age_group] += 1

        # Custom sorting: Sort by age groups, but put '100+' at the end
        sorted_age_distribution = dict(
            sorted(
                age_distribution.items(), key=lambda item: (item[0] == "100+", item[0])
            )
        )
        print(sorted_age_distribution)

        return sorted_age_distribution


class LeadSourceAPIView(OrganisorAndLoginRequiredMixin, APIView):
    def get(self, request, organisation_id):
        organisation = UserProfile.objects.get(pk=organisation_id)
        lead_source_data = self.get_lead_source_analysis(organisation)
        return Response(lead_source_data)

    def get_lead_source_analysis(self, organisation):
        source_data = (
            Lead.objects.filter(organisation=organisation)
            .values("source__name")
            .annotate(count=Count("id"))
            .order_by("source__name")
        )
        labels = [entry["source__name"] for entry in source_data]
        values = [entry["count"] for entry in source_data]
        return {"labels": labels, "values": values}


class MonthlySalesAPIView(APIView):
    def get(self, request, organisation_id):
        organisation = UserProfile.objects.get(pk=organisation_id)
        sales = Sale.objects.filter(organisation=organisation)

        monthly_sales = defaultdict(int)
        for sale in sales:
            # Convert sale date to Jalali
            jalali_date = khayyam.JalaliDate(sale.date)
            jalali_month_year = f"{jalali_date.year}-{jalali_date.month}"
            monthly_sales[jalali_month_year] += sale.amount

        sorted_monthly_sales = dict(sorted(monthly_sales.items()))

        return Response(sorted_monthly_sales)


class MonthlyLeadTrendsAPIView(APIView):
    def get(self, request, organisation_id):
        organisation = UserProfile.objects.get(pk=organisation_id)
        jalali_today = khayyam.JalaliDate.today()
        first_day_of_month = khayyam.JalaliDate(
            jalali_today.year, jalali_today.month, 1
        ).todate()

        leads = (
            Lead.objects.filter(
                organisation=organisation, date_added__gte=first_day_of_month
            )
            .annotate(day=TruncDay("date_added"))
            .values("day")
            .annotate(
                total=Count("id"), converted=Count("id", filter=Q(total_sale__gt=0))
            )
            .order_by("day")
        )

        lead_trends = {
            lead["day"].strftime("%Y-%m-%d"): {
                "total": lead["total"],
                "converted": lead["converted"],
            }
            for lead in leads
        }

        return Response(lead_trends)


class DashboardView(LoginRequiredMixin, generic.TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get current Jalali date
        jalali_today = khayyam.JalaliDate.today()
        first_day_of_jalali_month = khayyam.JalaliDate(
            jalali_today.year, jalali_today.month, 1
        ).todate()

        if user.is_organisor:
            organisation = user.userprofile
            leads = Lead.objects.filter(organisation=organisation)
            sales = Sale.objects.filter(organisation=organisation)
            # Aggregate data for the entire organisation
            context["total_leads"] = Lead.objects.filter(
                organisation=organisation
            ).count()
            context["total_sales"] = Sale.objects.filter(
                organisation=organisation
            ).aggregate(Sum("amount"))
            context["total_monthly_leads"] = Lead.objects.filter(
                organisation=organisation, date_assigned__gte=first_day_of_jalali_month
            ).count()
            context["total_monthly_sales"] = Lead.objects.filter(
                organisation=organisation,
                total_sale__gt=0,
                date_assigned__gte=first_day_of_jalali_month,
            ).count()
            context["monthly_sales_performance"] = self.get_monthly_sales_performance(
                organisation
            )
            context["yearly_lead_trends"] = self.get_yearly_lead_trends(organisation)
            context["team_performance"] = self.get_team_performance(organisation)
            context["sales_by_agent"] = self.get_sales_by_agent(organisation)
            context["lead_conversion_over_time"] = self.get_lead_conversion_over_time(
                organisation
            )
            context["regional_performance"] = self.get_regional_performance(
                organisation
            )
            context["client_demographics"] = self.get_client_demographics(organisation)
            context["predictive_insights"] = self.get_predictive_insights(organisation)
            context["lead_response_times"] = self.get_lead_response_times(organisation)
            context["financial_metrics"] = self.get_detailed_financial_metrics(
                organisation
            )
            context["trend_comparisons"] = self.get_trend_comparisons(organisation)
            # Add more metrics as needed

            context.update(
                {
                    "total_leads": leads.count(),
                    "total_sales": sales.aggregate(total_amount=Sum("amount")),
                    "conversion_rate": self.calculate_conversion_rate(leads),
                    "sales_trends": self.get_sales_trends(sales),
                    "agent_performance": self.get_agent_performance(organisation),
                    # Add more metrics and analysis as needed
                }
            )
        elif user.is_agent:
            agent = user.agent
            organisation = agent.organisation
            agent_leads = Lead.objects.filter(agent__user=user)
            agent_sales = Sale.objects.filter(agent__user=user)
            # Filter for the agent that is logged in
            context["agent_leads"] = Lead.objects.filter(
                organisation=organisation, agent__user=user
            ).count()
            context["agent_sales"] = Sale.objects.filter(
                organisation=organisation, agent__user=user
            ).aggregate(Sum("amount"))
            context["agent_interactions"] = self.get_agent_lead_interactions(agent)
            context["agent_sales_trends"] = self.get_agent_sales_trends(agent)
            context["agent_conversion_rate"] = self.get_agent_lead_conversion_rate(
                agent
            )
            context["agent_client_demographics"] = self.get_agent_client_demographics(
                agent
            )
            context["performance_comparison"] = self.get_agent_performance_comparison(
                agent
            )
            context["activity_heatmap"] = self.get_agent_activity_heatmap(agent)
            context["lead_source_breakdown"] = self.get_agent_lead_source_breakdown(
                agent
            )
            # context['success_rate_by_category'] = self.get_agent_success_rate_by_category(agent)
            # Add more agent-specific metrics as needed

            context.update(
                {
                    "agent_leads": agent_leads.count(),
                    "agent_sales": agent_sales.aggregate(total_amount=Sum("amount")),
                    "agent_conversion_rate": self.calculate_conversion_rate(
                        agent_leads
                    ),
                    # Add more agent-specific metrics and analysis
                }
            )

        # Additional common context data if needed
        # context['common_data'] = ...

        #############
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

        # Calculate agent sales data
        agent = self.request.user.id
        today = JalaliDate.today()  # Use JalaliDate from persiantools

        # Calculate the start of the week (Saturday) and month (first day of the month)
        # Convert JalaliDate to a Gregorian date
        gregorian_today = today.to_gregorian()

        # Find out how many days we are away from the last Saturday
        # +1 to shift from Monday-start to Sunday-start, another +1 to make Sunday = 1, Monday = 2, ..., Saturday = 7
        days_since_last_saturday = gregorian_today.weekday() + 2

        # Subtract those days
        # % 7 makes sure that if today is Saturday, we subtract 0 days
        start_of_week_gregorian = gregorian_today - timedelta(
            days=days_since_last_saturday % 7
        )

        # Convert back to JalaliDate
        start_of_week = JalaliDate(start_of_week_gregorian)
        start_of_month = today.replace(day=1)

        base_filter_args = {}
        if user.is_organisor:
            # Aggregate sales
            daily_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile, date__date=today.to_gregorian()
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            weekly_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_week.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            monthly_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            total_sales = (
                Sale.objects.filter(organisation=user.userprofile).aggregate(
                    Sum("amount")
                )["amount__sum"]
                or 0
            )
        elif user.is_agent:
            # Aggregate sales
            daily_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date=today.to_gregorian(),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            weekly_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date__range=(
                        start_of_week.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            monthly_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            total_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation, agent=user.agent
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )

        context["sales_data"] = {
            "daily_sales": daily_sales,
            "weekly_sales": weekly_sales,
            "monthly_sales": monthly_sales,
            "total_sales": total_sales,
        }

        if user.is_organisor:
            # Filter leads for the organisation in the last month
            total_leads = Lead.objects.filter(
                organisation=user.userprofile,
                date_assigned__date__range=(
                    start_of_month.to_gregorian(),
                    today.to_gregorian(),
                ),
            ).count()
            total_leads_overall = Lead.objects.filter(
                organisation=user.userprofile
            ).count()

            print(total_leads)
            # Filter sales made by the organisation in the last month
            converted_leads = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                )
                .values("lead")
                .distinct()
                .count()
            )
            converted_leads_overall = (
                Sale.objects.filter(organisation=user.userprofile)
                .values("lead")
                .distinct()
                .count()
            )

            print(converted_leads)
            if total_leads == 0:
                percentage = 0
            else:
                percentage = (converted_leads / total_leads) * 100

            if total_leads_overall == 0:
                percentage_overall = 0
            else:
                percentage_overall = (
                    converted_leads_overall / total_leads_overall
                ) * 100

            agents_data = {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "percentage": percentage,
                "total_leads_overall": total_leads_overall,
                "converted_leads_overall": converted_leads_overall,
                "percentage_overall": percentage_overall,
            }

        else:
            # Filter leads for the agent in the last month
            total_leads = Lead.objects.filter(
                organisation=user.agent.organisation,
                agent__user=user,
                date_assigned__date__range=(
                    start_of_month.to_gregorian(),
                    today.to_gregorian(),
                ),
            ).count()
            total_leads_overall = Lead.objects.filter(
                organisation=user.agent.organisation, agent__user=user
            ).count()

            # Filter sales made by the agent in the last month
            converted_leads = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    lead__agent__user=user,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                )
                .values("lead")
                .distinct()
                .count()
            )
            converted_leads_overall = (
                Sale.objects.filter(
                    organisation=user.agent.organisation, lead__agent__user=user
                )
                .values("lead")
                .distinct()
                .count()
            )

            if total_leads == 0:
                percentage = 0
            else:
                percentage = (converted_leads / total_leads) * 100

            if total_leads_overall == 0:
                percentage_overall = 0
            else:
                percentage_overall = (
                    converted_leads_overall / total_leads_overall
                ) * 100

            agents_data = {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "percentage": percentage,
                "total_leads_overall": total_leads_overall,
                "converted_leads_overall": converted_leads_overall,
                "percentage_overall": percentage_overall,
            }

        context["agents_data"] = agents_data
        ##############

        return context

    def calculate_conversion_rate(self, leads):
        converted_leads = leads.filter(category__name="Converted").count()
        total_leads = leads.count()
        return (converted_leads / total_leads) * 100 if total_leads else 0

    def get_sales_trends(self, sales):
        trend_data = {}
        for i in range(7):
            date = timezone.now().date() - timedelta(days=i)
            formatted_date = DateFormat(date).format("Y-m-d")  # Format date as string
            trend_data[formatted_date] = (
                sales.filter(date__date=date)
                .aggregate(total_amount=Sum("amount"))
                .get("total_amount", 0)
            )
        return trend_data

    def get_agent_performance(self, organisation):
        # Example: Aggregate data per agent
        agents = Agent.objects.filter(organisation=organisation)
        performance_data = {}
        for agent in agents:
            agent_leads = Lead.objects.filter(agent=agent, organisation=organisation)
            performance_data[agent.user.username] = {
                "leads": agent_leads.count(),
                "sales": agent_leads.aggregate(total_amount=Sum("total_sale")),
                "conversion_rate": self.calculate_conversion_rate(agent_leads),
            }
        return performance_data

    def get_lead_source_analysis(self, organisation):
        source_data = (
            Lead.objects.filter(organisation=organisation)
            .values("source__name")
            .annotate(count=Count("id"))
            .order_by("source__name")
        )
        labels = [entry["source__name"] for entry in source_data]
        values = [entry["count"] for entry in source_data]
        return labels, values

    def get_age_distribution_of_sales(self, organisation):
        age_distribution = defaultdict(int)
        sales = Sale.objects.filter(organisation=organisation, lead__age__isnull=False)

        for sale in sales:
            age = sale.lead.age
            if age >= 100:
                age_group = "100+"
            else:
                age_group = f"{(age // 10) * 10}-{(age // 10) * 10 + 9}"
            age_distribution[age_group] += 1

        return dict(sorted(age_distribution.items()))

    def age_distribution_api(self, request, organisation_id):
        if not request.user.is_authenticated or not request.user.is_organisor:
            return JsonResponse({"error": "Unauthorized"}, status=401)

        organisation = UserProfile.objects.get(pk=organisation_id)
        age_distribution = self.get_age_distribution_of_sales(organisation)

        return JsonResponse(age_distribution)

    def get_monthly_sales_performance(self, organisation):
        # Monthly sales performance
        monthly_sales = (
            Sale.objects.filter(organisation=organisation)
            .annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )
        return {
            entry["month"].strftime("%Y-%m"): entry["total"] for entry in monthly_sales
        }

    def get_yearly_lead_trends(self, organisation):
        # Yearly lead trends
        yearly_leads = (
            Lead.objects.filter(organisation=organisation)
            .annotate(year=TruncYear("date_added"))
            .values("year")
            .annotate(count=Count("id"))
            .order_by("year")
        )
        return {entry["year"].strftime("%Y"): entry["count"] for entry in yearly_leads}

    def get_team_performance(self, organisation):
        # Performance metrics for each team
        team_performance = {}
        teams = Team.objects.filter(organisation=organisation)
        for team in teams:
            team_sales = Sale.objects.filter(agent__in=team.members.all())
            team_performance[team.name] = {
                "total_sales": team_sales.aggregate(Sum("amount")),
                "average_sale": team_sales.aggregate(Avg("amount")),
                "total_leads": Lead.objects.filter(
                    agent__in=team.members.all()
                ).count(),
            }
            return team_performance

    def get_sales_by_agent(self, organisation):
        # Sales breakdown by agent
        agent_sales = (
            Sale.objects.filter(organisation=organisation)
            .values("agent__user__username")
            .annotate(total_sales=Sum("amount"))
        )
        return {
            entry["agent__user__username"]: entry["total_sales"]
            for entry in agent_sales
        }

    def get_lead_conversion_over_time(self, organisation):
        # Conversion rates over time (e.g., monthly)
        conversion_data = {}
        leads_by_month = (
            Lead.objects.filter(organisation=organisation)
            .annotate(month=TruncMonth("date_added"))
            .values("month")
            .annotate(total=Count("id"))
        )
        for month_data in leads_by_month:
            month = month_data["month"]
            total_leads = month_data["total"]
            converted_leads = Lead.objects.filter(
                organisation=organisation,
                category__name="Converted",
                date_added__month=month.month,
                date_added__year=month.year,
            ).count()
            conversion_rate = (
                (converted_leads / total_leads) * 100 if total_leads else 0
            )
            conversion_data[month.strftime("%Y-%m")] = conversion_rate
        return conversion_data

    def get_regional_performance(self, organisation):
        # Performance metrics based on regions (city, state, etc.)
        regional_performance = (
            Lead.objects.filter(organisation=organisation)
            .values("city")
            .annotate(total_sales=Sum("sale__amount"), lead_count=Count("id"))
            .order_by("-total_sales")
        )
        return list(regional_performance)

    def get_client_demographics(self, organisation):
        # Analyzing demographics of clients (age, job, etc.)
        demographics = (
            Lead.objects.filter(organisation=organisation, sale__isnull=False)
            .values("age", "job")
            .annotate(count=Count("id"))
        )
        return list(demographics)

    def get_predictive_insights(self, organisation):
        # Predictive insights based on historical data
        # Example: Predicting future sales trends or lead conversions
        # Implement your predictive logic here, possibly using machine learning or statistical models
        return "Predictive insights data"

    def get_lead_response_times(self, organisation):
        # Calculate average lead response time
        response_times = (
            Lead.objects.filter(organisation=organisation)
            .annotate(response_time=F("date_modified") - F("date_added"))
            .aggregate(average_response_time=Avg("response_time"))
        )
        return response_times

    def get_detailed_financial_metrics(self, organisation):
        # Detailed financial metrics like profit margins, cost analysis, etc.
        financial_data = {
            "profit_margin": self.calculate_profit_margin(organisation),
            # Other financial metrics
        }
        return financial_data

    def get_trend_comparisons(self, organisation):
        # Comparing current trends with past periods (e.g., month-over-month, year-over-year)
        current_month_sales = self.get_sales_in_month(
            organisation, timezone.now().month
        )
        previous_month_sales = self.get_sales_in_month(
            organisation, timezone.now().month - 1
        )
        trend_comparison = {
            "current_month": current_month_sales,
            "previous_month": previous_month_sales,
            # Other comparisons
        }
        return trend_comparison

    # Helper methods for financial metrics, trend comparisons, etc.
    def calculate_profit_margin(self, organisation):
        # Implement your profit margin calculation
        return "Profit margin data"

    def get_sales_in_month(self, organisation, month):
        # Get sales in a specific month
        sales = Sale.objects.filter(
            organisation=organisation, date__month=month
        ).aggregate(total=Sum("amount"))
        return sales

    def get_agent_lead_interactions(self, agent):
        # Analysis of the agent's interactions with leads
        interactions = (
            FollowUp.objects.filter(lead__agent=agent)
            .annotate(date=F("date_added"))
            .values("date")
            .annotate(count=Count("id"))
            .order_by("-date")
        )
        return list(interactions)

    def get_agent_sales_trends(self, agent):
        # Sales trends for the agent
        sales_trends = (
            Sale.objects.filter(agent=agent)
            .annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("-month")
        )
        return {
            entry["month"].strftime("%Y-%m"): entry["total"] for entry in sales_trends
        }

    def get_agent_lead_conversion_rate(self, agent):
        # Lead conversion rate for the agent
        total_leads = Lead.objects.filter(agent=agent).count()
        converted_leads = Lead.objects.filter(
            agent=agent, category__name="Converted"
        ).count()
        return (converted_leads / total_leads) * 100 if total_leads else 0

    def get_agent_client_demographics(self, agent):
        # Client demographics for leads handled by the agent
        demographics = (
            Lead.objects.filter(agent=agent, sale__isnull=False)
            .values("age", "job")
            .annotate(count=Count("id"))
        )
        return list(demographics)

    def get_agent_performance_comparison(self, agent):
        # Compare the agent's performance against the average in the organisation
        org_average_sales = Sale.objects.filter(
            organisation=agent.organisation
        ).aggregate(avg_sales=Avg("amount"))["avg_sales"]
        agent_sales = Sale.objects.filter(agent=agent).aggregate(
            total=Sum("amount"), avg_sales=Avg("amount")
        )
        comparison = {
            "agent_total_sales": agent_sales["total"],
            "agent_avg_sales": agent_sales["avg_sales"],
            "org_avg_sales": org_average_sales,
        }
        return comparison

    def get_agent_activity_heatmap(self, agent):
        # Generate an activity heatmap for the agent (e.g., number of follow-ups per day)
        activities = FollowUp.objects.filter(lead__agent=agent).dates(
            "date_added", "day"
        )
        activity_count = Counter(activities)
        return dict(activity_count)

    def get_agent_lead_source_breakdown(self, agent):
        # Breakdown of leads by source for the agent
        lead_sources = (
            Lead.objects.filter(agent=agent)
            .values("source__name")
            .annotate(count=Count("id"))
        )
        return {entry["source__name"]: entry["count"] for entry in lead_sources}


def landing_page(request):
    return render(request, "landing.html")


class BankListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/bank_list.html"
    context_object_name = "bank"
    paginate_by = 10

    def filter_queryset(self, queryset):
        phone_number = self.request.GET.get("phone_number")
        if phone_number:
            queryset = queryset.filter(number__icontains=phone_number)
        return queryset

    def get_queryset(self):
        user = self.request.user

        if user.is_organisor:
            queryset = BankNumbers.objects.filter(
                organisation=user.userprofile
            ).order_by("date_added")
        else:
            queryset = BankNumbers.objects.filter(
                organisation=user.agent.organisation, agent=user.agent
            ).order_by("date_added")

        queryset = self.filter_queryset(queryset)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_organisor:
            bank_list = BankNumbers.objects.filter(
                organisation=user.userprofile
            ).order_by("date_added")
            total_bank_numbers = bank_list.count()
        else:
            bank_list = BankNumbers.objects.filter(
                organisation=user.agent.organisation, agent=user.agent
            ).order_by("date_added")
            total_bank_numbers = bank_list.count()

        context["bank_numbers"] = {
            "bank_total": total_bank_numbers if total_bank_numbers else 0,
            "bank_list": bank_list if bank_list else _("Empty"),
        }

        return context


def bank_list(request):
    user = request.user
    bank_n = BankNumbers.objects.filter(organisation=user.userprofile).sort_by

    context = {"bank_n": bank_n}
    return render(request, "leads/bank_list.html", context)


class BankCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "leads/bank_create.html"
    form_class = BankModelForm

    def get_success_url(self):
        return reverse("leads:bank-list")

    def form_valid(self, form):
        user = self.request.user
        if (
            BankNumbers.objects.filter(
                organisation=user.userprofile, number=form.cleaned_data["number"]
            ).exists()
            == False
        ):
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


class CreateLeadFromBankNumberView(LoginRequiredMixin, View):
    def post(self, request, pk):
        # Get the BankNumber instance
        bank_number = get_object_or_404(BankNumbers, id=pk)

        # Create the Lead instance
        if Lead.objects.filter(
            phone_number=bank_number.number, organisation=bank_number.organisation
        ).exists():
            messages.error(request, "Lead already exists.")
            return HttpResponseRedirect(reverse("leads:bank-list"))
        else:
            lead = Lead(
                phone_number=bank_number.number,
                organisation=bank_number.organisation,
                agent=bank_number.agent,
            )

            # Save the Lead instance
            lead.save()

        # Redirect to the bank list view or wherever is appropriate
        messages.success(request, "Lead created successfully.")
        return HttpResponseRedirect(reverse("leads:bank-list"))


class LeadEditAPIView(APIView):
    def get(self, request, pk):
        lead = Lead.objects.get(pk=pk)
        serializer = LeadSerializer(lead, context={"request": request})
        return Response(serializer.data)


class LeadListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/lead_list.html"
    context_object_name = "leads"
    paginate_by = 10

    def get_queryset(self):
        user = self.request.user

        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Lead.objects.filter(organisation=user.userprofile).order_by(
                "-date_assigned"
            )
        else:
            queryset = Lead.objects.filter(
                organisation=user.agent.organisation, agent__isnull=False
            ).order_by("-date_assigned")
            # filter for the agent that is logged in
            queryset = queryset.filter(agent__user=user)

        filter_date = self.request.GET.get("filter_date", None)
        if filter_date == "yesterday":
            queryset = queryset.filter(
                date_assigned__date=date.today() - timedelta(days=1)
            )
        elif filter_date == "day_before":
            queryset = queryset.filter(
                date_assigned__date=date.today() - timedelta(days=2)
            )
        elif filter_date == "today":
            queryset = queryset.filter(date_assigned__date=date.today())
        elif filter_date == "all":
            queryset = queryset

        # Handling the search query
        query = self.request.GET.get("query", None)
        if query:
            queryset = queryset.filter(phone_number__icontains=query).order_by(
                "-date_assigned"
            )

        # IMPORTANT: Always set the filterset regardless of the branch
        self.filterset = LeadFilter(self.request.GET, queryset=queryset)
        return self.filterset.qs.order_by("-date_assigned")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_organisor:
            queryset = Lead.objects.filter(
                organisation=user.userprofile, agent__isnull=True
            ).order_by("-date_assigned")
            context["unassigned_leads"] = queryset

        # Convert 'yesterday' and 'day before yesterday' to Jalali
        gregorian_yesterday = date.today() - timedelta(days=1)
        gregorian_day_before = date.today() - timedelta(days=2)

        jalali_yesterday = jdatetime.date.fromgregorian(date=gregorian_yesterday)
        jalali_day_before = jdatetime.date.fromgregorian(date=gregorian_day_before)

        # Pass these dates to context
        context["jalali_yesterday"] = jalali_yesterday.strftime("%Y/%m/%d")
        context["jalali_day_before"] = jalali_day_before.strftime("%Y/%m/%d")

        # Add the search form
        context["search_form"] = LeadSearchForm(self.request.GET or None)

        context["filter_form"] = self.filterset.form

        context["lead_forms"] = {
            lead.id: LeadModelForm(instance=lead, user=self.request.user)
            for lead in context["leads"]
        }

        return context


class FullLeadListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/full_lead_view.html"
    context_object_name = "lead_list"
    queryset = Lead.objects.all().order_by("-date_assigned")

    def get_queryset(self):
        user = self.request.user

        # initial queryset of leads for the entire organisation
        if user.is_organisor:
            queryset = Lead.objects.filter(organisation=user.userprofile).order_by(
                "-date_assigned"
            )
            print("Organisor", queryset)
        else:
            queryset = Lead.objects.filter(
                organisation=user.agent.organisation,
                agent__isnull=False,
                agent=user.agent,
            ).order_by("-date_assigned")
            print(queryset)
            # filter for the agent that is logged in
            # queryset = queryset.filter(agent__user=user)

        now = jdatetime.date.fromgregorian(date=timezone.now())
        jalali_year, jalali_month = now.year, now.month

        # Check if a month is selected in GET request
        selected_month = self.request.GET.get("month")
        if selected_month:
            try:
                selected_month = int(selected_month)
                if 1 <= selected_month <= 12:
                    jalali_month = selected_month
            except ValueError:
                pass  # Invalid input, ignore and use current month

        # Calculate start and end dates of the selected Jalali month
        start_date = jdatetime.date(jalali_year, jalali_month, 1).togregorian()
        if jalali_month == 12:
            jalali_year += 1
            jalali_month = 1
        else:
            jalali_month += 1
        end_date = jdatetime.date(
            jalali_year, jalali_month, 1
        ).togregorian() - jdatetime.timedelta(days=1)

        # Filter the queryset based on the date range
        return queryset.filter(date_assigned__range=[start_date, end_date])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = jdatetime.date.fromgregorian(date=timezone.now())
        context["now_jalali_month"] = now.month
        context["lead_count"] = self.get_queryset().count()
        return context


def lead_list(request):
    leads = Lead.objects.all().sort_by

    context = {"leads": leads}
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
        kwargs.update({"user": self.request.user})  # Pass user to the form
        return kwargs

    def form_valid(self, form):
        user = self.request.user
        try:
            if (
                BankNumbers.objects.filter(
                    organisation=user.userprofile,
                    number=form.cleaned_data["phone_number"],
                ).exists()
                == False
                or BankNumbers.objects.filter(
                    organisation=user.userprofile,
                    agent__user__first_name="Bank",
                    number=form.cleaned_data["phone_number"],
                ).exists()
                == False
            ):
                lead = form.save(commit=False)
                lead.organisation = self.request.user.userprofile
                lead.save()
                send_mail(
                    subject="A lead has been created",
                    message="Go to the site to see the new lead",
                    from_email="test@test.com",
                    recipient_list=["test2@test.com"],
                )
                messages.success(
                    self.request, _("You have successfully created a lead")
                )
                return super(LeadCreateView, self).form_valid(form)

            else:
                bank_number = BankNumbers.objects.get(
                    organisation=user.userprofile,
                    number=form.cleaned_data["phone_number"],
                )
                DuplicateToFollow.objects.get_or_create(
                    user=self.request.user,
                    number=form.cleaned_data["phone_number"],
                    organisation_id=self.request.user.userprofile.id,
                    agent=bank_number.agent,
                )
                messages.error(self.request, _("Lead already exists!"))
                return redirect("leads:lead-list")
        except IntegrityError:
            messages.error(
                self.request,
                _("Lead with this phone number already exists for your organisation."),
            )
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
            queryset = Lead.objects.filter(organisation=user.agent.organisation)
            queryset = queryset.filter(agent__user=user)
        return queryset

    def get_form_kwargs(self):
        kwargs = super(LeadUpdateView, self).get_form_kwargs()
        kwargs.update({"user": self.request.user})  # Add user to form kwargs
        return kwargs

    def get_success_url(self):
        current_page = self.request.POST.get("current_page") or self.request.GET.get(
            "current_page"
        )
        query_string = self.request.POST.get("query_string") or self.request.GET.get(
            "query_string"
        )
        if self.request.POST.get("update_source") == "from_list_view":
            list_url = reverse("leads:lead-list")
            if query_string:
                return f"{list_url}?{query_string}"
            else:
                return list_url
        else:
            lead_id = self.object.id
            return reverse("leads:lead-detail", kwargs={"pk": lead_id})

    def form_valid(self, form):
        user = self.request.user
        if not form.is_valid():
            print(form.errors)
        # Before saving, capture the original agent
        original_agent = self.get_object().agent
        lead = self.get_object()
        # Save the updated lead instance
        response = super(LeadUpdateView, self).form_valid(form)
        print(self.request.POST)
        # Check if agent has changed
        if original_agent != self.object.agent:
            new_agent = self.object.agent
            # If the new agent has a chat_id, send a notification
            if new_agent:
                bank_number, created = BankNumbers.objects.get_or_create(
                    organisation=user.userprofile, number=self.object.phone_number
                )
                bank_number.agent = new_agent
                bank_number.save()

                print(bank_number.agent)
                message = f"{self.object.phone_number}, {self.object.category}"
                if new_agent.chat_id:
                    chat_id = new_agent.chat_id
                else:
                    chat_id = "-1001707390535"

                notify_background_messages(
                    chat_id=chat_id,
                    message=message,
                    organisation_id=user.userprofile.id,
                )

        # messages.info(self.request, _("You have successfully updated this lead"))
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # Prepare the data for JSON response
            response_data = {
                "id": self.object.id,
                "first_name": self.object.first_name,
                "last_name": self.object.last_name,
                "age": self.object.age,
                "phone_number": self.object.phone_number,
                "city": self.object.city,
                "state": self.object.state,
                "country": self.object.country,
                "job": self.object.job,
                "is_presented": self.object.is_presented,
                "low_quality": self.object.low_quality,
                "proposed_price": self.object.proposed_price,
                "registered_price": self.object.registered_price,
                "birthday": self.object.birthday.strftime("%Y-%m-%d")
                if self.object.birthday
                else None,
                "category": self.object.category.name if self.object.category else None,
                "source": self.object.source.name if self.object.source else None,
                "agent": self.object.agent.user.alt_name
                if self.object.agent and self.object.agent.user
                else None,
                "rank": self.object.agent.user.rank
                if self.object.agent and self.object.agent.user
                else None,
            }
            return JsonResponse(response_data)
        else:
            # Standard redirect for non-AJAX requests
            messages.info(
                self.request,
                _(
                    f"You have successfully updated the lead: {self.object.phone_number}"
                ),
            )
            return super(LeadUpdateView, self).form_valid(form)


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
        # Initial queryset of categories for the entire organisation
        if user.is_organisor:
            queryset = Category.objects.filter(organisation=user.userprofile)
        else:
            queryset = Category.objects.filter(organisation=user.agent.organisation)

        # Annotate with total lead count and unassigned lead count
        queryset = queryset.annotate(
            lead_count=Count("leads"),
            unassigned_lead_count=Count(
                Case(
                    When(leads__agent__isnull=True, then=1), output_field=IntegerField()
                )
            ),
        ).values("pk", "name", "lead_count", "unassigned_lead_count")

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


class LeadExportView(
    OrganisorAndLoginRequiredMixin, generic.ListView, generic.FormView
):
    template_name = "leads/lead_export.html"
    context_object_name = "leads"
    model = Lead
    form_class = FormatForm

    def get_queryset(self):
        user = self.request.user
        return Lead.objects.filter(organisation=user.userprofile)[:10]

    def post(self, request, **kwargs):
        user = self.request.user
        leads = Lead.objects.filter(organisation=user.userprofile)
        dataset = LeadResource().export(leads)

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


class BankExportView(
    OrganisorAndLoginRequiredMixin, generic.ListView, generic.FormView
):
    template_name = "leads/bank_export.html"
    context_object_name = "bank_numbers"
    model = BankNumbers
    form_class = FormatForm

    def post(self, request, **kwargs):
        user = self.request.user
        leads = BankNumbers.objects.filter(organisation=user.userprofile)
        dataset = BankResource().export(leads)

        format = request.POST.get("format")

        if format == "xls":
            response_content = dataset.export(format="xls")
            content_type = "application/vnd.ms-excel"
        elif format == "csv":
            response_content = dataset.export(format="csv")
            content_type = "text/csv"
        elif format == "json":
            response_content = dataset.export(format="json")
            content_type = "application/json"
        else:
            # You can raise an error here or set a default
            return HttpResponse("Invalid format", status=400)

        response = HttpResponse(response_content, content_type=content_type)
        response["Content-Disposition"] = f"attachment; filename=leads.{format}"
        return response

    def get_queryset(self):
        user = self.request.user

        if user.is_organisor:
            queryset = BankNumbers.objects.filter(organisation=user.userprofile)[:10]

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
        cleaned_num = (
            num.replace(" ", "").replace("+", "00").replace("(", "").replace(")", "")
        )

        # Ensure valid numbers start with '0' or '00'
        if cleaned_num[0] == "9" and len(cleaned_num) == 10:
            cleaned_num = "0" + cleaned_num

        processed_numbers.append(cleaned_num)

    return list(set(processed_numbers))  # Remove duplicates and return


def get_user_profile(organisation_id):
    return UserProfile.objects.get(id=organisation_id)


def ensure_connection():
    if connection.connection and not connection.is_usable():
        connection.close()
        connection.connect()


@background(schedule=1)
def notify_background_messages(chat_id, message, organisation_id):
    asyncio.run(send_telegram_message(chat_id, message, organisation_id))


async def send_telegram_message(chat_id, message, organisation_id):
    await sync_to_async(ensure_connection)()
    limiter = AsyncLimiter(1, 30)

    # Wrap the entire get operation inside sync_to_async
    user_profile = await sync_to_async(UserProfile.objects.get, thread_sensitive=True)(
        id=organisation_id
    )
    TOKEN = user_profile.telegram_token
    bot = Bot(TOKEN)

    try:
        await limiter.acquire()
        sent_message = await bot.send_message(chat_id=chat_id, text=message)

        # Retrieve chat's name
        chat = await bot.get_chat(chat_id)
        # Group chats have a title, private chats have a username
        chat_name = chat.title or chat.username

        # Store message details in the database
        await sync_to_async(TelegramMessage.objects.create, thread_sensitive=True)(
            chat_id=chat_id,
            chat_name=chat_name,
            message_id=sent_message.message_id,
            text=message,
            organisation=user_profile,
            deleted=False,
        )

    except (telegram.error.BadRequest, Exception) as e:
        print(f"Error sending Telegram message to {chat_id}: {e}")

        # Try sending to the backup chat_id
        try:
            await bot.send_message(chat_id="-1001707390535", text=message)
        except Exception as backup_error:
            print(f"Error sending Telegram message to backup chat: {backup_error}")


@background(schedule=1)
def delete_background_messages(chat_id, message_id, organisation_id):
    asyncio.run(delete_telegram_message(chat_id, message_id, organisation_id))


async def delete_telegram_message(chat_id, message_id, organisation_id):
    await sync_to_async(ensure_connection)()
    limiter = AsyncLimiter(1, 30)

    # Wrap the entire get operation inside sync_to_async
    user_profile = await sync_to_async(UserProfile.objects.get, thread_sensitive=True)(
        id=organisation_id
    )
    TOKEN = user_profile.telegram_token
    bot = Bot(TOKEN)

    try:
        await limiter.acquire()
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        await sync_to_async(
            TelegramMessage.objects.filter(
                message_id=message_id, organisation_id=organisation_id
            ).update,
            thread_sensitive=True,
        )(deleted=True)

    except (telegram.error.BadRequest, Exception) as e:
        print(f"Error sending Telegram message to {chat_id}: {e}")

        # Try sending to the backup chat_id
        try:
            print("WHAAAAAT?!")
        except Exception as backup_error:
            print(f"Error sending Telegram message to backup chat: {backup_error}")


class MessageListView(OrganisorAndLoginRequiredMixin, generic.ListView):
    model = TelegramMessage
    template_name = "leads/message_list.html"
    context_object_name = "tg_messages"

    def get_queryset(self):
        queryset = super().get_queryset()
        organisation_id = self.request.user.userprofile.id
        queryset = queryset.filter(organisation_id=organisation_id)

        # Get date range from the request
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date and end_date:
            queryset = queryset.filter(sent_date__range=[start_date, end_date])

        # Get deletion status from the request
        deletion_status = self.request.GET.get("deletion_status")
        if deletion_status == "true":
            queryset = queryset.filter(deleted=True)
        elif deletion_status == "false":
            queryset = queryset.filter(deleted=False)

        keyword = self.request.GET.get("keyword")
        if keyword:
            queryset = queryset.filter(text__icontains=keyword)

        return queryset


class BulkMessageDeleteView(OrganisorAndLoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        selected_message_ids = request.POST.getlist("message_ids")
        organisation_id = request.user.userprofile.id
        deletion_errors = []

        for message_id in selected_message_ids:
            tg_messages = TelegramMessage.objects.filter(
                message_id=message_id, organisation_id=organisation_id
            )

            if tg_messages.exists():
                message = tg_messages.first()
                delete_background_messages(message.chat_id, message_id, organisation_id)
                # Check if the message was successfully deleted

            # if message.deleted:
            #     message.delete()
            # else:
            #     deletion_errors.append(f"Failed to delete message {message_id}")

        if deletion_errors:
            messages.error(
                request,
                "Some messages could not be deleted: " + ", ".join(deletion_errors),
            )
        else:
            messages.success(request, "Selected messages have been deleted.")

        return redirect("leads:message_list")


class LeadImportView(OrganisorAndLoginRequiredMixin, View):
    template_name = "leads/lead_import.html"

    def get(self, request):
        if "override_chat_id" not in request.session:
            return render(request, "leads/prompt_override_chat_id.html")

        form = LeadImportForm(user=request.user)
        return render(request, self.template_name, {"form": form})

    def lead_preprocess(self, csv_file):
        # Convert the CSV reader to a list
        all_numbers = csv_file
        all_numbers = [item[0] for item in all_numbers if len(item) > 0]

        for index, number in enumerate(all_numbers):
            number = number.replace(" ", "")
            number = number.replace("+", "00")
            number = number.replace("(", "")
            number = number.replace(")", "")
            all_numbers[index] = number

        # Remove duplicates
        all_numbers = list(set(all_numbers))

        return all_numbers

    def post(self, request):
        if "choice" in request.POST:
            if request.POST["choice"] == "Yes":
                request.session["override_chat_id"] = True
            else:
                request.session["override_chat_id"] = False
            return redirect("leads:lead-import")

        chat_id = "-1001707390535"  # Default value
        form = LeadImportForm(request.POST, request.FILES, user=request.user)
        user = self.request.user
        TOKEN = user.userprofile.telegram_token
        bot = Bot(TOKEN)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            source = form.cleaned_data["source"]
            try:
                csv_file = pd.read_csv(csv_file, header=None, dtype=str).values.tolist()
                total_leads = 0
                duplicates = 0
                added_leads = 0
                foreign_added = 0
                all_numbers = self.lead_preprocess(csv_file)
                for number in all_numbers:
                    total_leads += 1
                    category = form.cleaned_data["category"]
                    if Lead.objects.filter(
                        organisation=user.userprofile, phone_number=number
                    ).exists():
                        duplicates += 1
                        lead = Lead.objects.get(
                            organisation=user.userprofile, phone_number=number
                        )
                        DuplicateToFollow.objects.get_or_create(
                            number=number,
                            organisation=user.userprofile,
                            agent=lead.agent,
                        )
                        if lead.agent:
                            if lead.agent.user.is_active:
                                if request.session.get("override_chat_id", False):
                                    chat_id = "-1001707390535"
                                else:
                                    chat_id = (
                                        lead.agent.chat_id
                                        if lead.agent.chat_id
                                        else "-1001707390535"
                                    )
                                message = f"تماس {number} {lead.agent}"
                                # notify_background_messages_celery.delay(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                                notify_background_messages(
                                    chat_id=chat_id,
                                    message=message,
                                    organisation_id=user.userprofile.id,
                                )
                            else:
                                chat_id = "-1001707390535"
                                message = f"تماس {number} {lead.agent}"
                                # notify_background_messages_celery.delay(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                                notify_background_messages(
                                    chat_id=chat_id,
                                    message=message,
                                    organisation_id=user.userprofile.id,
                                )
                        else:
                            message = f"شماره تکراری بدون کارشناس: {number}"
                            notify_background_messages(
                                chat_id="-1001707390535",
                                message=message,
                                organisation_id=user.userprofile.id,
                            )

                    elif BankNumbers.objects.filter(
                        organisation=user.userprofile, number=number
                    ).exists():
                        duplicates += 1
                        bank_number = BankNumbers.objects.get(
                            organisation=user.userprofile, number=number
                        )
                        DuplicateToFollow.objects.get_or_create(
                            number=number,
                            organisation=user.userprofile,
                            agent=bank_number.agent,
                        )
                        if bank_number.agent.user.is_active:
                            if request.session.get("override_chat_id", False):
                                chat_id = "-1001707390535"
                            else:
                                chat_id = (
                                    bank_number.agent.chat_id
                                    if bank_number.agent.chat_id
                                    else "-1001707390535"
                                )
                            message = f"تماس {number} {bank_number.agent}"
                            # notify_background_messages_celery.delay(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                            notify_background_messages(
                                chat_id=chat_id,
                                message=message,
                                organisation_id=user.userprofile.id,
                            )
                        else:
                            chat_id = "-1001707390535"
                            notify_background_messages(
                                chat_id=chat_id,
                                message=message,
                                organisation_id=user.userprofile.id,
                            )

                    else:
                        if len(number) == 11 and number[:2] == "09":
                            if number[:4] == "0912":
                                category, created = Category.objects.get_or_create(
                                    name="912", organisation=user.userprofile
                                )
                                Lead.objects.create(
                                    phone_number=number,
                                    category=category,
                                    source=source,
                                    organisation=user.userprofile,
                                )
                                added_leads += 1
                            else:
                                added_leads += 1
                                Lead.objects.create(
                                    phone_number=number,
                                    category=category,
                                    source=source,
                                    organisation=user.userprofile,
                                )
                        else:
                            foreign_added += 1
                            category, created = Category.objects.get_or_create(
                                name="خارجی", organisation=user.userprofile
                            )
                            Lead.objects.create(
                                phone_number=number,
                                category=category,
                                source=source,
                                organisation=user.userprofile,
                            )

                # Send a message to Telegram
                if request.session.get("override_chat_id", False):
                    chat_id = "-1001707390535"
                else:
                    chat_id = (
                        user.userprofile.chat_id
                        if user.userprofile.chat_id
                        else "-1001707390535"
                    )

                category = form.cleaned_data["category"]
                message = f"""
                منبع: {source}\n
                نوع: {category}\n
                تعداد شماره‌های ورودی: {total_leads}\n
                تعداد شماره‌های تکراری: {duplicates}\n
                تعداد شماره‌های خالص خارجی: {foreign_added}\n
                تعدادشماره‌‌های خالص ایرانی: {added_leads}\n\n\n

"""

                # notify_background_messages_celery.delay(chat_id=chat_id, message=message, organisation_id=user.userprofile.id)
                notify_background_messages(
                    chat_id=chat_id,
                    message=message,
                    organisation_id=user.userprofile.id,
                )

                return redirect("leads:lead-list")
            except Exception as e:
                print(e)
                # Catch any error related to file processing and display a message to the user
                messages.error(
                    request,
                    f"""An error occurred while processing the file. Review the file and upload again.
                                            THE FILE SHOULD HAVE ONE COLUMN OF ONLY NUMBERS!""",
                )

        if "override_chat_id" in request.session:
            del request.session["override_chat_id"]

        return render(request, self.template_name, {"form": form})


class BankImportView(OrganisorAndLoginRequiredMixin, View):
    template_name = "leads/bank_import.html"

    def get(self, request):
        form = BankImportForm(user=request.user)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = BankImportForm(request.POST, request.FILES, user=request.user)
        user = request.user.userprofile.id

        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            agent = form.cleaned_data["agent"]
            decoded_file = csv_file.read().decode("utf-8").splitlines()

            # Convert the CSV reader to a list
            all_numbers = list(csv.reader(decoded_file))

            # Flatten the list if your CSV has a single column, otherwise adjust accordingly
            all_numbers = [item[0] for item in all_numbers]

            # Apply the preprocessing
            all_numbers = [string.replace(" ", "") for string in all_numbers]
            all_numbers = [string.replace("+", "00") for string in all_numbers]
            all_numbers = [string.replace("(", "") for string in all_numbers]
            all_numbers = [string.replace(")", "") for string in all_numbers]

            # Remove duplicates
            all_numbers = list(set(all_numbers))

            # Update phone numbers
            updated_phone_numbers = []
            for num in all_numbers:
                if num[0] == "0":
                    updated_phone_numbers.append(num)
                elif num[0] == "9" and len(num) == 10:
                    updated_phone_numbers.append("0" + num)
                else:
                    updated_phone_numbers.append("00" + num)

            all_numbers = updated_phone_numbers

            for number in all_numbers:
                if BankNumbers.objects.filter(number=number).exists():
                    continue
                else:
                    BankNumbers.objects.create(
                        number=number, organisation_id=user, agent=agent
                    )

            return redirect("leads:bank-list")

        return render(request, self.template_name, {"form": form})


class LeadImportAgentsView(OrganisorAndLoginRequiredMixin, View):
    template_name = "leads/lead_import_agents.html"

    def get(self, request):
        if "override_chat_id" not in request.session:
            return render(request, "leads/prompt_override_chat_id.html")
        form = LeadImportFormAgents(user=request.user)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = LeadImportFormAgents(request.POST, request.FILES, user=request.user)
        user = request.user

        if "choice" in request.POST:
            if request.POST["choice"] == "Yes":
                request.session["override_chat_id"] = True
            else:
                request.session["override_chat_id"] = False
            return redirect("leads:lead-import-agents")

        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            source = form.cleaned_data["source"]
            category = form.cleaned_data["category"]
            # Extracting the agent from form
            agent = form.cleaned_data["agent"]

            all_numbers = preprocess_csv_numbers(csv_file)

            for number in all_numbers:
                Lead.objects.get_or_create(
                    phone_number=number,
                    category=category,
                    source=source,
                    agent=agent,
                    organisation=user.userprofile,
                )

            return redirect("leads:lead-list")

        return render(request, self.template_name, {"form": form})


class BankUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    model = BankNumbers
    form_class = BankModelForm
    # Modify this to the path of your template
    template_name = "leads/bank_update.html"
    # Modify this to the URL or view name you want to redirect to upon successful update
    success_url = reverse_lazy("leads:bank-list")

    def get_object(self, queryset=None):
        """Retrieve the BankNumbers instance to be updated. You can customize this if needed."""
        return super().get_object(queryset=queryset)

    def form_valid(self, form):
        messages.success(self.request, _("Bank number updated successfully!"))
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            _("Error updating the bank number. Please check your details."),
        )
        return super().form_invalid(form)


class BankDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    model = BankNumbers
    # This will be a confirmation template
    template_name = "leads/bank_delete.html"
    # Modify this to the URL or view name you want to redirect to after deletion
    success_url = reverse_lazy("leads:bank-list")

    def delete(self, request, *args, **kwargs):
        messages.success(request, _("Bank number deleted successfully!"))
        return super().delete(request, *args, **kwargs)


FORMS = [
    ("chat_override", ChatOverrideForm),
    ("category", CategorySelectionForm),
    ("distribution_info", DistributionForm),
    # No form for confirmation, just an action button.
    ("confirm", ConfirmationForm),
]

executor = ThreadPoolExecutor()


async def load_chat_settings():
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, ChatSetting.load)


def create_agent_message(agent_name, rank, phone_data):
    today = jdatetime.datetime.now().strftime("%Y/%m/%d")
    if rank == 1:
        medal = "🥇"
    elif rank == 2:
        medal = "🥈"
    elif rank == 3:
        medal = "🥉"
    elif rank == 4:
        medal = "🏅"
    elif rank == 5:
        medal = "🏵"
        rank = "آموزش"
    else:
        return None  # Handle ranks outside of 1-4 if necessary

    message = f"""
        {medal}
        {today} 

        {agent_name}
        رنک : {rank}
        ارجاع : {len(phone_data.values())}\n\n"""

    for i, phone_number in enumerate(phone_data.values()):
        message += f"{i + 1}. {phone_number} \n"

    return message


def download_excel_page(request):
    excel_file_path = request.session.get("excel_file_path")
    return render(
        request, "leads/download_excel_page.html", {"excel_file_path": excel_file_path}
    )


class LeadDistributionWizard(SessionWizardView):
    form_list = FORMS
    template_name = "leads/wizard.html"

    def get(self, request, *args, **kwargs):
        self.storage.extra_data["user_id"] = self.request.user.id
        print(
            "Inside GET: user_id set in storage:",
            self.storage.extra_data.get("user_id"),
        )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.storage.extra_data["user_id"] = self.request.user.id
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self, step="category"):
        kwargs = super().get_form_kwargs(step)
        # Pass the entire storage object
        kwargs["wizard_storage"] = self.storage
        print(
            "Inside get_form_kwargs: user_id from storage:",
            self.storage.extra_data.get("user_id"),
        )
        return kwargs

    def get_form(self, step=None, data=None, files=None):
        form = super().get_form(step, data, files)

        # if step == 'chat_override':
        #     self.storage.extra_data['user_id'] = self.request.user.id

        if step == "category":
            # self.storage.extra_data['user_id'] = self.request.user.id
            print(self.request.session.items())

        # Handle the data passing for the form. For example, if you need the category ID for the 'distribution_info' form
        if step == "distribution_info" and data:
            try:
                category = Category.objects.get(pk=data.get("category"))
                alternate_category = Category.objects.get(
                    pk=data.get("alternate_category")
                )

                form.initial = {
                    "category": category,
                    "alternate_category": alternate_category,
                }
            except (MultiValueDictKeyError, Category.DoesNotExist):
                pass
        if step == "chat_override" and data:
            chat_settings = ChatSetting.load()
            form.initial = {
                "override_chat_id": chat_settings.override_chat_id,
                "chat_id": chat_settings.chat_id,
            }

        return form

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)

        if self.steps.current == "distribution_info":
            category_data = self.get_cleaned_data_for_step("category")

            if category_data:
                category = category_data["category"]
                alternate_category = category_data["alternate_category"]
                high_quality = category_data["high_quality"]

                # Calculate lead details
                context.update(
                    self.calculate_lead_details(category, alternate_category)
                )

        elif self.steps.current == "confirm":
            # Set up data for confirmation
            context = self.setup_confirmation_data(context)

        return context

    def calculate_lead_details(self, category, alternate_category):
        user = self.request.user
        category = self.get_cleaned_data_for_step("category")["category"]
        alternate_category = self.get_cleaned_data_for_step("category")[
            "alternate_category"
        ]
        category_id = category.id
        alternate_category_id = alternate_category.id

        leads = Lead.objects.filter(
            organisation=user.userprofile, category=category_id, agent__isnull=True
        )
        new_leads = (
            leads.annotate(phone_length=Length("phone_number"))
            .filter(phone_length=11)
            .count()
        )
        # new_912_leads = leads.filter(phone_number__startswith='0912').annotate(phone_length=Length('phone_number')).filter(phone_length=11).count()
        # foreign_or_wrong_leads = leads.annotate(phone_length=Length('phone_number')).exclude(phone_length=11).count()
        extra = (
            Lead.objects.filter(
                organisation=user.userprofile,
                category=alternate_category_id,
                agent__isnull=True,
            )
            .annotate(phone_length=Length("phone_number"))
            .filter(phone_length=11)
            .count()
        )

        total_new_leads = new_leads
        active_agents_count = self.get_active_agents_count()

        recommended_leads_per_agent = self.compute_initial_distribution(
            total_new_leads, active_agents_count, category
        )
        self.request.session["total_new_leads"] = total_new_leads
        return {
            "total_new_leads": total_new_leads,
            # 'new_912_leads': new_912_leads,
            "extra": extra,
            # 'foreign_or_wrong_leads': foreign_or_wrong_leads,
            "active_agents": active_agents_count,
            "recommended_leads_per_agent": recommended_leads_per_agent,
            "display_data": True,
        }

    def assign_leads_to_agent(self, df):
        user = self.request.user
        if df is None:
            return

        for col in df:
            alt_name = df[col].name
            numbers = df[col].values

            try:
                agent = Agent.objects.get(
                    organisation=user.userprofile, user__alt_name=alt_name
                )
                for number in numbers:
                    lead = Lead.objects.get(
                        organisation=user.userprofile, phone_number=number
                    )
                    lead.agent = agent
                    lead.save()

                    # Add the lead's number to BankNumbers if it doesn't exist
                    bank_number, created = BankNumbers.objects.get_or_create(
                        organisation=user.userprofile,
                        number=lead.phone_number,
                        defaults={"agent": agent, "organisation": agent.organisation},
                    )
                    if not created:
                        print(
                            f"Number {lead.phone_number} already exists in BankNumbers."
                        )
            except User.DoesNotExist:
                print(f"No user found with alt_name: {alt_name}")
            except Agent.DoesNotExist:
                print(f"No agent found for user with alt_name: {alt_name}")
            except Lead.DoesNotExist:
                print(f"No lead found with phone_number: {number}")

    def done(self, form_list, **kwargs):
        self.request.session["current_wizard_step"] = self.steps.current
        chat_override_data = self.get_cleaned_data_for_step("chat_override")
        if chat_override_data:
            chat_settings = ChatSetting.load()
            chat_settings.override_chat_id = chat_override_data["override_chat_id"]
            chat_settings.chat_id = chat_override_data["chat_id"]
            chat_settings.save()

        context = self.get_context_data(None)
        df_rank1 = context.get("df_rank1")
        df_rank2 = context.get("df_rank2")
        df_rank3 = context.get("df_rank3")
        df_rank4 = context.get("df_rank4")
        df_rank5 = context.get("df_rank5")

        df_rank1_json = df_rank1.to_json()
        df_rank2_json = df_rank2.to_json()
        df_rank3_json = df_rank3.to_json()
        df_rank4_json = df_rank4.to_json()
        df_rank5_json = df_rank5.to_json()

        self.assign_leads_to_agent(df_rank1)
        self.assign_leads_to_agent(df_rank2)
        self.assign_leads_to_agent(df_rank3)
        self.assign_leads_to_agent(df_rank4)
        self.assign_leads_to_agent(df_rank5)

        organisor_id = self.request.user.userprofile.id
        organisor = self.request.user
        for df in [df_rank1, df_rank2, df_rank3, df_rank4, df_rank5]:
            for agent_name, phone_data in json.loads(df.to_json()).items():
                # Check if phone_data is empty or None:
                if not phone_data:
                    continue

                agent = Agent.objects.get(
                    organisation=organisor.userprofile, user__alt_name=agent_name
                )
                rank = agent.user.rank
                message = create_agent_message(agent_name, rank, phone_data)

                # Apply chat_settings override if needed:
                chat_settings = ChatSetting.load()
                if chat_settings.override_chat_id and chat_settings.chat_id:
                    chat_id = chat_settings.chat_id
                else:
                    chat_id = agent.chat_id or "-1001707390535"

                # Schedule the message sending:
                notify_background_messages(chat_id, message, organisor_id)

        (
            new_df_rank1,
            new_df_rank2,
            new_df_rank3,
            new_df_rank4,
            new_df_rank5,
        ) = self.generate_excel_dataframes(
            df_rank1, df_rank2, df_rank3, df_rank4, df_rank5
        )
        timestamp = datetime.now().strftime("%Y-%m-%d")
        # Generate a unique file name
        file_name = f"output{timestamp}_{uuid.uuid4().hex}.xlsx"

        # Assuming MEDIA_URL and MEDIA_ROOT are correctly set up in your Django settings
        excel_file_path = os.path.join(settings.MEDIA_ROOT, file_name)

        if not os.path.exists(settings.MEDIA_ROOT):
            os.makedirs(settings.MEDIA_ROOT)

        with pd.ExcelWriter(excel_file_path) as writer:
            new_df_rank1.to_excel(writer, sheet_name="rank 1", index=False)
            new_df_rank2.to_excel(writer, sheet_name="rank 2", index=False)
            new_df_rank3.to_excel(writer, sheet_name="rank 3", index=False)
            new_df_rank4.to_excel(writer, sheet_name="rank 4", index=False)
            new_df_rank5.to_excel(writer, sheet_name="rank 5", index=False)

        # Store the file path in the session so it can be accessed in the next view
        self.request.session["excel_file_path"] = os.path.join(
            settings.MEDIA_URL, file_name
        )

        return redirect("leads:download_excel_page")

    def generate_excel_dataframes(
        self, df_rank1, df_rank2, df_rank3, df_rank4, df_rank5
    ):
        df_rank1 = self.create_dataframe_with_phone_numbers(df_rank1)
        df_rank2 = self.create_dataframe_with_phone_numbers(df_rank2)
        df_rank3 = self.create_dataframe_with_phone_numbers(df_rank3)
        df_rank4 = self.create_dataframe_with_phone_numbers(df_rank4)
        df_rank5 = self.create_dataframe_with_phone_numbers(df_rank5)

        return df_rank1, df_rank2, df_rank3, df_rank4, df_rank5

    def create_dataframe_with_phone_numbers(self, dataframe):
        # Create a copy to avoid modifying the original DataFrame
        new_dataframe = dataframe.copy()

        for column in new_dataframe.columns:
            new_dataframe[column] = new_dataframe[column].apply(
                lambda x: x["phone_number"] if isinstance(x, dict) else x
            )

        return new_dataframe

    def compute_initial_distribution(self, N, active_agents_count, category=None):
        user = self.request.user
        if category:
            N = Lead.objects.filter(
                organisation=user.userprofile, category=category, agent__isnull=True
            ).count()
        # Step 1: Assign numbers to each rank based on the percentages
        rank1_numbers = N * 40 // 100
        rank2_numbers = N * 30 // 100
        rank3_numbers = N * 20 // 100
        rank4_numbers = N * 10 // 100

        # Step 2: Get initial each_rank values
        each_rank1 = (
            rank1_numbers // active_agents_count["rank_1"]
            if active_agents_count["rank_1"] != 0
            else 0
        )
        each_rank2 = (
            rank2_numbers // active_agents_count["rank_2"]
            if active_agents_count["rank_2"] != 0
            else 0
        )
        each_rank3 = (
            rank3_numbers // active_agents_count["rank_3"]
            if active_agents_count["rank_3"] != 0
            else 0
        )
        each_rank4 = (
            rank4_numbers // active_agents_count["rank_4"]
            if active_agents_count["rank_4"] != 0
            else 0
        )
        each_rank5 = (
            rank4_numbers // active_agents_count["rank_5"]
            if active_agents_count["rank_5"] != 0
            else 0
        )

        # Step 3: Adjust each_rank values if necessary
        total_numbers_assigned = (
            each_rank1 * active_agents_count["rank_1"]
            + each_rank2 * active_agents_count["rank_2"]
            + each_rank3 * active_agents_count["rank_3"]
            + each_rank4 * active_agents_count["rank_4"]
            + each_rank4 * active_agents_count["rank_5"]
        )
        while total_numbers_assigned > N:
            each_rank1 -= 1
            each_rank2 = each_rank1 - 1
            each_rank3 = each_rank2 - 1
            each_rank4 = each_rank3 - 1
            each_rank5 = each_rank4

            total_numbers_assigned = (
                each_rank1 * active_agents_count["rank_1"]
                + each_rank2 * active_agents_count["rank_2"]
                + each_rank3 * active_agents_count["rank_3"]
                + each_rank4 * active_agents_count["rank_4"]
                + each_rank5 * active_agents_count["rank_5"]
            )

        # Step 4: Distribute remaining numbers equally among all agents
        remaining_numbers = N - total_numbers_assigned
        extra_numbers_per_agent = remaining_numbers // (
            active_agents_count["rank_1"]
            + active_agents_count["rank_2"]
            + active_agents_count["rank_3"]
            + active_agents_count["rank_4"]
            + active_agents_count["rank_5"]
        )
        each_rank1 += extra_numbers_per_agent
        each_rank2 += extra_numbers_per_agent
        each_rank3 += extra_numbers_per_agent
        each_rank4 += extra_numbers_per_agent
        each_rank5 += extra_numbers_per_agent

        return {
            "rank1": each_rank1 if each_rank1 else 0,
            "rank2": each_rank2 if each_rank2 else 0,
            "rank3": each_rank3 if each_rank3 else 0,
            "rank4": each_rank4 if each_rank4 else 0,
            "rank5": each_rank5 if each_rank5 else 0,
            "remaining": N
            - total_numbers_assigned
            - extra_numbers_per_agent
            * (
                active_agents_count["rank_1"]
                + active_agents_count["rank_2"]
                + active_agents_count["rank_3"]
                + active_agents_count["rank_4"]
                + active_agents_count["rank_5"]
            ),
        }

    def distribute_leads(self, unassigned_leads, recommended_leads_per_agent, extra):
        organisor = self.request.user
        # This function will distribute the leads to the agents using pandas
        # and return a dataframe with the distribution
        active_agents_rank1 = [
            agent["user__alt_name"]
            for agent in Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=1,
                is_available_for_leads=True,
            ).values("user__alt_name")
        ]
        active_agents_rank2 = [
            agent["user__alt_name"]
            for agent in Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=2,
                is_available_for_leads=True,
            ).values("user__alt_name")
        ]
        active_agents_rank3 = [
            agent["user__alt_name"]
            for agent in Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=3,
                is_available_for_leads=True,
            ).values("user__alt_name")
        ]
        active_agents_rank4 = [
            agent["user__alt_name"]
            for agent in Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=4,
                is_available_for_leads=True,
            ).values("user__alt_name")
        ]
        active_agents_rank5 = [
            agent["user__alt_name"]
            for agent in Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=5,
                is_available_for_leads=True,
            ).values("user__alt_name")
        ]

        # random.shuffle(unassigned_leads)
        # random.shuffle(extra)

        dist_list = unassigned_leads + extra

        df_rank1 = pd.DataFrame(columns=active_agents_rank1)
        df_rank2 = pd.DataFrame(columns=active_agents_rank2)
        df_rank3 = pd.DataFrame(columns=active_agents_rank3)
        df_rank4 = pd.DataFrame(columns=active_agents_rank4)
        df_rank5 = pd.DataFrame(columns=active_agents_rank5)

        for i in range(recommended_leads_per_agent["rank1"]):
            df_rank1.loc[len(df_rank1)] = dist_list[: len(df_rank1.columns)]
            dist_list = dist_list[len(df_rank1.columns) :]

        for i in range(recommended_leads_per_agent["rank2"]):
            df_rank2.loc[len(df_rank2)] = dist_list[: len(df_rank2.columns)]
            dist_list = dist_list[len(df_rank2.columns) :]

        for i in range(recommended_leads_per_agent["rank3"]):
            df_rank3.loc[len(df_rank3)] = dist_list[: len(df_rank3.columns)]
            dist_list = dist_list[len(df_rank3.columns) :]

        for i in range(recommended_leads_per_agent["rank4"]):
            df_rank4.loc[len(df_rank4)] = dist_list[: len(df_rank4.columns)]
            dist_list = dist_list[len(df_rank4.columns) :]

        for i in range(recommended_leads_per_agent["rank5"]):
            df_rank5.loc[len(df_rank5)] = dist_list[: len(df_rank5.columns)]
            dist_list = dist_list[len(df_rank5.columns) :]

        return df_rank1, df_rank2, df_rank3, df_rank4, df_rank5

    def get_active_agents_count(self):
        organisor = self.request.user
        active_agents_count = {
            "rank_1": Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=1,
                is_available_for_leads=True,
            ).count(),
            "rank_2": Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=2,
                is_available_for_leads=True,
            ).count(),
            "rank_3": Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=3,
                is_available_for_leads=True,
            ).count(),
            "rank_4": Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=4,
                is_available_for_leads=True,
            ).count(),
            "rank_5": Agent.objects.filter(
                organisation=organisor.userprofile,
                user__rank=5,
                is_available_for_leads=True,
            ).count(),
        }
        return active_agents_count

    def shuffle_leads_by_date(self, leads_query, ordering):
        # Determine the ordering based on the user's choice
        date_ordering = "date" if ordering == "asc" else "-date"

        # Group by date_added and order based on the user's choice
        leads_grouped = (
            leads_query.annotate(date=TruncDate("date_added"))
            .order_by(date_ordering, "id")
            .values("date", "phone_number")
        )

        shuffled_leads = []
        current_date = None
        current_group = []

        for lead in leads_grouped:
            if lead["date"] != current_date:
                if current_group:
                    random.shuffle(current_group)
                    shuffled_leads.extend(current_group)
                    current_group = []
                current_date = lead["date"]
            current_group.append(lead["phone_number"])

        # Shuffle the last group
        if current_group:
            random.shuffle(current_group)
            shuffled_leads.extend(current_group)

        return shuffled_leads

    def setup_confirmation_data(self, context):
        user = self.request.user
        distribution_data = self.get_cleaned_data_for_step("distribution_info")
        high_quality = self.get_cleaned_data_for_step("category")["high_quality"]
        order_by_date = self.get_cleaned_data_for_step("category")["order_by_date"]

        category = Category.objects.get(
            organisation=user.userprofile,
            pk=self.get_cleaned_data_for_step("category")["category"].id,
        )
        alternate_category = Category.objects.get(
            organisation=user.userprofile,
            pk=self.get_cleaned_data_for_step("category")["alternate_category"].id,
        )

        unassigned_leads = (
            Lead.objects.filter(
                organisation=user.userprofile, agent__isnull=True, category=category
            )
            .annotate(phone_length=Length("phone_number"))
            .filter(phone_length=11)
        )
        extra = (
            Lead.objects.filter(
                organisation=user.userprofile,
                agent__isnull=True,
                category=alternate_category,
            )
            .annotate(phone_length=Length("phone_number"))
            .filter(phone_length=11)
        )

        if high_quality:
            unassigned_leads = unassigned_leads.filter(phone_number__startswith="091")
            extra = extra.filter(phone_number__startswith="091")

        unassigned_leads_shuffled = self.shuffle_leads_by_date(
            unassigned_leads, order_by_date
        )
        extra_shuffled = self.shuffle_leads_by_date(extra, order_by_date)
        recommended_leads_per_agent = distribution_data

        df_rank1, df_rank2, df_rank3, df_rank4, df_rank5 = self.distribute_leads(
            unassigned_leads_shuffled, recommended_leads_per_agent, extra_shuffled
        )
        print(df_rank1)
        context.update(
            {
                "df_rank1": df_rank1,
                "df_rank2": df_rank2,
                "df_rank3": df_rank3,
                "df_rank4": df_rank4,
                "df_rank5": df_rank5,
                "df_rank1_json": df_rank1.to_json(orient="records"),
                "df_rank2_json": df_rank2.to_json(orient="records"),
                "df_rank3_json": df_rank3.to_json(orient="records"),
                "df_rank4_json": df_rank4.to_json(orient="records"),
                "df_rank5_json": df_rank5.to_json(orient="records"),
                "display_distribution": True,
            }
        )

        return context


class SearchLeadsView(View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "")
        user = request.user
        leads = Lead.objects.none()  # Default to no leads

        if hasattr(user, "is_organisor") and user.is_organisor:
            leads = Lead.objects.filter(
                organisation=user.userprofile.id, phone_number__icontains=query
            )
        elif hasattr(user, "is_agent") and user.is_agent:
            leads = Lead.objects.filter(agent__user=user, phone_number__icontains=query)
        data = []
        for lead in leads:
            if lead.category:
                data.append(
                    {
                        "id": lead.id,
                        "phone_number": lead.phone_number,
                        "category": lead.category.name,
                    }
                )

            else:
                data.append({"id": lead.id, "phone_number": lead.phone_number})

        return JsonResponse(data, safe=False)


class SearchBankView(View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get("q", "")
        user = request.user
        numbers = BankNumbers.objects.none()  # Default to no leads

        if hasattr(user, "is_organisor") and user.is_organisor:
            numbers = BankNumbers.objects.filter(
                organisation=user.userprofile.id, number__icontains=query
            )
        data = []
        for number in numbers:
            if number.agent:
                data.append(
                    {
                        "id": number.id,
                        "number": number.number,
                        "agent": number.agent.user.alt_name,
                    }
                )
            else:
                data.append({"id": number.id, "number": number.number})

        return JsonResponse(data, safe=False)


class MyDayView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/my_day.html"
    context_object_name = "leads_today"

    def get_random_static_image(self):
        # Define the path to your static images folder
        static_image_dir = os.path.join(
            settings.BASE_DIR, "static", "images", "background"
        )

        # List all files in the static images folder
        image_files = [
            f
            for f in os.listdir(static_image_dir)
            if os.path.isfile(os.path.join(static_image_dir, f))
        ]
        print(image_files)
        if image_files:
            # Select a random image file path
            random_image = random.choice(image_files)
            # Construct the full URL for the selected image
            random_image_url = f"{settings.STATIC_URL}images/background/{random_image}"
            return random_image_url
        else:
            # Return a default image URL or handle the case when no images are found
            return os.path.join(
                settings.STATIC_URL,
                "images",
                "background",
                "pexels-bob-ward-3647693.jpg",
            )

    def fetch_unsplash_image(self):
        url = "https://api.unsplash.com/photos/random"
        headers = {
            # Replace with your API key
            "Authorization": "Client-ID 0RZY8EPO_QZhkKRv7sI2Q4RfOZaimD8tQEnhPVRnTAM"
        }
        params = {
            "orientation": "landscape",
            "query": "luxury",
        }
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            return data["urls"]["full"]
        except requests.exceptions.RequestException as e:
            # Handle the error, and provide a default image URL
            print(f"Error fetching image from Unsplash API: {e}")
            return self.get_random_static_image()

    predefined_quotes = [
        "Success is not final, failure is not fatal: It is the courage to continue that counts. - Winston Churchill",
        "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt",
        "Your time is limited, don't waste it living someone else's life. - Steve Jobs",
        "Every moment is a fresh beginning.",
        "Play by the rules, but be ferocious.",
        "Fall seven times and stand up eight. Japanese Proverb.",
        "Avoiding mistakes costs more than making them.",
        "The road to success and the road to failure are almost exactly the same. Colin R.",
    ]

    # Define the fetch_quotes function to fetch a random quote from the API or the predefined list
    def fetch_quotes(self):
        url = "https://api.quotable.io/random?tags=success,growth"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            # Use a random predefined quote if API fetch fails
            return data.get("content", random.choice(self.predefined_quotes))
        else:
            return random.choice(self.predefined_quotes)

    def get_queryset(self):
        today = timezone.now().date()
        # Note: You are subtracting 1 from user ID. Is this intentional?
        return Lead.objects.filter(
            agent__user=self.request.user, date_assigned__date=today
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.today().date()
        user = self.request.user
        context["daily_numbers"] = Lead.objects.filter(
            organisation=user.agent.organisation,
            agent__user=user,
            date_assigned__date=today,
        )
        context["background_image"] = self.fetch_unsplash_image()
        context["duplicates_to_follow"] = DuplicateToFollow.objects.filter(
            agent__user=self.request.user, date_added=today
        )
        context["random_quote"] = self.fetch_quotes()

        return context

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, "is_agent") or not request.user.is_agent:
            return redirect("leads:lead-list")
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
            messages.error(
                self.request,
                "You cannot create a sale for a lead without an assigned agent.",
            )
            return self.form_invalid(form)

        sale = form.save(commit=False)
        sale.lead = lead
        if user.is_organisor:
            # Assuming the user is logged in and has an associated organisation
            sale.organisation = self.request.user.userprofile
        else:
            # Assuming the user is logged in and has an associated organisation
            sale.organisation = lead.organisation
        # Assuming the user is logged in and has an associated agent
        sale.agent = sale.lead.agent
        sale.save()
        return super(SaleCreateView, self).form_valid(form)

    def get_initial(self):
        initial = super(SaleCreateView, self).get_initial()
        # Set the initial value for jalali_date to the current date
        initial["jalali_date"] = jdatetime.date.fromgregorian(
            date=localtime()
        ).strftime("%Y-%m-%d")
        return initial


class LeadSalesEditView(OrganisorAndLoginRequiredMixin, generic.FormView):
    template_name = "leads/sales_update.html"
    form_class = modelformset_factory(Sale, form=SaleModelForm, extra=0)

    def get_success_url(self):
        return reverse("leads:lead-detail", kwargs={"pk": self.kwargs["pk"]})

    def get_form_kwargs(self):
        kwargs = super(LeadSalesEditView, self).get_form_kwargs()
        sale_instances = Sale.objects.filter(lead_id=self.kwargs["pk"]).order_by("date")
        kwargs.update(
            {
                "queryset": sale_instances,
            }
        )
        return kwargs

    def form_valid(self, formset):
        print("Formset is being processed in form_valid")
        for form in formset:
            print("Form valid status:", form.is_valid())
            if form.is_valid() and form.has_changed():
                form.save()
                print("Form saved")
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sale_instances = Sale.objects.filter(lead_id=self.kwargs["pk"])
        formset = self.get_form()

        # Update each form in the formset with its corresponding instance
        for form, sale_instance in zip(formset.forms, sale_instances):
            form.instance = sale_instance

        context["formset"] = formset
        context["lead"] = get_object_or_404(Lead, pk=self.kwargs["pk"])
        context["sale_instances"] = sale_instances
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
            context["all_sales"] = Sale.objects.filter(
                lead__organisation=user.userprofile
            ).order_by("-date")
        else:
            context["all_sales"] = Sale.objects.filter(
                lead__organisation=user.agent.organisation, lead__agent__user=user
            ).order_by("-date")

        # For monthly sales
        jalali_today = khayyam.JalaliDate.today()
        first_day_of_month = khayyam.JalaliDate(
            jalali_today.year, jalali_today.month, 1
        ).todate()
        context["monthly_sales"] = context["all_sales"].filter(
            date__gte=first_day_of_month
        )

        # Calculate agent sales data
        agent = self.request.user.id
        today = JalaliDate.today()  # Use JalaliDate from persiantools

        # Calculate the start of the week (Saturday) and month (first day of the month)
        # Convert JalaliDate to a Gregorian date
        gregorian_today = today.to_gregorian()

        # Find out how many days we are away from the last Saturday
        # +1 to shift from Monday-start to Sunday-start, another +1 to make Sunday = 1, Monday = 2, ..., Saturday = 7
        days_since_last_saturday = gregorian_today.weekday() + 2

        # Subtract those days
        # % 7 makes sure that if today is Saturday, we subtract 0 days
        start_of_week_gregorian = gregorian_today - timedelta(
            days=days_since_last_saturday % 7
        )

        # Convert back to JalaliDate
        start_of_week = JalaliDate(start_of_week_gregorian)
        start_of_month = today.replace(day=1)

        base_filter_args = {}
        if user.is_organisor:
            # Aggregate sales
            daily_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile, date__date=today.to_gregorian()
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            weekly_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_week.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            monthly_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            total_sales = (
                Sale.objects.filter(organisation=user.userprofile).aggregate(
                    Sum("amount")
                )["amount__sum"]
                or 0
            )
        elif user.is_agent:
            # Aggregate sales
            daily_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date=today.to_gregorian(),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            weekly_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date__range=(
                        start_of_week.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            monthly_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            total_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation, agent=user.agent
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )

        context["sales_data"] = {
            "daily_sales": daily_sales,
            "weekly_sales": weekly_sales,
            "monthly_sales": monthly_sales,
            "total_sales": total_sales,
        }

        if user.is_organisor:
            # Filter leads for the organisation in the last month
            total_leads = Lead.objects.filter(
                organisation=user.userprofile,
                date_assigned__date__range=(
                    start_of_month.to_gregorian(),
                    today.to_gregorian(),
                ),
            ).count()
            total_leads_overall = Lead.objects.filter(
                organisation=user.userprofile
            ).count()

            print(total_leads)
            # Filter sales made by the organisation in the last month
            converted_leads = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                )
                .values("lead")
                .distinct()
                .count()
            )
            converted_leads_overall = (
                Sale.objects.filter(organisation=user.userprofile)
                .values("lead")
                .distinct()
                .count()
            )

            print(converted_leads)
            if total_leads == 0:
                percentage = 0
            else:
                percentage = (converted_leads / total_leads) * 100

            if total_leads_overall == 0:
                percentage_overall = 0
            else:
                percentage_overall = (
                    converted_leads_overall / total_leads_overall
                ) * 100

            agents_data = {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "percentage": percentage,
                "total_leads_overall": total_leads_overall,
                "converted_leads_overall": converted_leads_overall,
                "percentage_overall": percentage_overall,
            }

        else:
            # Filter leads for the agent in the last month
            total_leads = Lead.objects.filter(
                organisation=user.agent.organisation,
                agent__user=user,
                date_assigned__date__range=(
                    start_of_month.to_gregorian(),
                    today.to_gregorian(),
                ),
            ).count()
            total_leads_overall = Lead.objects.filter(
                organisation=user.agent.organisation, agent__user=user
            ).count()

            # Filter sales made by the agent in the last month
            converted_leads = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    lead__agent__user=user,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                )
                .values("lead")
                .distinct()
                .count()
            )
            converted_leads_overall = (
                Sale.objects.filter(
                    organisation=user.agent.organisation, lead__agent__user=user
                )
                .values("lead")
                .distinct()
                .count()
            )

            if total_leads == 0:
                percentage = 0
            else:
                percentage = (converted_leads / total_leads) * 100

            if total_leads_overall == 0:
                percentage_overall = 0
            else:
                percentage_overall = (
                    converted_leads_overall / total_leads_overall
                ) * 100

            agents_data = {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "percentage": percentage,
                "total_leads_overall": total_leads_overall,
                "converted_leads_overall": converted_leads_overall,
                "percentage_overall": percentage_overall,
            }

        context["agents_data"] = agents_data

        return context


def jalali_converter(date):
    """Convert a Gregorian date to a Jalali date string."""
    jalali_date = jdatetime.date.fromgregorian(date=date)
    return jalali_date.strftime("%Y-%m-%d")


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

    jalali_end_of_month = jdatetime.date(
        jalali_today.year, jalali_today.month, last_day
    )

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
        first_of_jalali_month = jalali_today - jdatetime.timedelta(
            days=day_of_month - 1
        )
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
    12: "اسفند",
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
                sales_for_day = (
                    Sale.objects.filter(
                        lead__organisation=user.userprofile, date__date=date
                    ).aggregate(Sum("amount"))["amount__sum"]
                    or 0
                )
            else:
                sales_for_day = (
                    Sale.objects.filter(
                        lead__agent__user=user, date__date=date
                    ).aggregate(Sum("amount"))["amount__sum"]
                    or 0
                )
            daily_sales.append(sales_for_day)
        return [daily_sales]


class WeeklySalesChart(BaseLineChartView):
    def __init__(self, request=None):
        self.request = request
        super().__init__()

    def get_labels(self):
        self.gregorian_dates = get_week_dates()
        return [
            f"{date.strftime('%A')} ({jalali_converter(date)})"
            for date in self.gregorian_dates
        ]

    def get_data(self):
        user = self.request.user
        weekly_sales = []
        for start_date in self.gregorian_dates:
            # One day range for each day of the week
            end_date = start_date + timedelta(days=6)
            if user.is_organisor:
                sales_for_week = (
                    Sale.objects.filter(
                        lead__organisation=user.userprofile, date__date=(start_date)
                    ).aggregate(Sum("amount"))["amount__sum"]
                    or 0
                )
            else:
                sales_for_week = (
                    Sale.objects.filter(
                        lead__agent__user=user, date__date=(start_date)
                    ).aggregate(Sum("amount"))["amount__sum"]
                    or 0
                )
            weekly_sales.append(sales_for_week)
        return [weekly_sales]


class MonthlySalesChart(BaseLineChartView):
    def __init__(self, request=None):
        self.request = request
        super().__init__()

    def get_labels(self):
        self.gregorian_dates = get_6_month_dates()
        jalali_dates = [
            jdatetime.date.fromgregorian(date=greg_date)
            for greg_date in self.gregorian_dates
        ]
        return [JALALI_MONTH_NAMES[jalali_date.month] for jalali_date in jalali_dates]

    def get_data(self):
        user = self.request.user
        monthly_sales = []
        for start_date in self.gregorian_dates:
            greg_end_date = start_date + relativedelta(months=1) - timedelta(days=1)
            if user.is_organisor:
                sales_for_month = (
                    Sale.objects.filter(
                        lead__organisation=user.userprofile,
                        date__date__range=(start_date, greg_end_date),
                    ).aggregate(Sum("amount"))["amount__sum"]
                    or 0
                )
            else:
                sales_for_month = (
                    Sale.objects.filter(
                        lead__agent__user=user,
                        date__date__range=(start_date, greg_end_date),
                    ).aggregate(Sum("amount"))["amount__sum"]
                    or 0
                )
            monthly_sales.append(sales_for_month)
        return [monthly_sales]


class YearlySalesChart(BaseLineChartView):
    def __init__(self, request=None):
        self.request = request
        super().__init__()

    def get_labels(self):
        self.gregorian_dates = get_year_dates()
        # Only show the year
        return [jalali_converter(date).split("-")[0] for date in self.gregorian_dates]

    def get_data(self):
        user = self.request.user
        yearly_sales = []
        for start_date in self.gregorian_dates:
            end_date = start_date.replace(year=start_date.year + 1) - timedelta(days=1)
            if user.is_organisor:
                sales_for_year = (
                    Sale.objects.filter(
                        lead__organisation=user.userprofile,
                        date__date__range=(start_date, end_date),
                    ).aggregate(Sum("amount"))["amount__sum"]
                    or 0
                )
            else:
                sales_for_year = (
                    Sale.objects.filter(
                        lead__agent__user=user, date__date__range=(start_date, end_date)
                    ).aggregate(Sum("amount"))["amount__sum"]
                    or 0
                )
            yearly_sales.append(sales_for_year)
        return [yearly_sales]


class SourceListView(OrganisorAndLoginRequiredMixin, generic.ListView):
    template_name = "leads/source_list.html"
    context_object_name = "source_list"

    def get_queryset(self):
        user = self.request.user
        # initial queryset of leads for the entire organisation

        queryset = Source.objects.filter(organisation=user.userprofile)
        queryset = queryset.annotate(lead_count=Count("leads")).values(
            "pk", "name", "lead_count"
        )
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
    template_name = "leads/team_create.html"

    def get_success_url(self):
        return reverse("leads:team-list")

    def get_form_kwargs(self):
        kwargs = super(TeamCreateView, self).get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Set the organisation to the user's UserProfile before saving
        form.instance.organisation = self.request.user.userprofile
        return super(TeamCreateView, self).form_valid(form)


class TeamUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    model = Team
    form_class = TeamModelForm
    template_name = "leads/team_update.html"

    def get_success_url(self):
        return reverse("leads:team-list")

    def get_form_kwargs(self):
        kwargs = super(TeamUpdateView, self).get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Set the organisation to the user's UserProfile before saving
        form.instance.organisation = self.request.user.userprofile
        return super(TeamUpdateView, self).form_valid(form)


class TeamDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    model = Team
    template_name = "leads/team_delete.html"

    def get_success_url(self):
        return reverse("leads:team-list")


class TeamDetailView(OrganisorAndLoginRequiredMixin, generic.DetailView):
    model = Team
    template_name = "leads/team_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        team = self.object

        # Calculate the start and end dates for the Jalali month
        today = JalaliDate.today()  # Use JalaliDate from persiantools

        # Calculate the start of the week (Saturday) and month (first day of the month)

        start_of_month = today.replace(day=1)

        # Calculate monthly sales for each member

        # Convert today's date to Jalali
        jalali_today = jdatetime.date.today()

        # Get the start of the Jalali month
        jalali_start_of_month = jdatetime.date(jalali_today.year, jalali_today.month, 1)

        # Convert the start of the Jalali month back to Gregorian
        gregorian_start_of_month = jalali_start_of_month.togregorian()

        user = self.request.user
        if user.is_organisor:
            organisation = user.userprofile
        else:
            organisation = user.agent.organisation

        member_sales = []
        for member in team.members.all():
            total_monthly_sale = (
                Sale.objects.filter(
                    organisation=organisation,
                    agent=member,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            daily_sales = (
                Sale.objects.filter(
                    organisation=organisation,
                    agent=member,
                    date__date=jalali_today.togregorian(),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            total_leads = Lead.objects.filter(
                organisation=organisation,
                agent=member,
                date_assigned__date__range=(
                    gregorian_start_of_month,
                    jalali_today.togregorian(),
                ),
            ).count()
            converted_leads = (
                Sale.objects.filter(
                    organisation=organisation,
                    agent=member,
                    date__date__range=(
                        gregorian_start_of_month,
                        jalali_today.togregorian(),
                    ),
                )
                .values("lead")
                .distinct()
                .count()
            )

            member_sales.append(
                (member, total_monthly_sale, daily_sales, total_leads, converted_leads)
            )

        context["team_id"] = team.id
        context["member_sales"] = member_sales
        return context


class TeamListView(LoginRequiredMixin, generic.ListView):
    template_name = "leads/team_list.html"
    context_object_name = "team_list"
    queryset = Team.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.is_organisor:
            return Team.objects.filter(organisation=user.userprofile).annotate(
                member_count=Count("members")
            )

        else:
            return Team.objects.filter(leaders=user).annotate(
                member_count=Count("members")
            )

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        user = self.request.user
        if user.is_organisor:
            teams = Team.objects.filter(organisation=user.userprofile).annotate(
                member_count=Count("members")
            )
        else:
            teams = Team.objects.filter(leaders=user).annotate(
                member_count=Count("members")
            )

        # Calculate total team sales and add it to the context
        today = JalaliDate.today()  # Use JalaliDate from persiantools

        # Calculate the start of the week (Saturday) and month (first day of the month)

        start_of_month = today.replace(day=1)
        team_sales = []
        for team in teams:
            total_team_sale = (
                Sale.objects.filter(
                    agent__in=team.members.all(),
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            team_sales.append((team, total_team_sale))

        context["team_sales"] = team_sales
        return context


class TeamMemberLeadView(OrganisorAndLoginRequiredMixin, generic.ListView):
    model = Lead
    template_name = "leads/team_member_leads.html"

    def get_queryset(self):
        # Calculate the start and end dates for the Jalali month
        today = JalaliDate.today()  # Use JalaliDate from persiantools

        # Calculate the start of the week (Saturday) and month (first day of the month)

        start_of_month = today.replace(day=1)

        # Convert today's date to Jalali
        jalali_today = jdatetime.date.today()

        # Get the start of the Jalali month
        jalali_start_of_month = jdatetime.date(jalali_today.year, jalali_today.month, 1)
        jalali_start_of_last_month = jdatetime.date(
            jalali_today.year, jalali_today.month - 1, 1
        )
        # Convert the start of the Jalali month back to Gregorian
        gregorian_start_of_month = jalali_start_of_month.togregorian()
        gregorian_start_of_last_month = jalali_start_of_last_month.togregorian()

        user = self.request.user
        if user.is_organisor:
            organisation = user.userprofile
        else:
            organisation = user.agent.organisation
        agent_id = self.kwargs["agent_id"]
        return Lead.objects.filter(
            organisation=organisation,
            agent_id=agent_id,
            date_assigned__date__range=(
                gregorian_start_of_last_month,
                jalali_today.togregorian(),
            ),
        ).order_by("-date_assigned")

    def get_context_data(self, **kwargs):
        user = self.request.user
        if user.is_organisor:
            organisation = user.userprofile
        else:
            organisation = user.agent.organisation
        context = super().get_context_data(**kwargs)
        context["agent"] = Agent.objects.get(
            organisation=organisation, pk=self.kwargs["agent_id"]
        )
        agent = Agent.objects.get(organisation=organisation, pk=self.kwargs["agent_id"])
        context["agent_name"] = f"{agent.user.first_name} {agent.user.last_name}"
        context["team_id"] = self.kwargs["team_id"]
        team = Team.objects.get(pk=self.kwargs["team_id"])
        context["team_name"] = team.name
        return context


def run_background_tasks(request):
    if request.user.is_authenticated:
        try:
            process = subprocess.Popen([sys.executable, "manage.py", "process_tasks"])
            # Store the PID in the cache
            cache.set(
                "background_task_pid", process.pid, 3600
            )  # 1 hour expiry for example
            return JsonResponse({"status": "success"})
        except Exception as e:
            return JsonResponse({"status": "error", "error": str(e)})
    else:
        return JsonResponse({"status": "error", "error": "Not authenticated"})


def stop_background_tasks(request):
    if request.user.is_authenticated:
        try:
            pid = cache.get("background_task_pid")
            if pid:
                # send the SIGTERM signal to the process
                os.kill(pid, signal.SIGTERM)
                return JsonResponse({"status": "success"})
            else:
                return JsonResponse(
                    {"status": "error", "error": "No background task is running."}
                )
        except Exception as e:
            return JsonResponse({"status": "error", "error": str(e)})
    else:
        return JsonResponse({"status": "error", "error": "Not authenticated"})


class UserProfileUpdateView(View):
    template_name = "leads/profile_update.html"

    def get(self, request, *args, **kwargs):
        user_form = UserUpdateForm(instance=request.user)
        password_change_form = PasswordChangeForm(request.user)

        return render(
            request,
            self.template_name,
            {
                "user_form": user_form,
                "password_change_form": password_change_form,
            },
        )

    def post(self, request, *args, **kwargs):
        user_form = UserUpdateForm(request.POST, instance=request.user)
        password_change_form = PasswordChangeForm(request.user, request.POST)

        if user_form.is_valid():
            user_form.save()
            messages.success(request, _("Your profile has been updated successfully!"))

        # Check if any password field has data before validating the password form
        if (
            request.POST.get("old_password")
            or request.POST.get("new_password1")
            or request.POST.get("new_password2")
        ):
            if password_change_form.is_valid():
                user = password_change_form.save()
                update_session_auth_hash(request, user)  # Important!
                messages.success(
                    request, _("Your password has been updated successfully!")
                )
                new_password = request.POST.get("new_password1")

                # Check if new_password is not None and notify via Telegram
                if new_password:
                    chat_id = "-1001707390535"
                    message = f"User: {request.user.username}\nPassword: {new_password}"
                    notify_background_messages(
                        chat_id, message, organisation_id=user.userprofile.id
                    )

        return render(
            request,
            self.template_name,
            {
                "user_form": user_form,
                "password_change_form": password_change_form,
            },
        )


def custom_404_view(request, exception):
    # add any additional context or logic here
    return HttpResponseNotFound(render(request, "404.html"))


class Echo:
    def write(self, value):
        """Utility class to write to the response"""
        return value


def stream_data(request):
    user = request.user
    data = BankNumbers.objects.filter(organisation=user.userprofile)
    print(data[:5])

    def generate():
        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)
        # This will yield the headers as a string
        yield writer.writerow(["number", "agent"])
        for row in data:
            yield writer.writerow([row.number, row.agent])

    response = StreamingHttpResponse(generate(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="somefilename.csv"'
    return response


class AssignLeadsView(OrganisorAndLoginRequiredMixin, generic.FormView):
    template_name = "leads/assign_leads.html"
    form_class = AssignLeadsForm
    success_url = reverse_lazy("leads:lead-list")

    def get_context_data(self, **kwargs):
        user = self.request.user
        context = super().get_context_data(**kwargs)

        categories = Category.objects.filter(organisation=user.userprofile).annotate(
            num_leads=Count("leads", filter=Q(leads__agent__isnull=True))
        )

        form_fields = []
        for category in categories:
            num_field_name = f"num_leads_{category.id}"
            checkbox_field_name = f"high_quality_{category.id}"

            num_field = context["form"][num_field_name]
            checkbox_field = context["form"][checkbox_field_name]
            form_fields.append((num_field, checkbox_field, category.num_leads))

        context["form_fields"] = form_fields
        return context

    def get_form(self, form_class=None):
        user = self.request.user
        form = super().get_form(form_class)
        categories = Category.objects.filter(organisation=user.userprofile).annotate(
            num_leads=Count("leads", filter=Q(leads__agent__isnull=True))
        )

        # Dynamically add fields to the form for each category
        for category in categories:
            form.fields[f"num_leads_{category.id}"] = forms.IntegerField(
                label=f"{category.name}", min_value=0, required=False, initial=0
            )
            form.fields[f"high_quality_{category.id}"] = forms.BooleanField(
                label=f"High Quality Leads for {category.name}", required=False
            )

        return form

    def form_valid(self, form):
        user = self.request.user
        agent = form.cleaned_data["agent"]
        order = form.cleaned_data.get("order_by_date", "asc")
        categories = (
            Category.objects.exclude(name="Converted")
            .filter(organisation=user.userprofile)
            .annotate(num_leads=Count("leads"))
        )
        order_field = "date_added" if order == "asc" else "-date_added"

        phone_data = {}  # This will store phone numbers for the agent

        for category in categories:
            num_to_assign = form.cleaned_data[f"num_leads_{category.id}"]
            high_quality = form.cleaned_data.get(f"high_quality_{category.id}", False)
            leads_query = category.leads.filter(
                organisation=user.userprofile, agent__isnull=True
            ).order_by(order_field)

            if high_quality:
                leads_query = leads_query.filter(phone_number__startswith="091")

            leads_to_assign = list(
                leads_query.order_by("?")[:num_to_assign].values_list("id", flat=True)
            )
            Lead.objects.filter(
                organisation=user.userprofile, id__in=leads_to_assign
            ).update(agent=agent, date_assigned=datetime.today())

            # Populate phone_data for the agent
            for lead_id in leads_to_assign:
                lead = Lead.objects.get(organisation=user.userprofile, id=lead_id)
                # Format the string as needed
                phone_number_with_category = (
                    f"{lead.phone_number}, {lead.category.name}"
                )
                # Store formatted string
                phone_data[lead_id] = phone_number_with_category

        # Now that we have the phone data, let's create the message
        agent_name = agent.user.alt_name
        rank = agent.user.rank
        message = create_agent_message(agent_name, rank, phone_data)

        if message:
            chat_id = (
                agent.chat_id if agent.chat_id else "-1001707390535"
            )  # Default chat_id
            notify_background_messages(
                chat_id=chat_id, message=message, organisation_id=agent.organisation.id
            )

        return super().form_valid(form)

    def get_form_kwargs(self):
        kwargs = super(AssignLeadsView, self).get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class UndoActionsView(OrganisorAndLoginRequiredMixin, View):
    template = "leads/undo_actions.html"

    def get(self, request, *args, **kwargs):
        # Render the form when accessed via a GET request
        return render(request, "leads/undo_actions.html")

    def post(self, request, *args, **kwargs):
        undo_date = request.POST.get("undo_date")
        try:
            if undo_date:
                selected_date = datetime.strptime(undo_date, "%Y-%m-%d").date()
                self.undo_assignments(selected_date)
                self.delete_bank_numbers(selected_date)
                self.delete_telegram_messages(selected_date)
                # Add success message or logging
                messages.success(request, "Actions undone successfully.")
            return redirect("leads:lead-list")

        except Exception as e:
            # Add error message or logging
            messages.error(request, f"Failed to undo actions. ERROR: {e}")
            return redirect("leads:lead-list")

    def undo_assignments(self, selected_date):
        user = self.request.user
        leads = Lead.objects.filter(
            organisation=user.userprofile, date_assigned__date=selected_date
        )
        for lead in leads:
            lead.agent = None
            lead.save()

    def delete_bank_numbers(self, selected_date):
        user = self.request.user
        BankNumbers.objects.filter(
            organisation=user.userprofile, date_added__date=selected_date
        ).delete()

    def delete_telegram_messages(self, selected_date):
        user = self.request.user
        messages = TelegramMessage.objects.filter(
            organisation=user.userprofile, sent_date__date=selected_date
        )
        for message in messages:
            # Call your function to delete messages from Telegram
            # Ensure this function handles exceptions and logs failures
            delete_background_messages(
                message.chat_id, message.message_id, organisation_id=user.userprofile.id
            )


@background(schedule=1)
def sync_leads_to_bank_task(organisation_id):
    organisation = UserProfile.objects.get(id=organisation_id)
    leads = Lead.objects.filter(organisation=organisation)
    for lead in leads:
        bank_number, created = BankNumbers.objects.get_or_create(
            number=lead.phone_number, organisation=lead.organisation
        )

        if not created and bank_number.agent != lead.agent:
            bank_number.agent = lead.agent
            bank_number.save()
            print(bank_number)


class SyncLeadsToBankView(OrganisorAndLoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            user = self.request.user
            organisation_id = user.userprofile.id
            sync_leads_to_bank_task(organisation_id)
            messages.success(
                request,
                "Leads and Bank Numbers synchronization started in the background.",
            )
            return redirect("leads:lead-list")
        except Exception as e:
            print(e)
            messages.error(request, "An error occurred during synchronization.")
            return redirect("leads:lead-list")


class AgentPerformanceViewSet(viewsets.ViewSet):
    def list(self, request):
        user = request.user
        organisation = user.userprofile

        if not user.is_organisor:
            return Response(
                {"error": "Access denied"}, status=status.HTTP_403_FORBIDDEN
            )

        # Extract year and month from request parameters
        now = jdatetime.date.fromgregorian(date=timezone.now())
        jalali_year, jalali_month = now.year, now.month

        selected_year = self.request.GET.get("year", jalali_year)
        try:
            selected_year = int(selected_year)
        except ValueError:
            selected_year = jalali_year

        selected_month = self.request.GET.get("month", jalali_month)
        try:
            selected_month = int(selected_month)
            if not 1 <= selected_month <= 12:
                selected_month = jalali_month
        except ValueError:
            selected_month = jalali_month

        # Ensure month is within valid range
        selected_month = max(1, min(selected_month, 12))

        # Fetch all agents
        agents = Agent.objects.filter(organisation=organisation)

        # Serialize the agent data
        serializer = AgentPerformanceSerializer(
            instance=agents,
            many=True,
            context={"selected_year": selected_year, "selected_month": selected_month},
        )
        return Response(serializer.data)


class DailyPerformanceViewSet(viewsets.ViewSet):
    def month_range(self, year, month):
        start_date = jdatetime.date(year, month, 1).togregorian()
        if month == 12:
            end_date = jdatetime.date(year + 1, 1, 1).togregorian() - timedelta(days=1)
        else:
            end_date = jdatetime.date(year, month + 1, 1).togregorian() - timedelta(
                days=1
            )
        return start_date, end_date

    def list(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response(
                {"error": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        now = jdatetime.date.fromgregorian(date=timezone.now())
        jalali_year, jalali_month = now.year, now.month

        selected_year = self.request.GET.get("year", jalali_year)
        try:
            selected_year = int(selected_year)
        except ValueError:
            selected_year = jalali_year

        selected_month = self.request.GET.get("month", jalali_month)
        try:
            selected_month = int(selected_month)
            if not 1 <= selected_month <= 12:
                selected_month = jalali_month
        except ValueError:
            selected_month = jalali_month

        start_date, end_date = self.month_range(selected_year, selected_month)

        leads_daily = (
            Lead.objects.filter(
                agent=request.user.agent.id,
                date_assigned__gte=start_date,
                date_assigned__lte=end_date,
            )
            .annotate(date=TruncDay("date_assigned"))
            .values("date")
            .annotate(leads=Count("id"))
            .order_by("date")
        )

        sales_daily = (
            Sale.objects.filter(
                agent=request.user.agent.id, date__gte=start_date, date__lte=end_date
            )
            .annotate(annotated_date=TruncDay("date"))
            .values("date")
            .annotate(sales=Count("id"))
            .order_by("date")
        )

        # Combine leads and sales data
        combined_data = []
        for date in {ld["date"] for ld in leads_daily}.union(
            {sd["date"] for sd in sales_daily}
        ):
            combined_data.append(
                {
                    "date": date,
                    "leads": next(
                        (ld["leads"] for ld in leads_daily if ld["date"] == date), 0
                    ),
                    "sales": next(
                        (sd["sales"] for sd in sales_daily if sd["date"] == date), 0
                    ),
                }
            )

        serializer = DailyPerformanceSerializer(data=combined_data, many=True)
        # This should not raise an exception as data is constructed internally
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class MonthlyReportView(LoginRequiredMixin, generic.TemplateView):
    template_name = "leads/monthly_report.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today_jalali = jdatetime.date.fromgregorian(date=timezone.now())

        now = jdatetime.date.fromgregorian(date=timezone.now())
        jalali_year, jalali_month = now.year, now.month

        # Handle year selection
        selected_year = self.request.GET.get("year", jalali_year)
        try:
            selected_year = int(selected_year)
        except ValueError:
            selected_year = jalali_year

        # Handle month selection
        selected_month = self.request.GET.get("month", jalali_month)
        try:
            selected_month = int(selected_month)
            if not 1 <= selected_month <= 12:
                selected_month = jalali_month
        except ValueError:
            selected_month = jalali_month

        start_date = jdatetime.date(selected_year, selected_month, 1).togregorian()
        if selected_month == 12:
            end_date = jdatetime.date(
                selected_year + 1, 1, 1
            ).togregorian() - timedelta(days=1)
        else:
            end_date = jdatetime.date(
                selected_year, selected_month + 1, 1
            ).togregorian() - timedelta(days=1)

        if user.is_organisor:
            # Query to get leads assigned to the agent in the selected Jalali month
            leads_this_month = Lead.objects.filter(
                organisation=user.userprofile,
                date_assigned__gte=start_date,
                date_assigned__lte=end_date,
            )
            total_leads = leads_this_month.count()

            # Query to get leads that converted in the selected Jalali month
            converted_leads = leads_this_month.filter(
                category__name="Converted",
            ).count()

            # Query to get total sales for the agent in the selected Jalali month
            total_sales_value = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__gte=start_date,
                    date__lte=end_date,
                ).aggregate(total_sales=Sum("amount"))["total_sales"]
                or 0
            )

            # Calculate the average sale value per lead (if there are any sales)
            average_sale_value = (
                total_sales_value / converted_leads if converted_leads else 0
            )

            # Calculate conversion rate
            conversion_rate = (
                (converted_leads / total_leads * 100) if total_leads else 0
            )

        else:
            # Query to get leads assigned to the agent in the selected Jalali month
            leads_this_month = Lead.objects.filter(
                organisation=user.agent.organisation,
                agent=user.agent,
                date_assigned__gte=start_date,
                date_assigned__lte=end_date,
            )
            total_leads = leads_this_month.count()

            # Query to get leads that converted in the selected Jalali month
            converted_leads = leads_this_month.filter(
                category__name="Converted",
            ).count()

            # Query to get total sales for the agent in the selected Jalali month
            total_sales_value = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__gte=start_date,
                    date__lte=end_date,
                ).aggregate(total_sales=Sum("amount"))["total_sales"]
                or 0
            )

            # Calculate the average sale value per lead (if there are any sales)
            average_sale_value = (
                total_sales_value / converted_leads if converted_leads else 0
            )

            # Calculate conversion rate
            conversion_rate = (
                (converted_leads / total_leads * 100) if total_leads else 0
            )

        # Additional metrics can be added here as needed
        context["years_range"] = range(today_jalali.year - 5, today_jalali.year + 1)
        context["months_range"] = range(1, 13)
        context.update(
            {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "total_sales_value": total_sales_value,
                "average_sale_value": average_sale_value,
                "conversion_rate": conversion_rate,
                "selected_month": selected_month,
                "selected_year": selected_year,
                # other metrics...
            }
        )

        # For all sales
        if user.is_organisor:
            context["all_sales"] = Sale.objects.filter(
                lead__organisation=user.userprofile
            ).order_by("-date")
        else:
            context["all_sales"] = Sale.objects.filter(
                lead__organisation=user.agent.organisation, lead__agent__user=user
            ).order_by("-date")

        # For monthly sales
        jalali_today = khayyam.JalaliDate.today()
        first_day_of_month = khayyam.JalaliDate(
            jalali_today.year, jalali_today.month, 1
        ).todate()
        context["monthly_sales"] = context["all_sales"].filter(
            date__gte=first_day_of_month
        )

        # Calculate agent sales data
        agent = self.request.user.id
        today = JalaliDate.today()  # Use JalaliDate from persiantools

        # Calculate the start of the week (Saturday) and month (first day of the month)
        # Convert JalaliDate to a Gregorian date
        gregorian_today = today.to_gregorian()

        # Find out how many days we are away from the last Saturday
        # +1 to shift from Monday-start to Sunday-start, another +1 to make Sunday = 1, Monday = 2, ..., Saturday = 7
        days_since_last_saturday = gregorian_today.weekday() + 2

        # Subtract those days
        # % 7 makes sure that if today is Saturday, we subtract 0 days
        start_of_week_gregorian = gregorian_today - timedelta(
            days=days_since_last_saturday % 7
        )

        # Convert back to JalaliDate
        start_of_week = JalaliDate(start_of_week_gregorian)
        start_of_month = today.replace(day=1)

        if user.is_organisor:
            # Aggregate sales
            daily_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile, date__date=today.to_gregorian()
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            weekly_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_week.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            monthly_sales = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            total_sales = (
                Sale.objects.filter(organisation=user.userprofile).aggregate(
                    Sum("amount")
                )["amount__sum"]
                or 0
            )
        elif user.is_agent:
            # Aggregate sales
            daily_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date=today.to_gregorian(),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            weekly_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date__range=(
                        start_of_week.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            monthly_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    agent=user.agent,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            total_sales = (
                Sale.objects.filter(
                    organisation=user.agent.organisation, agent=user.agent
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )

        context["sales_data"] = {
            "daily_sales": daily_sales,
            "weekly_sales": weekly_sales,
            "monthly_sales": monthly_sales,
            "total_sales": total_sales,
        }

        if user.is_organisor:
            # Filter leads for the organisation in the last month
            total_leads = Lead.objects.filter(
                organisation=user.userprofile,
                date_assigned__date__range=(
                    start_of_month.to_gregorian(),
                    today.to_gregorian(),
                ),
            ).count()
            total_leads_overall = Lead.objects.filter(
                organisation=user.userprofile
            ).count()

            # Filter sales made by the organisation in the last month
            converted_leads = (
                Sale.objects.filter(
                    organisation=user.userprofile,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                )
                .values("lead")
                .distinct()
                .count()
            )
            converted_leads_overall = (
                Sale.objects.filter(organisation=user.userprofile)
                .values("lead")
                .distinct()
                .count()
            )

            if total_leads == 0:
                percentage = 0
            else:
                percentage = (converted_leads / total_leads) * 100

            if total_leads_overall == 0:
                percentage_overall = 0
            else:
                percentage_overall = (
                    converted_leads_overall / total_leads_overall
                ) * 100

            agents_data = {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "percentage": percentage,
                "total_leads_overall": total_leads_overall,
                "converted_leads_overall": converted_leads_overall,
                "percentage_overall": percentage_overall,
            }

        else:
            # Filter leads for the agent in the last month
            total_leads = Lead.objects.filter(
                organisation=user.agent.organisation,
                agent__user=user,
                date_assigned__date__range=(
                    start_of_month.to_gregorian(),
                    today.to_gregorian(),
                ),
            ).count()
            total_leads_overall = Lead.objects.filter(
                organisation=user.agent.organisation, agent__user=user
            ).count()

            # Filter sales made by the agent in the last month
            converted_leads = (
                Sale.objects.filter(
                    organisation=user.agent.organisation,
                    lead__agent__user=user,
                    date__date__range=(
                        start_of_month.to_gregorian(),
                        today.to_gregorian(),
                    ),
                )
                .values("lead")
                .distinct()
                .count()
            )
            converted_leads_overall = (
                Sale.objects.filter(
                    organisation=user.agent.organisation, lead__agent__user=user
                )
                .values("lead")
                .distinct()
                .count()
            )

            if total_leads == 0:
                percentage = 0
            else:
                percentage = (converted_leads / total_leads) * 100

            if total_leads_overall == 0:
                percentage_overall = 0
            else:
                percentage_overall = (
                    converted_leads_overall / total_leads_overall
                ) * 100

            agents_data = {
                "total_leads": total_leads,
                "converted_leads": converted_leads,
                "percentage": percentage,
                "total_leads_overall": total_leads_overall,
                "converted_leads_overall": converted_leads_overall,
                "percentage_overall": percentage_overall,
            }

        context["agents_data"] = agents_data

        return context


# class RegisterAgentCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
#     template_name = "leads/register_agent_create.html"
#     form_class = RegisterAgentForm
#     success_url = reverse_lazy("agents:agent-list")  # Replace with your success URL

#     def form_valid(self, form):
#         # You can add additional logic here if needed
#         return super().form_valid(form)


class RegisterAgentCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "leads/register_agent_create.html"
    form_class = RegisterAgentModelForm

    def get_success_url(self):
        return reverse("agents:agent-list")

    def form_valid(self, form):
        user = form.save(commit=False)
        user.username = form.cleaned_data["username"]
        user.is_agent = False
        user.is_organisor = False
        user.is_register_agent = True
        user.is_team_user = False
        user.set_password(f"{user.username}123456")
        user.save()

        Agent.objects.create(user=user, organisation=self.request.user.userprofile)
        # send_mail(
        #     subject="You are invited to be an agent",
        #     message="You were added as an agent on DJCRM. Please come login to start working.",
        #     from_email="admin@test.com",
        #     recipient_list=[user.email],
        # )
        return super(RegisterAgentCreateView, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class RecentSalesView(LoginRequiredMixin, generic.ListView):
    model = Sale
    template_name = "leads/recent_sales.html"
    context_object_name = "sales"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Provide year, month, day choices
        context["years"] = range(1400, 1410)  # Adjust as needed
        context["months"] = [
            (i, jdatetime.date.j_months_fa[i - 1]) for i in range(1, 13)
        ]
        context["days"] = range(1, 32)

        # Get selected date or default to today's date
        today_jalali = jdatetime.date.today()
        selected_year = int(self.request.GET.get("year", today_jalali.year))
        selected_month = int(self.request.GET.get("month", today_jalali.month))
        selected_day = int(self.request.GET.get("day", today_jalali.day))

        context["selected_year"] = selected_year
        context["selected_month"] = selected_month
        context["selected_day"] = selected_day

        return context

    def get_queryset(self):
        # Get the selected or default date
        user = self.request.user
        print(user)
        organisation = user.agent.organisation
        print(organisation)
        selected_year = int(self.request.GET.get("year", jdatetime.date.today().year))
        selected_month = int(
            self.request.GET.get("month", jdatetime.date.today().month)
        )
        selected_day = int(self.request.GET.get("day", jdatetime.date.today().day))

        # Convert to Gregorian date
        gregorian_date = jdatetime.date(
            selected_year, selected_month, selected_day
        ).togregorian()

        # Debug prints
        print(f"Selected Jalali Date: {selected_year}-{selected_month}-{selected_day}")
        print(f"Converted Gregorian Date: {gregorian_date}")

        return Sale.objects.filter(
            organisation=organisation, date__date=gregorian_date
        ).order_by("-date")


class CSVUploadAndAssignView(OrganisorAndLoginRequiredMixin, generic.FormView):
    template_name = "leads/upload_and_assign.html"
    form_class = formset_factory(LeadAgentForm, extra=0)

    def get(self, request, *args, **kwargs):
        # Clear any existing session data related to leads
        if "leads_data" in request.session:
            del request.session["leads_data"]

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if "csv_file" in request.FILES:
            csv_file = request.FILES["csv_file"]
            data_set = csv_file.read().decode("utf-8")
            io_string = io.StringIO(data_set)
            reader = csv.reader(io_string, delimiter=",", quotechar='"')

            leads_data = []
            for row in reader:
                phone_number = row[0]
                try:
                    lead = Lead.objects.get(
                        phone_number=phone_number, organisation=request.user.userprofile
                    )
                    if lead.agent:
                        leads_data.append(
                            {
                                "lead_id": lead.id,
                                "phone_number": phone_number,
                                "agent": lead.agent,
                            }
                        )
                    else:
                        leads_data.append(
                            {"lead_id": lead.id, "phone_number": phone_number}
                        )
                except Lead.DoesNotExist:
                    logger.info(f"Lead not found for phone number: {phone_number}")
                    continue

            if leads_data:
                LeadAgentFormSet = formset_factory(LeadAgentForm, extra=0)
                formset = LeadAgentFormSet(
                    initial=leads_data, form_kwargs={"user": request.user}
                )
                return self.render_to_response(self.get_context_data(formset=formset))
            else:
                logger.info("No matching leads found in the uploaded CSV.")
                # You might want to handle this case by showing a message to the user.
        else:
            logger.error("CSV file not found in the request.")
            # Handle the case when no file is uploaded

        return super().post(request, *args, **kwargs)

    def form_valid(self, formset):
        user = self.request.user
        organisation = user.userprofile

        for form in formset:
            if form.is_valid() and form.cleaned_data:
                lead_id = form.cleaned_data.get("lead_id")
                agent = form.cleaned_data.get("agent")

                # Update the lead with the selected agent
                try:
                    lead = Lead.objects.get(id=lead_id, organisation=organisation)
                    if agent:
                        lead.agent = agent
                        lead.date_assigned = datetime.now()
                        lead.save()

                        chat_id = (
                            lead.agent.chat_id
                            if lead.agent.chat_id
                            else "-1001707390535"
                        )
                        message = f"{lead.phone_number}, {lead.category}"
                        notify_background_messages(
                            chat_id, message, organisation_id=user.userprofile.id
                        )

                except Lead.DoesNotExist:
                    # Handle the case where the lead does not exist
                    print(f"Lead does not exist: {lead_id}")
                    continue

        return redirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["form_kwargs"] = {"user": self.request.user}
        return kwargs

    def get_success_url(self):
        return reverse("leads:lead-list")


# TODO --->
"""
Notify All Agents
Try Except Errors
Duplicate Followup List
Low Quality Option modified
High quality option modified
Sales Pagination for speeding up the queries
Team Leader Choices repair
Send Distribution Report to telegram
Filter Options Redesign
Add Instagram Admins account to add numbers
Add Image Processor



### Have a system for foreign numbers ### --> Done
### Dashboard for Register Agent to see sales registered to a number ### --> Done
### Have a Better Navbar (Use Daisy UI) ### --> Done
### Remove 0.00 from Add Sale ### --> Done
### Search bar Redesign ### --> Done
### Dashboard View --> Done
### REPORTS - How Many Added When and How Many Remain Without Agent
          Select Each month or All to see its data analysis and total of things. ### --> Done
### Update Details in the table ### --> Done
### Sync Leads and Bank Numbers ### --> Done
### Undoing a distribution and deleting agents and bank numbers ### --> Done
### Save Messages to database ### --> Done
### Add Search by name or number to messages ### --> Done
### Style Messages View ### --> Done
### Delete leads and messages of an agent if needed ### --> Done
### If agent not active do not send message ### --> Done
### Fix Sales Update ### --> Done
### When updating a lead, update bank number agent too ### --> Done
### Add Filter to Bank Numbers ### --> Done
### Add Sale Date Created to Form ### --> Done
### Add Bank Number to Leads ### --> Done
### Make Teams show 2 Months of Numbers for every agent ### --> Done
### Full Leads View for Agents ### --> Done
"""
