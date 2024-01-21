from rest_framework import serializers
from rest_framework.response import Response

from .models import Lead, User, Agent, Category, Source, Sale
from django.db.models import Sum, Count, Case, When, Q, Value, BooleanField, F

import jdatetime
from datetime import timedelta


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['alt_name', 'rank']


class AgentSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Agent
        fields = ['id', 'position', 'user']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = ['id', 'name']


class LeadSerializer(serializers.ModelSerializer):
    agent = AgentSerializer(many=False, read_only=True)
    category = CategorySerializer(many=False, read_only=True)
    source = SourceSerializer(many=False, read_only=True)
    is_user_organisor = serializers.SerializerMethodField()
    agent_choices = serializers.SerializerMethodField()
    category_choices = serializers.SerializerMethodField()
    source_choices = serializers.SerializerMethodField()

    class Meta:
        model = Lead
        fields = [
            'first_name', 'last_name', 'job', 'city', 'state', 'country',
            'age', 'is_presented', 'low_quality', 'birthday',
            'proposed_price', 'registered_price', 'agent',
            'phone_number', 'category', 'source', 'is_user_organisor',
            'agent_choices', 'category_choices', 'source_choices'
        ]

    def get_is_user_organisor(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            return request.user.is_organisor
        return False

    def get_agent_choices(self, obj):
        if self.context['request'].user.is_organisor:
            user_profile = self.context['request'].user.userprofile
            agents = Agent.objects.filter(
                organisation=user_profile).values('id', 'user__alt_name')
            return list(agents)
        else:
            user_profile = self.context['request'].user.agent.id
            agents = Agent.objects.filter(id=user_profile).values(
                'id', 'user__alt_name', 'user__rank', 'position')
            return list(agents)

    def get_category_choices(self, obj):
        if self.context['request'].user.is_organisor:
            user_profile = self.context['request'].user.userprofile
            categories = Category.objects.filter(
                organisation=user_profile).values('id', 'name')
            return list(categories)
        else:
            user_profile = self.context['request'].user.agent.organisation
            categories = Category.objects.filter(
                organisation=user_profile).values('id', 'name')
            return list(categories)

    def get_source_choices(self, obj):
        if self.context['request'].user.is_organisor:
            user_profile = self.context['request'].user.userprofile
            sources = Source.objects.filter(
                organisation=user_profile).values('id', 'name')
            return list(sources)
        else:
            user_profile = self.context['request'].user.agent.organisation
            sources = Source.objects.filter(
                organisation=user_profile).values('id', 'name')
            return list(sources)


class AgentPerformanceSerializer(serializers.Serializer):
    agent_name = serializers.SerializerMethodField()
    total_leads = serializers.SerializerMethodField()
    total_converted_leads = serializers.SerializerMethodField()
    total_sales_value = serializers.SerializerMethodField()
    average_sale_value = serializers.SerializerMethodField()
    conversion_rate = serializers.SerializerMethodField()
    total_modified_leads = serializers.SerializerMethodField()
    total_modified_percentage = serializers.SerializerMethodField()

    monthly_leads = serializers.SerializerMethodField()
    monthly_converted_leads = serializers.SerializerMethodField()
    monthly_sales_value = serializers.SerializerMethodField()
    monthly_average_sale_value = serializers.SerializerMethodField()
    monthly_conversion_rate = serializers.SerializerMethodField()
    monthly_modified_leads = serializers.SerializerMethodField()
    monthly_modified_percentage = serializers.SerializerMethodField()

    def get_agent_name(self, agent):
        return agent.user.first_name + ' ' + agent.user.last_name

    def get_total_leads(self, agent):
        return Lead.objects.filter(agent=agent).count()

    def get_total_converted_leads(self, agent):
        return Lead.objects.filter(agent=agent, category__name='Converted').count()

    def get_total_sales_value(self, agent):
        return Sale.objects.filter(agent=agent).aggregate(Sum('amount'))['amount__sum'] or 0

    def get_average_sale_value(self, agent):
        converted_leads = self.get_total_converted_leads(agent)
        total_sales = self.get_total_sales_value(agent)
        return total_sales / converted_leads if converted_leads else 0

    def get_conversion_rate(self, agent):
        total_leads = self.get_total_leads(agent)
        converted_leads = self.get_total_converted_leads(agent)
        return (converted_leads / total_leads * 100) if total_leads else 0

    def get_total_modified_leads(self, agent):
        return Lead.objects.filter(agent=agent).annotate(
            is_modified=Case(
                When(Q(first_name__isnull=False) | Q(last_name__isnull=False) | Q(
                    age__isnull=False) | Q(city__isnull=False), then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).filter(is_modified=True, date_modified__gt=F('date_assigned')).count()

    def get_total_modified_percentage(self, agent):
        total_leads = self.get_total_leads(agent)
        modified_leads = self.get_total_modified_leads(agent)
        return (modified_leads / total_leads * 100) if total_leads else 0

    def get_monthly_leads(self, agent):
        selected_year = self.context.get('selected_year')
        selected_month = self.context.get('selected_month')
        start_date, end_date = self.month_range(
            year=selected_year, month=selected_month)
        return Lead.objects.filter(agent=agent, date_assigned__gte=start_date,
                                   date_assigned__lte=end_date).count()

    def get_monthly_converted_leads(self, agent):
        selected_year = self.context.get('selected_year')
        selected_month = self.context.get('selected_month')
        start_date, end_date = self.month_range(
            year=selected_year, month=selected_month)
        return Lead.objects.filter(agent=agent, category__name='Converted', date_assigned__gte=start_date,
                                   date_assigned__lte=end_date).count()

    def get_monthly_sales_value(self, agent):
        selected_year = self.context.get('selected_year')
        selected_month = self.context.get('selected_month')
        start_date, end_date = self.month_range(
            year=selected_year, month=selected_month)
        return Sale.objects.filter(agent=agent, date__gte=start_date,
                                   date__lte=end_date).aggregate(Sum('amount'))['amount__sum'] or 0

    def get_monthly_average_sale_value(self, agent):
        monthly_converted_leads = self.get_monthly_converted_leads(agent)
        monthly_sales = self.get_monthly_sales_value(agent)
        return monthly_sales / monthly_converted_leads if monthly_converted_leads else 0

    def get_monthly_conversion_rate(self, agent):
        monthly_leads = self.get_monthly_leads(agent)
        monthly_converted_leads = self.get_monthly_converted_leads(agent)
        return (monthly_converted_leads / monthly_leads * 100) if monthly_leads else 0

    def get_monthly_modified_leads(self, agent):
        selected_year = self.context.get('selected_year')
        selected_month = self.context.get('selected_month')
        start_date, end_date = self.month_range(
            year=selected_year, month=selected_month)
        return Lead.objects.filter(agent=agent, date_assigned__gte=start_date,
                                   date_assigned__lte=end_date).annotate(
            is_modified=Case(
                When(Q(first_name__isnull=False) | Q(last_name__isnull=False) | Q(
                    age__isnull=False) | Q(city__isnull=False), then=Value(True)),
                default=Value(False),
                output_field=BooleanField()
            )
        ).filter(is_modified=True).count()

    def get_monthly_modified_percentage(self, agent):
        monthly_leads = self.get_monthly_leads(agent)
        monthly_modified_leads = self.get_monthly_modified_leads(agent)
        return (monthly_modified_leads / monthly_leads * 100) if monthly_leads else 0

    def month_range(self, year, month):
        start_date = jdatetime.date(year, month, 1).togregorian()
        if month == 12:
            end_date = jdatetime.date(
                year + 1, 1, 1).togregorian() - timedelta(days=1)
        else:
            end_date = jdatetime.date(
                year, month + 1, 1).togregorian() - timedelta(days=1)
        return start_date, end_date


class DailyPerformanceSerializer(serializers.Serializer):
    date = serializers.DateField()
    leads = serializers.IntegerField()
    sales = serializers.IntegerField()

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        gregorian_date = instance.get('date')
        if gregorian_date:
            jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)
            representation['date'] = jalali_date.strftime('%Y-%m-%d')
        return representation
