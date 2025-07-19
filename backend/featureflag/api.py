from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from .models import FeatureFlag, AuditLog, Dependency
from .serializers import (
    FeatureFlagListSerializer,
    FeatureFlagRetrieveSerializer,
    FeatureFlagToggleSerializer,
    DependencySerializer,
)


@extend_schema(
    summary="List all Feature Flags or Create a new one",
    request=FeatureFlagRetrieveSerializer,
    responses={
        200: FeatureFlagListSerializer(
            many=True
        ), 
        201: FeatureFlagRetrieveSerializer(),
        400: {"description": "Bad Request"},
    },

    examples=[
        OpenApiExample(
            "Create Flag with No Dependencies",
            value={"title": "new_homepage_design", "is_enabled": False},
            request_only=True,
        ),
        OpenApiExample(
            "Create Flag with Dependencies",
            value={
                "title": "admin_dashboard_v2",
                "is_enabled": True,
                "initial_dependencies": [
                    {"source_flag_title": "feature_auth_service"},
                    {"source_flag_title": "feature_data_etl_ready"},
                ],
            },
            request_only=True,
            response_only=False,
            summary="Example of creating a flag and its initial dependencies.",
        ),
    ],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def feature_flag_list_create(request):
    """
    Handles listing all feature flags and creating new feature flags.
    For creation, you can optionally include `initial_dependencies` by their titles.
    """
    if request.method == "GET":
        queryset = FeatureFlag.objects.all().order_by("title")
        serializer = FeatureFlagListSerializer(queryset, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = FeatureFlagRetrieveSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        feature_flag = serializer.save()
        return Response(
            FeatureFlagRetrieveSerializer(feature_flag).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    summary="Retrieve a single Feature Flag by ID",
    parameters=[
        OpenApiParameter(
            name="pk",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="ID of the feature flag.",
        ),
    ],
    responses={
        200: FeatureFlagRetrieveSerializer,
        404: {"description": "Not Found"},
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def feature_flag_retrieve(request, pk):
    """
    Retrieves the details of a single feature flag by its ID.
    """
    try:
        feature_flag = FeatureFlag.objects.get(pk=pk)
    except FeatureFlag.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = FeatureFlagRetrieveSerializer(feature_flag)
    return Response(serializer.data)


@extend_schema(
    summary="Toggle Feature Flag Active Status",
    parameters=[
        OpenApiParameter(
            name="pk",
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description="ID of the feature flag.",
        ),
    ],
    request=FeatureFlagToggleSerializer,
    responses={
        200: FeatureFlagRetrieveSerializer,
        400: {"description": "Bad Request"},
        404: {"description": "Not Found"},
    },
    examples=[
        OpenApiExample(
            "Toggle Flag",
            value={"reason": "New feature rollout"},
            request_only=True,
            response_only=False,
            summary="Example of activating/Deactivation a flag with a reason.",
        ),
    ],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def feature_flag_toggle(request, pk):
    try:
        feature_flag = FeatureFlag.objects.get(pk=pk)
    except FeatureFlag.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = FeatureFlagToggleSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    serializer.update(feature_flag, serializer.validated_data)

    AuditLog.objects.create(
        flag=feature_flag,
        creator=request.user if request.user.is_authenticated else None,
        log_type=AuditLog.AuditLogType.TOGGLE,
        reason=serializer.validated_data.get("reason", "No reason provided."),
    )

    return Response(
        FeatureFlagRetrieveSerializer(feature_flag).data, status=status.HTTP_200_OK
    )


@extend_schema(
    summary="List all Feature Flag Dependencies or Create a new one",
    request=DependencySerializer,
    responses={
        200: DependencySerializer(many=True),
        201: DependencySerializer(),
        400: {"description": "Bad Request"},
    },
    methods=["GET", "POST"],
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@authentication_classes([TokenAuthentication])
def dependency_list_create(request):
    """
    Handles listing all feature flag dependencies and creating new ones.
    To create a dependency, provide the IDs of the dependent and source flags.
    """
    if request.method == "GET":
        queryset = Dependency.objects.all().order_by(
            "dependent_flag__title", "source_flag__title"
        )
        serializer = DependencySerializer(queryset, many=True)
        return Response(serializer.data)

    elif request.method == "POST":
        serializer = DependencySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        dependency = serializer.save()
        return Response(
            DependencySerializer(dependency).data, status=status.HTTP_201_CREATED
        )
