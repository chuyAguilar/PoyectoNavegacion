import numpy as np
import os

file_path = "../parametros_calibracion.npz"
if os.path.exists(file_path):
    data = np.load(file_path)
    print("Keys found in .npz file:")
    for key in data.files:
        print(f"- {key}")
else:
    print(f"File not found: {file_path}")
