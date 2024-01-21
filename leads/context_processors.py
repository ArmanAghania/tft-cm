from django.conf import settings


def language_code_context(request):
    return {
        'LANGUAGE_CODE': request.LANGUAGE_CODE or settings.LANGUAGE_CODE
    }
