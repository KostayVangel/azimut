from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Course, Semester, Subject, Topic, Material, MaterialFolder, MaterialFile
from .serializers import (
    CourseListSerializer,
    CourseWriteSerializer,
    SemesterSerializer,
    SemesterWriteSerializer,
    SubjectSerializer,
    SubjectWriteSerializer,
    TopicSerializer,
    TopicWriteSerializer,
    MaterialListSerializer,
    MaterialContentSerializer,
    MaterialWriteSerializer,
    MaterialFolderSerializer,
    MaterialFolderWriteSerializer,
    MaterialFileSerializer,
    MaterialFileWriteSerializer,
)


# =========================================================
# PERMISSIONS / HELPERS
# =========================================================

class IsCourseEditorOrReadOnly(permissions.BasePermission):
    """
    Пока что на запись пускаем любого авторизованного пользователя.
    Когда добавишь роли - замени проверку на request.user.role / permission.
    """

    message = "Недостаточно прав для изменения курсов."

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)


def get_available_courses_queryset(user):
    """
    Сейчас отдаем все активные курсы.
    Позже здесь можно добавить фильтрацию по покупкам пользователя.

    Пример будущей логики:
        if user.is_authenticated and not user.is_staff:
            qs = qs.filter(purchases__user=user, purchases__is_paid=True).distinct()
    """
    return Course.objects.filter(is_active=True).order_by("position", "id")


def get_published_materials_queryset(queryset):
    return queryset.filter(is_published=True).order_by("position", "id")


def root_breadcrumb():
    return [{"type": "root", "id": None, "title": "Все курсы"}]


def resolve_topic_course(topic):
    return topic.course if topic.course_id else topic.subject.semester.course


def resolve_material_course(material):
    if material.course_id:
        return material.course
    if material.subject_id:
        return material.subject.semester.course
    if material.topic_id:
        return resolve_topic_course(material.topic)
    return None


def build_course_breadcrumbs(course):
    return root_breadcrumb() + [
        {"type": "course", "id": course.id, "title": course.title}
    ]


def build_semester_breadcrumbs(semester):
    return build_course_breadcrumbs(semester.course) + [
        {"type": "semester", "id": semester.id, "title": semester.title}
    ]


def build_subject_breadcrumbs(subject):
    return build_semester_breadcrumbs(subject.semester) + [
        {"type": "subject", "id": subject.id, "title": subject.title}
    ]


def build_topic_breadcrumbs(topic):
    if topic.course_id:
        return build_course_breadcrumbs(topic.course) + [
            {"type": "topic", "id": topic.id, "title": topic.title}
        ]

    return build_subject_breadcrumbs(topic.subject) + [
        {"type": "topic", "id": topic.id, "title": topic.title}
    ]


def build_material_breadcrumbs(material):
    if material.course_id:
        base = build_course_breadcrumbs(material.course)
    elif material.subject_id:
        base = build_subject_breadcrumbs(material.subject)
    else:
        base = build_topic_breadcrumbs(material.topic)

    return base + [{"type": "material", "id": material.id, "title": material.title}]


def build_folder_breadcrumbs(folder):
    breadcrumbs = build_material_breadcrumbs(folder.material)

    ancestors = []
    current = folder
    while current is not None:
        ancestors.append(current)
        current = current.parent

    for node in reversed(ancestors):
        breadcrumbs.append({"type": "folder", "id": node.id, "title": node.title})

    return breadcrumbs


# =========================================================
# COURSE API
# =========================================================

class CourseListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [IsCourseEditorOrReadOnly]

    def get_queryset(self):
        return get_available_courses_queryset(self.request.user)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CourseWriteSerializer
        return CourseListSerializer


class CourseContentsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        course = get_object_or_404(get_available_courses_queryset(request.user), pk=pk)

        payload = {
            "node_type": "course",
            "current": CourseListSerializer(course, context={"request": request}).data,
            "breadcrumbs": build_course_breadcrumbs(course),
            "children": {},
        }

        if course.course_type == Course.CourseType.FULL:
            semesters = course.semesters.all().order_by("position", "id")
            payload["children"]["semesters"] = SemesterSerializer(
                semesters,
                many=True,
                context={"request": request},
            ).data
            payload["children"]["subjects"] = []
            payload["children"]["topics"] = []
            payload["children"]["materials"] = []
        else:
            topics = course.root_topics.all().order_by("position", "id")
            materials = get_published_materials_queryset(course.materials.all())
            payload["children"]["semesters"] = []
            payload["children"]["subjects"] = []
            payload["children"]["topics"] = TopicSerializer(
                topics,
                many=True,
                context={"request": request},
            ).data
            payload["children"]["materials"] = MaterialListSerializer(
                materials,
                many=True,
                context={"request": request},
            ).data

        return Response(payload)


# =========================================================
# SEMESTER API
# =========================================================

class SemesterCreateAPIView(generics.CreateAPIView):
    queryset = Semester.objects.all()
    serializer_class = SemesterWriteSerializer
    permission_classes = [IsCourseEditorOrReadOnly]


class SemesterContentsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        available_courses = get_available_courses_queryset(request.user)
        semester = get_object_or_404(
            Semester.objects.select_related("course").filter(course__in=available_courses),
            pk=pk,
        )
        subjects = semester.subjects.all().order_by("position", "id")

        return Response({
            "node_type": "semester",
            "current": SemesterSerializer(semester, context={"request": request}).data,
            "breadcrumbs": build_semester_breadcrumbs(semester),
            "children": {
                "subjects": SubjectSerializer(subjects, many=True, context={"request": request}).data,
                "topics": [],
                "materials": [],
            },
        })


