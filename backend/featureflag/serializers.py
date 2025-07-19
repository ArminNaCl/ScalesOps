from rest_framework import serializers
from django.db import transaction, IntegrityError
from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)  # Avoid conflict with DRF ValidationError

from .models import FeatureFlag, Dependency, AuditLog


class DependencyListSerializer(serializers.ModelSerializer):
    source_flag = serializers.CharField(source="source_flag.title")

    class Meta:
        model = Dependency
        fields = [
            "source_flag",
        ]


class DependencyCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a new dependency. Used for nested creation.
    Expects the title of the source flag.
    """

    source_flag_title = serializers.CharField(
        max_length=200,
        help_text="The title of the feature flag this new flag will depend on.",
    )

    def validate_source_flag_title(self, value):
        """
        Check that the source flag exists.
        """
        try:
            FeatureFlag.objects.get(title=value)
        except FeatureFlag.DoesNotExist:
            raise serializers.ValidationError(
                f"Feature Flag with title '{value}' does not exist."
            )
        return value


class FeatureFlagListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "title",
            "is_enabled",
            "is_active",
        ]


class FeatureFlagRetrieveSerializer(serializers.ModelSerializer):

    is_active = serializers.BooleanField(
        read_only=True, help_text="Current active status including dependencies."
    )
    initial_dependencies = DependencyCreateSerializer(
        many=True,
        write_only=True,
        required=False,
        help_text="List of initial dependencies (by source flag title) to create for this feature flag.",
    )

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result["existence_dependencies"] = DependencyListSerializer(
            instance.dependency_rules_as_dependent.all(), many=True
        ).data
        return result

    class Meta:
        model = FeatureFlag
        fields = [
            "id",
            "title",
            "is_enabled",
            "is_active",
            "initial_dependencies",
        ]

    def create(self, validated_data):
        # Extract initial_dependencies from validated_data, if provided
        initial_dependencies_data = validated_data.pop("initial_dependencies", [])

        with transaction.atomic():
            # Create the FeatureFlag instance first
            feature_flag = super().create(validated_data)

            # Create dependencies if provided
            for dep_data in initial_dependencies_data:
                source_flag_title = dep_data["source_flag_title"]
                try:
                    source_flag = FeatureFlag.objects.get(title=source_flag_title)
                    # Attempt to create the Dependency
                    Dependency.objects.create(
                        dependent_flag=feature_flag, source_flag=source_flag
                    )
                except FeatureFlag.DoesNotExist:
                    # This should ideally be caught by validate_source_flag_title, but good for safety
                    raise serializers.ValidationError(
                        f"Source flag '{source_flag_title}' not found for dependency."
                    )
                except DjangoValidationError as e:
                    # Catch model-level validation errors (like circular dependency)
                    # and re-raise as DRF ValidationError
                    raise serializers.ValidationError(e.message_dict)
                except IntegrityError as e:
                    # Catch database-level errors (like unique_together)
                    # and provide a more user-friendly message
                    if "unique constraint" in str(e).lower():
                        raise serializers.ValidationError(
                            f"Duplicate dependency detected: '{feature_flag.title}' already depends on '{source_flag_title}'."
                        )
                    raise serializers.ValidationError(
                        f"Database error during dependency creation: {e}"
                    )
                AuditLog.objects.create(
                    flag=source_flag,
                    creator=(
                        self.context.get("request").user
                        if self.context.get("request")
                        and self.context["request"].user.is_authenticated
                        else None
                    ),
                    log_type=AuditLog.AuditLogType.CREATE,
                    reason="",
                )

        return feature_flag


class FeatureFlagToggleSerializer(serializers.Serializer):
    reason = serializers.CharField()

    def update(self, instance, validated_data):

        instance.is_enabled = not instance.is_enabled
        try:
            instance.save()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        AuditLog.objects.create(
            flag=instance,
            creator=(
                self.context.get("request").user
                if self.context.get("request")
                and self.context["request"].user.is_authenticated
                else None
            ),
            log_type=AuditLog.AuditLogType.FLAG_TOGGLE,
            reason=reason,
        )

        return instance


class DependencySerializer(serializers.ModelSerializer):

    dependent_flag_title = serializers.CharField(
        source="dependent_flag.title", read_only=True
    )
    source_flag_title = serializers.CharField(
        source="source_flag.title", read_only=True
    )

    # For input: use PrimaryKeyRelatedField to accept flag IDs
    dependent_flag = serializers.PrimaryKeyRelatedField(
        queryset=FeatureFlag.objects.all(),
        write_only=True,
        help_text="ID of the feature flag that depends on another flag.",
    )
    source_flag = serializers.PrimaryKeyRelatedField(
        queryset=FeatureFlag.objects.all(),
        write_only=True,
        help_text="ID of the feature flag that this flag depends on.",
    )

    class Meta:
        model = Dependency
        fields = [
            "id",
            "dependent_flag",
            "source_flag",
            "dependent_flag_title",
            "source_flag_title",
        ]
        read_only_fields = ["id", "dependent_flag_title", "source_flag_title"]

    def create(self, validated_data):
        # The parent create method will handle creating the Dependency instance
        try:
            creator = (
                self.context.get("request").user
                if self.context.get("request")
                and self.context["request"].user.is_authenticated
                else None
            )
            validated_data["creator"] = creator
            dependency = super().create(validated_data)
            return dependency
        except DjangoValidationError as e:
            # Catch model-level validation errors (like circular dependency)
            # and re-raise as DRF ValidationError
            raise serializers.ValidationError(e.message_dict)
        except IntegrityError as e:
            # Catch database-level errors (like unique_together)
            # and provide a more user-friendly message
            if "unique constraint" in str(e).lower():
                raise serializers.ValidationError(
                    f"This dependency already exists: '{validated_data['dependent_flag'].title}' already depends on '{validated_data['source_flag'].title}'."
                )
            raise serializers.ValidationError(
                f"Database error during dependency creation: {e}"
            )
