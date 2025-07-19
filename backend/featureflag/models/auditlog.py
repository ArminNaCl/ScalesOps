from tabnanny import verbose
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.conf import settings



class AuditLog(models.Model):
    class AuditLogType(models.TextChoices):
        CREATE = "create", _("create")
        TOGGLE = "toggle", _("toggle")
        AUTO_DISABLE = "auto_disable", _("auto disable")
        DEPENDENCY_ADD = "dependency_add", ("dependency add")

    flag = models.ForeignKey(
        "featureflag.FeatureFlag",
        verbose_name=_("flag"),
        related_name="logs",
        on_delete=models.CASCADE,
    )


    log_type = models.CharField(
        _("log type"),
        max_length=100,
        choices=AuditLogType.choices,
        default=AuditLogType.CREATE
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("creator"),
        null=True,
        blank=True,
        related_name="logs",
        on_delete=models.SET_NULL,
    )

    reason = models.TextField(_("reason"), blank=True, null=True)
    created_at = models.DateTimeField(_("creatd at"), auto_now=True)

    class Meta:
        verbose_name = _("audit log")
        verbose_name_plural = _("audit logs")

    def __str__(self):
        return f"{self.flag.title} ({self.created_at})"
