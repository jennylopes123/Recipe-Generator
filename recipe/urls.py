from django.urls import path, include
from django.contrib.auth import views as auth_views
from .import views
from django.urls import path 
urlpatterns = [
    path('', views.index,name='index'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='index'), name='logout'),
    path('register/', views.register, name='register'),
    path('generate/', views.generate_recipe, name='generate_recipe'),
    path('my_recipes/', views.my_recipes, name='my_recipes'),
    path('save_recipe/<int:recipe_id>/', views.save_recipe, name='save_recipe'),
   # path('recipe/<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
]