from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

from users.enums import AccountType
from users.managers import UserManager


def user_avatar_upload_to(instance, filename):
    user_part = instance.pk or "new"
    return f"users/avatars/{user_part}/{filename}"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PermissionModule(TimeStampedModel):
    """
    Вкладка / раздел интерфейса.
    Пример:
    - store_settings
    - courses
    - employees
    """

    code = models.CharField(max_length=100, unique=True)
    title = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)
    allow_partial_permissions = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("position", "id")

    def __str__(self):
        return self.title


class PermissionAction(TimeStampedModel):
    """
    Конкретное действие внутри вкладки.
    Пример:
    - courses.folder.create
    - courses.tests.edit
    """

    module = models.ForeignKey(
        PermissionModule,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    code = models.CharField(max_length=150, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("module__position", "position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["module", "title"],
                name="uq_permission_action_module_title",
            ),
        ]

    def __str__(self):
        return f"{self.module.code} -> {self.title}"


class Role(TimeStampedModel):
    """
    Роль сотрудника.
    Пример:
    - Контент-менеджер
    - Куратор
    - Менеджер оплаты
    """

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True, allow_unicode=True)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    permissions = models.ManyToManyField(
        PermissionAction,
        through="RolePermission",
        related_name="roles",
        blank=True,
    )

    class Meta:
        ordering = ("name", "id")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name, allow_unicode=True)[:160] or "role"
            slug = base_slug
            counter = 1
            while Role.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        return super().save(*args, **kwargs)


class RolePermission(TimeStampedModel):
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name="role_permissions",
    )
    permission = models.ForeignKey(
        PermissionAction,
        on_delete=models.CASCADE,
        related_name="permission_roles",
    )

    class Meta:
        ordering = ("role_id", "permission__module__position", "permission__position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["role", "permission"],
                name="uq_role_permission",
            ),
        ]

    def __str__(self):
        return f"{self.role.name} -> {self.permission.code}"


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("email address"), unique=True)

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    middle_name = models.CharField(max_length=150, blank=True)

    avatar = models.ImageField(upload_to=user_avatar_upload_to, null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True, unique=True)

    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.STUDENT,
        db_index=True,
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        related_name="users",
        null=True,
        blank=True,
    )

    must_change_password = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="created_accounts",
        null=True,
        blank=True,
    )

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ("id",)
        indexes = [
            models.Index(fields=["account_type", "is_active"]),
            models.Index(fields=["role", "is_active"]),
        ]

    def __str__(self):
        return self.display_name

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = "%s %s %s" % (self.first_name, self.last_name, self.middle_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    @property
    def display_name(self):
        parts = [self.last_name, self.first_name, self.middle_name]
        full_name = " ".join(part for part in parts if part).strip()
        return full_name

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

        if self.account_type == self.AccountType.EMPLOYEE and not self.role_id:
            raise ValidationError({
                "role": "Для сотрудника обязательно нужно указать роль."
            })

        if self.account_type != self.AccountType.EMPLOYEE and self.role_id:
            raise ValidationError({
                "role": "Роль назначается только сотрудникам."
            })

    def get_permission_codes(self):
        if not self.is_authenticated or not self.is_active:
            return set()

        if self.is_superuser or self.account_type == self.AccountType.OWNER:
            return {"*"}

        if not self.role_id or not self.role or not self.role.is_active:
            return set()

        if hasattr(self, "_permission_codes_cache"):
            return self._permission_codes_cache

        codes = set(
            self.role.permissions.filter(
                is_active=True,
                module__is_active=True,
            ).values_list("code", flat=True)
        )
        self._permission_codes_cache = codes
        return codes

    def has_app_permission(self, permission_code: str) -> bool:
        permission_codes = self.get_permission_codes()
        return "*" in permission_codes or permission_code in permission_codes