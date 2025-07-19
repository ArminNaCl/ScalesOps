from django.contrib import admin
from .models import FeatureFlag, Dependency, AuditLog

# Register your models here.

admin.site.register(FeatureFlag)
admin.site.register(Dependency)
admin.site.register(AuditLog)