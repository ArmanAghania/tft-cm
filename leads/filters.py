import django_filters
from .models import Lead


RANK_CHOICES = (
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, 'آموزش')
)

class LeadFilter(django_filters.FilterSet):
    phone_number = django_filters.CharFilter(lookup_expr='icontains')
    agent_name = django_filters.CharFilter(field_name='agent__user__alt_name', lookup_expr='icontains')
    agent_rank = django_filters.ChoiceFilter(field_name='agent__user__rank', choices=RANK_CHOICES)
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')
    source = django_filters.CharFilter(field_name='source__name', lookup_expr='icontains')



    class Meta:
        model = Lead
        fields = []