from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.conf import settings


class FeatureFlag(models.Model):
    title = models.CharField(
        _("title"),
        max_length=200,
        unique=True,
        help_text="a unique name for a feature flag like slung",
    )
    is_enabled = models.BooleanField(_("is active"), default=False)

    created_at = models.DateTimeField(_("created at"), auto_now=True)
    update_at = models.DateTimeField(_("updated at"), auto_now_add=True)

    def _check_dependencies_recursively(self, visited_flags):

        if self.title in visited_flags:
            return False
        visited_flags.add(self.title)

        for rule in self.dependency_rules_as_dependent.all():
            if not rule.source_flag.is_enabled:
                return False
            if not rule.source_flag._check_dependencies_recursively(visited_flags.copy()):
                return False 
        return True

    def can_be_active(self):
        visited_flags = set()
        return self._check_dependencies_recursively(visited_flags)

    def is_active(self)->bool:
        if not self.is_enabled:
            return False

        return self.can_be_active()

    def clean(self):
        if self.pk is None:
            return None

        if self.is_enabled and not self.can_be_active():
            blocking_dependencies = []
            visited_flags_for_message = set()
            self._find_blocking_dependencies(visited_flags_for_message, blocking_dependencies)

            blocking_titles = [f"'{flag.title}'" for flag in blocking_dependencies]
            dependency_chain_message = ""
            if blocking_titles:
                dependency_chain_message = (
                    f"because its dependent flag(s) {', '.join(blocking_titles)} "
                    f"are currently not active or have unmet dependencies."
                )
            else:
                dependency_chain_message = "because one or more of its dependencies (direct or indirect) is not active."


            raise ValidationError(
                _("Cannot activate feature flag '%(flag_title)s' "
                  "due to unmet dependencies. %(dependency_chain_message)s "
                  "Please ensure all required flags in its dependency chain are active."
                ) % {
                    'flag_title': self.title,
                    'dependency_chain_message': dependency_chain_message
                }
            )

    def _find_blocking_dependencies(self, visited, blocking_list):
        if self.pk in visited:
            return
        visited.add(self.pk)


        for rule in self.dependency_rules_as_dependent.all():
            if not rule.source_flag.is_enabled:
                blocking_list.append(rule.source_flag)
            elif not rule.source_flag.can_be_active():
                rule.source_flag._find_blocking_dependencies(visited, blocking_list) 

    def save(self, *args, **kwargs):
        if self.pk is not None:
            print(self.pk)
            self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title}"

    class Meta:
        verbose_name = _("feature flag")
        verbose_name_plural = _("feature flags")
