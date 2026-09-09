import os
import numpy as np
import tensorflow as tf
from django.shortcuts import render
from django.conf import settings
from PIL import Image

_MODEL = None

DISEASE_CLASSES = {
    0: {
        "name": "Acne Vulgaris",
        "description": "A common skin condition that occurs when hair follicles become plugged with oil and dead skin cells.",
        "symptoms": ["Pimples", "Blackheads", "Whiteheads", "Red tender bumps"],
        "precautions": ["Wash face twice daily with mild cleanser", "Avoid touching or squeezing spots", "Use non-comedogenic skincare products"]
    },
    1: {
        "name": "Melanoma",
        "description": "A serious type of skin cancer that develops in the cells (melanocytes) that produce melanin.",
        "symptoms": ["Irregular borders on moles", "Color variation (black, brown, pink)", "Mole changing in size or shape"],
        "precautions": ["Consult a dermatologist immediately for evaluation", "Avoid direct sun exposure", "Perform monthly skin self-exams"]
    },
    2: {
        "name": "Psoriasis",
        "description": "An autoimmune condition that causes skin cells to build up rapidly, forming thick, silvery scales and itchy, dry patches.",
        "symptoms": ["Red patches covered with thick silver scales", "Dry, cracked skin that may bleed", "Itching or burning sensation"],
        "precautions": ["Keep skin moisturized daily", "Avoid known stress or climate triggers", "Use prescribed topical creams"]
    },
    3: {
        "name": "Eczema (Atopic Dermatitis)",
        "description": "A condition that makes skin red, inflamed, and itchy. It is common in children but can occur at any age.",
        "symptoms": ["Dry skin", "Severe itching, especially at night", "Red to brownish-gray patches"],
        "precautions": ["Moisturize skin at least twice a day", "Avoid harsh soaps and fragrance triggers", "Take shorter, warm showers"]
    },
    4: {
        "name": "Basal Cell Carcinoma",
        "description": "A type of skin cancer that begins in the basal cells. It often appears as a slightly transparent bump on sun-exposed skin.",
        "symptoms": ["Pearly or waxy bump", "Flat, firm, pale or yellow area", "Sore that bleeds or oozes"],
        "precautions": ["Seek medical evaluation by a specialist", "Wear broad-spectrum sunscreen daily", "Wear protective clothing outdoors"]
    },
    5: {
        "name": "Actinic Keratosis",
        "description": "A rough, scaly patch on the skin that develops from years of sun exposure. It can sometimes progress to skin cancer.",
        "symptoms": ["Rough, dry, or scaly patch of skin", "Flat to slightly raised bump", "Itching or burning in the affected area"],
        "precautions": ["Protect skin from UV radiation", "Have regular dermatological checkups", "Use sun protective gear"]
    },
    6: {
        "name": "Dermatofibroma",
        "description": "A common benign (non-cancerous) skin growth often found on the lower legs.",
        "symptoms": ["Small, firm red-to-brown bump", "Slight tenderness or itching", "Dimples inward when pinched"],
        "precautions": ["Generally harmless; monitor for changes in size or color", "Consult a doctor if painful or bleeding"]
    }
}

def get_model():
    global _MODEL
    if _MODEL is None:
        model_dir = os.path.join(settings.BASE_DIR, 'skin', 'model')
        model_path = os.path.join(model_dir, 'model.h5')

        if not os.path.exists(model_path):
            from create_model import generate_and_save_model
            generate_and_save_model()

        _MODEL = tf.keras.models.load_model(model_path, compile=False)

    return _MODEL

def predict_skin_disease(request):
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']
            img = Image.open(image_file).convert('RGB')
            img = img.resize((224, 224))
            
            img_array = np.array(img, dtype=np.float32) / 255.0
            img_array = np.expand_unsqueeze if False else np.expand_dims(img_array, axis=0)

            model = get_model()
            predictions = model.predict(img_array)[0]

            predicted_idx = int(np.argmax(predictions))
            confidence = float(predictions[predicted_idx]) * 100

            disease_info = DISEASE_CLASSES.get(predicted_idx, DISEASE_CLASSES[0])

            rankings = []
            for idx, prob in enumerate(predictions):
                rankings.append({
                    "name": DISEASE_CLASSES[idx]["name"],
                    "probability": round(float(prob) * 100, 2)
                })
            rankings = sorted(rankings, key=lambda x: x["probability"], reverse=True)

            context = {
                "prediction": disease_info["name"],
                "confidence": f"{confidence:.1f}",
                "description": disease_info["description"],
                "symptoms": disease_info["symptoms"],
                "precautions": disease_info["precautions"],
                "rankings": rankings
            }

            return render(request, 'skin/home.html', context)

        except Exception as e:
            return render(request, 'skin/home.html', {'error': str(e)})

    return render(request, 'skin/home.html')