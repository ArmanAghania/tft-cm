from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UsernameField
from .models import Lead, Agent, Category, FollowUp, BankNumbers, Sale, Source, Team, ChatSetting
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
from django.contrib.auth.forms import PasswordChangeForm as AuthPasswordChangeForm
from django.utils.translation import gettext as _
from jalali_date import datetime2jalali
from django.utils.timezone import localtime
import jdatetime
import datetime

import logging
# logger = logging.getLogger(__name__)

User = get_user_model()


class LeadModelForm(forms.ModelForm):

    class Meta:
        model = Lead
        fields = (
            'first_name',
            'last_name',
            'job',
            'city',
            'state',
            'country',
            'age',
            'is_presented',
            'low_quality',
            'proposed_price',
            'registered_price',
            'birthday',
            "agent",
            "phone_number",
            "category",
            'source',
        )

    def __init__(self, *args, **kwargs):
        # Get the user from the keyword arguments
        user = kwargs.pop('user', None)
        super(LeadModelForm, self).__init__(*args, **kwargs)

        self.fields['agent'].widget.attrs['class'] = 'agent-field'
        self.fields['phone_number'].widget.attrs['class'] = 'phone-number-field'
        self.fields['category'].widget.attrs['class'] = 'category-field'
        self.fields['source'].widget.attrs['class'] = 'source-field'

        if user:
            if user.is_organisor:
                organisation = user.userprofile
                self.fields['category'].widget.attrs['readonly'] = False
                self.fields['source'].widget.attrs['readonly'] = False
                self.fields['agent'].widget.attrs['readonly'] = False
                self.fields['phone_number'].widget.attrs['readonly'] = False
            else:
                organisation = user.agent.organisation
                self.fields['category'].widget.attrs['readonly'] = True
                self.fields['source'].widget.attrs['readonly'] = True
                self.fields['agent'].widget.attrs['readonly'] = True
                self.fields['phone_number'].widget.attrs['readonly'] = True

            self.fields['category'].queryset = Category.objects.filter(
                organisation=organisation)
            self.fields['source'].queryset = Source.objects.filter(
                organisation=organisation)
            self.fields['agent'].queryset = Agent.objects.filter(
                organisation=organisation)

        self.fields['birthday'] = JalaliDateField(
            widget=AdminJalaliDateWidget(), required=False, label='Birthday')

    def clean_category(self):
        instance = getattr(self, 'instance', None)
        user = self.initial.get('user')

        if instance and instance.pk and user and not user.is_organisor:
            return instance.category
        else:
            return self.cleaned_data['category']

    def clean_phone_number(self):
        instance = getattr(self, 'instance', None)
        user = self.initial.get('user')

        if instance and instance.pk and user and not user.is_organisor:
            return instance.phone_number
        else:
            return self.cleaned_data['phone_number']

    def clean_source(self):
        instance = getattr(self, 'instance', None)
        user = self.initial.get('user')

        if instance and instance.pk and user and not user.is_organisor:
            return instance.source
        else:
            return self.cleaned_data['source']

    def clean_agent(self):
        instance = getattr(self, 'instance', None)
        user = self.initial.get('user')

        if instance and instance.pk and user and not user.is_organisor:
            return instance.agent
        else:
            return self.cleaned_data['agent']


class LeadForm(forms.Form):
    first_name = forms.CharField()
    last_name = forms.CharField()
    age = forms.IntegerField(min_value=0)
    # sale_amount = forms.IntegerField(min_value=0)


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username",)
        field_classes = {"username": UsernameField}


class AssignAgentForm(forms.Form):
    agent = forms.ModelChoiceField(queryset=Agent.objects.none())

    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request")
        agents = Agent.objects.filter(organisation=request.user.userprofile)
        super(AssignAgentForm, self).__init__(*args, **kwargs)
        self.fields["agent"].queryset = agents


class LeadCategoryUpdateForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ("category",)


class CategoryModelForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name",)


