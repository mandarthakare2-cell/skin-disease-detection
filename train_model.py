import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (
    Conv2D,
    MaxPooling2D,
    Flatten,
    Dense,
    Dropout
)

# ==============================
# SETTINGS
# ==============================

DATASET_PATH = "dataset"
MODEL_PATH = "skin/model/skin_disease_model.h5"
CLASS_NAMES_PATH = "class_names.txt"

IMAGE_SIZE = 224
BATCH_SIZE = 16
EPOCHS = 10


# ==============================
# CHECK DATASET
# ==============================

print("\nChecking dataset...\n")

if not os.path.exists(DATASET_PATH):
    print("ERROR: Dataset folder not found!")
    print("Expected location:", DATASET_PATH)
    exit()


# ==============================
# CREATE MODEL FOLDER
# ==============================

os.makedirs("skin/model", exist_ok=True)


# ==============================
# IMAGE DATA GENERATOR
# ==============================

datagen = ImageDataGenerator(
    rescale=1.0 / 255,
    validation_split=0.2,
    rotation_range=15,
    width_shift_range=0.1,
    height_shift_range=0.1,
    zoom_range=0.1,
    horizontal_flip=True
)


# ==============================
# TRAINING DATA
# ==============================

train_data = datagen.flow_from_directory(
    DATASET_PATH,
    target_size=(IMAGE_SIZE, IMAGE_SIZE),
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="training",
    shuffle=True
)


# ==============================
# VALIDATION DATA
# ==============================

validation_data = datagen.flow_from_directory(
    DATASET_PATH,
    target_size=(IMAGE_SIZE, IMAGE_SIZE),
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="validation",
    shuffle=True
)


# ==============================
# SAVE CLASS NAMES
# ==============================

class_indices = train_data.class_indices

class_names = [
    name for name, index in
    sorted(class_indices.items(), key=lambda item: item[1])
]

with open(CLASS_NAMES_PATH, "w") as file:
    for class_name in class_names:
        file.write(class_name + "\n")


print("\nDisease Classes:")

for index, name in enumerate(class_names):
    print(f"{index} -> {name}")


print("\nTotal Classes:", len(class_names))


# ==============================
# CREATE CNN MODEL
# ==============================

model = Sequential([

    Conv2D(
        32,
        (3, 3),
        activation="relu",
        input_shape=(IMAGE_SIZE, IMAGE_SIZE, 3)
    ),

    MaxPooling2D(pool_size=(2, 2)),

    Conv2D(
        64,
        (3, 3),
        activation="relu"
    ),

    MaxPooling2D(pool_size=(2, 2)),

    Conv2D(
        128,
        (3, 3),
        activation="relu"
    ),

    MaxPooling2D(pool_size=(2, 2)),

    Flatten(),

    Dense(
        256,
        activation="relu"
    ),

    Dropout(0.5),

    Dense(
        len(class_names),
        activation="softmax"
    )
])


# ==============================
# COMPILE MODEL
# ==============================

model.compile(
    optimizer="adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)


# ==============================
# MODEL SUMMARY
# ==============================

print("\nModel Summary:\n")

model.summary()


# ==============================
# TRAIN MODEL
# ==============================

print("\nTraining Started...\n")


history = model.fit(
    train_data,
    validation_data=validation_data,
    epochs=EPOCHS
)


# ==============================
# SAVE TRAINED MODEL
# ==============================

model.save(MODEL_PATH)

print("\n================================")
print("MODEL TRAINING COMPLETED!")
print("================================")

print("\nModel saved at:")
print(MODEL_PATH)

print("\nClass names saved at:")
print(CLASS_NAMES_PATH)