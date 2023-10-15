from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from leads.models import Team, Agent
from django.utils.translation import gettext_lazy as _
User = get_user_model()


class AgentModelForm(forms.ModelForm):
    teams = forms.ModelMultipleChoiceField(
        queryset=Team.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    is_team_leader = forms.BooleanField(required=False, label='Is He/She a Team Leader?')
    chat_id = forms.IntegerField(required=False)
    position = forms.IntegerField(required=True)
    is_available_for_leads = forms.BooleanField(required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', "email", "rank","position", "is_active","is_available_for_leads", "alt_name", "teams", 'chat_id')
        labels = {
            'teams': _('Teams'),
            "is_available_for_leads": _('On/Off Duty'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].initial = self.instance.is_active
        self.fields['rank'].initial = self.instance.rank
        self.fields['alt_name'].initial = self.instance.alt_name

        if self.instance and hasattr(self.instance, 'agent'):
            self.fields['teams'].initial = self.instance.agent.teams.all()
            self.fields['is_team_leader'].initial = self.instance.agent.is_team_leader 
            self.fields['chat_id'].initial = self.instance.agent.chat_id
            self.fields['position'].initial = self.instance.agent.position
            self.fields['is_available_for_leads'].initial = self.instance.agent.position



    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = self.cleaned_data['is_active']
        user.rank = self.cleaned_data['rank']
        user.alt_name = self.cleaned_data['alt_name']
        
        if commit:
            user.save()

            # Ensure an Agent instance is associated with the user
            agent, created = Agent.objects.get_or_create(user=user)
            agent.teams.set(self.cleaned_data['teams'])
            agent.is_team_leader = self.cleaned_data['is_team_leader']
            agent.chat_id = self.cleaned_data.get('chat_id')
            agent.position = self.cleaned_data.get('position')
            agent.is_available_for_leads = self.cleaned_data.get('is_available_for_leads')
            agent.save()
        return user

class AgentImportForm(forms.Form):

    RANK_CHOICES = (
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, 'آموزش')
)
    csv_file = forms.FileField()
    rank = forms.ChoiceField(choices=RANK_CHOICES)

    class Meta:
        Model = User