from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.urls import path, include
from leads.views import landing_page, LandingPageView, SignupView, DashboardView
import debug_toolbar
from leads.views import custom_404_view
from leads.views import (
    DailySalesChart,
    WeeklySalesChart,
    MonthlySalesChart,
    YearlySalesChart,
    AgeDistributionAPIView,
    LeadSourceAPIView,
    LeadStatsAPIView,
    MonthlySalesAPIView,
    MonthlyLeadTrendsAPIView,
    LeadEditAPIView,
    AgentPerformanceViewSet,
    DailyPerformanceViewSet,
    CustomLoginView,
)
from django.views import generic
from rest_framework.routers import DefaultRouter

handler404 = custom_404_view
router = DefaultRouter()
router.register(
    r"agent_performance", AgentPerformanceViewSet, basename="agent-performance"
)
router.register(
    r"daily_performance", DailyPerformanceViewSet, basename="daily_performance"
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", LandingPageView.as_view(), name="landing-page"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("leads/", include("leads.urls", namespace="leads")),
    path("agents/", include("agents.urls", namespace="agents")),
    path("signup/", SignupView.as_view(), name="signup"),
    path("reset-password/", PasswordResetView.as_view(), name="reset-password"),
    path(
        "password-reset-done/",
        PasswordResetDoneView.as_view(),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("i18n/", include("django.conf.urls.i18n")),
    path(
        "dashboard/daily_sales_chart/",
        generic.TemplateView.as_view(template_name="leads/daily_chart.html"),
        name="daily_sales_chart",
    ),
    path(
        "dashboard/daily_sales_chart/data/",
        DailySalesChart.as_view(),
        name="daily_sales_chart_data",
    ),
    path(
        "dashboard/weekly_sales_chart/",
        generic.TemplateView.as_view(template_name="leads/weekly_chart.html"),
        name="weekly_sales_chart",
    ),
    path(
        "dashboard/weekly_sales_chart/data/",
        WeeklySalesChart.as_view(),
        name="weekly_sales_chart_data",
    ),
    path(
        "dashboard/monthly_sales_chart/",
        generic.TemplateView.as_view(template_name="leads/monthly_chart.html"),
        name="monthly_sales_chart",
    ),
    path(
        "dashboard/monthly_sales_chart/data/",
        MonthlySalesChart.as_view(),
        name="monthly_sales_chart_data",
    ),
    path(
        "dashboard/yearly_sales_chart/",
        generic.TemplateView.as_view(template_name="leads/yearly_chart.html"),
        name="yearly_sales_chart",
    ),
    path(
        "dashboard/yearly_sales_chart/data/",
        YearlySalesChart.as_view(),
        name="yearly_sales_chart_data",
    ),
    # APIS
    path(
        "dashboard/api/age-distribution/<int:organisation_id>/",
        AgeDistributionAPIView.as_view(),
        name="age-distribution-api",
    ),
    path(
        "dashboard/api/lead-source/<int:organisation_id>/",
        LeadSourceAPIView.as_view(),
        name="lead-source-api",
    ),
    path(
        "dashboard/api/lead-stats/<int:organisation_id>/",
        LeadStatsAPIView.as_view(),
        name="lead-stats-api",
    ),
    path(
        "dashboard/api/monthly-sales/<int:organisation_id>/",
        MonthlySalesAPIView.as_view(),
        name="monthly-sales-api",
    ),
    path(
        "dashboard/api/monthly-lead-trends/<int:organisation_id>/",
        MonthlyLeadTrendsAPIView.as_view(),
        name="monthly-lead-trends-api",
    ),
    path(
        "leads/api/lead/<int:pk>/edit/", LeadEditAPIView.as_view(), name="api-lead-edit"
    ),
    path("api/", include(router.urls)),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += [
        path(r"^__debug__/", include(debug_toolbar.urls)),
    ]
