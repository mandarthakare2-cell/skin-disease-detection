import os
import json
import numpy as np
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Count
from datetime import timedelta
from django.utils import timezone

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages

from .models import PredictionHistory, LoginTracker


# Global model variable
model = None

DISEASE_DESCRIPTIONS = {
    "Acne": "Acne is a common skin condition caused by clogged pores, inflammation, and excess oil production.",
    "Dermatitis": "Dermatitis is skin irritation or inflammation that can be triggered by allergens, irritants, or eczema-related factors.",
    "Eczema": "Eczema is a chronic inflammatory skin condition causing dry, itchy, and red patches.",
    "Melanoma": "Melanoma is a serious form of skin cancer that often appears as an unusual or changing mole.",
    "Psoriasis": "Psoriasis is an autoimmune condition that leads to thick, scaly, red patches on the skin.",
    "Ringworm": "Ringworm is a fungal infection that causes circular, itchy, raised patches on the skin.",
    "Vitiligo": "Vitiligo causes loss of skin pigment, creating pale patches that may expand over time.",
}


def get_client_ip(request):
    """
    Get client's IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_model():
    """
    Load the AI model only when an image is analyzed.
    """

    global model

    if model is not None:
        return model

    try:
        import tensorflow as tf

        model_candidates = [
            os.path.join(settings.BASE_DIR, "skin", "model", "skin_disease_model.h5"),
            os.path.join(settings.BASE_DIR, "skin", "model", "skin_disease_model.keras"),
            os.path.join(settings.BASE_DIR, "skin_disease_model.h5"),
            os.path.join(settings.BASE_DIR, "skin_disease_model.keras"),
        ]

        model_path = next((path for path in model_candidates if os.path.exists(path)), None)

        if model_path is None:
            raise FileNotFoundError(
                "Model file not found. Expected a .h5 or .keras model in the project root or skin/model folder."
            )

        print(f"Loading AI model from {model_path}...")

        model = tf.keras.models.load_model(
            model_path,
            compile=False
        )

        print("AI model loaded successfully!")

        return model

    except Exception as e:
        print("MODEL ERROR:", str(e))
        raise e


def get_class_names():
    class_file = os.path.join(settings.BASE_DIR, "class_names.txt")

    if os.path.exists(class_file):
        with open(class_file, "r", encoding="utf-8") as file:
            class_names = [line.strip() for line in file.readlines() if line.strip()]
        return class_names

    return [f"Class {i}" for i in range(7)]


# =========================
# HOME PAGE
# =========================

@login_required
def home(request):

    context = {
        "prediction": None,
        "confidence": None,
        "error": None,
        "message": None,
        "description": None,
        "image_url": None,
        "class_scores": [],
        "low_confidence_warning": False,
        "image_not_found": False,
        "warning_type": None,
        "warning_message": None,
        "pie_chart_data": None,
    }

    if request.method == "POST":

        if "image" not in request.FILES:

            context["error"] = (
                "Please select an image before clicking Analyze Image."
            )
            context["message"] = context["error"]

            return render(
                request,
                "skin/home.html",
                context
            )

        try:

            uploaded_image = request.FILES["image"]

            os.makedirs(
                settings.MEDIA_ROOT,
                exist_ok=True
            )

            image_path = os.path.join(
                settings.MEDIA_ROOT,
                uploaded_image.name
            )

            with open(
                image_path,
                "wb+"
            ) as destination:

                for chunk in uploaded_image.chunks():
                    destination.write(chunk)

            context["image_url"] = settings.MEDIA_URL + uploaded_image.name

            ai_model = get_model()

            image = Image.open(image_path).convert("RGB")
            image = image.resize((224, 224))
            image_array = np.array(image).astype("float32")
            image_array = np.expand_dims(image_array, axis=0)

            prediction_result = ai_model.predict(image_array, verbose=0)
            predicted_index = int(np.argmax(prediction_result[0]))
            confidence = float(np.max(prediction_result[0]) * 100)

            class_names = get_class_names()

            if predicted_index < len(class_names):
                predicted_class = class_names[predicted_index]
            else:
                predicted_class = f"Class {predicted_index}"

            class_scores = []
            for idx, score in enumerate(prediction_result[0]):
                label = class_names[idx] if idx < len(class_names) else f"Class {idx}"
                class_scores.append({
                    "label": label,
                    "value": round(float(score * 100), 2),
                    "is_predicted": idx == predicted_index,
                })

            ranked_scores = sorted(
                class_scores,
                key=lambda item: item["value"],
                reverse=True
            )

            for rank, item in enumerate(ranked_scores, start=1):
                item["rank"] = rank

            context["prediction"] = predicted_class
            context["confidence"] = round(confidence, 2)
            context["class_scores"] = ranked_scores
            
            # Create pie chart data
            pie_labels = [item["label"] for item in ranked_scores]
            pie_values = [item["value"] for item in ranked_scores]
            pie_colors = ["#3b82f6", "#14b8a6", "#0f766e", "#ec4899", "#f59e0b", "#10b981", "#8b5cf6"]
            
            context["pie_chart_data"] = json.dumps({
                "labels": pie_labels,
                "values": pie_values,
                "colors": pie_colors[:len(pie_labels)]
            })
            
            # Add warning for image not in dataset or low confidence
            if confidence < 25:
                context["image_not_found"] = True
                context["warning_type"] = "error"
                context["warning_message"] = "❌ Image Not Found in Dataset - The uploaded image does not match any disease in our training database. Please try another image."
                context["low_confidence_warning"] = True
            elif confidence < 40:
                context["low_confidence_warning"] = True
                context["warning_type"] = "warning"
                context["warning_message"] = f"⚠️ Low Confidence Detected ({confidence}%) - The disease prediction has low confidence. Consider consulting with a dermatologist or uploading a clearer image."
                context["image_not_found"] = False
            else:
                context["low_confidence_warning"] = False
                context["image_not_found"] = False
            
            context["description"] = DISEASE_DESCRIPTIONS.get(
                predicted_class,
                "This result may require medical review from a dermatologist."
            )

            if request.user.is_authenticated:
                with open(image_path, "rb") as image_file:
                    image_content = image_file.read()
                PredictionHistory.objects.create(
                    user=request.user,
                    image=SimpleUploadedFile(
                        uploaded_image.name,
                        image_content,
                        content_type=uploaded_image.content_type or "image/jpeg"
                    ),
                    prediction=predicted_class,
                    confidence=context["confidence"],
                )

        except FileNotFoundError as e:

            context["error"] = (
                f"Model file error: {str(e)}"
            )
            context["message"] = context["error"]

        except Exception as e:

            context["error"] = (
                f"Error analyzing image: {str(e)}"
            )
            context["message"] = context["error"]

    return render(
        request,
        "skin/home.html",
        context
    )


# =========================
# REGISTER USER
# =========================

def register_view(request):

    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if not username or not password or not email:
            messages.error(request, "Please fill all required fields.")
            return redirect("register")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("register")

        User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        messages.success(request, "Registration successful. Please login.")
        return redirect("login")

    return render(request, "skin/register.html")


# =========================
# LOGIN USER
# =========================

def login_view(request):

    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            
            # Track login
            ip_address = get_client_ip(request)
            LoginTracker.objects.create(
                user=user,
                ip_address=ip_address
            )
            
            messages.success(request, "Login successful.")
            return redirect("home")

        messages.error(request, "Invalid username or password.")
        return redirect("login")

    return render(request, "skin/login.html")


# =========================
# LOGOUT USER
# =========================

def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out. Please login again.")
    return redirect("login")


# =========================
# HISTORY PAGE
# =========================

@login_required
def history_view(request):
    history = PredictionHistory.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "skin/history.html", {"history": history})


# =========================
# LOGIN ANALYTICS PAGE
# =========================

def analytics_view(request):
    """
    Display login statistics and user activity
    """
    # Get all login records
    all_logins = LoginTracker.objects.select_related('user').order_by('-login_time')
    
    # Get unique users who logged in
    unique_users = LoginTracker.objects.values('user').distinct().count()
    
    # Get total login count
    total_logins = LoginTracker.objects.count()
    
    # Get logins in the last 7 days
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_logins = LoginTracker.objects.filter(login_time__gte=seven_days_ago).count()
    
    # Get logins by user (most active users)
    login_by_user = LoginTracker.objects.values('user__username').annotate(
        login_count=Count('id')
    ).order_by('-login_count')[:10]
    
    # Get logins by date (last 7 days)
    logins_by_date = LoginTracker.objects.filter(
        login_time__gte=seven_days_ago
    ).extra(
        select={'login_date': 'DATE(login_time)'}
    ).values('login_date').annotate(
        count=Count('id')
    ).order_by('login_date')
    
    context = {
        'all_logins': all_logins[:50],  # Show last 50 logins
        'unique_users': unique_users,
        'total_logins': total_logins,
        'recent_logins': recent_logins,
        'login_by_user': login_by_user,
        'logins_by_date': list(logins_by_date),
    }
    
    return render(request, 'skin/analytics.html', context)