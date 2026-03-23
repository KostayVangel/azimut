from django.db import transaction
from rest_framework import serializers

from .models import (
    Course,
    Semester,
    Subject,
    Topic,
    Material,
    LectureMaterial,
    PresentationMaterial,
    DocumentMaterial,
    TestMaterial,
    MaterialFolder,
    MaterialFile,
    TestQuestion,
    TestAnswerOption,
)


# =========================================================
# READ SERIALIZERS
# =========================================================

class CourseListSerializer(serializers.ModelSerializer):
    course_type_display = serializers.CharField(source="get_course_type_display", read_only=True)

    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "slug",
            "description",
            "course_type",
            "course_type_display",
            "position",
            "is_active",
        )


class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ("id", "course", "title", "position")


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ("id", "semester", "title", "description", "position")


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ("id", "course", "subject", "title", "description", "position")


class MaterialListSerializer(serializers.ModelSerializer):
    material_type_display = serializers.CharField(source="get_material_type_display", read_only=True)

    class Meta:
        model = Material
        fields = (
            "id",
            "course",
            "subject",
            "topic",
            "title",
            "material_type",
            "material_type_display",
            "description",
            "position",
            "is_published",
            "free_preview",
        )


class MaterialFolderSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialFolder
        fields = ("id", "material", "parent", "title", "position")


class MaterialFileSerializer(serializers.ModelSerializer):
    file_role_display = serializers.CharField(source="get_file_role_display", read_only=True)

    class Meta:
        model = MaterialFile
        fields = (
            "id",
            "material",
            "folder",
            "title",
            "file",
            "file_role",
            "file_role_display",
            "position",
        )


class LectureMaterialReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LectureMaterial
        fields = ("content", "duration_minutes")


class PresentationMaterialReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PresentationMaterial
        fields = ("speaker_notes", "slides_count")


class DocumentMaterialReadSerializer(serializers.ModelSerializer):
    document_format_display = serializers.CharField(source="get_document_format_display", read_only=True)

    class Meta:
        model = DocumentMaterial
        fields = ("document_format", "document_format_display", "extracted_text")


class TestAnswerOptionPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestAnswerOption
        fields = ("id", "text", "position")


class TestQuestionPublicSerializer(serializers.ModelSerializer):
    options = TestAnswerOptionPublicSerializer(many=True, read_only=True)

    class Meta:
        model = TestQuestion
        fields = (
            "id",
            "text",
            "question_type",
            "points",
            "position",
            "options",
        )


class TestMaterialPublicSerializer(serializers.ModelSerializer):
    questions = TestQuestionPublicSerializer(many=True, read_only=True)

    class Meta:
        model = TestMaterial
        fields = (
            "time_limit_minutes",
            "attempts_limit",
            "passing_percentage",
            "shuffle_questions",
            "show_correct_answers_after_submit",
            "questions",
        )


class MaterialContentSerializer(serializers.ModelSerializer):
    material_type_display = serializers.CharField(source="get_material_type_display", read_only=True)
    lecture_data = LectureMaterialReadSerializer(read_only=True)
    presentation_data = PresentationMaterialReadSerializer(read_only=True)
    document_data = DocumentMaterialReadSerializer(read_only=True)
    test_data = TestMaterialPublicSerializer(read_only=True)

    class Meta:
        model = Material
        fields = (
            "id",
            "course",
            "subject",
            "topic",
            "title",
            "material_type",
            "material_type_display",
            "description",
            "position",
            "is_published",
            "free_preview",
            "lecture_data",
            "presentation_data",
            "document_data",
            "test_data",
            "created_at",
            "updated_at",
        )


# =========================================================
# WRITE SERIALIZERS
# =========================================================

class CourseWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = (
            "id",
            "title",
            "slug",
            "description",
            "course_type",
            "position",
            "is_active",
        )
        read_only_fields = ("id",)


class SemesterWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ("id", "course", "title", "position")
        read_only_fields = ("id",)


class SubjectWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ("id", "semester", "title", "description", "position")
        read_only_fields = ("id",)


class TopicWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ("id", "course", "subject", "title", "description", "position")
        read_only_fields = ("id",)


class LectureMaterialWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LectureMaterial
        fields = ("content", "duration_minutes")


class PresentationMaterialWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PresentationMaterial
        fields = ("speaker_notes", "slides_count")


class DocumentMaterialWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentMaterial
        fields = ("document_format", "extracted_text")


class TestAnswerOptionWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestAnswerOption
        fields = ("text", "is_correct", "position")


