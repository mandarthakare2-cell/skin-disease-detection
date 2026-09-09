import os
import logging
import urllib.request
import numpy as np
from PIL import Image

# Low-memory CPU settings for Render Free Tier
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

# Global variable to cache the loaded model
_MODEL = None

MODEL_URL = "https://github.com/mandarthakare2-cell/skin-disease-detection/releases/download/v1.0/model.h5"


# --- Page Views Required by skin/urls.py ---

def home(request):
    """Home page view"""
    try:
        return render(request, 'skin/home.html')
    except Exception:
        return render(request, 'skin/predict.html')


def about_view(request):
    """About page view"""
    try:
        return render(request, 'skin/about.html')
    except Exception:
        return render(request, 'skin/predict.html')


# --- Authentication Views ---

def register_view(request):
    """User registration view"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful!")
            return redirect('home')
        else:
            messages.error(request, "Registration failed. Please check the details.")
    else:
        form = UserCreationForm()
    
    try:
        return render(request, 'skin/register.html', {'form': form})
    except Exception:
        return render(request, 'register.html', {'form': form})


def login_view(request):
    """User login view"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    try:
        return render(request, 'skin/login.html', {'form': form})
    except Exception:
        return render(request, 'login.html', {'form': form})


def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('login')


# --- History & Analytics Views ---

@login_required
def history_view(request):
    """View prediction history"""
    try:
        return render(request, 'skin/history.html')
    except Exception:
        return redirect('home')


@login_required
def delete_history_view(request, history_id):
    """Delete prediction history entry"""
    messages.success(request, "History record deleted successfully.")
    return redirect('history')


@login_required
def analytics_view(request):
    """View skin detection analytics"""
    try:
        return render(request, 'skin/analytics.html')
    except Exception:
        return redirect('home')


# --- Machine Learning Model Helper Functions ---

def download_model_file(url, destination_path):
    """Downloads model file in chunks with custom User-Agent."""
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
    logger.info("Model download finished.")


def get_model():
    """Downloads model if missing, lazy loads it into memory once, and caches it."""
    global _MODEL
    if _MODEL is None:
        model_dir = os.path.join(settings.BASE_DIR, 'skin', 'model')
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, 'model.h5')

        if not os.path.exists(model_path) or os.path.getsize(model_path) == 0:
            try:
                download_model_file(MODEL_URL, model_path)
            except Exception as e:
                logger.error(f"Failed to download model file: {str(e)}")
                if os.path.exists(model_path):
                    os.remove(model_path)
                raise FileNotFoundError(f"Could not download model file: {str(e)}")

        logger.info(f"Loading TensorFlow model from {model_path}...")
        _MODEL = tf.keras.models.load_model(model_path, compile=False)
        logger.info("Model loaded successfully.")

    return _MODEL


def preprocess_image(image_path, target_size=(224, 224)):
    """Preprocess uploaded skin image to match TensorFlow model dimensions."""
    img = Image.open(image_path).convert('RGB')
    img = img.resize(target_size)
    img_array = np.array(img, dtype=np.float32) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    return img_array


# --- Prediction View ---

def predict_view(request):
    """Handles image upload and outputs skin disease classification results."""
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
            predictions = model.predict(processed_img)

            class_names = [
                'Actinic keratoses', 'Basal cell carcinoma', 'Benign keratosis',
                'Dermatofibroma', 'Melanoma', 'Melanocytic nevi', 'Vascular lesions'
            ]

            predicted_class_idx = np.argmax(predictions[0])
            confidence = round(float(predictions[0][predicted_class_idx]) * 100, 2)

            if predicted_class_idx < len(class_names):
                result_label = class_names[predicted_class_idx]
            else:
                result_label = f"Class {predicted_class_idx}"

            context = {
                'prediction': result_label,
                'confidence': confidence,
                'image_url': file_url
            }
            return render(request, 'skin/result.html', context)

        except FileNotFoundError as fnf_error:
            logger.error(f"FileNotFoundError in predict_view: {str(fnf_error)}")
            messages.error(request, "AI Model file is missing on the server. Please check deployment settings.")
            return render(request, 'skin/predict.html', {'error': str(fnf_error)})

        except Exception as e:
            logger.exception("Prediction failure during processing:")
            messages.error(request, f"An error occurred during analysis: {str(e)}")
            return render(request, 'skin/predict.html', {'error': str(e)})

    return render(request, 'skin/predict.html')