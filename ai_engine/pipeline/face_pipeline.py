"""
Face Processing Pipeline: RetinaFace Landmarks, 112x112 Alignment, AuraFace 512D Embeddings,
and Calibrated Biometric Verification.
"""

import logging
import math
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any
import cv2
import numpy as np
import torch
import onnxruntime as ort

from ai_engine.config import (
    RETINAFACE_MODEL_PATH,
    AURAFACE_MODEL_PATH,
    RETINAFACE_THIRD_PARTY_DIR,
    DEFAULT_TEMPLATE_PATH,
    FACE_CONFIDENCE_THRESHOLD,
    FACE_NMS_THRESHOLD,
    FACE_MIN_SIZE_PIXELS,
    COSINE_MATCH_THRESHOLD,
    COSINE_AMBIGUOUS_THRESHOLD,
    REFERENCE_5PTS,
)

logger = logging.getLogger(__name__)

# Ensure retinaface-pytorch modules are importable
if str(RETINAFACE_THIRD_PARTY_DIR) not in sys.path:
    sys.path.insert(0, str(RETINAFACE_THIRD_PARTY_DIR))

try:
    from config import get_config
    from models.retinaface import RetinaFace
    from layers.functions.prior_box import PriorBox
    from utils.box_utils import decode, decode_landmarks, nms
    RETINAFACE_AVAILABLE = True
except ImportError as e:
    logger.warning("Could not import retinaface-pytorch components: %s", e)
    RETINAFACE_AVAILABLE = False


@dataclass
class FaceRecognitionResult:
    """Result of facial detection, alignment, embedding, and template matching."""
    face_detected: bool
    face_box: tuple[float, float, float, float] | None = None
    face_confidence: float = 0.0
    landmarks_5pts: list[list[float]] | None = None
    aligned_crop: np.ndarray | None = None
    embedding_512d: list[float] | None = None
    matched_employee_id: str | None = None
    max_similarity: float = 0.0
    classification: str = "no_face"  # 'recognized', 'unknown', 'ambiguous', 'no_face'


