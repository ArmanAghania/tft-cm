from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import AbstractUser
from extensions.utils import jalali_converter
from django.utils import timezone
from datetime import datetime
from simple_history.models import HistoricalRecords
from decimal import Decimal
from django_jalali.db import models as jmodels
from django.utils.translation import gettext_lazy as _
from asgiref.sync import sync_to_async


RANK_CHOICES = (
    (1, _('1')),
    (2, _('2')),
    (3, _('3')),
    (4, _('Education'))
)

class User(AbstractUser):
    is_organisor = models.BooleanField(default=True, verbose_name=_("Organisor"))
    is_agent = models.BooleanField(default=False, verbose_name=_("Agent"))
    rank = models.IntegerField(choices=RANK_CHOICES, default=1, verbose_name=_("Rank"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    alt_name = models.CharField(max_length=100, default='Persian Name', blank=True, null=True, verbose_name=_("Alternate Name"))
    

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name=_("User"))
    def __str__(self):
        return self.user.username


class LeadManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


class Lead(models.Model):
    first_name = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('First Name'))
    last_name = models.CharField(max_length=20, null=True, blank=True, verbose_name=_('Last Name'))
    age = models.IntegerField(default=0, null=True, blank=True, verbose_name=_('Age'))
    birthday = jmodels.jDateField(null=True, blank=True, verbose_name=_('Birthday'))
    job = models.CharField(max_length=50, null=True, blank=True, verbose_name=_('Job'))
    city = models.CharField(max_length=50, null=True, blank=True, verbose_name=_('City'))
    state = models.CharField(max_length=50, null=True, blank=True, verbose_name=_('State'))
    country = models.CharField(max_length=50, null=True, blank=True, verbose_name=_('Country'))
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name=_('Organisation'))
    agent = models.ForeignKey("Agent", null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("Agent"))
    category = models.ForeignKey(
        "Category",
        related_name="leads",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Category"),
    )
    feedback = models.TextField(null=True, blank=True, verbose_name=_("Feedback"))
    date_added = models.DateTimeField(auto_now_add=True, verbose_name=_("Date Added"))
    phone_number = models.CharField(max_length=20, unique=True, verbose_name=_('Phone Number'))
    converted_date = models.DateTimeField(null=True, blank=True, verbose_name=_('Converted Date'))
    date_modified = models.DateTimeField(auto_now=True, verbose_name=_("Date Modified"))
    date_assigned = models.DateTimeField(null=True, blank=True, verbose_name=_("Date Assigned"))
    objects = LeadManager()
    total_sale = models.IntegerField(default=0, null=True, blank=True, verbose_name=_("Total Sales"))
    source = models.ForeignKey(
        "Source",
        related_name="leads",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Source"),
    )
    proposed_price = models.IntegerField(default=0, null=True, blank=True, verbose_name=_("Proposed Price"))
    registered_price = models.IntegerField(default=0, null=True, blank=True, verbose_name=_("Registered Price"))
    is_presented = models.BooleanField(default=False, verbose_name=_("Is Presented?"))
    

    class Meta:
        verbose_name = _("Lead")
        verbose_name_plural = _("Leads")

    def __str__(self):
        return f"{self.phone_number} {self.category}"
    
    def date_added_jalali(self):
        return jalali_converter(self.date_added)

    def date_modified_jalali(self):
        return jalali_converter(self.date_modified)
    
    def save(self, *args, **kwargs):
        # Check if the agent is being assigned for the first time
        if self.agent and not self.date_assigned:
            self.date_assigned = datetime.today()

        super(Lead, self).save(*args, **kwargs)
    

def handle_upload_follow_ups(instance, filename):
    return f"lead_followups/lead_{instance.lead.pk}/{filename}"


class FollowUp(models.Model):
    lead = models.ForeignKey(Lead, related_name="followups", on_delete=models.CASCADE, verbose_name=_("Lead"))
    date_added = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True, verbose_name=_("Notes"))
    file = models.FileField(null=True, blank=True, upload_to=handle_upload_follow_ups, verbose_name=_("File"))

    class Meta:
        verbose_name = _("Follow-up")
        verbose_name_plural = _("Follow-ups")
    
    def __str__(self):
        return f"{self.lead.agent} {self.lead.phone_number} {self.lead.category}"



class Agent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name=_("User"))
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name=_("Organisation"))
    is_team_leader = models.BooleanField(default=False, verbose_name=_("Team Leader"))
    chat_id = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name=_("Chat ID"))
    


    class Meta:
        verbose_name = _("Agent")
        verbose_name_plural = _("Agents")
    
    def __str__(self):
        return f"{self.user.alt_name}, {self.user.rank}"

