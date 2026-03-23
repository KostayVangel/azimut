from django.db import models


class AccountType(models.TextChoices):
    OWNER = "owner", "Главный пользователь"
    EMPLOYEE = "employee", "Сотрудник"
    STUDENT = "student", "Учащийся"