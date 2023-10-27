
from django.urls import path
from django.views import generic
from .views import (
    LeadListView, LeadDetailView, LeadCreateView, LeadUpdateView, LeadDeleteView,
    AssignAgentView, 
    CategoryListView, CategoryDetailView, LeadCategoryUpdateView, CategoryCreateView, CategoryUpdateView, CategoryDeleteView, 
    LeadJsonView, 
    FollowUpCreateView, FollowUpUpdateView, FollowUpDeleteView, 
    LeadExportView, BankExportView,
    LeadImportView, BankImportView, LeadImportAgentsView,
    BankListView, BankCreateView, BankUpdateView, BankDeleteView,
    LeadDistributionWizard, FORMS, 
    SearchLeadsView,  SearchBankView, 
    MyDayView,
    SaleListView, SaleCreateView, SaleDeleteView, LeadSalesEditView,
    DailySalesChart, WeeklySalesChart, MonthlySalesChart, YearlySalesChart, 
    SourceListView, SourceDetailView, SourceCreateView, SourceUpdateView, SourceDeleteView,
    TeamCreateView, TeamDetailView, TeamUpdateView, TeamDeleteView, TeamListView, TeamMemberLeadView,
    download_excel_page,
    run_background_tasks, stop_background_tasks,
    UserProfileUpdateView,
    stream_data
)

app_name = "leads"

urlpatterns = [
    path('', LeadListView.as_view(), name='lead-list'),
    path('json/', LeadJsonView.as_view(), name='lead-list-json'),
    path('<int:pk>/', LeadDetailView.as_view(), name='lead-detail'),
    path('<int:pk>/update/', LeadUpdateView.as_view(), name='lead-update'),
    path('<int:pk>/delete/', LeadDeleteView.as_view(), name='lead-delete'),
    path('<int:pk>/assign-agent/', AssignAgentView.as_view(), name='assign-agent'),
    path('<int:pk>/category/', LeadCategoryUpdateView.as_view(), name='lead-category-update'),
    path('<int:pk>/followups/create/', FollowUpCreateView.as_view(), name='lead-followup-create'),
    path('followups/<int:pk>/', FollowUpUpdateView.as_view(), name='lead-followup-update'),
    path('followups/<int:pk>/delete/', FollowUpDeleteView.as_view(), name='lead-followup-delete'),
    path('create/', LeadCreateView.as_view(), name='lead-create'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/<int:pk>/', CategoryDetailView.as_view(), name='category-detail'),
    path('categories/<int:pk>/update/', CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', CategoryDeleteView.as_view(), name='category-delete'),
    path('create-category/', CategoryCreateView.as_view(), name='category-create'),
    path('export_leads/', LeadExportView.as_view(), name='lead-export'),
    path('import_leads/', LeadImportView.as_view(), name='lead-import'),
    path('import_leads_agents/', LeadImportAgentsView.as_view(), name='lead-import-agents'),
    path('import_bank/', BankImportView.as_view(), name='bank-import'),
    path('bank/', BankListView.as_view(), name='bank-list'),
    path('bank_create/', BankCreateView.as_view(), name='bank-create'),
    path('bank/update/<int:pk>/', BankUpdateView.as_view(), name='bank-update'),
    path('bank/<int:pk>/delete/', BankDeleteView.as_view(), name='bank-delete'),
    path('bank_export/', BankExportView.as_view(), name='bank-export'),
    path('distribution_wizard/', LeadDistributionWizard.as_view(FORMS), name='dist_view'),
    path('search/', SearchLeadsView.as_view(), name='search_leads'),
    path('myday/', MyDayView.as_view(), name='my-day'),
    path('bank/search_bank/', SearchBankView.as_view(), name='search_bank'),
    path('sales/', SaleListView.as_view(), name='sale-list'),
    path('<int:pk>/sales/create/', SaleCreateView.as_view(), name='lead-sales-create'),
    path('sales/update/<int:pk>/', LeadSalesEditView.as_view(), name='lead-sales-update'),
    path('sales/<int:pk>/delete/', SaleDeleteView.as_view(), name='lead-sales-delete'),
    # path('daily_sales_chart/', generic.TemplateView.as_view(template_name='leads/daily_chart.html'), name='daily_sales_chart'),
    path('sales/daily_sales_chart/', generic.TemplateView.as_view(template_name='leads/daily_chart.html'), name='daily_sales_chart'),

    # path('daily_sales_chart/data/', DailySalesChart.as_view(), name='daily_sales_chart_data'),
    path('sales/daily_sales_chart/data/', DailySalesChart.as_view(), name='daily_sales_chart_data'),

    # path('weekly_sales_chart/', generic.TemplateView.as_view(template_name='leads/weekly_chart.html'), name='weekly_sales_chart'),
    path('sales/weekly_sales_chart/', generic.TemplateView.as_view(template_name='leads/weekly_chart.html'), name='weekly_sales_chart'),

    # path('weekly_sales_chart/data/', WeeklySalesChart.as_view(), name='weekly_sales_chart_data'),
    path('sales/weekly_sales_chart/data/', WeeklySalesChart.as_view(), name='weekly_sales_chart_data'),

    # path('monthly_sales_chart/', generic.TemplateView.as_view(template_name='leads/monthly_chart.html'), name='monthly_sales_chart'),
    path('sales/monthly_sales_chart/', generic.TemplateView.as_view(template_name='leads/monthly_chart.html'), name='monthly_sales_chart'),

    # path('monthly_sales_chart/data/', MonthlySalesChart.as_view(), name='monthly_sales_chart_data'),
    path('sales/monthly_sales_chart/data/', MonthlySalesChart.as_view(), name='monthly_sales_chart_data'),

    # path('yearly_sales_chart/', generic.TemplateView.as_view(template_name='leads/yearly_chart.html'), name='yearly_sales_chart'),
    path('sales/yearly_sales_chart/', generic.TemplateView.as_view(template_name='leads/yearly_chart.html'), name='yearly_sales_chart'),

    # path('yearly_sales_chart/data/', YearlySalesChart.as_view(), name='yearly_sales_chart_data'),
    path('sales/yearly_sales_chart/data/', YearlySalesChart.as_view(), name='yearly_sales_chart_data'),

    path('sources/', SourceListView.as_view(), name='source-list'),
    path('sources/<int:pk>/', SourceDetailView.as_view(), name='source-detail'),
    path('sources/<int:pk>/update/', SourceUpdateView.as_view(), name='source-update'),
    path('sources/<int:pk>/delete/', SourceDeleteView.as_view(), name='source-delete'),
    path('create-source/', SourceCreateView.as_view(), name='source-create'),
    path('teams/', TeamListView.as_view(), name='team-list'),
    path('teams/<int:pk>/', TeamDetailView.as_view(), name='team-detail'),
    path('teams/<int:pk>/update/', TeamUpdateView.as_view(), name='team-update'),
    path('teams/<int:pk>/delete/', TeamDeleteView.as_view(), name='team-delete'),
    path('team/<int:team_id>/member/<int:agent_id>/leads/', TeamMemberLeadView.as_view(), name='team-member-leads'),
    path('create-team/', TeamCreateView.as_view(), name='team-create'),
    path('download-excel/', download_excel_page, name='download_excel_page'),
    path('run_background_tasks/', run_background_tasks, name='run_background_tasks'),
    path('stop_background_tasks/', stop_background_tasks, name='stop_background_tasks'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile_update'),
    path('stream-data/', stream_data, name='stream-data'),
]