class Category(models.Model):
    name = models.CharField(max_length=30)  # New, Contacted, Converted, Unconverted
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    # class Meta:
    #     verbose_name = "دسته بندی"
    #     verbose_name_plural = "دسته بندی ها"
    def __str__(self):
        return self.name


def post_user_created_signal(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


post_save.connect(post_user_created_signal, sender=User)
    

class BankNumbers(models.Model):
    number = models.CharField(max_length=20, unique=True, verbose_name=_("Phone Number"))
    agent = models.ForeignKey("Agent", null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("Agent"))
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name=_("Organisation"))
    date_added = models.DateTimeField(auto_now_add=True, verbose_name=_("Date Added"))

    class Meta:
        verbose_name = _('Database Number')
        verbose_name_plural = _('Database Numbers')

    def date_added_jalali(self):
        return jalali_converter(self.date_added)

    def __str__(self):
        return f"{self.number}"
    
class DuplicateToFollow(models.Model):
    number = models.CharField(max_length=20, verbose_name=_("Phone Number"))
    agent = models.ForeignKey("Agent", null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_("Agent"))
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, default='1', verbose_name=_("Organisation"))
    date_added = models.DateField(auto_now_add=True, verbose_name=_("Date Added"))

    class Meta:
        verbose_name = _('Duplicate Followup')
        verbose_name_plural = _('Duplicate Followups')

    def __str__(self):
        return f"{self.number} {self.agent} {self.date_added}"


class Sale(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, verbose_name=_('Lead'))
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, verbose_name=_('Agent'))
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name=_('Organisation'))
    date = models.DateTimeField(auto_now_add=True, verbose_name=_('Date Added'))
    amount = models.DecimalField(max_digits=10, decimal_places=0, default=Decimal('0.00'), verbose_name=_('Amount'))  # This will be the amount for the current transaction
    total = models.DecimalField(max_digits=10, decimal_places=0, default=Decimal('0.00'), verbose_name=_('Total'))  # This will be the total amount for the lead
    history = HistoricalRecords()

    class Meta:
        verbose_name = _('Sale')
        verbose_name_plural = _('Sales')

    def __str__(self):
        return f'{self.lead.phone_number} , {self.agent.user.alt_name} , {self.date}'

    def save(self, *args, **kwargs):
        if not self.pk:  # if object does not have a primary key, it's being created
            self.total = self.amount
        else:
            self.total += self.amount
        
        super(Sale, self).save(*args, **kwargs)  # Save the sale instance first

        # Update the lead's total sale based on all sales
        total_sales_for_lead = Sale.objects.filter(lead=self.lead).aggregate(models.Sum('amount'))['amount__sum']
        self.lead.total_sale = total_sales_for_lead
        self.lead.save()

    def delete(self, *args, **kwargs):
        lead_to_update = self.lead  # Store reference to the lead before deleting the sale
        
        super(Sale, self).delete(*args, **kwargs)  # Delete the sale instance first
        
        # Update the lead's total sale based on all remaining sales
        total_sales_for_lead = Sale.objects.filter(lead=lead_to_update).aggregate(models.Sum('amount'))['amount__sum'] or 0
        lead_to_update.total_sale = total_sales_for_lead
        lead_to_update.save()

class Source(models.Model):
    name = models.CharField(max_length=30, verbose_name=_("Source Name"))  # New, Contacted, Converted, Unconverted
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, verbose_name=_("Organisation"))

    class Meta:
        verbose_name = _("Source")
        verbose_name_plural = _("Sources")

    def __str__(self):
        return self.name
    
class Team(models.Model):
    name = models.CharField(max_length=255, unique=True, verbose_name=_("Team Name"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    members = models.ManyToManyField(Agent, related_name="teams", verbose_name=_("Members"))  # Relating to Agent model
    leaders = models.ManyToManyField(User, related_name="lead_teams", verbose_name=_("Leaders"))  # Relating to User model
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, default='1', verbose_name=_("Organisation"))

    class Meta:
        verbose_name = _("Team")
        verbose_name_plural = _("Teams")

    def __str__(self):
        return self.name

    @property
    def team_leaders(self):
        return self.members.filter(is_team_leader=True)
    

class ChatSetting(models.Model):
    override_chat_id = models.BooleanField(default=False)
    chat_id = models.CharField(max_length=50, blank=True, null=True)

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj