import os

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


def material_file_upload_to(instance, filename):
    return f"courses/materials/{instance.material_id}/{filename}"


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


# =========================================================
# 1. ИЕРАРХИЯ КУРСОВ
# =========================================================

class Course(BaseModel):
    class CourseType(models.TextChoices):
        FULL = "full", "Полноценный"
        SIMPLE = "simple", "Неполный"

    title = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True, allow_unicode=True)
    description = models.TextField(blank=True)
    course_type = models.CharField(max_length=10, choices=CourseType.choices)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("position", "id")
        indexes = [
            models.Index(fields=["course_type", "is_active"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title, allow_unicode=True)[:240] or "course"
            slug = base_slug
            counter = 1

            while Course.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        return super().save(*args, **kwargs)


class Semester(BaseModel):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="semesters",
    )
    title = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["course", "title"],
                name="uq_semester_course_title",
            ),
            models.UniqueConstraint(
                fields=["course", "position"],
                name="uq_semester_course_pos",
            ),
        ]

    def __str__(self):
        return f"{self.course.title} -> {self.title}"

    def clean(self):
        if self.course and self.course.course_type != Course.CourseType.FULL:
            raise ValidationError({
                "course": "Семестры можно создавать только у полноценного курса."
            })


class Subject(BaseModel):
    semester = models.ForeignKey(
        Semester,
        on_delete=models.CASCADE,
        related_name="subjects",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["semester", "title"],
                name="uq_subject_sem_title",
            ),
            models.UniqueConstraint(
                fields=["semester", "position"],
                name="uq_subject_sem_pos",
            ),
        ]

    def __str__(self):
        return f"{self.semester} -> {self.title}"

    @property
    def course(self):
        return self.semester.course

    def clean(self):
        if self.semester and self.semester.course.course_type != Course.CourseType.FULL:
            raise ValidationError({
                "semester": "Предметы можно создавать только внутри полноценного курса."
            })


class Topic(BaseModel):
    """
    Для полноценного курса topic привязывается к Subject.
    Для неполного курса topic привязывается напрямую к Course.
    """

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="root_topics",
        null=True,
        blank=True,
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="topics",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(course__isnull=False, subject__isnull=True) |
                    Q(course__isnull=True, subject__isnull=False)
                ),
                name="topic_one_parent",
            ),
            models.UniqueConstraint(
                fields=["course", "title"],
                condition=Q(course__isnull=False),
                name="uq_topic_course_title",
            ),
            models.UniqueConstraint(
                fields=["subject", "title"],
                condition=Q(subject__isnull=False),
                name="uq_topic_subject_title",
            ),
            models.UniqueConstraint(
                fields=["course", "position"],
                condition=Q(course__isnull=False),
                name="uq_topic_course_pos",
            ),
            models.UniqueConstraint(
                fields=["subject", "position"],
                condition=Q(subject__isnull=False),
                name="uq_topic_subject_pos",
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def course_owner(self):
        if self.course_id:
            return self.course
        if self.subject_id:
            return self.subject.semester.course
        return None

    def clean(self):
        if bool(self.course_id) == bool(self.subject_id):
            raise ValidationError("Тема должна принадлежать либо курсу, либо предмету.")

        if self.course_id and self.course.course_type != Course.CourseType.SIMPLE:
            raise ValidationError({
                "course": "Тему напрямую к курсу можно привязать только у неполного курса."
            })

        if self.subject_id and self.subject.semester.course.course_type != Course.CourseType.FULL:
            raise ValidationError({
                "subject": "Тему к предмету можно привязать только у полноценного курса."
            })


# =========================================================
# 2. БАЗОВЫЙ МАТЕРИАЛ
# =========================================================

class Material(BaseModel):
    class MaterialType(models.TextChoices):
        LECTURE = "lecture", "Лекция"
        PRESENTATION = "presentation", "Презентация"
        DOCUMENT = "document", "Документ"
        TEST = "test", "Тест"
        OTHER = "other", "Другое"

    # У неполного курса материал можно вешать прямо на Course
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="materials",
        null=True,
        blank=True,
    )

    # У полноценного курса материал можно вешать на Subject
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="materials",
        null=True,
        blank=True,
    )

    # У обоих типов курса материал можно вешать на Topic
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="materials",
        null=True,
        blank=True,
    )

    title = models.CharField(max_length=255)
    material_type = models.CharField(max_length=20, choices=MaterialType.choices)
    description = models.TextField(blank=True)
    position = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    free_preview = models.BooleanField(default=False)

    class Meta:
        ordering = ("position", "id")
        indexes = [
            models.Index(fields=["material_type", "is_published"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    Q(course__isnull=False, subject__isnull=True, topic__isnull=True) |
                    Q(course__isnull=True, subject__isnull=False, topic__isnull=True) |
                    Q(course__isnull=True, subject__isnull=True, topic__isnull=False)
                ),
                name="material_one_parent",
            ),

            models.UniqueConstraint(
                fields=["course", "title"],
                condition=Q(course__isnull=False),
                name="uq_mat_course_title",
            ),
            models.UniqueConstraint(
                fields=["subject", "title"],
                condition=Q(subject__isnull=False),
                name="uq_mat_subject_title",
            ),
            models.UniqueConstraint(
                fields=["topic", "title"],
                condition=Q(topic__isnull=False),
                name="uq_mat_topic_title",
            ),

            models.UniqueConstraint(
                fields=["course", "position"],
                condition=Q(course__isnull=False),
                name="uq_mat_course_pos",
            ),
            models.UniqueConstraint(
                fields=["subject", "position"],
                condition=Q(subject__isnull=False),
                name="uq_mat_subject_pos",
            ),
            models.UniqueConstraint(
                fields=["topic", "position"],
                condition=Q(topic__isnull=False),
                name="uq_mat_topic_pos",
            ),
        ]

    def __str__(self):
        return f"{self.get_material_type_display()}: {self.title}"

    @property
    def course_owner(self):
        if self.course_id:
            return self.course
        if self.subject_id:
            return self.subject.semester.course
        if self.topic_id:
            return self.topic.course_owner
        return None

    def clean(self):
        parents_count = sum([
            bool(self.course_id),
            bool(self.subject_id),
            bool(self.topic_id),
        ])
        if parents_count != 1:
            raise ValidationError("Материал должен принадлежать только одному родителю: Course, Subject или Topic.")

        if self.course_id and self.course.course_type != Course.CourseType.SIMPLE:
            raise ValidationError({
                "course": "Материалы напрямую к курсу можно прикреплять только у неполного курса."
            })

        if self.subject_id and self.subject.semester.course.course_type != Course.CourseType.FULL:
            raise ValidationError({
                "subject": "Материалы к предмету можно прикреплять только у полноценного курса."
            })


