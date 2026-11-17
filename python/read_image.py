"""Lecture des fichiers binaires CIFAR-10 (version « binary » : *.bin).

Format d'un batch : 10 000 enregistrements de 3073 octets chacun
    [1 octet : label 0..9][1024 octets R][1024 octets G][1024 octets B]
Chaque plan couleur fait 32x32, rangé ligne par ligne (planar, pas entrelacé).
"""
import os
import numpy as np

IMG_SIZE = 32
IMG_BYTES = 3 * IMG_SIZE * IMG_SIZE   # 3072
RECORD_BYTES = 1 + IMG_BYTES           # 3073

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "cifar-10-batches-bin")


def load_label_names(data_dir=DATA_DIR):
    """Noms des 10 classes (airplane, automobile, ...)."""
    with open(os.path.join(data_dir, "batches.meta.txt")) as f:
        return [line.strip() for line in f if line.strip()]


def load_batch(path):
    """Charge un batch complet.

    Retourne (images, labels) :
      images : uint8, forme (N, 32, 32, 3)  -> HWC, prêt pour matplotlib
      labels : uint8, forme (N,)
    """
    raw = np.fromfile(path, dtype=np.uint8).reshape(-1, RECORD_BYTES)
    labels = raw[:, 0]
    images = raw[:, 1:].reshape(-1, 3, IMG_SIZE, IMG_SIZE)   # (N, C, H, W)
    return images.transpose(0, 2, 3, 1), labels               # (N, H, W, C)


def load_image(path, n):
    """Lit uniquement l'image n (équivalent du `dd skip=n*3073+1`)."""
    with open(path, "rb") as f:
        f.seek(n * RECORD_BYTES)
        record = np.frombuffer(f.read(RECORD_BYTES), dtype=np.uint8)
    label = record[0]
    image = record[1:].reshape(3, IMG_SIZE, IMG_SIZE).transpose(1, 2, 0)
    return image, label


def save_ppm(image, path):
    """Sauve une image (32, 32, 3) uint8 en PPM binaire (P6), lisible par display/convert."""
    with open(path, "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (image.shape[1], image.shape[0]))
        f.write(np.ascontiguousarray(image, dtype=np.uint8).tobytes())


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    names = load_label_names()
    images, labels = load_batch(os.path.join(DATA_DIR, "data_batch_1.bin"))
    print(f"{len(images)} images, forme {images.shape}, dtype {images.dtype}")

    fig, axes = plt.subplots(2, 5, figsize=(10, 4))
    for ax, img, lab in zip(axes.flat, images, labels):
        ax.imshow(img)
        ax.set_title(names[lab])
        ax.axis("off")
    plt.tight_layout()
    plt.show()
