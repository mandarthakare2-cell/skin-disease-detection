import json
import os
import uuid
from datetime import timedelta
from functools import lru_cache

import numpy as np
from PIL import Image
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ImageUploadForm, LoginForm, RegistrationForm
from .logging_config import get_logger
from .models import LoginTracker, PredictionHistory
from .utils import ModelCache

logger = get_logger(__name__)

DISEASE_DESCRIPTIONS = {
    "Acne": "Acne is a common skin condition caused by clogged pores, inflammation, and excess oil production.",
    "Dermatitis": "Dermatitis is skin irritation or inflammation that can be triggered by allergens, irritants, or eczema-related factors.",
    "Eczema": "Eczema is a chronic inflammatory skin condition causing dry, itchy, and red patches.",
    "Melanoma": "Melanoma is a serious form of skin cancer that often appears as an unusual or changing mole.",
    "Psoriasis": "Psoriasis is an autoimmune condition that leads to thick, scaly, red patches on the skin.",
    "Ringworm": "Ringworm is a fungal infection that causes circular, itchy, raised patches on the skin.",
    "Vitiligo": "Vitiligo causes loss of skin pigment, creating pale patches that may expand over time.",
}

DISEASE_DETAILS = {
    "Acne": {
        "symptoms": ["Blackheads or whiteheads", "Red or inflamed pimples", "Oily skin"],
        "precautions": ["Keep the skin clean and avoid touching the face", "Use non-comedogenic skincare products", "Avoid excess oil and harsh scrubs"],
        "medical_advice": "If acne is painful, widespread, or causing scarring, consult a dermatologist for evaluation.",
    },
    "Dermatitis": {
        "symptoms": ["Redness", "Itching", "Dry or cracked skin"],
        "precautions": ["Moisturize regularly", "Avoid known irritants or harsh detergents", "Use gentle, fragrance-free products"],
        "medical_advice": "Seek professional care if the rash is severe, spreads quickly, or does not improve.",
    },
    "Eczema": {
        "symptoms": ["Very dry skin", "Itching", "Patchy red inflamed areas"],
        "precautions": ["Keep skin moisturized", "Avoid triggers like hot showers and allergens", "Wear soft, breathable fabrics"],
        "medical_advice": "Consult a healthcare professional if eczema is severe, infected, or affecting sleep and daily life.",
    },
    "Melanoma": {
        "symptoms": ["New or changing mole", "Irregular border or color", "Bleeding or itching mole"],
        "precautions": ["Monitor skin changes regularly", "Protect skin from UV exposure", "Use sunscreen and check moles consistently"],
        "medical_advice": "Seek prompt medical assessment for any changing mole or concerning skin lesion.",
    },
    "Psoriasis": {
        "symptoms": ["Thick scaly patches", "Silver-white scale", "Itching or burning sensation"],
        "precautions": ["Keep skin moisturized", "Avoid skin trauma or harsh products", "Manage stress and skin dryness"],
        "medical_advice": "Consult a dermatologist if patches are widespread or painful.",
    },
    "Ringworm": {
        "symptoms": ["Circular itchy rash", "Raised edges", "Scaly skin"],
        "precautions": ["Keep affected areas clean and dry", "Avoid sharing towels or personal items", "Follow proper hygiene practices"],
        "medical_advice": "See a clinician if the rash spreads or does not respond to hygiene measures.",
    },
    "Vitiligo": {
        "symptoms": ["White patches on skin", "Loss of pigment", "Patchy skin changes"],
        "precautions": ["Protect skin from sunburn", "Use sunscreen on affected skin", "Avoid skin irritation from harsh products"],
        "medical_advice": "Dermatology evaluation is recommended to discuss the best care plan.",
    },
}


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "Unknown")


def get_model():
    return ModelCache.get_model()


@lru_cache(maxsize=1)
def get_class_names():
    class_file = os.path.join(settings.BASE_DIR, "class_names.txt")
    if os.path.exists(class_file):
        with open(class_file, "r", encoding="utf-8") as file:
            class_names = [line.strip() for line in file.readlines() if line.strip()]
        return class_names
    return [f"Class {i}" for i in range(7)]


