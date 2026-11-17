"""Lecture des fichiers binaires CIFAR-10 (version « binary » : *.bin).

Format d'un batch : 10 000 enregistrements de 3073 octets chacun
    [1 octet : label 0..9][1024 octets R][1024 octets G][1024 octets B]
Chaque plan couleur fait 32x32, rangé ligne par ligne (planar, pas entrelacé).

Les images retournées sont rognées au centre (24x24) puis normalisées
via normalize().
"""
import os
import numpy as np

IMG_SIZE = 32
IMG_BYTES = 3 * IMG_SIZE * IMG_SIZE   # 3072
RECORD_BYTES = 1 + IMG_BYTES           # 3073

CROP_SIZE = 24                          # taille après rognage
CROP_OFFSET = (IMG_SIZE - CROP_SIZE) // 2   # 4 pixels retirés sur chaque bord

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "cifar-10-batches-bin")


def normalize(images):
    """
    Reçoit un tableau uint8 de forme (..., 24, 24, 3) (une image seule ou un
    batch) et doit retourner le tableau normalisé (typiquement en float32).
    """
    x = images.astype(np.float32)
    axes = (-3, -2, -1)                          # H, W, C : tous les pixels d'une image
    n = x.shape[-3] * x.shape[-2] * x.shape[-1]  # N = 24 * 24 * 3 = 1728

    mu = x.mean(axis=axes, keepdims=True)
    sigma = x.std(axis=axes, keepdims=True)      # écart-type avec 1/N (ddof=0)
    return (x - mu) / np.maximum(sigma, 1.0 / np.sqrt(n))


def center_crop(images):
    """Rogne au centre : (..., 32, 32, C) -> (..., 24, 24, C)."""
    o, e = CROP_OFFSET, CROP_OFFSET + CROP_SIZE
    return images[..., o:e, o:e, :]


def load_label_names(data_dir=DATA_DIR):
    """Noms des 10 classes (airplane, automobile, ...)."""
    with open(os.path.join(data_dir, "batches.meta.txt")) as f:
        return [line.strip() for line in f if line.strip()]


def load_batch(path, apply_normalize=True):
    """Charge un batch complet.

    Retourne (images, labels) :
      images : forme (N, 24, 24, 3) -> HWC, rognées au centre, puis normalisées
               si apply_normalize=True (sinon uint8 brut)
      labels : uint8, forme (N,)
    """
    raw = np.fromfile(path, dtype=np.uint8).reshape(-1, RECORD_BYTES)
    labels = raw[:, 0]
    images = raw[:, 1:].reshape(-1, 3, IMG_SIZE, IMG_SIZE)   # (N, C, H, W)
    images = center_crop(images.transpose(0, 2, 3, 1))        # (N, 24, 24, C)
    if apply_normalize:
        images = normalize(images)
    return images, labels


def load_image(path, n, apply_normalize=True):
    """Lit uniquement l'image n (équivalent du `dd skip=n*3073+1`)."""
    with open(path, "rb") as f:
        f.seek(n * RECORD_BYTES)
        record = np.frombuffer(f.read(RECORD_BYTES), dtype=np.uint8)
    label = record[0]
    image = record[1:].reshape(3, IMG_SIZE, IMG_SIZE).transpose(1, 2, 0)
    image = center_crop(image)                                # (24, 24, C)
    if apply_normalize:
        image = normalize(image)
    return image, label


def save_ppm(image, path):
    """Sauve une image (H, W, 3) uint8 en PPM binaire (P6), lisible par display/convert.

    Attention : passer une image NON normalisée (apply_normalize=False),
    sinon les valeurs ne sont plus dans 0..255.
    """
    with open(path, "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (image.shape[1], image.shape[0]))
        f.write(np.ascontiguousarray(image, dtype=np.uint8).tobytes())


if __name__ == "__main__":
    import matplotlib.pyplot as plt

    names = load_label_names()
    # Version brute (uint8) pour l'affichage
    images, labels = load_batch(os.path.join(DATA_DIR, "data_batch_1.bin"), apply_normalize=False)
    print(f"{len(images)} images, forme {images.shape}, dtype {images.dtype}")

    fig, axes = plt.subplots(2, 5, figsize=(10, 4))
    for ax, img, lab in zip(axes.flat, images, labels):
        ax.imshow(img)
        ax.set_title(names[lab])
        ax.axis("off")
    plt.tight_layout()
    plt.show()