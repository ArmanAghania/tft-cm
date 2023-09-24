from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from leads.models import Team
User = get_user_model()


class AgentModelForm(forms.ModelForm):
    teams = forms.ModelMultipleChoiceField(
        queryset=Team.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    is_team_leader = forms.BooleanField(required=False, label='Is He/She a Team Leader?')
    chat_id = forms.IntegerField(required=False)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', "email", "rank", "is_active", "alt_name", "teams", 'chat_id')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].initial = self.instance.is_active
        self.fields['rank'].initial = self.instance.rank
        self.fields['alt_name'].initial = self.instance.alt_name
        if self.instance and hasattr(self.instance, 'agent'):
            self.fields['teams'].initial = self.instance.agent.teams.all()
            self.fields['is_team_leader'].initial = self.instance.agent.is_team_leader 
            self.fields['chat_id'].initial = self.instance.agent.chat_id

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_active = self.cleaned_data['is_active']
        user.rank = self.cleaned_data['rank']
        user.alt_name = self.cleaned_data['alt_name']
        chat_id = self.cleaned_data.get('chat_id')
        

        if commit:
            user.save()
            if hasattr(user, 'agent'):
                user.agent.teams.set(self.cleaned_data['teams'])
                user.agent.is_team_leader = self.cleaned_data['is_team_leader']
                user.agent.chat_id = chat_id
                user.agent.save()
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