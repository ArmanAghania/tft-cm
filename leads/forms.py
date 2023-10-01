from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UsernameField
from .models import Lead, Agent, Category, FollowUp, BankNumbers, Sale, Source, Team, ChatSetting
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget
from django.contrib.auth.forms import PasswordChangeForm as AuthPasswordChangeForm

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
            'birthday',
            "agent",
            "phone_number",
            "category",
            'source',
        )
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)  # Get the user from the keyword arguments
        super(LeadModelForm, self).__init__(*args, **kwargs)
        self.fields['birthday'] = JalaliDateField(widget=AdminJalaliDateWidget(), required=False, label='Birthday')

        if user:
            # Filter the category and source fields based on the user
            self.fields['category'].queryset = Category.objects.filter(organisation=user.userprofile)
            self.fields['source'].queryset = Source.objects.filter(organisation=user.userprofile)
            self.fields['agent'].queryset = Agent.objects.filter(organisation=user.userprofile)

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
        choices=FORMAT_CHOICES, widget=forms.Select(attrs={"class": "form-select"})
    )

class LeadImportForm(forms.Form):
    csv_file = forms.FileField()
    category = forms.ModelChoiceField(queryset=Category.objects.all())
    source = forms.ModelChoiceField(queryset=Source.objects.all())

class BankImportForm(forms.Form):
    csv_file = forms.FileField()
    agent = forms.ModelChoiceField(queryset=Agent.objects.all())

class BankModelForm(forms.ModelForm):
    class Meta:
        model = BankNumbers
        fields = (
            "agent",
        )

    def __init__(self, *args, **kwargs):
        super(BankModelForm, self).__init__(*args, **kwargs)
        self.fields['agent'].required = False

class DistributionForm(forms.Form):

    rank1 = forms.IntegerField()
    rank2 = forms.IntegerField()
    rank3 = forms.IntegerField()
    rank4 = forms.IntegerField()
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

class CategorySelectionForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), label="Select a Category")

class ConfirmationForm(forms.Form):
    confirmation = forms.BooleanField(label="Confirm", required=True)

class LeadSearchForm(forms.Form):
    query = forms.CharField(label='', widget=forms.TextInput(attrs={'placeholder': 'Search leads...'}), required=False)

class SaleModelForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ("amount",)
        labels = {'amount': 'Sale Amount'}

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
        self.fields['members'].queryset = Agent.objects.filter(organisation=user.userprofile)

class ChatOverrideForm(forms.ModelForm):
    class Meta:
        model = ChatSetting
        fields = ['override_chat_id', 'chat_id']

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['is_active', 'alt_name']

class PasswordChangeForm(AuthPasswordChangeForm):
    class Meta:
        model = User
        fields = ['old_password', 'new_password1', 'new_password2']

    def __init__(self, *args, **kwargs):
        super(PasswordChangeForm, self).__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].help_text = None