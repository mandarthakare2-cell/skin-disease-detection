import os
import logging
import urllib.request
import numpy as np
from PIL import Image

# Low-memory CPU settings for deployment environments
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['TF_NUM_INTRAOP_THREADS'] = '1'
os.environ['TF_NUM_INTEROP_THREADS'] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import tensorflow as tf
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.conf import settings
from django.core.files.storage import FileSystemStorage

logger = logging.getLogger('django')

# Global cached model
_MODEL = None
MODEL_URL = "https://github.com/mandarthakare2-cell/skin-disease-detection/releases/download/v1.0/model.h5"

# Metadata for HAM10000 Skin Conditions
DISEASE_INFO = {
    'Actinic keratoses': {
        'description': 'A rough, scaly patch on the skin caused by years of sun exposure. It is considered a precancerous condition.',
        'symptoms': ['Rough or scaly skin patch', 'Flat to slightly raised bump', 'Itching or burning feeling', 'Pink, red, or brown discoloration'],
        'precautions': ['Avoid direct sun exposure', 'Wear broad-spectrum sunscreen (SPF 30+)', 'Wear protective clothing and broad-brimmed hats', 'Avoid tanning beds'],
        'advice': 'Consult a dermatologist for evaluation. Actinic keratosis should be treated to prevent potential progression to squamous cell carcinoma.'
    },
    'Basal cell carcinoma': {
        'description': 'A type of skin cancer that begins in the basal cells. It often appears as a slightly transparent bump on sun-exposed skin.',
        'symptoms': ['Pearly or waxy bump', 'Flat, firm, flesh-colored or brown scar-like lesion', 'Bleeding or scabbing sore that heals and returns'],
        'precautions': ['Minimize sun exposure during peak hours', 'Perform regular self-examinations', 'Use daily sun protection'],
        'advice': 'Requires prompt medical evaluation and treatment by a dermatologist or oncologist.'
    },
    'Benign keratosis': {
        'description': 'A non-cancerous skin condition that includes seborrheic keratoses. Commonly appears as waxy, raised growths as people age.',
        'symptoms': ['Waxy, stuck-on skin appearance', 'Round or oval shape', 'Color ranges from light tan to black', 'Slightly raised surface'],
        'precautions': ['Avoid scratching or picking at the lesions', 'Keep the skin moisturized', 'Protect skin from severe friction'],
        'advice': 'Benign keratoses are harmless, but seek medical evaluation if a lesion changes size, bleeds, or causes discomfort.'
    },
    'Dermatofibroma': {
        'description': 'Common non-cancerous skin growths that usually appear as small, firm bumps on the lower legs.',
        'symptoms': ['Firm, hard bump under the skin', 'Dimples inward when pinched', 'Color ranges from red-brown to pink', 'Usually painless'],
        'precautions': ['Avoid picking or attempting to remove at home', 'Protect skin from local trauma or insect bites'],
        'advice': 'Generally harmless and requires no treatment unless it becomes painful or cosmetically concerning.'
    },
    'Melanoma': {
        'description': 'The most serious type of skin cancer, developing in melanocytes. Early detection and treatment are essential.',
        'symptoms': ['Asymmetrical shape or irregular borders', 'Color variations (black, brown, red, white)', 'Diameter greater than 6mm', 'Evolving size, shape, or color'],
        'precautions': ['Strict sun protection', 'Perform monthly self-skin checks (ABCDE rule)', 'Avoid sunburns'],
        'advice': 'URGENT: Schedule an immediate medical evaluation with a dermatologist.'
    },
    'Melanocytic nevi': {
        'description': 'Common moles formed by clusters of melanocytes. Most moles are completely benign and common.',
        'symptoms': ['Uniform brown, tan, or black color', 'Distinct, smooth border', 'Flat or slightly raised round shape'],
        'precautions': ['Monitor for changes in size, shape, or color', 'Use sun protection to prevent dysplastic changes'],
        'advice': 'Harmless, but any mole that changes rapidly or bleeds should be inspected by a doctor.'
    },
    'Vascular lesions': {
        'description': 'Skin anomalies involving blood vessels, such as cherry angiomas, hemangiomas, or port-wine stains.',
        'symptoms': ['Red, purple, or blue skin discoloration', 'Raised bumps or flat red spots', 'May bleed if scratched'],
        'precautions': ['Avoid irritating or scratching the area', 'Protect fragile lesions from friction'],
        'advice': 'Usually benign. Seek medical advice if bleeding is persistent or if rapid growth occurs.'
    }
}


