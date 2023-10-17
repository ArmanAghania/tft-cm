import django_filters
from .models import Lead
from django.utils.translation import gettext_lazy as _
from django_jalali.forms.widgets import jDateInput
from jdatetime import date as jdate
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime
from django import forms
RANK_CHOICES = (
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, 'آموزش')
)

class LeadFilter(django_filters.FilterSet):
    date_assigned_jalali = django_filters.CharFilter(
        method='filter_date_assigned_jalali',
        widget=forms.TextInput(attrs={'placeholder': 'YYYY-MM-DD'}),
        label=_('Date Assigned (Jalali)'),
    )
    phone_number = django_filters.CharFilter(lookup_expr='icontains')
    first_name = django_filters.CharFilter(lookup_expr='icontains')
    last_name = django_filters.CharFilter(lookup_expr='icontains')
    city = django_filters.CharFilter(lookup_expr='icontains')
    agent_name = django_filters.CharFilter(field_name='agent__user__alt_name', lookup_expr='icontains')
    agent_rank = django_filters.ChoiceFilter(field_name='agent__user__rank', choices=RANK_CHOICES)
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')
    source = django_filters.CharFilter(field_name='source__name', lookup_expr='icontains')
    has_agent = django_filters.BooleanFilter(
        field_name='agent',  # Use the 'agent' field for filtering
        method='filter_has_agent',  # Specify the custom filter method
        label='Has Agent',  # Optional label for the filter

        # You can customize the widget for this filter, for example:
        widget=django_filters.widgets.BooleanWidget(attrs={'class': 'custom-checkbox'}),
    )
    not_starts_with_09 = django_filters.BooleanFilter(
        method='filter_not_starts_with_09',  # Specify the custom filter method
        label='Phone number does not start with 09',  # Label for the filter
        
        # Customize the widget for this filter if needed
        widget=django_filters.widgets.BooleanWidget(attrs={'class': 'custom-checkbox'}),
    )

    # Define the custom filter method
    def filter_has_agent(self, queryset, name, value):
        if value:
            # Filter leads with agents (agents are not None)
            return queryset.exclude(agent=None)
        else:
            # Filter leads without agents (agents are None)
            return queryset.filter(agent=None)
        
    def filter_not_starts_with_09(self, queryset, name, value):
        if value:  # If the checkbox is checked
            return queryset.exclude(phone_number__startswith='09')
        return queryset
    
    def filter_date_assigned_jalali(self, queryset, name, value):
        try:
            # Convert the Jalali date to a Gregorian date
            jdate_obj = jdate.fromisoformat(str(value).strip())  # Creates a Jalali date object
            gregorian_date = jdate_obj.togregorian()  # Converts it to Gregorian
        
            # Filter the queryset by the Gregorian date
            return queryset.filter(date_assigned__date=gregorian_date)
        except Exception as e:
            # If there's an error, log it and return the original queryset
            print(f"Error while filtering by Jalali date: {e}")
            return queryset

    class Meta:
        model = Lead
        fields = []