# =========================================================
# 3. ДЕТАЛИ ПО ТИПАМ МАТЕРИАЛА
# =========================================================

class LectureMaterial(BaseModel):
    material = models.OneToOneField(
        Material,
        on_delete=models.CASCADE,
        related_name="lecture_data",
    )
    content = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"LectureData -> {self.material.title}"

    def clean(self):
        if self.material and self.material.material_type != Material.MaterialType.LECTURE:
            raise ValidationError({
                "material": "LectureMaterial можно создавать только для материала типа Лекция."
            })


class PresentationMaterial(BaseModel):
    material = models.OneToOneField(
        Material,
        on_delete=models.CASCADE,
        related_name="presentation_data",
    )
    speaker_notes = models.TextField(blank=True)
    slides_count = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"PresentationData -> {self.material.title}"

    def clean(self):
        if self.material and self.material.material_type != Material.MaterialType.PRESENTATION:
            raise ValidationError({
                "material": "PresentationMaterial можно создавать только для материала типа Презентация."
            })


class DocumentMaterial(BaseModel):
    class DocumentFormat(models.TextChoices):
        PDF = "pdf", "PDF"
        DOC = "doc", "DOC"
        DOCX = "docx", "DOCX"
        XLS = "xls", "XLS"
        XLSX = "xlsx", "XLSX"
        TXT = "txt", "TXT"
        OTHER = "other", "Другое"

    material = models.OneToOneField(
        Material,
        on_delete=models.CASCADE,
        related_name="document_data",
    )
    document_format = models.CharField(
        max_length=10,
        choices=DocumentFormat.choices,
        default=DocumentFormat.OTHER,
    )
    extracted_text = models.TextField(blank=True)

    def __str__(self):
        return f"DocumentData -> {self.material.title}"

    def clean(self):
        if self.material and self.material.material_type != Material.MaterialType.DOCUMENT:
            raise ValidationError({
                "material": "DocumentMaterial можно создавать только для материала типа Документ."
            })


