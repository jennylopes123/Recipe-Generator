from django.shortcuts import render
import google.generativeai as genai
import os
import json
import requests
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .models import Recipe
from django.contrib import messages


# Configure API key and model settings
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

# Function to interact with Gemini API and fetch multiple recipes based on ingredients
def fetch_gemini_recipes(ingredients, time, servings, cuisine, num_recipes=3):
    chat_session = model.start_chat(
        history=[{
            "role": "user",
            "parts": [
                "Generate multiple unique recipes based on the following inputs:\n\n"
                f"Ingredients available: {ingredients}\n"
                f"Time available: {time} minutes\n"
                f"Number of servings: {servings}\n"
                f"Cuisine type: {cuisine}\n"
                "Important requirements:\n"
                "- Use only the provided ingredients and no additional or extra ingredients.\n"
                "- Ensure the recipe is feasible and realistic within the provided time and servings.\n\n"
                "Please provide 3 unique recipes in JSON format with the following fields:\n"
                "- title\n"
                "- cookingTime:The estimated cooking time in minutes\n"
                "- servings:The number of servings\n"
                "- cuisine:The cuisine type\n"
                "- ingredients:A list of ingredients needed with measurments\n"
                "- instructions: A step-by-step list of instructions for preparing the dish, with each step as a separate item\n"
                "- extraIngredients\n"
            ],
        }]
    )
    response = chat_session.send_message("Provide three unique recipes with additional ingredient suggestions if needed.")
    
    # Print the raw response text to see what the Gemini API returns
    if response and hasattr(response, 'text'):
        print("Gemini API Response:", response.text)  # Print response for debugging
        
        try:
            # Parse the response JSON and access the 'recipes' key
            recipes_data = json.loads(response.text)
            if 'recipes' in recipes_data:
                return recipes_data['recipes']  # Return the list of recipes
            else:
                return None
        except json.JSONDecodeError:
            return None
    return None

# Function to handle image upload and extract ingredients from the image
def handle_image_upload(image_file):
    if image_file:
        # Save the uploaded image to default storage
        file_name = default_storage.save(image_file.name, ContentFile(image_file.read()))
        file_path = default_storage.path(file_name)

        print(f"Image uploaded: {file_path}")
        
        # Call Gemini API to extract ingredients from the image
        myfile = genai.upload_file(file_path)
        response = model.generate_content([myfile, "\n\n", "Extract the ingredients from this image and return them as a list."])

        if response:
            print("Gemini API Response (Image):", response.text)

        if response and hasattr(response, 'text'):
            try:
                # Parse the response text
                ingredients_data = json.loads(response.text)
                
                # Check if the 'ingredients' key is in the response and extract the list
                if 'ingredients' in ingredients_data:
                    return ingredients_data['ingredients']  # Return the list of ingredients
                else:
                    print("Error: The response does not contain an 'ingredients' key.")
                    return None
            except json.JSONDecodeError:
                print("Error: Unable to parse the JSON response from Gemini API.")
                return None
    return None

# Function to get a different image from Pexels API for each recipe title
def get_pexels_image(query, cuisine=None):
    if not PEXELS_API_KEY:
        return None

    # Dynamically enhance the query based on the title and cuisine
    enhanced_query = f"{query} recipe dish food plated close-up {cuisine or ''} style ingredients realistic high-quality photography".strip()
    
    # Request multiple results for better filtering
    url = f'https://api.pexels.com/v1/search?query={enhanced_query}&per_page=5'
    headers = {'Authorization': PEXELS_API_KEY}

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if data.get('photos'):
            # Prioritize filtering images based on aspect ratio and relevance
            for photo in data['photos']:
                if 0.8 < photo['width'] / photo['height'] < 1.5:  # Check for visually appealing dimensions
                    return photo['src']['original']
            # Fallback to the first image if no filtering criteria match
            return data['photos'][0]['src']['original']
    return None

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

# Main view for the index page
def index(request):
    return render(request, 'index.html')

def my_recipes(request):
    recipes = Recipe.objects.filter(user=request.user)
    return render(request, 'my_recipes.html', {'recipes': recipes})
def save_recipe(request, recipe_id):
    try:
        recipe = Recipe.objects.get(id=recipe_id)
        # Check if the recipe is already saved by the user
        if not Recipe.objects.filter(user=request.user, id=recipe_id).exists():
            # Save the recipe to the current user
            recipe.pk = None  # Remove primary key to create a new instance
            recipe.user = request.user
            recipe.save()
            message = "Recipe saved successfully!"
        else:
            message = "This recipe is already saved."
    except Recipe.DoesNotExist:
        message = "Recipe not found."
    
    # Optionally, show a success message or redirect
    return redirect('generated_recipes') 

# Recipe generation view with image handling
def generate_recipe(request):
    if request.method == 'POST':
        ingredients = request.POST.get("ingredients", "").strip()
        time = request.POST.get('time')
        servings = request.POST.get('servings')
        cuisine = request.POST.get('cuisine')
        image_file = request.FILES.get('image')

        if image_file:
            ingredients = handle_image_upload(image_file)
            if not ingredients:
                return render(request, 'generate_recipe.html', {'error': 'Could not extract ingredients from the image.'})

        if ingredients:
            try:
                recipes_data = fetch_gemini_recipes(ingredients, time, servings, cuisine)

                if recipes_data:
                    recipes = []
                    for recipe_data in recipes_data:
                        image_url = get_pexels_image(recipe_data.get('title', ''))

                        # Save recipe to the database
                        recipe = Recipe.objects.create(
                            user=request.user,
                            title=recipe_data.get('title', ''),
                            time=recipe_data.get('cookingTime'),
                            cuisine=recipe_data.get('cuisine'),
                            servings=servings,
                            ingredients=recipe_data.get('ingredients', []),
                            instructions=recipe_data.get('instructions', []),
                            image_url=image_url,
                        )

                        recipes.append(recipe)

                    return render(request, 'recipe_detail.html', {'recipes': recipes})
                else:
                    return render(request, 'generate_recipe.html', {'error': 'Could not generate recipes.'})
            except Exception as e:
                return render(request, 'generate_recipe.html', {'error': f'Error: {str(e)}'})

        return render(request, 'generate_recipe.html', {'error': 'No ingredients provided.'})

    return render(request, 'generate_recipe.html')