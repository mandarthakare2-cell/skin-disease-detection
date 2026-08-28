import os
import numpy as np
from PIL import Image

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.conf import settings

import keras

from .models import PredictionHistory


# =====================================================
# CLASS NAMES
# =====================================================

CLASS_NAMES = [
    "Acne",
    "Dermatitis",
    "Eczema",
    "Melanoma",
    "Psoriasis",
    "Ringworm",
    "Vitiligo"
]


# =====================================================
# DISEASE INFORMATION
# =====================================================

DISEASE_INFO = {

    "Acne": (
        "Acne is a common skin condition that can cause "
        "pimples and inflamed areas."
    ),

    "Dermatitis": (
        "Dermatitis is skin inflammation that may cause "
        "itching, redness, dryness, or irritation."
    ),

    "Eczema": (
        "Eczema may cause dry, itchy, inflamed, or "
        "irritated skin."
    ),

    "Melanoma": (
        "Melanoma is a serious skin condition that affects "
        "skin cells."
    ),

    "Psoriasis": (
        "Psoriasis may cause thickened or scaly patches "
        "on the skin."
    ),

    "Ringworm": (
        "Ringworm is a fungal skin infection that may cause "
        "itchy or ring-shaped patches."
    ),

    "Vitiligo": (
        "Vitiligo causes areas of skin to lose pigment, "
        "resulting in lighter patches."
    )
}


# =====================================================
# MODEL PATH
# =====================================================
# Your GitHub screenshot shows:
#
# skin_disease_model.keras
#
# in the ROOT project folder.
#
# BASE_DIR points to the project root.
# =====================================================

MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "skin_disease_model.keras"
)


# =====================================================
# LOAD MODEL
# =====================================================

model = None


def get_model():

    global model

    if model is None:

        if not os.path.exists(MODEL_PATH):

            raise FileNotFoundError(
                f"Model file not found at: {MODEL_PATH}"
            )

        model = keras.models.load_model(
            MODEL_PATH,
            compile=False
        )

    return model


# =====================================================
# REGISTER
# =====================================================

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
                "Username already exists. Please choose another username."
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


# =====================================================
# LOGIN
# =====================================================

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


# =====================================================
# LOGOUT
# =====================================================

def logout_view(request):

    logout(request)

    return redirect("login")


# =====================================================
# HOME / IMAGE PREDICTION
# =====================================================

@login_required(login_url="login")
def home(request):

    context = {}

    if request.method == "POST":

        uploaded_image = request.FILES.get(
            "image"
        )

        # -----------------------------------------------
        # CHECK IMAGE
        # -----------------------------------------------

        if not uploaded_image:

            context = {
                "message": "Please select an image first."
            }

            return render(
                request,
                "skin/home.html",
                context
            )

        try:

            # -------------------------------------------
            # SAVE IMAGE
            # -------------------------------------------

            fs = FileSystemStorage()

            filename = fs.save(
                uploaded_image.name,
                uploaded_image
            )

            image_url = fs.url(
                filename
            )

            image_path = fs.path(
                filename
            )

            # -------------------------------------------
            # OPEN IMAGE
            # -------------------------------------------

            image = Image.open(
                image_path
            )

            image = image.convert(
                "RGB"
            )

            image = image.resize(
                (224, 224)
            )

            # -------------------------------------------
            # CONVERT IMAGE TO ARRAY
            # -------------------------------------------

            image_array = np.array(
                image,
                dtype=np.float32
            )

            # Normalize image
            image_array = image_array / 255.0

            # Add batch dimension
            image_array = np.expand_dims(
                image_array,
                axis=0
            )

            # -------------------------------------------
            # LOAD AI MODEL
            # -------------------------------------------

            loaded_model = get_model()

            # -------------------------------------------
            # MAKE PREDICTION
            # -------------------------------------------

            predictions = loaded_model.predict(
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

            # -------------------------------------------
            # GET DISEASE NAME
            # -------------------------------------------

            predicted_disease = CLASS_NAMES[
                predicted_index
            ]

            description = DISEASE_INFO.get(
                predicted_disease,
                "No description available."
            )

            # -------------------------------------------
            # SAVE PREDICTION HISTORY
            # -------------------------------------------

            PredictionHistory.objects.create(
                user=request.user,
                image=filename,
                prediction=predicted_disease,
                confidence=confidence
            )

            # -------------------------------------------
            # SEND RESULT TO HTML
            # -------------------------------------------

            context = {

                "image_url": image_url,

                "message": (
                    "Image analyzed successfully!"
                ),

                "prediction": predicted_disease,

                "confidence": round(
                    confidence,
                    2
                ),

                "description": description
            }


        except FileNotFoundError:

            context = {

                "message": (
                    "AI model file not found. "
                    "Please check skin_disease_model.keras."
                )
            }


        except Exception as e:

            context = {

                "message": (
                    f"Error analyzing image: {str(e)}"
                )
            }


    return render(
        request,
        "skin/home.html",
        context
    )


# =====================================================
# PREDICTION HISTORY
# =====================================================

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