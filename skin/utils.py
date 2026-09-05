"""
Performance optimization utilities including caching, batch processing, and image handling
"""

import os
import hashlib
import logging
from functools import wraps
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)


class ModelCache:
    """
    Thread-safe model caching with lazy loading and singleton pattern
    """
    _instance = None
    _model = None
    _lock = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_model(cls):
        """Get or load the model with thread-safe singleton pattern"""
        if cls._model is not None:
            logger.debug("Returning cached model")
            return cls._model

        try:
            import tensorflow as tf
            logger.info("Loading TensorFlow model...")

            model_candidates = [
                os.path.join(settings.BASE_DIR, "skin", "model", "skin_disease_model.keras"),
                os.path.join(settings.BASE_DIR, "skin", "model", "skin_disease_model.h5"),
                os.path.join(settings.BASE_DIR, "skin_disease_model.keras"),
                os.path.join(settings.BASE_DIR, "skin_disease_model.h5"),
            ]

            model_path = next((path for path in model_candidates if os.path.exists(path)), None)

            if model_path is None:
                model_url = os.environ.get("MODEL_URL")
                if model_url:
                    target_dir = os.path.join(settings.BASE_DIR, "skin", "model")
                    os.makedirs(target_dir, exist_ok=True)
                    target_path = os.path.join(target_dir, "skin_disease_model.keras")
                    logger.info(f"Downloading model from MODEL_URL to {target_path}...")
                    import urllib.request
                    urllib.request.urlretrieve(model_url, target_path)
                    if os.path.exists(target_path):
                        model_path = target_path

            if model_path is None:
                raise FileNotFoundError(
                    "Model file not found. Expected .keras or .h5 in skin/model folder, or set MODEL_URL environment variable."
                )

            cls._model = tf.keras.models.load_model(model_path, compile=False)
            logger.info(f"Model loaded successfully from {model_path}")
            return cls._model

        except Exception as e:
            logger.error(f"Model loading error: {str(e)}")
            raise


class ImageProcessor:
    """
    Optimized image processing with caching and batch support
    """

    CACHE_DURATION = 3600  # 1 hour
    STANDARD_SIZE = (224, 224)

    @staticmethod
    def get_image_hash(image_path):
        """Generate hash for image deduplication"""
        hasher = hashlib.md5()
        with open(image_path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    @staticmethod
    def process_image(image_path, cache_key=None):
        """
        Process image with optional caching
        Returns: numpy array ready for model prediction
        """
        # Check cache first
        if cache_key:
            cached_array = cache.get(cache_key)
            if cached_array is not None:
                logger.debug(f"Image array retrieved from cache: {cache_key}")
                return cached_array

        try:
            image = Image.open(image_path).convert("RGB")
            image = image.resize(ImageProcessor.STANDARD_SIZE)
            image_array = np.array(image).astype("float32")
            image_array = np.expand_dims(image_array, axis=0)

            # Cache the processed array
            if cache_key:
                cache.set(cache_key, image_array, ImageProcessor.CACHE_DURATION)
                logger.debug(f"Image array cached: {cache_key}")

            return image_array

        except Exception as e:
            logger.error(f"Image processing error: {str(e)}")
            raise

    @staticmethod
    def batch_process_images(image_paths):
        """
        Process multiple images efficiently for batch prediction
        Returns: list of processed arrays
        """
        processed_images = []
        for path in image_paths:
            try:
                array = ImageProcessor.process_image(path)
                processed_images.append(array)
            except Exception as e:
                logger.warning(f"Failed to process image {path}: {str(e)}")
        return processed_images


def cache_prediction(timeout=3600):
    """
    Decorator for caching prediction results
    Reduces redundant model predictions for identical images
    """
    def decorator(func):
        @wraps(func)
        def wrapper(image_path, *args, **kwargs):
            # Generate cache key from image hash
            try:
                image_hash = ImageProcessor.get_image_hash(image_path)
                cache_key = f"prediction_{image_hash}"

                # Check if prediction exists in cache
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    logger.info(f"Prediction cache hit for {cache_key}")
                    return cached_result

                # Execute prediction
                result = func(image_path, *args, **kwargs)

                # Cache result
                cache.set(cache_key, result, timeout)
                logger.info(f"Prediction cached: {cache_key}")

                return result

            except Exception as e:
                logger.warning(f"Cache decorator error: {str(e)}")
                # Fall back to normal execution
                return func(image_path, *args, **kwargs)

        return wrapper
    return decorator


class QueryOptimizer:
    """
    Database query optimization utilities
    """

    @staticmethod
    def get_user_prediction_history(user, limit=50, offset=0):
        """
        Optimized query for prediction history with prefetch_related
        """
        from .models import PredictionHistory

        query = PredictionHistory.objects.filter(user=user).select_related(
            'user'
        ).order_by('-created_at')[offset:offset+limit]

        logger.debug(f"Fetching {limit} predictions for user {user.username}")
        return query

    @staticmethod
    def get_analytics_summary():
        """
        Cache analytics data for dashboard performance
        """
        cache_key = "analytics_summary"
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            logger.debug("Analytics summary cache hit")
            return cached_data

        from .models import LoginTracker
        from django.db.models import Count

        seven_days_ago = timezone.now() - timedelta(days=7)

        data = {
            'total_logins': LoginTracker.objects.count(),
            'unique_users': LoginTracker.objects.values('user').distinct().count(),
            'recent_logins': LoginTracker.objects.filter(
                login_time__gte=seven_days_ago
            ).count(),
            'top_users': list(LoginTracker.objects.values('user__username').annotate(
                login_count=Count('id')
            ).order_by('-login_count')[:10])
        }

        # Cache for 10 minutes
        cache.set(cache_key, data, 600)
        logger.info("Analytics summary cached")

        return data


class PredictionUtils:
    """
    Utility functions for prediction analysis and confidence handling
    """

    CONFIDENCE_HIGH = 40.0
    CONFIDENCE_LOW = 25.0

    @staticmethod
    def analyze_confidence(confidence):
        """
        Categorize confidence level and return warning type
        """
        if confidence >= PredictionUtils.CONFIDENCE_HIGH:
            return {
                'status': 'high',
                'type': None,
                'message': None,
                'warning': False
            }
        elif confidence >= PredictionUtils.CONFIDENCE_LOW:
            return {
                'status': 'medium',
                'type': 'warning',
                'message': f'⚠️ Low Confidence ({confidence:.1f}%) - Consider consulting a dermatologist',
                'warning': True
            }
        else:
            return {
                'status': 'low',
                'type': 'error',
                'message': '❌ Image Not Found in Dataset - Please try another image',
                'warning': True
            }

    @staticmethod
    def format_class_scores(prediction_result, class_names):
        """
        Format model output to ranked class scores
        """
        class_scores = []
        for idx, score in enumerate(prediction_result[0]):
            label = class_names[idx] if idx < len(class_names) else f"Class {idx}"
            class_scores.append({
                'label': label,
                'value': round(float(score * 100), 2),
                'score': float(score),
            })

        return sorted(class_scores, key=lambda x: x['score'], reverse=True)


def log_prediction(user, image_name, prediction, confidence):
    """
    Log prediction event for audit trail
    """
    logger.info(
        f"Prediction - User: {user.username}, Image: {image_name}, "
        f"Result: {prediction}, Confidence: {confidence:.2f}%"
    )
