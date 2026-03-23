from django.urls import path

from .views import (
    CourseListCreateAPIView,
    CourseContentsAPIView,
    SemesterCreateAPIView,
    SemesterContentsAPIView,
    SubjectCreateAPIView,
    SubjectContentsAPIView,
    TopicCreateAPIView,
    TopicContentsAPIView,
    MaterialCreateAPIView,
    MaterialContentsAPIView,
    MaterialFolderCreateAPIView,
    MaterialFolderContentsAPIView,
    MaterialFileCreateAPIView,
)

app_name = "courses"

urlpatterns = [
    path("", CourseListCreateAPIView.as_view(), name="course-list-create"),
    path("<int:pk>/contents/", CourseContentsAPIView.as_view(), name="course-contents"),

    path("semesters/", SemesterCreateAPIView.as_view(), name="semester-create"),
    path("semesters/<int:pk>/contents/", SemesterContentsAPIView.as_view(), name="semester-contents"),

    path("subjects/", SubjectCreateAPIView.as_view(), name="subject-create"),
    path("subjects/<int:pk>/contents/", SubjectContentsAPIView.as_view(), name="subject-contents"),

    path("topics/", TopicCreateAPIView.as_view(), name="topic-create"),
    path("topics/<int:pk>/contents/", TopicContentsAPIView.as_view(), name="topic-contents"),

    path("materials/", MaterialCreateAPIView.as_view(), name="material-create"),
    path("materials/<int:pk>/contents/", MaterialContentsAPIView.as_view(), name="material-contents"),

    path("folders/", MaterialFolderCreateAPIView.as_view(), name="folder-create"),
    path("folders/<int:pk>/contents/", MaterialFolderContentsAPIView.as_view(), name="folder-contents"),

    path("files/", MaterialFileCreateAPIView.as_view(), name="file-create"),
]