class FaceProcessingPipeline:
    """
    Decoupled face detection, alignment, and biometric feature extraction pipeline.
    Uses:
      - RetinaFace ResNet34 for face bounding boxes and 5 facial landmarks.
      - cv2.estimateAffinePartial2D to canonical 112x112 reference landmarks.
      - AuraFace v1 ONNX runtime producing 512D L2-normalized feature vectors.
      - Cosine similarity evaluation against cached employee templates.
    """

    def __init__(
        self,
        retinaface_weights: str | Path = RETINAFACE_MODEL_PATH,
        auraface_weights: str | Path = AURAFACE_MODEL_PATH,
        template_path: str | Path | None = DEFAULT_TEMPLATE_PATH,
        match_threshold: float = COSINE_MATCH_THRESHOLD,
        ambiguous_threshold: float = COSINE_AMBIGUOUS_THRESHOLD,
        device: str | int | None = None,
    ):
        self.retinaface_weights = Path(retinaface_weights)
        self.auraface_weights = Path(auraface_weights)
        self.template_path = Path(template_path) if template_path else None
        self.match_threshold = match_threshold
        self.ambiguous_threshold = ambiguous_threshold

        # Determine Torch device
        if device is not None:
            self.device = torch.device(device)
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        else:
            self.device = torch.device("cpu")

        self.retinaface_model: Any | None = None
        self.retinaface_cfg: dict[str, Any] | None = None
        self.auraface_session: ort.InferenceSession | None = None

        # Template cache: {employee_id: normalized_512d_vector}
        self._enrolled_templates: dict[str, np.ndarray] = {}
        self._reference_landmarks = np.array(REFERENCE_5PTS, dtype=np.float32)

        self._load_models()
        self._load_templates()

    def _load_models(self):
        """Initialize RetinaFace and AuraFace ONNX sessions."""
        # 1. Load RetinaFace
        if RETINAFACE_AVAILABLE and self.retinaface_weights.exists():
            try:
                cfg = get_config("resnet34").copy()
                cfg["pretrain"] = False
                model = RetinaFace(cfg=cfg)
                checkpoint = torch.load(
                    self.retinaface_weights,
                    map_location=self.device,
                    weights_only=True,
                )
                model.load_state_dict(checkpoint)
                model.to(self.device)
                model.eval()
                self.retinaface_model = model
                self.retinaface_cfg = cfg
                logger.info("Loaded RetinaFace ResNet34 on %s", self.device)
            except Exception as e:
                logger.error("Failed to load RetinaFace: %s", e)

        # 2. Load AuraFace ONNX
        if self.auraface_weights.exists():
            try:
                available_providers = ort.get_available_providers()
                providers = []
                if "CUDAExecutionProvider" in available_providers and self.device.type == "cuda":
                    providers.append("CUDAExecutionProvider")
                providers.append("CPUExecutionProvider")

                session = ort.InferenceSession(
                    str(self.auraface_weights),
                    providers=providers,
                )
                self.auraface_session = session
                logger.info("Loaded AuraFace v1 ONNX with providers: %s", session.get_providers())
            except Exception as e:
                logger.error("Failed to load AuraFace ONNX: %s", e)

    def _load_templates(self):
        """Pre-load local employee biometric templates if archive exists."""
        if self.template_path and self.template_path.exists():
            try:
                data = np.load(self.template_path, allow_pickle=False)
                emp_ids = data["employee_ids"].astype(str)
                tmps = data["templates"].astype(np.float32)
                for eid, vec in zip(emp_ids, tmps):
                    norm = np.linalg.norm(vec)
                    if norm > 1e-6:
                        self._enrolled_templates[eid] = vec / norm
                logger.info("Loaded %d enrolled employee templates.", len(self._enrolled_templates))
            except Exception as e:
                logger.warning("Could not load employee templates from %s: %s", self.template_path, e)

    def set_enrolled_templates(self, templates: dict[str, list[float] | np.ndarray]):
        """Dynamically update template cache from backend or database."""
        self._enrolled_templates.clear()
        for eid, vec in templates.items():
            arr = np.asarray(vec, dtype=np.float32).reshape(-1)
            norm = np.linalg.norm(arr)
            if norm > 1e-6 and arr.shape[0] == 512:
                self._enrolled_templates[str(eid)] = arr / norm

    @torch.inference_mode()
    def detect_face_and_landmarks(
        self,
        image: np.ndarray,
    ) -> tuple[tuple[float, float, float, float] | None, list[list[float]] | None, float]:
        """Detect the most prominent face and extract 5 landmark points."""
        if self.retinaface_model is None or self.retinaface_cfg is None:
            return None, None, 0.0

        h, w = image.shape[:2]
        if w < FACE_MIN_SIZE_PIXELS or h < FACE_MIN_SIZE_PIXELS:
            return None, None, 0.0

        # Pad to multiple of 32 for RetinaFace feature maps
        pad_w = ((w + 31) // 32) * 32
        pad_h = ((h + 31) // 32) * 32
        padded = np.zeros((pad_h, pad_w, 3), dtype=np.uint8)
        padded[:h, :w] = image

        img_float = padded.astype(np.float32) - np.array([104, 117, 123], dtype=np.float32)
        tensor = torch.from_numpy(
            np.ascontiguousarray(img_float.transpose(2, 0, 1))
        ).unsqueeze(0).to(self.device)

        loc, conf, landmarks = self.retinaface_model(tensor)
        loc = loc.squeeze(0)
        conf = conf.squeeze(0)
        landmarks = landmarks.squeeze(0)

        priorbox = PriorBox(self.retinaface_cfg, image_size=(pad_h, pad_w))
        priors = priorbox.generate_anchors().to(self.device)

        boxes = decode(loc, priors, self.retinaface_cfg["variance"])
        landmarks = decode_landmarks(landmarks, priors, self.retinaface_cfg["variance"])

        scale_box = torch.tensor([pad_w, pad_h, pad_w, pad_h], dtype=torch.float32, device=self.device)
        boxes = boxes * scale_box

        scale_land = torch.tensor(
            [pad_w, pad_h, pad_w, pad_h, pad_w, pad_h, pad_w, pad_h, pad_w, pad_h],
            dtype=torch.float32,
            device=self.device,
        )
        landmarks = landmarks * scale_land

        scores = conf[:, 1]
        mask = scores > FACE_CONFIDENCE_THRESHOLD
        boxes = boxes[mask]
        landmarks = landmarks[mask]
        scores = scores[mask]

        if boxes.shape[0] == 0:
            return None, None, 0.0

        scores_np = scores.cpu().numpy()
        boxes_np = boxes.cpu().numpy()
        landmarks_np = landmarks.cpu().numpy()

        order = scores_np.argsort()[::-1][:1000]
        boxes_np = boxes_np[order]
        landmarks_np = landmarks_np[order]
        scores_np = scores_np[order]

        detections = np.hstack((boxes_np, scores_np[:, np.newaxis])).astype(np.float32, copy=False)
        keep = nms(detections, FACE_NMS_THRESHOLD)
        if len(keep) == 0:
            return None, None, 0.0

        detections = detections[keep]
        landmarks_np = landmarks_np[keep]

        best_box = detections[0][:4].tolist()
        best_score = float(detections[0][4])
        best_landmarks = landmarks_np[0].reshape(5, 2).tolist()

        return tuple(best_box), best_landmarks, best_score

    def align_face_112x112(
        self,
        image: np.ndarray,
        landmarks: list[list[float]],
    ) -> np.ndarray | None:
        """Apply similarity transform to crop and warp face to 112x112 canonical reference."""
        try:
            pts = np.array(landmarks, dtype=np.float32)
            M, inliers = cv2.estimateAffinePartial2D(pts, self._reference_landmarks)
            if M is None:
                return None
            aligned = cv2.warpAffine(image, M, (112, 112), borderValue=0.0)
            return aligned
        except Exception as e:
            logger.debug("Affine alignment failed: %s", e)
            return None

    def extract_embedding_512d(self, aligned_112x112: np.ndarray) -> np.ndarray | None:
        """Extract 512D L2-normalized feature embedding via AuraFace v1."""
        if self.auraface_session is None or aligned_112x112 is None:
            return None

        try:
            # AuraFace standard preprocessing: RGB, scaled to [-1, 1], NCHW
            rgb = cv2.cvtColor(aligned_112x112, cv2.COLOR_BGR2RGB).astype(np.float32)
            normalized = (rgb - 127.5) / 127.5
            nchw = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...]

            input_name = self.auraface_session.get_inputs()[0].name
            raw_out = self.auraface_session.run(None, {input_name: nchw})[0]
            vec = raw_out.reshape(-1).astype(np.float32)

            norm = np.linalg.norm(vec)
            if norm < 1e-6:
                return None
            return vec / norm
        except Exception as e:
            logger.error("AuraFace inference exception: %s", e)
            return None

    def verify_against_templates(
        self,
        embedding: np.ndarray,
    ) -> tuple[str | None, float, str]:
        """
        Evaluate 512D embedding against pre-loaded employee templates via cosine similarity.
        Returns: (matched_employee_id, max_similarity, classification)
        """
        if not self._enrolled_templates:
            return None, 0.0, "unknown"

        best_id = None
        best_sim = -1.0

        for emp_id, tmpl in self._enrolled_templates.items():
            sim = float(np.dot(embedding, tmpl))
            if sim > best_sim:
                best_sim = sim
                best_id = emp_id

        if best_sim >= self.match_threshold:
            classification = "recognized"
        elif best_sim >= self.ambiguous_threshold:
            classification = "ambiguous"
        else:
            classification = "unknown"

        return best_id, best_sim, classification

    def process_person_crop(self, person_crop: np.ndarray) -> FaceRecognitionResult:
        """
        End-to-end face processing on a person bounding box crop:
        1. Detect face and 5 landmarks (RetinaFace)
        2. Warp to 112x112 canonical reference
        3. Extract 512D L2-normalized vector (AuraFace)
        4. Match against enrolled templates
        """
        box, landmarks, face_conf = self.detect_face_and_landmarks(person_crop)
        if box is None or landmarks is None:
            return FaceRecognitionResult(face_detected=False)

        aligned = self.align_face_112x112(person_crop, landmarks)
        if aligned is None:
            return FaceRecognitionResult(
                face_detected=True,
                face_box=box,
                face_confidence=face_conf,
                landmarks_5pts=landmarks,
                classification="no_face",
            )

        emb = self.extract_embedding_512d(aligned)
        if emb is None:
            return FaceRecognitionResult(
                face_detected=True,
                face_box=box,
                face_confidence=face_conf,
                landmarks_5pts=landmarks,
                aligned_crop=aligned,
                classification="no_face",
            )

        matched_id, max_sim, classification = self.verify_against_templates(emb)

        return FaceRecognitionResult(
            face_detected=True,
            face_box=box,
            face_confidence=face_conf,
            landmarks_5pts=landmarks,
            aligned_crop=aligned,
            embedding_512d=emb.tolist(),
            matched_employee_id=matched_id,
            max_similarity=max_sim,
            classification=classification,
        )
