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
    team_leader_for = forms.ModelMultipleChoiceField(
    queryset=Team.objects.all(),
    widget=forms.CheckboxSelectMultiple,
    required=False,
    label="Team Leader For",
)
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

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].initial = self.instance.is_active
        self.fields['rank'].initial = self.instance.rank
        self.fields['alt_name'].initial = self.instance.alt_name
        organisation = user.userprofile

        # Filter the teams based on the organization
        self.fields['teams'].queryset = Team.objects.filter(organisation=organisation)
        self.fields['team_leader_for'].queryset = Team.objects.filter(organisation=organisation)

        if self.instance and hasattr(self.instance, 'agent'):
            self.fields['teams'].initial = self.instance.agent.teams.filter(organisation=organisation)
            self.fields['team_leader_for'].initial = self.instance.lead_teams.filter(organisation=organisation)
            self.fields['chat_id'].initial = self.instance.agent.chat_id
            self.fields['position'].initial = self.instance.agent.position
            self.fields['is_available_for_leads'].initial = self.instance.agent.is_available_for_leads



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
            for team in self.cleaned_data['team_leader_for']:
                team.leaders.add(agent.user)
            # Remove leadership roles from teams not selected
            for team in agent.user.lead_teams.all():
                if team not in self.cleaned_data['team_leader_for']:
                    team.leaders.remove(agent.user)
            agent.chat_id = self.cleaned_data.get('chat_id')
            agent.position = self.cleaned_data.get('position')
            agent.is_available_for_leads = self.cleaned_data.get('is_available_for_leads')
            agent.save()
        return user
    
    def clean(self):
        cleaned_data = super().clean()
        teams = cleaned_data.get('teams')
        team_leader_for = cleaned_data.get('team_leader_for')

        # Check if the user is set as a leader for a team they're not a part of
        invalid_teams = [team for team in team_leader_for if team not in teams]

        if invalid_teams:
            raise forms.ValidationError(f"The agent cannot be a leader for teams they're not a part of: {', '.join(str(team) for team in invalid_teams)}")

        return cleaned_data

class AgentImportForm(forms.Form):

    RANK_CHOICES = (
    (1, '1'),
    (2, '2'),
    (3, '3'),
    (4, '4')
)
    csv_file = forms.FileField()
    rank = forms.ChoiceField(choices=RANK_CHOICES)

    class Meta:
        Model = User