def get_disease_detail(predicted_class):
    return {
        "description": DISEASE_DESCRIPTIONS.get(predicted_class, "This result may require medical review from a dermatologist."),
        "symptoms": DISEASE_DETAILS.get(predicted_class, {}).get("symptoms", ["Consult a dermatologist for review."]),
        "precautions": DISEASE_DETAILS.get(predicted_class, {}).get("precautions", ["Avoid unnecessary self-treatment and seek professional advice."]),
        "medical_advice": DISEASE_DETAILS.get(predicted_class, {}).get("medical_advice", "Please consult a qualified healthcare professional for medical advice."),
    }


@login_required
def home(request):
    context = {
        "prediction": None,
        "confidence": None,
        "error": None,
        "message": None,
        "description": None,
        "symptoms": [],
        "precautions": [],
        "medical_advice": None,
        "image_url": None,
        "class_scores": [],
        "low_confidence_warning": False,
        "image_not_found": False,
        "warning_type": None,
        "warning_message": None,
        "pie_chart_data": None,
        "upload_form": ImageUploadForm(),
    }

    if request.method == "POST":
        form = ImageUploadForm(request.POST, request.FILES)
        context["upload_form"] = form

        if not form.is_valid():
            context["error"] = "Please upload a valid image file in JPEG, PNG, or WebP format."
            context["message"] = context["error"]
            return render(request, "skin/home.html", context)

        try:
            uploaded_image = form.cleaned_data["image"]
            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            safe_name = f"{uuid.uuid4().hex}_{uploaded_image.name}"
            image_path = os.path.join(settings.MEDIA_ROOT, safe_name)

            with open(image_path, "wb+") as destination:
                for chunk in uploaded_image.chunks():
                    destination.write(chunk)

            context["image_url"] = f"{settings.MEDIA_URL}{safe_name}"

            ai_model = get_model()
            image = Image.open(image_path).convert("RGB")
            image = image.resize((224, 224))
            image_array = np.array(image).astype("float32")
            image_array = np.expand_dims(image_array, axis=0)

            prediction_result = ai_model.predict(image_array, verbose=0)
            predicted_index = int(np.argmax(prediction_result[0]))
            confidence = float(np.max(prediction_result[0]) * 100)
            class_names = get_class_names()
            predicted_class = class_names[predicted_index] if predicted_index < len(class_names) else f"Class {predicted_index}"

            class_scores = []
            for idx, score in enumerate(prediction_result[0]):
                label = class_names[idx] if idx < len(class_names) else f"Class {idx}"
                class_scores.append({
                    "label": label,
                    "value": round(float(score * 100), 2),
                    "is_predicted": idx == predicted_index,
                })

            ranked_scores = sorted(class_scores, key=lambda item: item["value"], reverse=True)
            for rank, item in enumerate(ranked_scores, start=1):
                item["rank"] = rank

            context["prediction"] = predicted_class
            context["confidence"] = round(confidence, 2)
            context["class_scores"] = ranked_scores

            pie_labels = [item["label"] for item in ranked_scores]
            pie_values = [item["value"] for item in ranked_scores]
            pie_colors = ["#3b82f6", "#14b8a6", "#0f766e", "#ec4899", "#f59e0b", "#10b981", "#8b5cf6"]
            context["pie_chart_data"] = json.dumps({
                "labels": pie_labels,
                "values": pie_values,
                "colors": pie_colors[: len(pie_labels)],
            })

            detail = get_disease_detail(predicted_class)
            context["description"] = detail["description"]
            context["symptoms"] = detail["symptoms"]
            context["precautions"] = detail["precautions"]
            context["medical_advice"] = detail["medical_advice"]

            if confidence < 25:
                context["image_not_found"] = True
                context["warning_type"] = "error"
                context["warning_message"] = "❌ This image does not match the disease classes in the training data. Please try another clear image."
                context["low_confidence_warning"] = True
            elif confidence < 40:
                context["low_confidence_warning"] = True
                context["warning_type"] = "warning"
                context["warning_message"] = f"⚠️ Low-confidence prediction ({confidence:.2f}%). Please review the image or consult a medical professional."
            else:
                context["low_confidence_warning"] = False
                context["image_not_found"] = False

            if request.user.is_authenticated:
                with open(image_path, "rb") as image_file:
                    image_content = image_file.read()
                PredictionHistory.objects.create(
                    user=request.user,
                    image=SimpleUploadedFile(
                        safe_name,
                        image_content,
                        content_type=uploaded_image.content_type or "image/jpeg",
                    ),
                    prediction=predicted_class,
                    confidence=context["confidence"],
                )

            context["message"] = "Analysis complete. Review your result and precautions below."
            messages.success(request, "Analysis complete.")

        except FileNotFoundError as exc:
            context["error"] = f"Model file error: {exc}"
            context["message"] = context["error"]
        except Exception as exc:
            logger.exception("Image analysis failed")
            context["error"] = f"Error analyzing image: {exc}"
            context["message"] = context["error"]

    return render(request, "skin/home.html", context)


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.create_user(
            username=form.cleaned_data["username"].strip(),
            email=form.cleaned_data["email"].strip(),
            password=form.cleaned_data["password"],
        )
        user.save()
        messages.success(request, "Registration successful. Please log in to continue.")
        return redirect("login")

    return render(request, "skin/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"].strip()
        password = form.cleaned_data["password"]
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            LoginTracker.objects.create(user=user, ip_address=get_client_ip(request))
            messages.success(request, "Login successful.")
            return redirect("home")

        messages.error(request, "Invalid username or password.")

    return render(request, "skin/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out. Please log in again.")
    return redirect("login")


