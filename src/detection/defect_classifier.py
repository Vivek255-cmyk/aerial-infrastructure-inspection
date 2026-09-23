"""Deep learning classifier for defect type and severity prediction."""

from pathlib import Path

import numpy as np


class DefectClassifier:
    """Classify defect types using a trained neural network (PyTorch or TensorFlow)."""

    def __init__(self, model_path: str | Path | None = None, framework: str = "pytorch"):
        self.model_path = model_path
        self.framework = framework
        self.model = None
        self.class_names = [
            "crack", "corrosion", "spalling", "vegetation_overgrowth",
            "insulator_damage", "rust", "missing_component", "structural_deformation",
        ]

        if model_path and Path(model_path).exists():
            self._load_model()

    def _load_model(self) -> None:
        if self.framework == "pytorch":
            import torch
            self.model = torch.load(str(self.model_path), map_location="cpu")
            self.model.eval()
        elif self.framework == "tensorflow":
            import tensorflow as tf
            self.model = tf.keras.models.load_model(str(self.model_path))

    def predict(self, image_crop: np.ndarray) -> dict:
        """Predict defect class and confidence from a cropped image region."""
        if self.model is None:
            return self._rule_based_predict(image_crop)

        if self.framework == "pytorch":
            return self._predict_pytorch(image_crop)
        return self._predict_tensorflow(image_crop)

    def _predict_pytorch(self, image: np.ndarray) -> dict:
        import torch
        from torchvision import transforms

        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

        tensor = transform(image).unsqueeze(0)
        with torch.no_grad():
            outputs = self.model(tensor)
            probs = torch.softmax(outputs, dim=1)[0]
            idx = int(torch.argmax(probs))
            return {
                "class": self.class_names[idx],
                "confidence": round(float(probs[idx]), 4),
            }

    def _predict_tensorflow(self, image: np.ndarray) -> dict:
        import cv2
        resized = cv2.resize(image, (224, 224)) / 255.0
        batch = np.expand_dims(resized, axis=0)
        probs = self.model.predict(batch, verbose=0)[0]
        idx = int(np.argmax(probs))
        return {
            "class": self.class_names[idx],
            "confidence": round(float(probs[idx]), 4),
        }

    @staticmethod
    def _rule_based_predict(image: np.ndarray) -> dict:
        """Fallback heuristic when no trained model is available."""
        import cv2
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size

        if edge_density > 0.15:
            return {"class": "crack", "confidence": 0.6}
        if np.mean(gray) < 80:
            return {"class": "corrosion", "confidence": 0.5}
        return {"class": "unknown", "confidence": 0.3}
