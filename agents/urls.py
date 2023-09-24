from django.urls import path
from .views import (
    AgentListView, AgentCreateView, AgentDetailView, 
    AgentUpdateView, AgentDeleteView, AgentImportView
)

app_name = 'agents'

urlpatterns = [
    path('', AgentListView.as_view(), name='agent-list'),
    path('<int:pk>/', AgentDetailView.as_view(), name='agent-detail'),
    path('<int:pk>/update/', AgentUpdateView.as_view(), name='agent-update'),
    path('<int:pk>/delete/', AgentDeleteView.as_view(), name='agent-delete'),
    path('create/', AgentCreateView.as_view(), name='agent-create'),
    # path('export_leads/', LeadExportView.as_view(), name='lead-export'),
    path('import_agents/', AgentImportView.as_view(), name='agent-import'),
]