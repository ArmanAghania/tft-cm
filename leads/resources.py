from import_export import resources
from .models import Lead, BankNumbers


class LeadResource(resources.ModelResource):
    class Meta:
        model = Lead
        fields = ("phone_number")


class BankResource(resources.ModelResource):
    class Meta:
        model = BankNumbers
        fields = ("number")
