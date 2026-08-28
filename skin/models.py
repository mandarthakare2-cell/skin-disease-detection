from django.db import models
from django.contrib.auth.models import User


class PredictionHistory(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    image = models.ImageField(
        upload_to="history_images/"
    )

    prediction = models.CharField(
        max_length=100
    )

    confidence = models.FloatField(
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.prediction}"