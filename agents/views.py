import random
from typing import Any
from django.contrib import messages

from django.core.mail import send_mail
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, reverse
from leads.models import Agent, User, UserProfile, Sale, Lead
from .forms import AgentModelForm, AgentImportForm
from .mixins import OrganisorAndLoginRequiredMixin
import csv
from django.db.models import F
from datetime import timedelta, date, datetime
from django.db.models import Sum
import jdatetime
from django.utils.translation import gettext as _


class AgentListView(OrganisorAndLoginRequiredMixin, generic.ListView):
    template_name = "agents/agent_list.html"

    def get_queryset(self):
        organisation = self.request.user.userprofile
        return (
            Agent.objects.filter(organisation=organisation)
            .annotate(rank=F("user__rank"))
            .exclude(user__is_register_agent=True)
        )

    def get_context_data(self, **kwargs):
        context = super(AgentListView, self).get_context_data(**kwargs)
        user = self.request.user
        organisation = user.userprofile
        # Convert today's date to Jalali
        jalali_today = jdatetime.date.today()

        # Get the start of the Jalali month
        jalali_start_of_month = jdatetime.date(jalali_today.year, jalali_today.month, 1)

        # Convert the start of the Jalali month back to Gregorian
        gregorian_start_of_month = jalali_start_of_month.togregorian()

        agent_list = Agent.objects.filter(
            organisation=self.request.user.userprofile
        ).annotate(rank=F("user__rank"))
        agents_sales_data = []
        for agent in agent_list:
            daily_sales = (
                Sale.objects.filter(
                    organisation=organisation,
                    agent=agent,
                    date__date=jalali_today.togregorian(),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            monthly_sales = (
                Sale.objects.filter(
                    organisation=organisation,
                    agent=agent,
                    date__date__range=(
                        gregorian_start_of_month,
                        jalali_today.togregorian(),
                    ),
                ).aggregate(Sum("amount"))["amount__sum"]
                or 0
            )
            total_leads = Lead.objects.filter(
                organisation=organisation,
                agent=agent,
                date_assigned__range=(
                    gregorian_start_of_month,
                    jalali_today.togregorian(),
                ),
            ).count()
            converted_leads = (
                Sale.objects.filter(
                    organisation=organisation,
                    agent=agent,
                    date__date__range=(
                        gregorian_start_of_month,
                        jalali_today.togregorian(),
                    ),
                )
                .values("lead")
                .distinct()
                .count()
            )
            total_leads_overall = Lead.objects.filter(
                organisation=organisation, agent=agent
            ).count()
            converted_leads_overall = (
                Sale.objects.filter(organisation=organisation, agent=agent)
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

            agent_teams = agent.teams.all()

            agents_sales_data.append(
                {
                    "agent": agent,
                    "daily_sales": daily_sales,
                    "monthly_sales": monthly_sales,
                    "total_leads": total_leads,
                    "converted_leads": converted_leads,
                    "conversion_rate": round(percentage, 2),
                    "total_leads_overall": total_leads_overall,
                    "converted_leads_overall": converted_leads_overall,
                    "conversion_rate_overall": round(percentage_overall, 2),
                    "teams": agent_teams,
                }
            )

        context["agents_sales_data"] = agents_sales_data
        return context


class AgentCreateView(OrganisorAndLoginRequiredMixin, generic.CreateView):
    template_name = "agents/agent_create.html"
    form_class = AgentModelForm

    def get_success_url(self):
        return reverse("agents:agent-list")

    def form_valid(self, form):
        first_name = form.cleaned_data["first_name"]
        last_name = form.cleaned_data["last_name"]
        user = form.save(commit=False)
        user.username = (
            f'{first_name}{last_name.replace(" ", "")}{random.randint(0, 1000)}'
        )
        user.is_agent = True
        user.is_organisor = False
        user.set_password(f"{user.username}")
        user.save()
        Agent.objects.create(user=user, organisation=self.request.user.userprofile)
        send_mail(
            subject="You are invited to be an agent",
            message="You were added as an agent on DJCRM. Please come login to start working.",
            from_email="admin@test.com",
            recipient_list=[user.email],
        )
        return super(AgentCreateView, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class AgentDetailView(OrganisorAndLoginRequiredMixin, generic.DetailView):
    template_name = "agents/agent_detail.html"
    context_object_name = "agent"

    def get_queryset(self):
        organisation = self.request.user.userprofile
        return Agent.objects.filter(organisation=organisation)


class AgentUpdateView(OrganisorAndLoginRequiredMixin, generic.UpdateView):
    template_name = "agents/agent_update.html"
    form_class = AgentModelForm

    def get_success_url(self):
        return reverse("agents:agent-list")

    def get_queryset(self):
        organisation = self.request.user.userprofile
        return Agent.objects.filter(organisation=organisation)

    def get_form(self, form_class=None):
        # Override the get_form method to pass the User object to the form
        if form_class is None:
            form_class = self.get_form_class()
        agent = self.get_object()
        form_kwargs = self.get_form_kwargs()
        form_kwargs["instance"] = agent.user
        return form_class(**form_kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)

        agent = self.get_object()

        # Check if the agent is marked as a leader
        if agent.is_team_leader:
            # Add the agent to the leaders field of their teams
            for team in agent.teams.all():
                team.leaders.add(agent.user)
        else:
            # If the agent is not a leader, remove them from the leaders field
            for team in agent.teams.all():
                team.leaders.remove(agent.user)

        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class AgentDeleteView(OrganisorAndLoginRequiredMixin, generic.DeleteView):
    template_name = "agents/agent_delete.html"
    context_object_name = "agent"

    def get_success_url(self):
        return reverse("agents:agent-list")

    def get_queryset(self):
        organisation = self.request.user.userprofile
        return Agent.objects.filter(organisation=organisation)


class AgentImportView(generic.View):
    template_name = "agents/agent_import.html"

    def get(self, request):
        form = AgentImportForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = AgentImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            rank = form.cleaned_data["rank"]

            try:
                decoded_file = csv_file.read().decode("utf-8")
                csv_data = csv.reader(decoded_file.splitlines(), delimiter=",")

                for row in csv_data:
                    if len(row) == 3:
                        first_name, last_name, alt_name = row
                    else:
                        first_name, last_name = row
                        alt_name = ""

                    username = f'{first_name}{last_name.replace(" ", "")}{random.randint(0, 1000)}'
                    user, created = User.objects.get_or_create(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        alt_name=alt_name,
                        defaults={
                            "is_agent": True,
                            "rank": rank,
                            "is_organisor": False,
                        },
                    )

                    if created:
                        user.set_password(f"{user.username}")
                        user.save()
                        Agent.objects.create(
                            user=user, organisation=request.user.userprofile
                        )

                return redirect("agents:agent-list")

            except Exception as e:
                # Catch any error related to file processing and display a message to the user
                print(e)
                messages.error(
                    request,
                    _(
                        f"""An error occurred while processing the file. Review the file and upload again."""
                    ),
                )

        return render(request, self.template_name, {"form": form})
