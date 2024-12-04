from django.db import models
from django.contrib.auth.models import User

class Recipe(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recipes')
    title = models.CharField(max_length=200)
    time = models.IntegerField()  # Cooking time in minutes
    cuisine = models.CharField(max_length=100)
    servings = models.IntegerField()
    ingredients = models.JSONField()  # Store ingredients as JSON
    instructions = models.JSONField()  # Store instructions as JSON
    image_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.title
