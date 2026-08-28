import os

# Reduce unnecessary TensorFlow resource usage
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import tensorflow as tf


# ==========================================================
# CONFIGURATION
# ==========================================================

IMAGE_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 10

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_DIR = os.path.join(
    BASE_DIR,
    "dataset"
)

MODEL_PATH = os.path.join(
    BASE_DIR,
    "skin_disease_model.keras"
)

CLASS_NAMES_PATH = os.path.join(
    BASE_DIR,
    "class_names.txt"
)


# ==========================================================
# CHECK DATASET
# ==========================================================

if not os.path.exists(DATASET_DIR):

    raise FileNotFoundError(
        f"Dataset folder not found: {DATASET_DIR}"
    )


# ==========================================================
# LOAD TRAINING DATA
# ==========================================================

print("Loading training dataset...")


train_dataset = tf.keras.utils.image_dataset_from_directory(

    DATASET_DIR,

    validation_split=0.2,

    subset="training",

    seed=123,

    image_size=IMAGE_SIZE,

    batch_size=BATCH_SIZE,

    label_mode="int"
)


# ==========================================================
# LOAD VALIDATION DATA
# ==========================================================

print("Loading validation dataset...")


validation_dataset = tf.keras.utils.image_dataset_from_directory(

    DATASET_DIR,

    validation_split=0.2,

    subset="validation",

    seed=123,

    image_size=IMAGE_SIZE,

    batch_size=BATCH_SIZE,

    label_mode="int"
)


# ==========================================================
# GET CLASS NAMES
# ==========================================================

CLASS_NAMES = train_dataset.class_names

print("\nDetected classes:")

for index, class_name in enumerate(CLASS_NAMES):

    print(f"{index}: {class_name}")


# ==========================================================
# SAVE CLASS NAMES
# ==========================================================

with open(
    CLASS_NAMES_PATH,
    "w",
    encoding="utf-8"
) as file:

    for class_name in CLASS_NAMES:

        file.write(
            class_name + "\n"
        )


print(
    f"\nClass names saved to: {CLASS_NAMES_PATH}"
)


# ==========================================================
# PERFORMANCE OPTIMIZATION
# ==========================================================

AUTOTUNE = tf.data.AUTOTUNE


train_dataset = train_dataset.prefetch(
    AUTOTUNE
)

validation_dataset = validation_dataset.prefetch(
    AUTOTUNE
)


# ==========================================================
# DATA AUGMENTATION
#
# These layers are used during training.
# ==========================================================

data_augmentation = tf.keras.Sequential(

    [

        tf.keras.layers.RandomFlip(
            "horizontal"
        ),

        tf.keras.layers.RandomRotation(
            0.1
        ),

        tf.keras.layers.RandomZoom(
            0.1
        ),

    ],

    name="data_augmentation"
)


# ==========================================================
# CREATE MODEL
# ==========================================================

num_classes = len(
    CLASS_NAMES
)


model = tf.keras.Sequential(

    [

        tf.keras.layers.Input(
            shape=(224, 224, 3)
        ),


        # Rescale pixel values
        tf.keras.layers.Rescaling(
            1.0 / 255.0
        ),


        # DATA AUGMENTATION
        data_augmentation,


        # CONVOLUTION BLOCK 1
        tf.keras.layers.Conv2D(
            32,
            (3, 3),
            activation="relu",
            padding="same"
        ),

        tf.keras.layers.MaxPooling2D(
            (2, 2)
        ),


        # CONVOLUTION BLOCK 2
        tf.keras.layers.Conv2D(
            64,
            (3, 3),
            activation="relu",
            padding="same"
        ),

        tf.keras.layers.MaxPooling2D(
            (2, 2)
        ),


        # CONVOLUTION BLOCK 3
        tf.keras.layers.Conv2D(
            128,
            (3, 3),
            activation="relu",
            padding="same"
        ),

        tf.keras.layers.MaxPooling2D(
            (2, 2)
        ),


        # REDUCE PARAMETERS
        tf.keras.layers.GlobalAveragePooling2D(),


        # DROPOUT
        tf.keras.layers.Dropout(
            0.3
        ),


        # OUTPUT LAYER
        tf.keras.layers.Dense(
            num_classes,
            activation="softmax"
        )

    ]

)


# ==========================================================
# COMPILE MODEL
# ==========================================================

model.compile(

    optimizer=tf.keras.optimizers.Adam(
        learning_rate=0.001
    ),

    loss=tf.keras.losses.SparseCategoricalCrossentropy(),

    metrics=[
        "accuracy"
    ]

)


# ==========================================================
# DISPLAY MODEL
# ==========================================================

model.summary()


# ==========================================================
# CALLBACKS
# ==========================================================

early_stopping = tf.keras.callbacks.EarlyStopping(

    monitor="val_loss",

    patience=3,

    restore_best_weights=True
)


# ==========================================================
# TRAIN MODEL
# ==========================================================

print("\nStarting model training...\n")


history = model.fit(

    train_dataset,

    validation_data=validation_dataset,

    epochs=EPOCHS,

    callbacks=[
        early_stopping
    ]

)


# ==========================================================
# EVALUATE MODEL
# ==========================================================

loss, accuracy = model.evaluate(
    validation_dataset
)


print("\n==============================")

print(
    f"Validation Loss: {loss:.4f}"
)

print(
    f"Validation Accuracy: {accuracy * 100:.2f}%"
)

print("==============================\n")


# ==========================================================
# SAVE MODEL
# ==========================================================

model.save(
    MODEL_PATH
)


print(
    "Model successfully saved!"
)

print(
    f"Model location: {MODEL_PATH}"
)

print(
    f"Class names location: {CLASS_NAMES_PATH}"
)