from django.apps import AppConfig


class LeadsConfig(AppConfig):
    name = 'leads'
    verbose_name = 'لیدها'

    def ready(self):
        import leads.signals

