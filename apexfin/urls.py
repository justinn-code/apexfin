from django.contrib import admin
from django.urls import path, include
from users import views  # Ensure this is correctly imported

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.homepage, name='homepage'),  # Homepage view
    path('users/', include('users.urls', namespace='users')),  # ✅ Include users URLs
]