class TestQuestionWriteSerializer(serializers.ModelSerializer):
    options = TestAnswerOptionWriteSerializer(many=True, required=False)

    class Meta:
        model = TestQuestion
        fields = (
            "text",
            "question_type",
            "explanation",
            "points",
            "position",
            "correct_text_answers",
            "case_sensitive",
            "options",
        )

    def validate(self, attrs):
        question_type = attrs.get("question_type")
        options = attrs.get("options", [])
        correct_text_answers = attrs.get("correct_text_answers", [])

        if question_type == TestQuestion.QuestionType.TEXT and options:
            raise serializers.ValidationError({
                "options": "Для текстового вопроса нельзя передавать варианты ответа."
            })

        if question_type in (TestQuestion.QuestionType.SINGLE, TestQuestion.QuestionType.MULTIPLE) and correct_text_answers:
            raise serializers.ValidationError({
                "correct_text_answers": "Для single/multiple вопроса правильные ответы нужно хранить в options[].is_correct."
            })

        return attrs


class TestMaterialWriteSerializer(serializers.ModelSerializer):
    questions = TestQuestionWriteSerializer(many=True, required=False)

    class Meta:
        model = TestMaterial
        fields = (
            "time_limit_minutes",
            "attempts_limit",
            "passing_percentage",
            "shuffle_questions",
            "show_correct_answers_after_submit",
            "questions",
        )


class MaterialWriteSerializer(serializers.ModelSerializer):
    lecture_data = LectureMaterialWriteSerializer(required=False)
    presentation_data = PresentationMaterialWriteSerializer(required=False)
    document_data = DocumentMaterialWriteSerializer(required=False)
    test_data = TestMaterialWriteSerializer(required=False)

    class Meta:
        model = Material
        fields = (
            "id",
            "course",
            "subject",
            "topic",
            "title",
            "material_type",
            "description",
            "position",
            "is_published",
            "free_preview",
            "lecture_data",
            "presentation_data",
            "document_data",
            "test_data",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        parent_fields = [attrs.get("course"), attrs.get("subject"), attrs.get("topic")]
        parents_count = sum(1 for value in parent_fields if value is not None)
        if parents_count != 1:
            raise serializers.ValidationError(
                "Материал должен принадлежать только одному родителю: course, subject или topic."
            )

        details_map = {
            Material.MaterialType.LECTURE: "lecture_data",
            Material.MaterialType.PRESENTATION: "presentation_data",
            Material.MaterialType.DOCUMENT: "document_data",
            Material.MaterialType.TEST: "test_data",
        }

        passed_detail_fields = [
            field_name
            for field_name in ("lecture_data", "presentation_data", "document_data", "test_data")
            if self.initial_data.get(field_name) is not None
        ]

        if len(passed_detail_fields) > 1:
            raise serializers.ValidationError(
                "Можно передать только одну структуру деталей материала: lecture_data / presentation_data / document_data / test_data."
            )

        expected_detail_field = details_map.get(attrs.get("material_type"))
        if passed_detail_fields and expected_detail_field and passed_detail_fields[0] != expected_detail_field:
            raise serializers.ValidationError({
                passed_detail_fields[0]: "Структура деталей не соответствует типу материала."
            })

        return attrs

    def create(self, validated_data):
        lecture_data = validated_data.pop("lecture_data", None)
        presentation_data = validated_data.pop("presentation_data", None)
        document_data = validated_data.pop("document_data", None)
        test_data = validated_data.pop("test_data", None)

        with transaction.atomic():
            material = Material.objects.create(**validated_data)

            if material.material_type == Material.MaterialType.LECTURE:
                LectureMaterial.objects.create(material=material, **(lecture_data or {}))

            elif material.material_type == Material.MaterialType.PRESENTATION:
                PresentationMaterial.objects.create(material=material, **(presentation_data or {}))

            elif material.material_type == Material.MaterialType.DOCUMENT:
                DocumentMaterial.objects.create(material=material, **(document_data or {}))

            elif material.material_type == Material.MaterialType.TEST:
                test_questions = []
                if test_data:
                    test_questions = test_data.pop("questions", [])

                test_instance = TestMaterial.objects.create(material=material, **(test_data or {}))

                for question_data in test_questions:
                    options_data = question_data.pop("options", [])
                    question = TestQuestion.objects.create(test=test_instance, **question_data)

                    for option_data in options_data:
                        TestAnswerOption.objects.create(question=question, **option_data)

        return material


class MaterialFolderWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialFolder
        fields = ("id", "material", "parent", "title", "position")
        read_only_fields = ("id",)


class MaterialFileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MaterialFile
        fields = ("id", "material", "folder", "title", "file", "file_role", "position")
        read_only_fields = ("id",)