@login_required
def history_view(request):
    history_queryset = PredictionHistory.objects.filter(user=request.user).order_by("-created_at")

    search_query = request.GET.get("q", "").strip()
    disease_filter = request.GET.get("disease", "").strip()
    sort_by = request.GET.get("sort", "-created_at")

    if search_query:
        history_queryset = history_queryset.filter(
            Q(prediction__icontains=search_query) |
            Q(created_at__icontains=search_query)
        )

    if disease_filter:
        history_queryset = history_queryset.filter(prediction__icontains=disease_filter)

    allowed_sort_fields = {"-created_at": "-created_at", "created_at": "created_at", "-confidence": "-confidence", "confidence": "confidence", "prediction": "prediction"}
    sort_value = allowed_sort_fields.get(sort_by, "-created_at")
    history = history_queryset.order_by(sort_value)

    if history.exists():
        empty_message = ""
    elif disease_filter:
        empty_message = f"No data found for {disease_filter} with the current filters."
    elif search_query:
        empty_message = "No data found for the current search."
    else:
        empty_message = "No prediction history yet. Upload an image and analyze it to begin tracking results."

    disease_options = get_class_names()

    context = {
        "history": history,
        "search_query": search_query,
        "disease_filter": disease_filter,
        "sort_by": sort_by,
        "disease_options": disease_options,
        "empty_message": empty_message,
    }
    return render(request, "skin/history.html", context)


@login_required
def delete_history_view(request, history_id):
    history_item = get_object_or_404(PredictionHistory, id=history_id, user=request.user)
    history_item.delete()
    messages.success(request, "Prediction record deleted successfully.")
    return redirect("history")


@login_required
def analytics_view(request):
    user_history = PredictionHistory.objects.filter(user=request.user)
    total_analyses = user_history.count()
    recent_analyses = user_history.filter(created_at__gte=timezone.now() - timedelta(days=7)).count()
    average_confidence = user_history.aggregate(avg_confidence=Avg("confidence"))["avg_confidence"] or 0

    most_predicted = user_history.values("prediction").annotate(total=Count("id")).order_by("-total", "prediction").first()

    disease_names = get_class_names()
    disease_totals = {
        item["prediction"]: item["total"]
        for item in user_history.values("prediction").annotate(total=Count("id")).order_by("-total")
    }
    disease_breakdown = [
        {"prediction": disease_name, "total": disease_totals.get(disease_name, 0)}
        for disease_name in disease_names
    ]
    recent_entries = user_history.order_by("-created_at")[:8]

    daily_data = list(
        user_history.filter(created_at__gte=timezone.now() - timedelta(days=7))
        .extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(total=Count("id"))
        .order_by("day")
    )

    all_logins = LoginTracker.objects.select_related("user").order_by("-login_time")[:10]
    total_logins = LoginTracker.objects.filter(user=request.user).count()
    recent_logins = LoginTracker.objects.filter(user=request.user, login_time__gte=timezone.now() - timedelta(days=7)).count()

    context = {
        "total_analyses": total_analyses,
        "recent_analyses": recent_analyses,
        "most_predicted": most_predicted,
        "average_confidence": round(float(average_confidence), 2) if average_confidence else 0,
        "disease_breakdown": disease_breakdown,
        "recent_entries": recent_entries,
        "daily_data": daily_data,
        "all_logins": all_logins,
        "total_logins": total_logins,
        "recent_logins": recent_logins,
    }
    return render(request, "skin/analytics.html", context)


def about_view(request):
    return render(request, "skin/about.html")