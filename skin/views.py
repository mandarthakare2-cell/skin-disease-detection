import os
import numpy as np
from PIL import Image
import tensorflow as tf

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from .models import PredictionHistory


# ==========================================================
# CLASS NAMES
# ==========================================================

CLASS_NAMES = [
    "Acne",
    "Dermatitis",
    "Eczema",
    "Melanoma",
    "Psoriasis",
    "Ringworm",
    "Vitiligo"
]


# ==========================================================
# DISEASE INFORMATION
# ==========================================================

DISEASE_INFO = {

    "Acne":
        "Acne is a common skin condition that can cause pimples and inflamed areas.",

    "Dermatitis":
        "Dermatitis is skin inflammation that may cause itching, redness, dryness, or irritation.",

    "Eczema":
        "Eczema may cause dry, itchy, inflamed, or irritated skin.",

    "Melanoma":
        "Melanoma is a serious skin condition that should be checked by a medical professional.",

    "Psoriasis":
        "Psoriasis may cause thickened or scaly patches on the skin.",

    "Ringworm":
        "Ringworm is a fungal skin infection that may cause itchy or ring-shaped patches.",

    "Vitiligo":
        "Vitiligo causes areas of skin to lose pigment, resulting in lighter patches."
}


# ==========================================================
# FIND MODEL FILE
# ==========================================================

def find_model_path():

    possible_paths = [

        # Model beside manage.py
        os.path.join(
            settings.BASE_DIR,
            "skin_disease_model.keras"
        ),

        # Model inside skin folder
        os.path.join(
            settings.BASE_DIR,
            "skin",
            "skin_disease_model.keras"
        ),

        # Model inside model folder
        os.path.join(
            settings.BASE_DIR,
            "skin",
            "model",
            "skin_disease_model.keras"
        ),

        # Old H5 format
        os.path.join(
            settings.BASE_DIR,
            "skin_disease_model.h5"
        ),

        os.path.join(
            settings.BASE_DIR,
            "skin",
            "model",
            "skin_disease_model.h5"
        )
    ]

    for path in possible_paths:

        if os.path.exists(path):
            return path

    return None


# ==========================================================
# LOAD AI MODEL
# ==========================================================

MODEL = None
MODEL_ERROR = None


def get_model():

    global MODEL
    global MODEL_ERROR

    if MODEL is not None:
        return MODEL

    if MODEL_ERROR is not None:
        return None

    model_path = find_model_path()

    if model_path is None:

        MODEL_ERROR = (
            "AI model file not found. "
            "Please make sure skin_disease_model.keras "
            "is uploaded to GitHub."
        )

        return None

    try:

        MODEL = tf.keras.models.load_model(
            model_path,
            compile=False
        )

        return MODEL

    except Exception as error:

        MODEL_ERROR = f"Unable to load AI model: {str(error)}"

        return None


# ==========================================================
# REGISTER
# ==========================================================

def register_view(request):

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        email = request.POST.get(
            "email",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        if not username or not email or not password:

            messages.error(
                request,
                "Please fill in all fields."
            )

        elif User.objects.filter(
            username=username
        ).exists():

            messages.error(
                request,
                "Username already exists."
            )

        else:

            User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            messages.success(
                request,
                "Registration successful. Please login."
            )

            return redirect("login")

    return render(
        request,
        "skin/register.html"
    )


# ==========================================================
# LOGIN
# ==========================================================

def login_view(request):

    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(
                request,
                user
            )

            return redirect("home")

        else:

            messages.error(
                request,
                "Invalid username or password."
            )

    return render(
        request,
        "skin/login.html"
    )


# ==========================================================
# LOGOUT
# ==========================================================

def logout_view(request):

    logout(request)

    return redirect("login")


# ==========================================================
# HOME / PREDICTION
# ==========================================================

@login_required(login_url="login")
def home(request):

    context = {}

    if request.method == "POST":

        uploaded_image = request.FILES.get(
            "image"
        )

        if not uploaded_image:

            context = {
                "message":
                    "Please select an image first."
            }

            return render(
                request,
                "skin/home.html",
                context
            )

        # --------------------------------------------------
        # LOAD MODEL
        # --------------------------------------------------

        model = get_model()

        if model is None:

            context = {
                "message": MODEL_ERROR
            }

            return render(
                request,
                "skin/home.html",
                context
            )

        try:

            # --------------------------------------------------
            # SAVE UPLOADED IMAGE
            # --------------------------------------------------

            fs = FileSystemStorage()

            filename = fs.save(
                uploaded_image.name,
                uploaded_image
            )

            image_path = fs.path(
                filename
            )

            image_url = fs.url(
                filename
            )

            # --------------------------------------------------
            # OPEN IMAGE
            # --------------------------------------------------

            image = Image.open(
                image_path
            )

            image = image.convert(
                "RGB"
            )

            image = image.resize(
                (224, 224)
            )

            # --------------------------------------------------
            # PREPROCESS IMAGE
            # --------------------------------------------------

            image_array = np.array(
                image,
                dtype=np.float32
            )

            image_array = image_array / 255.0

            image_array = np.expand_dims(
                image_array,
                axis=0
            )

            # --------------------------------------------------
            # AI PREDICTION
            # --------------------------------------------------

            predictions = model.predict(
                image_array,
                verbose=0
            )

            predicted_index = int(
                np.argmax(
                    predictions[0]
                )
            )

            confidence = float(
                np.max(
                    predictions[0]
                ) * 100
            )

            predicted_disease = CLASS_NAMES[
                predicted_index
            ]

            description = DISEASE_INFO.get(
                predicted_disease,
                "No description available."
            )

            # --------------------------------------------------
            # SAVE HISTORY
            # --------------------------------------------------

            PredictionHistory.objects.create(

                user=request.user,

                image=filename,

                prediction=predicted_disease,

                confidence=confidence

            )

            # --------------------------------------------------
            # SEND RESULT TO HTML
            # --------------------------------------------------

            context = {

                "image_url": image_url,

                "message":
                    "Image analyzed successfully!",

                "prediction":
                    predicted_disease,

                "confidence":
                    round(
                        confidence,
                        2
                    ),

                "description":
                    description
            }

        except Exception as error:

            context = {

                "message":
                    f"Error analyzing image: {str(error)}"

            }

    return render(
        request,
        "skin/home.html",
        context
    )


# ==========================================================
# PREDICTION HISTORY
# ==========================================================

@login_required(login_url="login")
def prediction_history(request):

    history = PredictionHistory.objects.filter(

        user=request.user

    ).order_by(

        "-created_at"

    )

    return render(

        request,

        "skin/history.html",

        {
            "history": history
        }

    )