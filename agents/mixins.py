from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect


class OrganisorAndLoginRequiredMixin(AccessMixin):
    """Verify that the current user is authenticated and is an organisor."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("leads:lead-list")
        return super().dispatch(request, *args, **kwargs)



# class OrganisorAndLoginRequiredMixin(AccessMixin):
#     """Verify that the current user is authenticated and is an organizer or an agent."""
#     def dispatch(self, request, *args, **kwargs):
#         if not request.user.is_authenticated or (not request.user.is_organisor and not request.user.is_agent):
#             return redirect("leads:lead-list")
#         return super().dispatch(request, *args, **kwargs)

# class OrganisorAndLoginRequiredMixin(AccessMixin):
#     """Verify that the current user is authenticated and is an organiser."""
#     def dispatch(self, request, *args, **kwargs):
#         if not request.user.is_authenticated:
#             return redirect("leads:lead-list")
#         return super().dispatch(request, *args, **kwargs)