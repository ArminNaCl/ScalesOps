from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.conf import settings


class Dependency(models.Model):

    dependent_flag = models.ForeignKey(
        "featureflag.FeatureFlag",
        on_delete=models.CASCADE,
        related_name=_("dependency_rules_as_dependent"),
        help_text=_("The feature flag whose state is dependent on this rule."),
    )

    source_flag = models.ForeignKey(
        "featureflag.FeatureFlag",
        on_delete=models.CASCADE,
        related_name=_("dependency_rules_as_source"),
        help_text=_("The feature flag that this rule evaluates against"),
    )

    created_at = models.DateTimeField(_("created at"), auto_now=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("creator"),
        null=True,
        blank=True,
        related_name="dependencies",
        on_delete=models.SET_NULL,
    )



    def evaluate(self):
        return self.source_flag.is_active()

    def clean(self):
        """
        Custom validation to prevent circular dependencies before saving.
        """
        if self.dependent_flag == self.source_flag:
            raise ValidationError(
                _(
                    "A feature flag cannot depend on itself. Please select two different flags."
                ),
                code="dependency_conflict",
            )

        visited = set()
        path_list = []

        if self._find_path_and_detect_cycle(
            self.source_flag, self.dependent_flag, visited, path_list
        ):

            if path_list:
                cycle_str_parts = [self.dependent_flag.title] + [
                    flag.title for flag in path_list
                ]
                full_cycle_path = " -> ".join(cycle_str_parts)

                raise ValidationError(
                    _(
                        "This dependency creates a circular relationship. "
                        "Adding '%(dependent_flag_title)s' depending on '%(source_flag_title)s' "
                        "would form a direct or indirect cycle: %(full_cycle_path)s. "
                        "Please remove the existing dependency that causes this cycle, or re-evaluate your flag structure."
                    )
                    % {
                        "dependent_flag_title": self.dependent_flag.title,
                        "source_flag_title": self.source_flag.title,
                        "full_cycle_path": full_cycle_path,
                    },
                    code="dependency_conflict",
                )

    def _find_path_and_detect_cycle(
        self, current_node, target_node, visited, path_list
    ):
        if current_node.pk == target_node.pk:
            path_list.append(current_node)
            return True

        if current_node.pk in visited:
            return False

        visited.add(current_node.pk)
        path_list.append(current_node)

        for dependency_rule in current_node.dependency_rules_as_dependent.all():

            next_node = dependency_rule.source_flag

            if self._find_path_and_detect_cycle(
                next_node, target_node, visited, path_list
            ):
                return True

        path_list.pop()
        return False

    def save(self, *args, **kwargs):

        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = _("dependency")
        verbose_name_plural = _("dependencies")
        unique_together = ("dependent_flag", "source_flag")

    def __str__(self):
        return f"{self.dependent_flag.title} -> {self.source_flag.title}"