class FollowUpModelForm(forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = ("notes", "file")


FORMAT_CHOICES = (
    ("xls", "xls"),
    ("csv", "csv"),
    ("json", "json"),
)


class FormatForm(forms.Form):
    format = forms.ChoiceField(
        choices=FORMAT_CHOICES, widget=forms.Select(
            attrs={"class": "form-select"})
    )


class LeadImportForm(forms.Form):
    csv_file = forms.FileField()
    category = forms.ModelChoiceField(queryset=Category.objects.none())
    source = forms.ModelChoiceField(queryset=Source.objects.none())

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(LeadImportForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(
                organisation=user.userprofile)
            self.fields['source'].queryset = Source.objects.filter(
                organisation=user.userprofile)


class BankImportForm(forms.Form):
    csv_file = forms.FileField()
    agent = forms.ModelChoiceField(queryset=Agent.objects.none())

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(BankImportForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['agent'].queryset = Agent.objects.filter(
                organisation=user.userprofile)


class LeadImportFormAgents(forms.Form):
    csv_file = forms.FileField()
    category = forms.ModelChoiceField(queryset=Category.objects.none())
    source = forms.ModelChoiceField(queryset=Source.objects.none())
    agent = forms.ModelChoiceField(queryset=Agent.objects.none())

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super(LeadImportFormAgents, self).__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(
                organisation=user.userprofile)
            self.fields['source'].queryset = Source.objects.filter(
                organisation=user.userprofile)
            self.fields['agent'].queryset = Agent.objects.filter(
                organisation=user.userprofile)


class BankModelForm(forms.ModelForm):
    class Meta:
        model = BankNumbers
        fields = (
            "agent",
            "number",
        )

    def __init__(self, *args, **kwargs):
        super(BankModelForm, self).__init__(*args, **kwargs)
        self.fields['agent'].required = False


class DistributionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.wizard_storage = kwargs.pop('wizard_storage', None)
        super().__init__(*args, **kwargs)

    rank1 = forms.IntegerField()
    rank2 = forms.IntegerField()
    rank3 = forms.IntegerField()
    rank4 = forms.IntegerField()
    rank5 = forms.IntegerField()

    def clean_rank1(self):
        data = self.cleaned_data['rank1']
        if data < 0:
            raise forms.ValidationError("Rank1 leads cannot be negative.")
        return data

    def clean_rank2(self):
        data = self.cleaned_data['rank2']
        if data < 0:
            raise forms.ValidationError("Rank2 leads cannot be negative.")
        return data

    def clean_rank3(self):
        data = self.cleaned_data['rank3']
        if data < 0:
            raise forms.ValidationError("Rank3 leads cannot be negative.")
        return data

    def clean_rank4(self):
        data = self.cleaned_data['rank4']
        if data < 0:
            raise forms.ValidationError("Rank4 leads cannot be negative.")
        return data

    def clean_rank5(self):
        data = self.cleaned_data['rank5']
        if data < 0:
            raise forms.ValidationError("Rank5 leads cannot be negative.")
        return data


class CategorySelectionForm(forms.Form):
    ORDER_CHOICES = [
        ('asc', 'Ascending'),
        ('desc', 'Descending')
    ]

    category = forms.ModelChoiceField(
        queryset=Category.objects.none(), label="Select a Category")
    alternate_category = forms.ModelChoiceField(
        queryset=Category.objects.none(), label="Select an Alternate Category")
    high_quality = forms.BooleanField(
        required=False, label='High Quality Leads')
    order_by_date = forms.ChoiceField(
        choices=ORDER_CHOICES, label='Order by Date', required=False)

    def __init__(self, *args, **kwargs):
        self.wizard_storage = kwargs.pop('wizard_storage', None)
        super().__init__(*args, **kwargs)

        if self.wizard_storage:
            user_id = self.wizard_storage.extra_data.get('user_id')
            self.fields['order_by_date'].initial = 'desc'
            if user_id:
                user = User.objects.get(id=user_id)
                organisation = user.userprofile
                categories = Category.objects.filter(organisation=organisation)

                self.fields['category'].queryset = categories
                self.fields['alternate_category'].queryset = categories


class ConfirmationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.wizard_storage = kwargs.pop('wizard_storage', None)
        super().__init__(*args, **kwargs)
    confirmation = forms.BooleanField(label="Confirm", required=True)


class ChatOverrideForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.wizard_storage = kwargs.pop('wizard_storage', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = ChatSetting
        fields = ['override_chat_id', 'chat_id']


class LeadSearchForm(forms.Form):
    query = forms.CharField(label='', widget=forms.TextInput(
        attrs={'placeholder': 'Search leads...'}), required=False)


class SaleModelForm(forms.ModelForm):
    jalali_date = JalaliDateField(
        label='Sale Date (Jalali)',
        widget=AdminJalaliDateWidget(attrs={'class': 'jalali_date-input'}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super(SaleModelForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.date:
            jalali_date = jdatetime.date.fromgregorian(date=self.instance.date)
            self.initial['jalali_date'] = jalali_date.strftime('%Y-%m-%d')
        self.fields['jalali_date'] = JalaliDateField(
            widget=AdminJalaliDateWidget(), required=False, label=_('Date'))

    class Meta:
        model = Sale
        fields = ("amount", "jalali_date")
        labels = {'amount': 'Sale Amount'}

    def clean_jalali_date(self):
        jalali_date = self.cleaned_data.get('jalali_date')

        if isinstance(jalali_date, datetime.date):
            return jalali_date

        try:
            parsed_jalali_date = jdatetime.datetime.strptime(
                jalali_date, '%Y-%m-%d').date()
            gregorian_date = parsed_jalali_date.togregorian()
        except ValueError:
            raise forms.ValidationError("Invalid date format.")

        return gregorian_date

    def save(self, commit=True):
        instance = super(SaleModelForm, self).save(commit=False)
        instance.date = self.cleaned_data['jalali_date'] or instance.date
        if commit:
            instance.save()
        return instance


class SourceModelForm(forms.ModelForm):
    class Meta:
        model = Source
        fields = ("name",)


class TeamModelForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'members']
        widgets = {
            'members': forms.CheckboxSelectMultiple
        }

    def __init__(self, user, *args, **kwargs):
        super(TeamModelForm, self).__init__(*args, **kwargs)
        # Filter the agents based on the organization of the logged-in user
        self.fields['members'].queryset = Agent.objects.filter(
            organisation=user.userprofile)


class UserUpdateForm(forms.ModelForm):
    telegram_token = forms.CharField(required=False, max_length=500)
    chat_id = forms.CharField(required=False, max_length=255)

    class Meta:
        model = User
        fields = ['is_active', 'alt_name', 'telegram_token', 'chat_id']

    def __init__(self, *args, **kwargs):
        super(UserUpdateForm, self).__init__(*args, **kwargs)

        # Check if the instance (user) is related to the form and if the user is an organisor
        if self.instance and self.instance.is_organisor:
            self.fields['telegram_token'].initial = self.instance.userprofile.telegram_token
            self.fields['chat_id'].initial = self.instance.userprofile.chat_id

        else:
            del self.fields['telegram_token']
            del self.fields['chat_id']

    def save(self, commit=True):
        user = super(UserUpdateForm, self).save(commit=commit)

        # If the user is an organisor, save the telegram token to their profile
        if user.is_organisor and 'telegram_token' in self.cleaned_data:
            profile = user.userprofile
            profile.telegram_token = self.cleaned_data['telegram_token']
            if commit:
                profile.save()

        if user.is_organisor and 'chat_id' in self.cleaned_data:
            profile = user.userprofile
            profile.chat_id = self.cleaned_data['chat_id']
            if commit:
                profile.save()

        return user


class PasswordChangeForm(AuthPasswordChangeForm):
    class Meta:
        model = User
        fields = ['old_password', 'new_password1', 'new_password2']

    def __init__(self, *args, **kwargs):
        super(PasswordChangeForm, self).__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].help_text = None
            # Making fields not required
            self.fields[field_name].required = False

    def clean(self):
        cleaned_data = super().clean()
        # Check if any of the password fields are filled out
        fields_filled = [cleaned_data.get('old_password'), cleaned_data.get(
            'new_password1'), cleaned_data.get('new_password2')]
        if any(fields_filled) and not all(fields_filled):
            raise forms.ValidationError(
                _('All password fields are required to change your password.'))
        return cleaned_data


class AssignLeadsForm(forms.Form):

    ORDER_CHOICES = [
        ('asc', 'Ascending'),
        ('desc', 'Descending')
    ]

    agent = forms.ModelChoiceField(
        queryset=Agent.objects.none(), label=_("Agent to assign"))
    order_by_date = forms.ChoiceField(
        choices=ORDER_CHOICES, label=_("Order by Date"), required=False)
    # Other fields for categories will be dynamically added in the view

    def __init__(self, user, *args, **kwargs):
        super(AssignLeadsForm, self).__init__(*args, **kwargs)
        # Filter the agents based on the organization of the logged-in user
        self.fields['agent'].queryset = Agent.objects.filter(
            organisation=user.userprofile)