# =========================================================
# SUBJECT API
# =========================================================

class SubjectCreateAPIView(generics.CreateAPIView):
    queryset = Subject.objects.all()
    serializer_class = SubjectWriteSerializer
    permission_classes = [IsCourseEditorOrReadOnly]


class SubjectContentsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        available_courses = get_available_courses_queryset(request.user)
        subject = get_object_or_404(
            Subject.objects.select_related("semester", "semester__course").filter(
                semester__course__in=available_courses
            ),
            pk=pk,
        )
        topics = subject.topics.all().order_by("position", "id")
        materials = get_published_materials_queryset(subject.materials.all())

        return Response({
            "node_type": "subject",
            "current": SubjectSerializer(subject, context={"request": request}).data,
            "breadcrumbs": build_subject_breadcrumbs(subject),
            "children": {
                "topics": TopicSerializer(topics, many=True, context={"request": request}).data,
                "materials": MaterialListSerializer(materials, many=True, context={"request": request}).data,
                "folders": [],
                "files": [],
            },
        })


# =========================================================
# TOPIC API
# =========================================================

class TopicCreateAPIView(generics.CreateAPIView):
    queryset = Topic.objects.all()
    serializer_class = TopicWriteSerializer
    permission_classes = [IsCourseEditorOrReadOnly]


class TopicContentsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        available_courses = get_available_courses_queryset(request.user)
        topic = get_object_or_404(
            Topic.objects.select_related(
                "course",
                "subject",
                "subject__semester",
                "subject__semester__course",
            ).filter(
                Q(course__in=available_courses) |
                Q(subject__semester__course__in=available_courses)
            ),
            pk=pk,
        )
        materials = get_published_materials_queryset(topic.materials.all())

        return Response({
            "node_type": "topic",
            "current": TopicSerializer(topic, context={"request": request}).data,
            "breadcrumbs": build_topic_breadcrumbs(topic),
            "children": {
                "materials": MaterialListSerializer(materials, many=True, context={"request": request}).data,
                "folders": [],
                "files": [],
            },
        })


# =========================================================
# MATERIAL API
# =========================================================

class MaterialCreateAPIView(generics.CreateAPIView):
    queryset = Material.objects.all()
    serializer_class = MaterialWriteSerializer
    permission_classes = [IsCourseEditorOrReadOnly]


class MaterialContentsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        available_courses = get_available_courses_queryset(request.user)
        material = get_object_or_404(
            Material.objects.select_related(
                "course",
                "subject",
                "subject__semester",
                "subject__semester__course",
                "topic",
                "topic__course",
                "topic__subject",
                "topic__subject__semester",
                "topic__subject__semester__course",
                "lecture_data",
                "presentation_data",
                "document_data",
                "test_data",
            ).prefetch_related(
                "test_data__questions__options",
            ).filter(
                Q(course__in=available_courses) |
                Q(subject__semester__course__in=available_courses) |
                Q(topic__course__in=available_courses) |
                Q(topic__subject__semester__course__in=available_courses)
            ).filter(is_published=True),
            pk=pk,
        )

        folders = material.folders.filter(parent__isnull=True).order_by("position", "id")
        files = material.files.filter(folder__isnull=True).order_by("position", "id")

        return Response({
            "node_type": "material",
            "current": MaterialContentSerializer(material, context={"request": request}).data,
            "breadcrumbs": build_material_breadcrumbs(material),
            "children": {
                "folders": MaterialFolderSerializer(folders, many=True, context={"request": request}).data,
                "files": MaterialFileSerializer(files, many=True, context={"request": request}).data,
            },
        })


# =========================================================
# FOLDER / FILE API
# =========================================================

class MaterialFolderCreateAPIView(generics.CreateAPIView):
    queryset = MaterialFolder.objects.all()
    serializer_class = MaterialFolderWriteSerializer
    permission_classes = [IsCourseEditorOrReadOnly]


class MaterialFolderContentsAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        available_courses = get_available_courses_queryset(request.user)
        folder = get_object_or_404(
            MaterialFolder.objects.select_related(
                "material",
                "material__course",
                "material__subject",
                "material__subject__semester",
                "material__subject__semester__course",
                "material__topic",
                "material__topic__course",
                "material__topic__subject",
                "material__topic__subject__semester",
                "material__topic__subject__semester__course",
                "parent",
            ).filter(
                Q(material__course__in=available_courses) |
                Q(material__subject__semester__course__in=available_courses) |
                Q(material__topic__course__in=available_courses) |
                Q(material__topic__subject__semester__course__in=available_courses)
            ).filter(material__is_published=True),
            pk=pk,
        )

        subfolders = folder.children.all().order_by("position", "id")
        files = folder.files.all().order_by("position", "id")

        return Response({
            "node_type": "folder",
            "current": MaterialFolderSerializer(folder, context={"request": request}).data,
            "breadcrumbs": build_folder_breadcrumbs(folder),
            "children": {
                "folders": MaterialFolderSerializer(subfolders, many=True, context={"request": request}).data,
                "files": MaterialFileSerializer(files, many=True, context={"request": request}).data,
            },
        })


class MaterialFileCreateAPIView(generics.CreateAPIView):
    queryset = MaterialFile.objects.all()
    serializer_class = MaterialFileWriteSerializer
    permission_classes = [IsCourseEditorOrReadOnly]
    parser_classes = (MultiPartParser, FormParser)