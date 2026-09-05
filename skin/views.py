import os
import logging
import numpy as np
from PIL import Image

# 1. Optimize TensorFlow settings for low memory before loading
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

# Force TensorFlow to run on CPU only to save memory
tf.config.set_visible_devices([], 'GPU')

logger = logging.getLogger('django')

# Global variable to cache the loaded model
_MODEL = None

def get_model():
    """Lazy loads the model once and reuses it to prevent memory leaks."""
    global _MODEL
    if _MODEL is None:
        # Construct absolute path to the model file inside skin/model/
        model_dir = os.path.join(settings.BASE_DIR, 'skin', 'model')
        model_path = os.path.join(model_dir, 'model.h5') # Change to .keras if using keras format

        if not os.path.exists(model_path):
            # Fallback search inside project root if path differs
            model_path = os.path.join(settings.BASE_DIR, 'model.h5')

        if not os.path.exists(model_path):
            logger.error(f"Model file missing at: {model_path}")
            raise FileNotFoundError(f"Model file not found at {model_path}")

        logger.info(f"Loading TensorFlow model from {model_path}...")
        _MODEL = tf.keras.models.load_model(model_path, compile=False)
        logger.info("Model loaded successfully.")
    
    return _MODEL


def preprocess_image(image_path, target_size=(224, 224)):
    """Preprocess the skin image to match TensorFlow model inputs."""
    img = Image.open(image_path).convert('RGB')
    img = img.resize(target_size)
    img_array = np.array(img, dtype=np.float32) / 255.0
    img_array = np.expand_dims(img_array, axis=0)
    return img_array


@login_required
def predict_view(request):
    """View to handle skin image upload and AI prediction."""
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']
            
            # Ensure media storage directory exists
            media_root = getattr(settings, 'MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'media'))
            os.makedirs(media_root, exist_ok=True)

            # Save uploaded image
            fs = FileSystemStorage(location=media_root)
            filename = fs.save(image_file.name, image_file)
            uploaded_file_path = fs.path(filename)
            file_url = fs.url(filename)

            # Load model and run prediction
            model = get_model()
            processed_img = preprocess_image(uploaded_file_path)
            predictions = model.predict(processed_img)

            # Map predictions to class labels
            class_names = ['Actinic keratoses', 'Basal cell carcinoma', 'Benign keratosis', 
                           'Dermatofibroma', 'Melanoma', 'Melanocytic nevi', 'Vascular lesions']
            
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
            messages.error(request, "AI Model file is missing on the server. Please verify deployment.")
            return render(request, 'skin/predict.html', {'error': str(fnf_error)})

        except Exception as e:
            logger.exception("Prediction failure during request processing:")
            messages.error(request, f"An error occurred during analysis: {str(e)}")
            return render(request, 'skin/predict.html', {'error': str(e)})

    return render(request, 'skin/predict.html')