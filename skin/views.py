import os
import logging
import urllib.request
import numpy as np
from PIL import Image

# 1. Low-memory CPU settings for Render Free Tier
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['TF_NUM_INTRAOP_THREADS'] = '1'
os.environ['TF_NUM_INTEROP_THREADS'] = '1'

import tensorflow as tf
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.files.storage import FileSystemStorage

# Force CPU execution to prevent GPU memory allocation overhead
tf.config.set_visible_devices([], 'GPU')

logger = logging.getLogger('django')

# Global variable to cache the loaded model
_MODEL = None

# Update this URL to your direct download link (e.g., GitHub Release, Dropbox, or Cloud Storage)
MODEL_URL = "https://github.com/mandarthakare2-cell/skin-disease-detection/releases/download/v1.0/model.h5"


def get_model():
    """Downloads model if missing, lazy loads it into memory once, and caches it."""
    global _MODEL
    if _MODEL is None:
        model_dir = os.path.join(settings.BASE_DIR, 'skin', 'model')
        os.makedirs(model_dir, exist_ok=True)
        model_path = os.path.join(model_dir, 'model.h5')

        # Download model automatically if missing on Render container
        if not os.path.exists(model_path):
            logger.info(f"Model file missing. Downloading from {MODEL_URL}...")
            try:
                urllib.request.urlretrieve(MODEL_URL, model_path)
                logger.info("Model downloaded successfully.")
            except Exception as e:
                logger.error(f"Failed to download model file: {str(e)}")
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


@login_required
def predict_view(request):
    """Handles image upload and outputs skin disease classification results."""
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']

            # Dynamic Media Root directory handling
            media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
            os.makedirs(media_root, exist_ok=True)

            # Store uploaded image file
            fs = FileSystemStorage(location=media_root)
            filename = fs.save(image_file.name, image_file)
            uploaded_file_path = fs.path(filename)
            file_url = fs.url(filename)

            # Retrieve model and predict
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