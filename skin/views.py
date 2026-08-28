import os

# Set environment variables BEFORE importing TensorFlow
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import numpy as np
import tensorflow as tf

from PIL import Image

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.conf import settings

from .models import PredictionHistory


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR = settings.BASE_DIR


MODEL_PATH = os.path.join(
    BASE_DIR,
    "skin_disease_model.keras"
)


CLASS_NAMES_PATH = os.path.join(
    BASE_DIR,
    "class_names.txt"
)


# ==========================================================
# LOAD CLASS NAMES
# ==========================================================

def load_class_names():

    if not os.path.exists(
        CLASS_NAMES_PATH
    ):

        return [
            "Acne",
            "Dermatitis",
            "Eczema",
            "Melanoma",
            "Psoriasis",
            "Ringworm",
            "Vitiligo"
        ]

    with open(
        CLASS_NAMES_PATH,
        "r",
        encoding="utf-8"
    ) as file:

        class_names = [

            line.strip()

            for line in file

            if line.strip()

        ]

    return class_names


# ==========================================================
# DISEASE INFORMATION
# ==========================================================

DISEASE_INFO = {

    "Acne":
        "Acne is a skin condition that may cause pimples and inflamed areas.",

    "Dermatitis":
        "Dermatitis is skin inflammation that may cause redness, dryness, itching, or irritation.",

    "Eczema":
        "Eczema may cause dry, itchy, inflamed, or irritated skin.",

    "Melanoma":
        "Melanoma is a serious condition affecting skin cells.",

    "Psoriasis":
        "Psoriasis may cause thickened, dry, or scaly patches on the skin.",

    "Ringworm":
        "Ringworm is a fungal skin infection that may cause itchy or ring-shaped patches.",

    "Vitiligo":
        "Vitiligo causes areas of skin to lose pigment and become lighter."
}


# ==========================================================
# MODEL VARIABLE
# ==========================================================

model = None


# ==========================================================
# LOAD MODEL ONLY WHEN NEEDED
# ==========================================================

def get_model():

    global model

    if model is None:

        if not os.path.exists(
            MODEL_PATH
        ):

            raise FileNotFoundError(
                f"Model file not found: {MODEL_PATH}"
            )

        model = tf.keras.models.load_model(

            MODEL_PATH,

            compile=False

        )

    return model


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


            return redirect(
                "login"
            )


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


            return redirect(
                "home"
            )


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

    logout(
        request
    )


    return redirect(
        "login"
    )


# ==========================================================
# HOME / PREDICTION
# ==========================================================

@login_required(
    login_url="login"
)
def home(request):

    context = {}


    if request.method == "POST":

        uploaded_image = request.FILES.get(
            "image"
        )


        # ----------------------------------------------
        # CHECK IMAGE
        # ----------------------------------------------

        if not uploaded_image:

            context["message"] = (
                "Please select an image first."
            )


            return render(

                request,

                "skin/home.html",

                context

            )


        try:

            # ------------------------------------------
            # SAVE IMAGE
            # ------------------------------------------

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


            # ------------------------------------------
            # OPEN IMAGE
            # ------------------------------------------

            image = Image.open(
                image_path
            )


            image = image.convert(
                "RGB"
            )


            image = image.resize(
                (224, 224)
            )


            # ------------------------------------------
            # CONVERT IMAGE TO NUMPY ARRAY
            # ------------------------------------------

            image_array = np.array(

                image,

                dtype=np.float32

            )


            # ------------------------------------------
            # IMPORTANT
            #
            # DO NOT DIVIDE BY 255 HERE.
            #
            # The trained model already contains:
            #
            # Rescaling(1.0 / 255.0)
            #
            # ------------------------------------------


            # ------------------------------------------
            # ADD BATCH DIMENSION
            # ------------------------------------------

            image_array = np.expand_dims(

                image_array,

                axis=0

            )


            # ------------------------------------------
            # LOAD MODEL
            # ------------------------------------------

            loaded_model = get_model()


            # ------------------------------------------
            # PREDICT
            # ------------------------------------------

            predictions = loaded_model.predict(

                image_array,

                verbose=0

            )


            # ------------------------------------------
            # GET CLASS NAMES
            # ------------------------------------------

            class_names = load_class_names()


            # ------------------------------------------
            # GET PREDICTED INDEX
            # ------------------------------------------

            predicted_index = int(

                np.argmax(
                    predictions[0]
                )

            )


            # ------------------------------------------
            # CONFIDENCE
            # ------------------------------------------

            confidence = float(

                np.max(
                    predictions[0]
                ) * 100

            )


            # ------------------------------------------
            # GET DISEASE
            # ------------------------------------------

            predicted_disease = class_names[
                predicted_index
            ]


            # ------------------------------------------
            # DESCRIPTION
            # ------------------------------------------

            description = DISEASE_INFO.get(

                predicted_disease,

                "No description available."

            )


            # ------------------------------------------
            # SAVE HISTORY
            # ------------------------------------------

            PredictionHistory.objects.create(

                user=request.user,

                image=filename,

                prediction=predicted_disease,

                confidence=confidence

            )


            # ------------------------------------------
            # SEND RESULT TO HTML
            # ------------------------------------------

            context = {

                "image_url": image_url,

                "message":
                    "Image analyzed successfully!",

                "prediction":
                    predicted_disease,

                "confidence":
                    round(confidence, 2),

                "description":
                    description

            }


        # ----------------------------------------------
        # MODEL NOT FOUND
        # ----------------------------------------------

        except FileNotFoundError as error:

            context = {

                "message":
                    f"Model file error: {str(error)}"

            }


        # ----------------------------------------------
        # OTHER ERROR
        # ----------------------------------------------

        except Exception as error:

            print(
                "ANALYSIS ERROR:",
                str(error)
            )


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

@login_required(
    login_url="login"
)
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

            "history":
                history

        }

    )