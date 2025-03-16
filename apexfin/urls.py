from django.contrib import admin
from django.urls import path, include
from users import views  # Ensure views are correctly imported

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.homepage, name='homepage'),  # Homepage view
    path('users/', include('users.urls')),  # ❌ Removed `namespace='users'`, not needed here
]


