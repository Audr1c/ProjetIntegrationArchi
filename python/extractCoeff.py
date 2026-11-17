import os
import re
import numpy as np

COEF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "coef")


def parse_tensors(path):
    """Lit le fichier et retourne un dict {nom_du_tenseur: np.ndarray}."""
    with open(path, "r") as f:
        content = f.read()

    # Découpe le fichier en blocs : un par "tensor_name:"
    blocks = re.split(r"^tensor_name:\s*", content, flags=re.MULTILINE)[1:]

    tensors = {}
    for block in blocks:
        name, _, body = block.partition("\n")
        name = name.strip()
        body = body.strip()

        # Nombre de '[' consécutifs au début = nombre de dimensions
        ndim = len(re.match(r"\[+", body).group(0))

        # Toutes les valeurs numériques (gère les notations 1.23e-01)
        values = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", body)
        flat = np.array(values, dtype=np.float32)

        # Reconstruction de la forme à partir des crochets
        shape = infer_shape(body, ndim)
        tensors[name] = flat.reshape(shape)

    return tensors


def infer_shape(body, ndim):
    """Déduit la forme à partir de la structure des crochets imbriqués."""
    # Tokens : '[' , ']' ou nombre
    tokens = re.findall(r"\[|\]|[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", body)

    shape = [None] * ndim
    depth = 0
    counts = [0] * ndim  # nombre d'éléments dans le conteneur courant, par niveau

    for t in tokens:
        if t == "[":
            if depth > 0:
                counts[depth - 1] += 1
            depth += 1
            if depth <= ndim:
                counts[depth - 1] = 0
        elif t == "]":
            level = depth - 1
            if shape[level] is None:
                shape[level] = counts[level]
            depth -= 1
        else:  # nombre
            counts[depth - 1] += 1

    return tuple(shape)


if __name__ == "__main__":
    tensors = parse_tensors(os.path.join(COEF_DIR, "CNN_coeff_3x3.txt"))

    for name, arr in tensors.items():
        print(name, arr.shape, arr.dtype)

    biases = tensors["conv1/biases"]    # shape (64,)
    weights = tensors["conv1/weights"]  # shape (H, W, C_in, 64) en principe

    print(biases)