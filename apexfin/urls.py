from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView  # To serve the homepage

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='homepage.html'), name='homepage'),  # ✅ Add this
    path('users/', include('users.urls', namespace='users')),
]
