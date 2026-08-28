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


# ==========================================
# MODEL PATH
# ==========================================

MODEL_PATH = os.path.join(
    settings.BASE_DIR,
    "skin_disease_model.keras"
)


# ==========================================
# LOAD MODEL ONLY WHEN NEEDED
# ==========================================

model = None


def get_model():
    global model

    # Model is already loaded
    if model is not None:
        return model

    # Check whether model file exists
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"AI model file not found: {MODEL_PATH}"
        )

    try:
        # Load the trained model
        model = tf.keras.models.load_model(
            MODEL_PATH,
            compile=False
        )

        return model

    except Exception as error:

        raise Exception(
            f"Unable to load AI model: {str(error)}"
        )


# ==========================================
# CLASS NAMES
# IMPORTANT:
# These must be in the SAME ORDER used
# while training your model.
# ==========================================

CLASS_NAMES = [
    "Acne",
    "Dermatitis",
    "Eczema",
    "Melanoma",
    "Psoriasis",
    "Ringworm",
    "Vitiligo"
]


# ==========================================
# DISEASE INFORMATION
# ==========================================

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
        "Eczema may cause dry, itchy, inflamed, "
        "or irritated skin."
    ),

    "Melanoma": (
        "Melanoma is a serious skin condition. "
        "AI predictions are not a medical diagnosis."
    ),

    "Psoriasis": (
        "Psoriasis may cause thickened or scaly "
        "patches on the skin."
    ),

    "Ringworm": (
        "Ringworm is a fungal skin infection that may "
        "cause itchy or ring-shaped patches."
    ),

    "Vitiligo": (
        "Vitiligo causes areas of skin to lose pigment, "
        "resulting in lighter patches."
    )
}


# ==========================================
# REGISTER USER
# ==========================================

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

        # Validate fields
        if not username or not email or not password:

            messages.error(
                request,
                "Please fill in all fields."
            )

        # Check username
        elif User.objects.filter(
            username=username
        ).exists():

            messages.error(
                request,
                "Username already exists. "
                "Please choose another username."
            )

        else:

            # Create user
            User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            messages.success(
                request,
                "Registration successful. "
                "Please login."
            )

            return redirect("login")

    return render(
        request,
        "skin/register.html"
    )


# ==========================================
# LOGIN
# ==========================================

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

        # Successful login
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


# ==========================================
# LOGOUT
# ==========================================

def logout_view(request):

    logout(request)

    return redirect("login")


# ==========================================
# HOME / IMAGE PREDICTION
# ==========================================

@login_required(login_url="login")
def home(request):

    context = {}

    # Only process when form is submitted
    if request.method == "POST":

        uploaded_image = request.FILES.get(
            "image"
        )

        # Check image
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

            # ======================================
            # CREATE MEDIA DIRECTORY
            # ======================================

            os.makedirs(
                settings.MEDIA_ROOT,
                exist_ok=True
            )


            # ======================================
            # SAVE UPLOADED IMAGE
            # ======================================

            fs = FileSystemStorage(
                location=settings.MEDIA_ROOT,
                base_url=settings.MEDIA_URL
            )

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


            # ======================================
            # CHECK IMAGE EXISTS
            # ======================================

            if not os.path.exists(
                image_path
            ):

                raise FileNotFoundError(
                    f"Uploaded image not found: "
                    f"{image_path}"
                )


            # ======================================
            # OPEN IMAGE
            # ======================================

            image = Image.open(
                image_path
            )

            # Convert to RGB
            image = image.convert(
                "RGB"
            )


            # ======================================
            # RESIZE IMAGE
            # ======================================

            image = image.resize(
                (224, 224)
            )


            # ======================================
            # CONVERT IMAGE TO ARRAY
            # ======================================

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


            # ======================================
            # LOAD AI MODEL
            # ======================================

            prediction_model = get_model()


            # ======================================
            # PREDICT DISEASE
            # ======================================

            predictions = prediction_model.predict(
                image_array,
                verbose=0
            )


            # Get highest probability index
            predicted_index = int(
                np.argmax(
                    predictions[0]
                )
            )


            # Calculate confidence
            confidence = float(
                np.max(
                    predictions[0]
                ) * 100
            )


            # Get disease name
            predicted_disease = CLASS_NAMES[
                predicted_index
            ]


            # Get description
            description = DISEASE_INFO.get(
                predicted_disease,
                "No description available."
            )


            # ======================================
            # SAVE PREDICTION HISTORY
            # ======================================

            PredictionHistory.objects.create(
                user=request.user,
                image=filename,
                prediction=predicted_disease,
                confidence=confidence
            )


            # ======================================
            # SEND RESULT TO HTML
            # ======================================

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


        # ==========================================
        # MODEL OR IMAGE FILE NOT FOUND
        # ==========================================

        except FileNotFoundError as error:

            context = {

                "message":
                    f"File error: {str(error)}"
            }


        # ==========================================
        # ANY OTHER ERROR
        # ==========================================

        except Exception as error:

            context = {

                "message":
                    f"Error analyzing image: {str(error)}"
            }


    # Render page
    return render(
        request,
        "skin/home.html",
        context
    )


# ==========================================
# PREDICTION HISTORY
# ==========================================

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