from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from rest_framework.routers import DefaultRouter

from .views import (
    MeAccessAPIView,
    MeProfileAPIView,
    PermissionModuleListAPIView,
    RoleListCreateAPIView,
    RoleRetrieveUpdateDestroyAPIView,
    StaffListCreateAPIView,
    StaffRetrieveUpdateAPIView,
    StudentsViewSet,
)

app_name = "users"

router = DefaultRouter()
router.register(prefix="students", viewset=StudentsViewSet, basename="students")

urlpatterns = [
    path("me/", MeProfileAPIView.as_view(), name="me"),
    path("me/access/", MeAccessAPIView.as_view(), name="me-access"),

    path("permission-modules/", PermissionModuleListAPIView.as_view(), name="permission-modules"),

    path("roles/", RoleListCreateAPIView.as_view(), name="roles-list-create"),
    path("roles/<int:pk>/", RoleRetrieveUpdateDestroyAPIView.as_view(), name="roles-detail"),

    path("staff/", StaffListCreateAPIView.as_view(), name="staff-list-create"),
    path("staff/<int:pk>/", StaffRetrieveUpdateAPIView.as_view(), name="staff-detail"),

    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),

    path('', include(router.urls)),

]