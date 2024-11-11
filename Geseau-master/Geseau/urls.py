from django.contrib import admin
from django.urls import path, include
from django.conf import settings # new
from  django.conf.urls.static import static #new

urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('conso.urls')),
]
