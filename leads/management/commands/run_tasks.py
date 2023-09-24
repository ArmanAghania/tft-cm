from django.core.management.base import BaseCommand

from background_task.models import Task

class Command(BaseCommand):
    help = 'Run background tasks'

    def handle(self, *args, **kwargs):
        for task in Task.objects.all():
            try:
                task.run()
                task.delete()  # delete the task after running
                self.stdout.write(self.style.SUCCESS(f'Successfully ran task with ID: {task.id}'))
            except Exception as e:
                # Log the error for inspection
                self.stderr.write(self.style.ERROR(f'Error running task with ID: {task.id}: {str(e)}'))
                # You can choose not to delete the task if it fails