from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import (
    PermissionAction,
    PermissionModule,
    Role,
    User,
)


def build_permission_modules_payload(*, granted_action_ids=None, grant_all=False):
    granted_action_ids = set(granted_action_ids or [])

    modules = PermissionModule.objects.filter(is_active=True).prefetch_related(
        Prefetch(
            "actions",
            queryset=PermissionAction.objects.filter(is_active=True).order_by("position", "id"),
        )
    ).order_by("position", "id")

    result = []
    for module in modules:
        actions_payload = []
        has_access = False

        for action in module.actions.all():
            granted = grant_all or (action.id in granted_action_ids)
            if granted:
                has_access = True

            actions_payload.append({
                "id": action.id,
                "code": action.code,
                "title": action.title,
                "description": action.description,
                "position": action.position,
                "granted": granted,
            })

        result.append({
            "id": module.id,
            "code": module.code,
            "title": module.title,
            "position": module.position,
            "allow_partial_permissions": module.allow_partial_permissions,
            "has_access": grant_all or has_access,
            "actions": actions_payload,
        })

    return result


class PermissionActionReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PermissionAction
        fields = (
            "id",
            "code",
            "title",
            "description",
            "position",
        )


class PermissionModuleReadSerializer(serializers.ModelSerializer):
    actions = PermissionActionReadSerializer(many=True, read_only=True)

    class Meta:
        model = PermissionModule
        fields = (
            "id",
            "code",
            "title",
            "position",
            "allow_partial_permissions",
            "actions",
        )


class RoleShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("id", "name", "slug")


class RoleListSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "is_system",
            "is_active",
            "user_count",
        )


class RoleReadSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()
    modules = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "is_system",
            "is_active",
            "permission_codes",
            "modules",
        )

    def get_permission_codes(self, obj):
        return list(
            obj.permissions.filter(
                is_active=True,
                module__is_active=True,
            ).order_by("module__position", "position", "id").values_list("code", flat=True)
        )

    def get_modules(self, obj):
        granted_action_ids = list(
            obj.permissions.filter(
                is_active=True,
                module__is_active=True,
            ).values_list("id", flat=True)
        )
        return build_permission_modules_payload(granted_action_ids=granted_action_ids)


class RoleWriteSerializer(serializers.ModelSerializer):
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "permission_codes",
        )
        read_only_fields = ("id", "slug")

    def validate_permission_codes(self, value):
        unique_codes = list(dict.fromkeys(value))

        permissions = list(
            PermissionAction.objects.select_related("module").filter(
                code__in=unique_codes,
                is_active=True,
                module__is_active=True,
            )
        )
        permissions_map = {permission.code: permission for permission in permissions}
        missing_codes = [code for code in unique_codes if code not in permissions_map]

        if missing_codes:
            raise serializers.ValidationError(
                f"Неизвестные permission codes: {', '.join(missing_codes)}"
            )

        permissions_ordered = [permissions_map[code] for code in unique_codes]

        modules_map = {}
        for permission in permissions_ordered:
            modules_map.setdefault(permission.module_id, []).append(permission)

        for module_id, selected_permissions in modules_map.items():
            module = selected_permissions[0].module
            if not module.allow_partial_permissions:
                total_active_in_module = PermissionAction.objects.filter(
                    module_id=module_id,
                    is_active=True,
                ).count()
                if len(selected_permissions) != total_active_in_module:
                    raise serializers.ValidationError(
                        f"Для модуля '{module.title}' нужно либо выдать весь доступ, либо не выдавать вообще."
                    )

        self._validated_permissions = permissions_ordered
        return unique_codes

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("permission_codes", None)
        permissions = getattr(self, "_validated_permissions", [])
        role = Role.objects.create(**validated_data)
        if permissions:
            role.permissions.set(permissions)
        return role

    @transaction.atomic
    def update(self, instance, validated_data):
        permission_codes_passed = "permission_codes" in self.initial_data
        validated_data.pop("permission_codes", None)
        permissions = getattr(self, "_validated_permissions", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if permission_codes_passed:
            instance.permissions.set(permissions or [])

        return instance

    def to_representation(self, instance):
        return RoleReadSerializer(instance, context=self.context).data


class UserProfileSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    account_type_display = serializers.CharField(source="get_account_type_display", read_only=True)
    role = RoleShortSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "display_name",
            "first_name",
            "last_name",
            "middle_name",
            "email",
            "phone",
            "avatar",
            "account_type",
            "account_type_display",
            "role",
            "must_change_password",
            "date_joined",
        )
        read_only_fields = (
            "id",
            "display_name",
            "account_type",
            "account_type_display",
            "role",
            "must_change_password",
            "date_joined",
        )


