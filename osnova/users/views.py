from functools import partial

from django.contrib.auth import login
from django.db import transaction
from django.db.models import Count, Prefetch
from rest_framework import generics, permissions, status
from rest_framework.exceptions import ValidationError, MethodNotAllowed
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet, ModelViewSet
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework_simplejwt.serializers import TokenBlacklistSerializer

from rest_framework_simplejwt.tokens import RefreshToken

from osnova import settings
from .enums import AccountType
from .models import PermissionAction, PermissionModule, Role, User
from .permissions import HasAppPermission
from .serializers import (
    PermissionModuleReadSerializer,
    RoleListSerializer,
    RoleReadSerializer,
    RoleWriteSerializer,
    StaffUserCreateSerializer,
    StaffUserListSerializer,
    StaffUserReadSerializer,
    StaffUserUpdateSerializer,
    UserAccessSerializer,
    UserProfileSerializer, LoginSerializer, ChangePasswordSerializer, StudentSerializer,
)


def get_refresh_token(request, name='refresh_token'):
    return request.COOKIES.get(name) or request.data.get(name)


class MeProfileAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_object(self):
        return self.request.user


class MeAccessAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserAccessSerializer(request.user, context={"request": request})
        return Response(serializer.data)


class PermissionModuleListAPIView(generics.ListAPIView):
    serializer_class = PermissionModuleReadSerializer
    parser_classes = (JSONParser,)

    def get_permissions(self):
        return [
            permissions.IsAuthenticated(),
            HasAppPermission("employees.roles.configure"),
        ]

    def get_queryset(self):
        return PermissionModule.objects.filter(is_active=True).prefetch_related(
            Prefetch(
                "actions",
                queryset=PermissionAction.objects.filter(is_active=True).order_by("position", "id"),
            )
        ).order_by("position", "id")


class RoleListCreateAPIView(generics.ListCreateAPIView):
    parser_classes = (JSONParser,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [
                permissions.IsAuthenticated(),
                HasAppPermission("employees.roles.view"),
            ]
        return [
            permissions.IsAuthenticated(),
            HasAppPermission("employees.roles.create"),
        ]

    def get_queryset(self):
        return Role.objects.filter(is_active=True).annotate(
            user_count=Count("users")
        ).order_by("name", "id")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return RoleWriteSerializer
        return RoleListSerializer


class RoleRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    parser_classes = (JSONParser,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [
                permissions.IsAuthenticated(),
                HasAppPermission("employees.roles.view"),
            ]
        if self.request.method in ("PUT", "PATCH"):
            return [
                permissions.IsAuthenticated(),
                HasAppPermission("employees.roles.configure"),
            ]
        return [
            permissions.IsAuthenticated(),
            HasAppPermission("employees.roles.delete"),
        ]

    def get_queryset(self):
        return Role.objects.filter(is_active=True).prefetch_related(
            "permissions__module",
        )

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return RoleWriteSerializer
        return RoleReadSerializer

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError("Системную роль удалять нельзя.")

        if instance.users.exists():
            raise ValidationError("Нельзя удалить роль, пока она назначена сотрудникам.")

        instance.is_active = False
        instance.save()


class StaffListCreateAPIView(generics.ListCreateAPIView):
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_permissions(self):
        if self.request.method == "GET":
            return [
                permissions.IsAuthenticated(),
                HasAppPermission("employees.staff.view"),
            ]
        return [
            permissions.IsAuthenticated(),
            HasAppPermission("employees.staff.create"),
        ]

    def get_queryset(self):
        return User.objects.filter(
            account_type=AccountType.EMPLOYEE
        ).select_related("role").order_by("id")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return StaffUserCreateSerializer
        return StaffUserListSerializer


class StaffRetrieveUpdateAPIView(generics.RetrieveUpdateAPIView):
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_permissions(self):
        if self.request.method == "GET":
            return [
                permissions.IsAuthenticated(),
                HasAppPermission("employees.staff.view"),
            ]
        return [
            permissions.IsAuthenticated(),
            HasAppPermission("employees.staff.edit"),
        ]

    def get_queryset(self):
        return User.objects.filter(
            account_type=AccountType.EMPLOYEE
        ).select_related("role")

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return StaffUserUpdateSerializer
        return StaffUserReadSerializer

class StudentsViewSet(ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "list":
            return UserProfileSerializer
        return StudentSerializer

    def get_queryset(self):
        return User.objects.filter(
            account_type=AccountType.EMPLOYEE
        ).select_related("role")


    def get_permissions(self):
        permissions = super().get_permissions()

        if self.request.method == "GET":
            return permissions + [
                HasAppPermission("distribution.students.sensitive_data.view"),
            ]
        elif self.request.method == "POST":
            return permissions + [
                HasAppPermission("distribution.students.create"),
            ]
        raise MethodNotAllowed() # заглушка, должно еше быть удаление и обновление студентов

    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[*permission_classes, partial(HasAppPermission, "distribution.students.create")]
    )
    def many_create(self, request, *args, **kwargs):
        ignore_conflicts = request.query_params.get("ignore_conflicts", False)

        if not request.data:
            raise ValidationError("Не может быть передан пустой список")

        if len(request.data) > settings.MAX_STUDENTS_PER_TIME:
            raise ValidationError("Первышено кол-во студентов, которых можно создать за раз")

        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        students = [
            User(
                **data,
                **dict(
                    created_by=request.user,
                    account_type=AccountType.STUDENT,
                    must_change_password=True
                )
            ) for data in serializer.validated_data
        ]

        with transaction.atomic():
            students_obj = User.objects.bulk_create(students, ignore_conflicts=ignore_conflicts)

        return Response(
            data=UserProfileSerializer(students_obj, many=True).data,
            status=status.HTTP_201_CREATED
        )


class LoginViewSet(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # login(request, user) только для админки, в проде оставить закомментированной

        refresh_token = RefreshToken.for_user(user)

        return Response({
            "user": UserProfileSerializer(user),
            "refresh": str(refresh_token),
            "access": str(refresh_token.access_token)
        })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    """Смена пароля с проверкой старого пароля"""
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)

    user = request.user
    user.set_password(
        serializer.validated_data['new_password']
    )
    user.save()

    refresh_token = get_refresh_token(request)

    if not refresh_token:
        return Response({"detail": "Refresh token not found in cookies"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        serializer = TokenBlacklistSerializer({"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)
    except Exception as ex:
        return Response(status=status.HTTP_400_BAD_REQUEST)

    refresh_token = RefreshToken.for_user(request.user)

    return Response({
        'message': 'Пароль успешно изменен',
        "refresh": str(refresh_token),
        "access": str(refresh_token.access_token)
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def user_logout(request):
    refresh_token = get_refresh_token(request)

    if not refresh_token:
        return Response({"detail": "Refresh token not found in cookies"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        serializer = TokenBlacklistSerializer({"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)
        return Response(status=status.HTTP_200_OK)
    except Exception as ex:
        return Response(status=status.HTTP_400_BAD_REQUEST)

