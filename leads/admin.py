from django.contrib import admin

from .models import User, Lead, Agent, UserProfile, Category, FollowUp, BankNumbers, DuplicateToFollow, Sale, Source, Team
from import_export.admin import ImportExportModelAdmin


class LeadAdmin(ImportExportModelAdmin):
    # fields = (
        
    # )

    list_display = ["phone_number", "category"]
    list_display_links = ["phone_number"]
    list_editable = ["category"]
    list_filter = ["category"]
    search_fields = ["phone_number", "category"]


admin.site.register(Category)
admin.site.register(User)
admin.site.register(UserProfile)
admin.site.register(Lead, LeadAdmin)
admin.site.register(Agent)
admin.site.register(FollowUp)
admin.site.register(BankNumbers)
admin.site.register(DuplicateToFollow)
admin.site.register(Sale)
admin.site.register(Source)
admin.site.register(Team)







# class LeadAdminIE(ImportExportModelAdmin):
#     pass