class UserAccessSerializer(serializers.Serializer):
    user = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    modules = serializers.SerializerMethodField()

    def get_user(self, obj):
        return UserProfileSerializer(obj, context=self.context).data

    def get_role(self, obj):
        if obj.is_superuser or obj.account_type == User.AccountType.OWNER:
            return {
                "id": None,
                "name": "Главный пользователь",
                "slug": "owner",
            }
        if obj.role_id:
            return RoleShortSerializer(obj.role, context=self.context).data
        return None

    def get_modules(self, obj):
        grant_all = obj.is_superuser or obj.account_type == User.AccountType.OWNER
        granted_action_ids = []

        if obj.role_id and obj.role and obj.role.is_active:
            granted_action_ids = list(
                obj.role.permissions.filter(
                    is_active=True,
                    module__is_active=True,
                ).values_list("id", flat=True)
            )

        return build_permission_modules_payload(
            granted_action_ids=granted_action_ids,
            grant_all=grant_all,
        )


class StaffUserListSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    account_type_display = serializers.CharField(source="get_account_type_display", read_only=True)
    role = RoleShortSerializer(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "display_name",
            "email",
            "phone",
            "avatar",
            "account_type",
            "account_type_display",
            "role",
            "is_active",
        )


class StaffUserReadSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    account_type_display = serializers.CharField(source="get_account_type_display", read_only=True)
    role = RoleShortSerializer(read_only=True)
    temporary_password = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "display_name",
            "first_name",
            "last_name",
            "middle_name",
            "email",
            "phone",
            "avatar",
            "account_type",
            "account_type_display",
            "role",
            "is_active",
            "must_change_password",
            "temporary_password",
            "date_joined",
        )

    def get_temporary_password(self, obj):
        return getattr(obj, "_generated_password", None)


class StaffUserCreateSerializer(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(is_active=True),
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = (
            "id",
            "password",
            "first_name",
            "last_name",
            "middle_name",
            "email",
            "phone",
            "avatar",
            "role",
            "is_active",
        )
        read_only_fields = ("id",)

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password", None)
        role = validated_data.pop("role")
        creator = self.context["request"].user

        user = User.objects.create_employee_account(
            role=role,
            password=password,
            created_by=creator,
            **validated_data,
        )

        if password:
            user._generated_password = None

        return user

    def to_representation(self, instance):
        return StaffUserReadSerializer(instance, context=self.context).data


class StaffUserUpdateSerializer(serializers.ModelSerializer):
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(is_active=True),
        required=False,
    )
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = (
            "password",
            "first_name",
            "last_name",
            "middle_name",
            "email",
            "phone",
            "avatar",
            "role",
            "is_active",
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
            instance.must_change_password = True

        instance.save()
        return instance

    def to_representation(self, instance):
        return StaffUserReadSerializer(instance, context=self.context).data


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if not (email and password):
            raise ValidationError(
                "Must include 'email' and 'password'"
            )

        user = authenticate(
            request=self.context.get("request"),
            username=email.lower(),
            password=password
        )

        if not user or not user.is_active:
            raise ValidationError(
                "Such user does not exists or was delete"
            )

        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Старый пароль неверен")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Пароли не совпадают")

        validate_password(attrs['new_password'])
        return attrs


class StudentSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            "email", "first_name", "last_name", "middle_name", "phone"
        )