class TestMaterial(BaseModel):
    material = models.OneToOneField(
        Material,
        on_delete=models.CASCADE,
        related_name="test_data",
    )
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    attempts_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="NULL = без ограничения",
    )
    passing_percentage = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    shuffle_questions = models.BooleanField(default=False)
    show_correct_answers_after_submit = models.BooleanField(default=False)

    def __str__(self):
        return f"TestData -> {self.material.title}"

    def clean(self):
        if self.material and self.material.material_type != Material.MaterialType.TEST:
            raise ValidationError({
                "material": "TestMaterial можно создавать только для материала типа Тест."
            })


# =========================================================
# 4. ПАПКИ И ФАЙЛЫ ВНУТРИ МАТЕРИАЛА
# =========================================================

class MaterialFolder(BaseModel):
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name="folders",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["material", "title"],
                condition=Q(parent__isnull=True),
                name="uq_root_folder_title",
            ),
            models.UniqueConstraint(
                fields=["parent", "title"],
                condition=Q(parent__isnull=False),
                name="uq_child_folder_title",
            ),
            models.UniqueConstraint(
                fields=["material", "position"],
                condition=Q(parent__isnull=True),
                name="uq_root_folder_pos",
            ),
            models.UniqueConstraint(
                fields=["parent", "position"],
                condition=Q(parent__isnull=False),
                name="uq_child_folder_pos",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError({"parent": "Папка не может быть родителем самой себе."})

            if self.parent.material_id != self.material_id:
                raise ValidationError({
                    "parent": "Родительская папка должна принадлежать тому же материалу."
                })


class MaterialFile(BaseModel):
    class FileRole(models.TextChoices):
        MAIN = "main", "Основной файл"
        ATTACHMENT = "attachment", "Вложение"
        IMAGE = "image", "Изображение"
        OTHER = "other", "Другое"

    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name="files",
    )
    folder = models.ForeignKey(
        MaterialFolder,
        on_delete=models.CASCADE,
        related_name="files",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to=material_file_upload_to)
    file_role = models.CharField(
        max_length=20,
        choices=FileRole.choices,
        default=FileRole.ATTACHMENT,
    )
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["material", "position"],
                condition=Q(folder__isnull=True),
                name="uq_root_file_pos",
            ),
            models.UniqueConstraint(
                fields=["folder", "position"],
                condition=Q(folder__isnull=False),
                name="uq_child_file_pos",
            ),
        ]

    def __str__(self):
        return self.title or os.path.basename(self.file.name)

    def save(self, *args, **kwargs):
        if not self.title and self.file:
            self.title = os.path.basename(self.file.name)
        return super().save(*args, **kwargs)

    def clean(self):
        if self.folder_id and self.folder.material_id != self.material_id:
            raise ValidationError({
                "folder": "Файл и папка должны принадлежать одному и тому же материалу."
            })


# =========================================================
# 5. ТЕСТЫ: ВОПРОСЫ И ПРАВИЛЬНЫЕ ОТВЕТЫ
# =========================================================

class TestQuestion(BaseModel):
    class QuestionType(models.TextChoices):
        SINGLE = "single", "Один вариант"
        MULTIPLE = "multiple", "Несколько вариантов"
        TEXT = "text", "Текстовый ответ"

    test = models.ForeignKey(
        TestMaterial,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE,
    )
    explanation = models.TextField(blank=True)
    points = models.PositiveIntegerField(default=1)
    position = models.PositiveIntegerField(default=0)

    # Для текстовых вопросов можно хранить сразу список допустимых ответов
    correct_text_answers = models.JSONField(default=list, blank=True)
    case_sensitive = models.BooleanField(default=False)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["test", "position"],
                name="uq_test_question_pos",
            ),
        ]

    def __str__(self):
        return f"Q{self.position}: {self.text[:50]}"

    def clean(self):
        if self.question_type == self.QuestionType.TEXT and not self.correct_text_answers:
            raise ValidationError({
                "correct_text_answers": "Для текстового вопроса нужно указать хотя бы один правильный ответ."
            })

        if self.question_type != self.QuestionType.TEXT and self.correct_text_answers:
            raise ValidationError({
                "correct_text_answers": "correct_text_answers используется только для текстовых вопросов."
            })


class TestAnswerOption(BaseModel):
    question = models.ForeignKey(
        TestQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )
    text = models.CharField(max_length=1000)
    is_correct = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["question", "position"],
                name="uq_question_option_pos",
            ),
        ]

    def __str__(self):
        return self.text

    def clean(self):
        if self.question and self.question.question_type == TestQuestion.QuestionType.TEXT:
            raise ValidationError({
                "question": "У текстового вопроса не должно быть вариантов ответа."
            })  