# --- Page Views ---

def home(request):
    """Home page view"""
    return render(request, 'skin/home.html')


def about_view(request):
    """About page view"""
    return render(request, 'skin/about.html')


def register_view(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful!")
            return redirect('home')
        messages.error(request, "Registration failed.")
    else:
        form = UserCreationForm()
    return render(request, 'skin/register.html', {'form': form})


def login_view(request):
    """User login view"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('home')
        messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'skin/login.html', {'form': form})


def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('login')


@login_required
def history_view(request):
    return render(request, 'skin/history.html')


@login_required
def delete_history_view(request, history_id):
    messages.success(request, "Record deleted.")
    return redirect('history')


@login_required
def analytics_view(request):
    return render(request, 'skin/analytics.html')


# --- Model Helper Logic ---

def download_model_file(url, destination_path):
    logger.info(f"Downloading model from {url}...")
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req) as response, open(destination_path, 'wb') as out_file:
        while True:
            chunk = response.read(16384)
            if not chunk:
                break
            out_file.write(chunk)


def get_model():
    global _MODEL
    if _MODEL is None:
        model_dir = os.path.join(settings.BASE_DIR, 'skin', 'model')
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, 'model.h5')

        if not os.path.exists(model_path) or os.path.getsize(model_path) == 0:
            try:
                download_model_file(MODEL_URL, model_path)
            except Exception as e:
                logger.error(f"Download failed: {str(e)}")
                if os.path.exists(model_path):
                    os.remove(model_path)
                raise FileNotFoundError(f"Model download failed: {str(e)}")

        _MODEL = tf.keras.models.load_model(model_path, compile=False)

    return _MODEL


def preprocess_image(image_path, target_size=(224, 224)):
    img = Image.open(image_path).convert('RGB')
    img = img.resize(target_size)
    img_array = np.array(img, dtype=np.float32) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    return img_array


# --- Prediction Route View ---

def predict_view(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']

            media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
            os.makedirs(media_root, exist_ok=True)

            fs = FileSystemStorage(location=media_root)
            filename = fs.save(image_file.name, image_file)
            uploaded_file_path = fs.path(filename)
            file_url = fs.url(filename)

            model = get_model()
            processed_img = preprocess_image(uploaded_file_path)
            predictions = model.predict(processed_img)[0]

            class_names = [
                'Actinic keratoses', 'Basal cell carcinoma', 'Benign keratosis',
                'Dermatofibroma', 'Melanoma', 'Melanocytic nevi', 'Vascular lesions'
            ]

            predicted_class_idx = int(np.argmax(predictions))
            predicted_label = class_names[predicted_class_idx]
            confidence = round(float(predictions[predicted_class_idx]) * 100, 2)

            # Build class probability ranking
            class_scores = []
            for idx, prob in enumerate(predictions):
                class_scores.append({
                    'label': class_names[idx],
                    'value': round(float(prob) * 100, 2)
                })
            class_scores = sorted(class_scores, key=lambda x: x['value'], reverse=True)

            # Retrieve disease info metadata
            info = DISEASE_INFO.get(predicted_label, {
                'description': 'No specific description available.',
                'symptoms': ['N/A'],
                'precautions': ['Consult a doctor for further evaluation.'],
                'advice': 'Consult a dermatologist.'
            })

            context = {
                'prediction': predicted_label,
                'confidence': confidence,
                'image_url': file_url,
                'description': info['description'],
                'symptoms': info['symptoms'],
                'precautions': info['precautions'],
                'medical_advice': info['advice'],
                'class_scores': class_scores
            }

            return render(request, 'skin/home.html', context)

        except Exception as e:
            logger.exception("Prediction failure:")
            return render(request, 'skin/home.html', {'error': f"Error processing image: {str(e)}"})

    return render(request, 'skin/home.html')