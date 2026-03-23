from rest_framework import permissions


class HasAppPermission(permissions.BasePermission):
    message = "Недостаточно прав для выполнения действия."

    def __init__(self, permission_code=None):
        self.permission_code = permission_code

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        if not self.permission_code:
            return True

        return user.has_app_permission(self.permission_code)