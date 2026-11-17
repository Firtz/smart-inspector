"""Image input loader and Preprocessor interface for Smart Inspector System.

Supports loading a sample image file (PPM/PGM natively via NumPy, or PNG/JPG
when Pillow/OpenCV is installed) as well as synthetic test frames, and transforms
raw HxWxC images into normalized model input tensors according to `ModelInputSpec`.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

from src.execution.execution_config import ModelInputSpec

logger = logging.getLogger(__name__)


class InputValidationError(ValueError):
    """Raised when an input image is missing, empty, or has invalid shape/dtype."""


@dataclass
class PreprocessedInput:
    """Container holding the preprocessed tensor and original image metadata."""

    tensor: np.ndarray
    original_dimensions: Dict[str, int]
    model_dimensions: Dict[str, int]


class BasePreprocessor(ABC):
    """Abstract interface for model input preprocessing."""

    @abstractmethod
    def validate_image(self, image: np.ndarray) -> Dict[str, int]:
        """Validate raw input image array and return its dimensions (`width`, `height`, `channels`)."""

    @abstractmethod
    def preprocess(self, image: np.ndarray, spec: ModelInputSpec) -> PreprocessedInput:
        """Transform a validated raw image into a normalized tensor matching `spec`."""


class StandardImagePreprocessor(BasePreprocessor):
    """Reusable NumPy-based image preprocessor supporting resize, color conversion, and normalization."""

    def validate_image(self, image: np.ndarray) -> Dict[str, int]:
        if not isinstance(image, np.ndarray):
            raise InputValidationError(
                f"Input citra harus berupa numpy.ndarray, tetapi menerima {type(image).__name__}."
            )
        if image.size == 0:
            raise InputValidationError("Input citra kosong (size == 0).")

        if image.ndim == 2:
            height, width = image.shape
            channels = 1
        elif image.ndim == 3:
            height, width, channels = image.shape
            if channels not in (1, 3):
                raise InputValidationError(
                    f"Jumlah channel citra tidak didukung: {channels} (harus 1 atau 3)."
                )
        else:
            raise InputValidationError(
                f"Dimensi array citra tidak valid: ndim={image.ndim} (harus 2D atau 3D HxWxC)."
            )

        if height <= 0 or width <= 0:
            raise InputValidationError(
                f"Ukuran citra tidak valid: width={width}, height={height}."
            )

        return {"width": int(width), "height": int(height), "channels": int(channels)}

    def _resize_nearest(self, image: np.ndarray, target_width: int, target_height: int) -> np.ndarray:
        """Fast pure-NumPy nearest-neighbor resize (works without OpenCV/Pillow)."""
        src_h, src_w = image.shape[:2]
        if src_w == target_width and src_h == target_height:
            return image

        row_indices = np.linspace(0, src_h - 1, target_height).astype(np.intp)
        col_indices = np.linspace(0, src_w - 1, target_width).astype(np.intp)
        return image[np.ix_(row_indices, col_indices)]

    def preprocess(self, image: np.ndarray, spec: ModelInputSpec) -> PreprocessedInput:
        original_dims = self.validate_image(image)
        spec.validate("preprocessor_target")

        work = image
        if work.ndim == 2:
            work = work[:, :, np.newaxis]

        # Ensure channel compatibility
        if work.shape[2] == 1 and spec.channels == 3:
            work = np.repeat(work, 3, axis=2)
        elif work.shape[2] == 3 and spec.channels == 1:
            work = np.mean(work, axis=2, keepdims=True).astype(work.dtype)

        # Color format conversion (assumes input is RGB by convention)
        if spec.channels == 3 and spec.color_format == "BGR":
            work = work[:, :, ::-1]

        # Resize to target model dimensions
        resized = self._resize_nearest(work, spec.width, spec.height)
        tensor = resized.astype(np.float32)

        # Scale normalization
        if spec.scale == "0_to_1":
            if image.dtype == np.uint8 or tensor.max() > 1.0:
                tensor = tensor / 255.0

        # Mean / Std standardization
        if spec.channels == 3:
            mean_arr = np.array(spec.mean, dtype=np.float32).reshape((1, 1, 3))
            std_arr = np.array(spec.std, dtype=np.float32).reshape((1, 1, 3))
            tensor = (tensor - mean_arr) / np.maximum(std_arr, 1e-6)

        # Convert HWC -> NCHW (1, C, H, W) standard for ONNX/PyTorch inference
        tensor_nchw = np.transpose(tensor, (2, 0, 1))[np.newaxis, ...]

        return PreprocessedInput(
            tensor=tensor_nchw,
            original_dimensions=original_dims,
            model_dimensions={
                "width": spec.width,
                "height": spec.height,
                "channels": spec.channels,
            },
        )


def create_synthetic_palm_image(
    width: int = 640,
    height: int = 640,
    channels: int = 3,
    seed: int = 42,
) -> np.ndarray:
    """Generate a deterministic synthetic RGB test image representing a palm bunch scene."""
    if width <= 0 or height <= 0 or channels not in (1, 3):
        raise InputValidationError("Parameter citra sintetis tidak valid.")

    rng = np.random.default_rng(seed)
    # Base green foliage background
    img = np.zeros((height, width, channels), dtype=np.uint8)
    if channels == 3:
        img[:, :, 0] = 35   # R
        img[:, :, 1] = 110  # G
        img[:, :, 2] = 45   # B
        # Simulated reddish-orange ripe FFB region in center
        y0, y1 = height // 4, (3 * height) // 4
        x0, x1 = width // 4, (3 * width) // 4
        img[y0:y1, x0:x1, 0] = 210
        img[y0:y1, x0:x1, 1] = 85
        img[y0:y1, x0:x1, 2] = 30
    else:
        img[:, :, 0] = 128

    noise = rng.integers(0, 15, size=img.shape, dtype=np.uint8)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def save_ppm_image(path: Path, image: np.ndarray) -> None:
    """Save an HxWx3 uint8 RGB array as a binary PPM (P6) image file without external dependencies."""
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise InputValidationError("save_ppm_image memerlukan array uint8 dengan shape (H, W, 3).")
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width, _ = image.shape
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    with path.open("wb") as handle:
        handle.write(header)
        handle.write(image.tobytes())


def load_image_from_path(path: Path) -> np.ndarray:
    """Load an image file into an HxWx3 uint8 RGB NumPy array.

    Supports binary PPM (`.ppm`) and `.npy` out-of-the-box with zero extra libraries,
    and automatically uses Pillow (`PIL`) or OpenCV (`cv2`) if installed for `.jpg`/`.png`.
    """
    if not path.exists():
        raise InputValidationError(f"File citra input tidak ditemukan: {path}")

    suffix = path.suffix.lower()
    if suffix == ".npy":
        arr = np.load(str(path))
        if not isinstance(arr, np.ndarray):
            raise InputValidationError(f"File .npy tidak berisi ndarray: {path}")
        return arr

    if suffix == ".ppm":
        with path.open("rb") as handle:
            magic = handle.readline().strip()
            if magic != b"P6":
                raise InputValidationError(f"Format PPM tidak didukung (bukan P6): {path}")
            dims_line = handle.readline().strip()
            while dims_line.startswith(b"#"):
                dims_line = handle.readline().strip()
            parts = dims_line.split()
            if len(parts) != 2:
                raise InputValidationError(f"Header dimensi PPM rusak: {path}")
            width, height = int(parts[0]), int(parts[1])
            maxval = int(handle.readline().strip())
            if maxval != 255:
                raise InputValidationError(f"Nilai maksimum PPM tidak didukung ({maxval}): {path}")
            raw_bytes = handle.read()
            expected_bytes = width * height * 3
            if len(raw_bytes) < expected_bytes:
                raise InputValidationError(
                    f"Data piksel PPM kurang dari {expected_bytes} byte: {path}"
                )
            arr = np.frombuffer(raw_bytes[:expected_bytes], dtype=np.uint8)
            return arr.reshape((height, width, 3)).copy()

    # Try Pillow for PNG/JPEG if available
    try:
        from PIL import Image  # type: ignore[import-not-found]

        with Image.open(path) as img:
            rgb_img = img.convert("RGB")
            return np.asarray(rgb_img, dtype=np.uint8)
    except ImportError:
        pass

    # Try OpenCV if available
    try:
        import cv2  # type: ignore[import-not-found]

        bgr = cv2.imread(str(path))
        if bgr is None:
            raise InputValidationError(f"OpenCV gagal membaca file gambar: {path}")
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    except ImportError as exc:
        raise InputValidationError(
            f"Tidak dapat membaca format file '{suffix}' ({path}) tanpa pustaka Pillow atau OpenCV. "
            "Gunakan file .ppm/.npy atau instal Pillow (`pip install Pillow`)."
        ) from exc

