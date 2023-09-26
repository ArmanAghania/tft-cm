from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import AbstractUser
from extensions.utils import jalali_converter
from django.utils import timezone
from datetime import datetime
from simple_history.models import HistoricalRecords
from decimal import Decimal
from django_jalali.db import models as jmodels

RANK_CHOICES = (
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, 'آموزش')
)

class User(AbstractUser):
    is_organisor = models.BooleanField(default=True)
    is_agent = models.BooleanField(default=False)
    rank = models.IntegerField(choices=RANK_CHOICES, default=1)
    is_active = models.BooleanField(default=True)
    alt_name = models.CharField(max_length=100, default='Persian Name', blank=True, null=True)
    

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    def __str__(self):
        return self.user.username


class LeadManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()


class Lead(models.Model):
    first_name = models.CharField(max_length=20, null=True, blank=True)
    last_name = models.CharField(max_length=20, null=True, blank=True)
    age = models.IntegerField(default=0, null=True, blank=True)
    birthday = jmodels.jDateField(null=True, blank=True)
    job = models.CharField(max_length=50, null=True, blank=True)
    city = models.CharField(max_length=50, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)
    country = models.CharField(max_length=50, null=True, blank=True)
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    agent = models.ForeignKey("Agent", null=True, blank=True, on_delete=models.SET_NULL)
    category = models.ForeignKey(
        "Category",
        related_name="leads",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    feedback = models.TextField(null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    phone_number = models.CharField(max_length=20, unique=True)
    converted_date = models.DateTimeField(null=True, blank=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_assigned = models.DateTimeField(null=True, blank=True)
    objects = LeadManager()
    total_sale = models.IntegerField(default=0, null=True, blank=True)
    source = models.ForeignKey(
        "Source",
        related_name="leads",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    # class Meta:
    #     verbose_name = "شماره"
    #     verbose_name_plural = "شماره ها"

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
    lead = models.ForeignKey(Lead, related_name="followups", on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    file = models.FileField(null=True, blank=True, upload_to=handle_upload_follow_ups)

    # class Meta:
    #     verbose_name = "پیگیری"
    #     verbose_name_plural = "پیگیری ها"
    
    def __str__(self):
        return f"{self.lead.agent} {self.lead.phone_number} {self.lead.category}"



class Agent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    is_team_leader = models.BooleanField(default=False)
    chat_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    


    # class Meta:
    #     verbose_name = "کارشناس"
    #     verbose_name_plural = "کارشناس ها"
    
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
    number = models.CharField(max_length=20, unique=True)
    agent = models.ForeignKey("Agent", null=True, blank=True, on_delete=models.SET_NULL)
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, default='1')
    date_added = models.DateTimeField(auto_now_add=True)

    # class Meta:
    #     verbose_name = "شماره دیتابیس"
    #     verbose_name_plural = " شماره های دیتابیس"

    def date_added_jalali(self):
        return jalali_converter(self.date_added)

    def __str__(self):
        return f"{self.number}"
    
class DuplicateToFollow(models.Model):
    number = models.CharField(max_length=20)
    agent = models.ForeignKey("Agent", null=True, blank=True, on_delete=models.SET_NULL)
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, default='1')
    date_added = models.DateField(auto_now_add=True)

    # class Meta:
    #     verbose_name = "شماره‌ پیگیری"
    #     verbose_name_plural = "شماره‌های پیگیری"

    def __str__(self):
        return f"{self.number} {self.agent} {self.date_added}"


class Sale(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE)
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, default='1')
    date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=0, default=Decimal('0.00'))  # This will be the amount for the current transaction
    total = models.DecimalField(max_digits=10, decimal_places=0, default=Decimal('0.00'))
    history = HistoricalRecords()

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

class Source(models.Model):
    name = models.CharField(max_length=30)  # New, Contacted, Converted, Unconverted
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    # class Meta:
    #     verbose_name = "منبع"
    #     verbose_name_plural = "منابع"
    def __str__(self):
        return self.name
    
class Team(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(Agent, related_name="teams")  # Relating to Agent model
    leaders = models.ManyToManyField(User, related_name="lead_teams")
    organisation = models.ForeignKey(UserProfile, on_delete=models.CASCADE, default='1')

    def __str__(self):
        return self.name

    @property
    def team_leaders(self):
        return self.members.filter(is_team_leader=True)