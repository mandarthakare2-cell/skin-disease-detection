import os
import tensorflow as tf
from tensorflow.keras import layers, models

def generate_and_save_model():
    print("Building MobileNetV2 for Acne, Melanoma, Psoriasis, Eczema, etc...")

    base_model = tf.keras.applications.MobileNetV2(
        input_shape=(224, 224, 3),
        include_top=False,
        weights='imagenet'
    )
    base_model.trainable = False

    # 7 output classes for the targeted skin conditions
    model = models.Sequential([
        base_model,
        layers.GlobalAveragePooling2D(),
        layers.Dropout(0.2),
        layers.Dense(7, activation='softmax', name='predictions')
    ])

    model.compile(
        optimizer='adam',
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    output_dir = os.path.join('skin', 'model')
    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, 'model.h5')

    model.save(model_path)
    print(f"✅ Success! Model updated and saved to: {os.path.abspath(model_path)}")

if __name__ == '__main__':
    generate_and_save_model()