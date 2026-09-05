import os
import json
import tensorflow as tf

from tensorflow import keras
from tensorflow.keras import layers


# --------------------------------------------------
# PROJECT PATH
# --------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.join(BASE_DIR, "dataset")

MODEL_PATH = os.path.join(
    BASE_DIR,
    "skin_disease_model.keras"
)

CLASS_NAMES_PATH = os.path.join(
    BASE_DIR,
    "class_names.json"
)


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

IMAGE_SIZE = (224, 224)

BATCH_SIZE = 16

EPOCHS = 10

SEED = 123


# --------------------------------------------------
# CHECK DATASET
# --------------------------------------------------

if not os.path.exists(DATASET_DIR):

    raise FileNotFoundError(
        f"Dataset folder not found: {DATASET_DIR}"
    )


print("\nLoading dataset...\n")


# --------------------------------------------------
# LOAD TRAINING DATA
# --------------------------------------------------

train_dataset = tf.keras.utils.image_dataset_from_directory(

    DATASET_DIR,

    validation_split=0.2,

    subset="training",

    seed=SEED,

    image_size=IMAGE_SIZE,

    batch_size=BATCH_SIZE
)


# --------------------------------------------------
# LOAD VALIDATION DATA
# --------------------------------------------------

validation_dataset = tf.keras.utils.image_dataset_from_directory(

    DATASET_DIR,

    validation_split=0.2,

    subset="validation",

    seed=SEED,

    image_size=IMAGE_SIZE,

    batch_size=BATCH_SIZE
)


# --------------------------------------------------
# GET DISEASE NAMES
# --------------------------------------------------

class_names = train_dataset.class_names

print("\nDiseases found:")

for disease in class_names:

    print("-", disease)


# --------------------------------------------------
# SAVE DISEASE NAMES
# --------------------------------------------------

with open(CLASS_NAMES_PATH, "w") as file:

    json.dump(class_names, file)


print(
    "\nClass names saved successfully."
)


# --------------------------------------------------
# PERFORMANCE OPTIMIZATION
# --------------------------------------------------

AUTOTUNE = tf.data.AUTOTUNE


train_dataset = train_dataset.prefetch(
    AUTOTUNE
)

validation_dataset = validation_dataset.prefetch(
    AUTOTUNE
)


# --------------------------------------------------
# DATA AUGMENTATION
# --------------------------------------------------

data_augmentation = keras.Sequential([

    layers.RandomFlip("horizontal"),

    layers.RandomRotation(0.1),

    layers.RandomZoom(0.1),

])


# --------------------------------------------------
# CREATE MODEL
# --------------------------------------------------

model = keras.Sequential([

    layers.Input(
        shape=(224, 224, 3)
    ),

    layers.Rescaling(
        1.0 / 255
    ),

    data_augmentation,


    # CNN LAYER 1

    layers.Conv2D(

        32,

        (3, 3),

        activation="relu",

        padding="same"
    ),

    layers.MaxPooling2D(),


    # CNN LAYER 2

    layers.Conv2D(

        64,

        (3, 3),

        activation="relu",

        padding="same"
    ),

    layers.MaxPooling2D(),


    # CNN LAYER 3

    layers.Conv2D(

        128,

        (3, 3),

        activation="relu",

        padding="same"
    ),

    layers.MaxPooling2D(),


    # CLASSIFICATION

    layers.GlobalAveragePooling2D(),

    layers.Dropout(0.3),

    layers.Dense(

        128,

        activation="relu"
    ),

    layers.Dropout(0.2),

    layers.Dense(

        len(class_names),

        activation="softmax"
    )

])


# --------------------------------------------------
# COMPILE MODEL
# --------------------------------------------------

model.compile(

    optimizer="adam",

    loss="sparse_categorical_crossentropy",

    metrics=["accuracy"]
)


# --------------------------------------------------
# DISPLAY MODEL
# --------------------------------------------------

model.summary()


# --------------------------------------------------
# CALLBACKS
# --------------------------------------------------

early_stopping = keras.callbacks.EarlyStopping(

    monitor="val_loss",

    patience=3,

    restore_best_weights=True
)


# --------------------------------------------------
# TRAIN MODEL
# --------------------------------------------------

print("\nTraining started...\n")


history = model.fit(

    train_dataset,

    validation_data=validation_dataset,

    epochs=EPOCHS,

    callbacks=[early_stopping]
)


# --------------------------------------------------
# SAVE MODEL
# --------------------------------------------------

model.save(

    MODEL_PATH
)


print("\n--------------------------------")

print("TRAINING COMPLETED SUCCESSFULLY")

print("--------------------------------")

print(
    f"\nModel saved at:\n{MODEL_PATH}"
)

print(
    f"\nClasses saved at:\n{CLASS_NAMES_PATH}"
)

print(
    "\nYou can now run your Django project."
)