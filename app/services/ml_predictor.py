# app/services/ml_predictor.py
"""
ML Video Recommendation Service for ReWire

This service uses a pre-trained ONNX model to predict which YouTube videos
are most likely to induce chills (frisson) for a given user based on their
questionnaire responses.

The model takes personality trait scores and demographics as input and
outputs probability scores for 40 different video stimuli.

IMPORTANT: This follows the EXACT same methodology as the original app.py
from rewire-ml-app-main. Do not modify the prediction logic without
verifying against the original.
"""

import os
import re
import json
import logging
import unicodedata
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
import onnxruntime as rt

# Setup logging
logger = logging.getLogger(__name__)

# ============================================================================
# PATH CONFIGURATION
# ============================================================================

# Get the directory where this file is located
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Model files paths
ML_MODELS_DIR = os.path.join(BASE_DIR, "ml_models")
DATA_DIR = os.path.join(BASE_DIR, "data")

ONNX_MODEL_PATH = os.path.join(ML_MODELS_DIR, "final_global_mlp.onnx")
PREPROCESSOR_PATH = os.path.join(ML_MODELS_DIR, "preprocessor_minimal.joblib")
FEATURES_PATH = os.path.join(ML_MODELS_DIR, "minimal_features.json")
STIMULI_CSV_PATH = os.path.join(DATA_DIR, "Stimuli.csv")

# ============================================================================
# STIMULUS LIST (40 videos the model was trained on)
# Must match EXACTLY with original app.py
# ============================================================================

STIM = [
    "Great Dictator",
    "Think Too Much Feel Too Little (audio)",
    "Perfect Planet",
    "Aramaic (Audio)",
    "Unsung Hero (Thai Insurance)",
    "Interstellar",
    "Dead Poets",
    "Great Dictator (Audio)",
    "Dead Poets (Audio)",
    "Feynman (audio)",
    "Agnus Dei (Audio)",
    "Miserere Me (Audio)",
    "3rd Grade Drop Out (Audio)",
    "Unbroken (Audio)",
    "Laughing Heart (Audio)",
    "Hallelujah Choir (Audio)",
    "Jason Silva (Audio)",
    "Clair de Lune (Audio)",
    "Pale Blue Dot (Audio)",
    "Motorcycle Diaries (Audio)",
    "Pema Chodron (Audio)",
    "Duo Des Fleurs (Audio)",
    "Radiohead Reckoner (Audio)",
    "Sigur Ros - Hoppipolla (Audio)",
    "Wild Geese (Audio)",
    "Air France",
    "Be Kind",
    "Mr. Rogers Testimony",
    "Cloud Atlas",
    "A Thing About Life",
    "Remember the Titans",
    "Amelie",
    "Thai Medicine",
    "Muhammad Ali",
    "Italy Balconies",
    "Mr. Rogers Doc",
    "Hans Zimmer Time",
    "Rocky",
    "Think Too Much Feel Too Little",
    "Aramaic Choir",
]

# ============================================================================
# ALIASES FOR STIMULUS NAME MATCHING (from original app.py)
# ============================================================================

ALIASES = {
    "mr rogers testimony": ["mr rogers testimony", "mr rogers congress testimony", "mr rogers senate testimony"],
    "mr rogers doc": ["mr rogers documentary", "mr rogers doc"],
    "hans zimmer time": ["time hans zimmer", "hans zimmer time"],
    "sigur ros hoppipolla": ["sigur ros hoppipolla", "sigur ros hoppipolla audio", "sigur ros hoppipolla live"],
    "radiohead reckoner": ["radiohead reckoner"],
    "3rd grade drop out": ["3rd grade drop out", "third grade drop out"],
    "think too much feel too little": ["think too much feel too little", "think too much feel too little chaplin", "great dictator speech think too much"],
    "great dictator": ["the great dictator", "great dictator"],
    "dead poets": ["dead poets", "dead poets society"],
    "pale blue dot": ["pale blue dot", "carl sagan pale blue dot"],
    "feynman": ["feynman", "richard feynman", "feynman fun to imagine", "pleasure of finding things out", "fun to imagine", "the feynmann series - beauty (audio)"],
    "miserere me": ["miserere me", "miserere mei", "misere mei, deus (audio)"],
    "thai medicine": ["thai medicine", "thai medical ad", "thai hospital ad", "thai medicine ad"],
}

HARD_MAP = {
    "Feynman (audio)": "The Feynmann Series - Beauty (Audio)",
    "Miserere Me (Audio)": "Misere Mei, Deus (Audio)",
    "Thai Medicine": "Thai Medicine",
}

# ============================================================================
# CHILLS HEAD CONFIGURATION (from original app.py)
# ============================================================================

CHILLS_HEAD_ENV = os.getenv("REWIRE_CHILLS_HEAD_INDEX")
CHILLS_NAME_HINTS = ("chills", "chills_bin", "prob_chills", "head0")

# ============================================================================
# TEXT NORMALIZATION UTILITIES (from original app.py)
# ============================================================================

def nkey(s: Optional[str]) -> str:
    """Normalize string to key format (lowercase, alphanumeric only)."""
    if s is None:
        s = ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def canon(s: Optional[str]) -> str:
    """Canonicalize string for matching (lowercase, cleaned)."""
    if s is None:
        s = ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = s.replace("&", " and ").replace("'", "'").replace("'", "'").replace(""", "\"").replace(""", "\"")
    s = re.sub(r"\(audio\)", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def nm(x: str) -> str:
    """Normalize string to identifier format."""
    return re.sub(r"[^0-9a-zA-Z_]+", "_", str(x).strip())


def ag(x: Any) -> float:
    """
    Parse age from various formats (number, range, category).
    Exact copy from original app.py 'ag' function.
    """
    x = str(x or "").strip()
    try:
        return float(x)
    except:
        y = re.sub(r"\s+", "", x)
        m = re.match(r"^(\d+)[\-–](\d+)$", y)
        if m:
            return (float(m.group(1)) + float(m.group(2))) / 2.0
        m = re.match(r"^(\d+)\+$", y)
        if m:
            return float(m.group(1)) + 5.0
        d = {"18-24": 21, "25-34": 30, "35-44": 40, "45-54": 50, "55-64": 60, "65+": 70}
        return float(d.get(x, 0))


# ============================================================================
# PROBABILITY EXTRACTION UTILITIES (from original app.py)
# ============================================================================

def _choose_chills_head_index(outs: List[str]) -> int:
    """
    Choose which output head to use for chills probabilities.
    Exact copy from original app.py.
    """
    if CHILLS_HEAD_ENV is not None:
        try:
            i = int(CHILLS_HEAD_ENV)
            if 0 <= i < len(outs):
                return i
        except Exception:
            pass
    ln = [str(x).lower() for x in outs]
    for hint in CHILLS_NAME_HINTS:
        for i, n in enumerate(ln):
            if hint in n:
                return i
    return 0


def _extract_from_probabilities_struct(prob_output: Any) -> Optional[np.ndarray]:
    """
    Extract chills probabilities from various output structures.
    Exact copy from original app.py.
    """
    try:
        if not hasattr(prob_output, "__len__") or len(prob_output) != len(STIM):
            return None
        
        # Handle list of dicts
        if isinstance(prob_output[0], dict):
            chills = []
            for row in prob_output:
                found = None
                for key in ("Chills_bin", "chills_bin", "chills", "0", "head0", "H0"):
                    if key in row:
                        val = row[key]
                        if isinstance(val, (list, tuple, np.ndarray)) and len(val) >= 2:
                            found = float(val[1])
                        elif isinstance(val, (int, float)):
                            found = float(val)
                        break
                if found is None:
                    if "0" in row and isinstance(row["0"], (list, tuple, np.ndarray)) and len(row["0"]) >= 2:
                        found = float(row["0"][1])
                    elif "0" in row and isinstance(row["0"], (int, float)):
                        found = float(row["0"])
                    else:
                        for v in row.values():
                            if isinstance(v, (list, tuple, np.ndarray)) and len(v) >= 2:
                                found = float(v[1])
                                break
                            if isinstance(v, (int, float)):
                                found = float(v)
                                break
                chills.append(found if found is not None else 0.0)
            return np.asarray(chills, dtype=np.float32)
        
        # Handle list/tuple/array
        if isinstance(prob_output[0], (list, tuple, np.ndarray)):
            arr = np.asarray(prob_output)
            if arr.ndim == 2 and arr.shape[0] == len(STIM):
                return arr[:, 1].astype(np.float32)
            if arr.ndim == 3 and arr.shape[:2] == (len(STIM), 2):
                return arr[:, 1, 0].astype(np.float32)
        
        return None
    except Exception:
        return None


# ============================================================================
# ML PREDICTOR CLASS
# ============================================================================

class MLPredictor:
    """
    ML Video Recommendation Predictor
    
    Loads and manages the ONNX model for predicting video recommendations
    based on user questionnaire responses.
    
    Follows the exact same methodology as original app.py from rewire-ml-app-main.
    """
    
    def __init__(self):
        """Initialize the predictor by loading all required model files."""
        self._initialized = False
        self._error_message = None
        
        # Model components
        self.features: List[str] = []
        self.preprocessor = None
        self.session = None
        self.input_name = None
        
        # Stimuli data
        self.stimuli_df = None
        self.csv_idx: Dict[str, int] = {}
        self.csv_canon_rows: List[Tuple[int, str]] = []
        self.stim_to_csv_idx: Dict[int, int] = {}  # Maps STIM index to CSV row index
        
        try:
            self._load_all()
            self._initialized = True
            logger.info("MLPredictor initialized successfully")
        except Exception as e:
            self._error_message = str(e)
            logger.error(f"Failed to initialize MLPredictor: {e}")
    
    def _load_all(self):
        """Load all model components."""
        self._load_features()
        self._load_preprocessor()
        self._load_onnx_model()
        self._load_stimuli_csv()
        self._build_stimulus_mapping()
    
    def _load_features(self):
        """Load feature configuration from JSON."""
        if not os.path.exists(FEATURES_PATH):
            raise FileNotFoundError(f"Features file not found: {FEATURES_PATH}")
        
        with open(FEATURES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.features = data.get("features", [])
        logger.info(f"Loaded {len(self.features)} features: {self.features}")
    
    def _load_preprocessor(self):
        """Load sklearn preprocessor."""
        if not os.path.exists(PREPROCESSOR_PATH):
            raise FileNotFoundError(f"Preprocessor file not found: {PREPROCESSOR_PATH}")
        
        self.preprocessor = joblib.load(PREPROCESSOR_PATH)
        
        # Ensure required attributes exist (compatibility fix from original app.py)
        for attr, default in [("_name_to_fitted_passthrough", {}), ("_remainder", "drop")]:
            if not hasattr(self.preprocessor, attr):
                try:
                    setattr(self.preprocessor, attr, default)
                except Exception:
                    pass
        
        logger.info("Preprocessor loaded successfully")
    
    def _load_onnx_model(self):
        """Load ONNX model for inference."""
        if not os.path.exists(ONNX_MODEL_PATH):
            raise FileNotFoundError(f"ONNX model not found: {ONNX_MODEL_PATH}")
        
        self.session = rt.InferenceSession(
            ONNX_MODEL_PATH,
            providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name
        
        logger.info("ONNX model loaded successfully")
    
    def _load_stimuli_csv(self):
        """Load stimuli CSV with video URLs. Follows original app.py loadG() function."""
        if not os.path.exists(STIMULI_CSV_PATH):
            raise FileNotFoundError(f"Stimuli CSV not found: {STIMULI_CSV_PATH}")
        
        # Try utf-8 first, fallback to latin-1 (same as original)
        try:
            self.stimuli_df = pd.read_csv(STIMULI_CSV_PATH, encoding="utf-8")
        except Exception:
            self.stimuli_df = pd.read_csv(STIMULI_CSV_PATH, encoding="latin-1")
        
        # Clean column names (same as original)
        self.stimuli_df = self.stimuli_df.rename(
            columns={str(c).strip(): str(c).strip() for c in self.stimuli_df.columns}
        )
        
        # Find columns by pattern matching (same logic as original loadG)
        def nn(x):
            return re.sub(r"[^a-z0-9]+", "", str(x).lower())
        
        m = {nn(c): c for c in self.stimuli_df.columns}
        
        def pick(eq, ct):
            for k in eq:
                if k in m:
                    return m[k]
            for k in ct:
                for z, o in m.items():
                    if k in z:
                        return o
            return None
        
        cu = pick(["url", "youtube", "link", "video_url"], ["url", "youtube", "link", "video"])
        cn = pick(["train_name", "name", "title", "stimulus", "original", "item", "stimulusname"], 
                  ["train_name", "stimulusname", "title", "name", "stimulus"])
        cd = pick(["description", "desc"], ["description", "desc"])
        
        # Build standardized dataframe
        x = pd.DataFrame()
        x["url"] = self.stimuli_df[cu].astype(str) if cu else ""
        x["name"] = self.stimuli_df[cn].astype(str) if cn else ""
        x["desc"] = self.stimuli_df[cd].astype(str) if cd else ""
        
        # Fix URLs (same as original)
        def fx(u):
            u = (u or "").strip()
            if u and not u.lower().startswith(("http://", "https://")):
                return "https://" + u
            return u
        
        x["url"] = x["url"].apply(fx)
        x = x.fillna({"url": "", "name": "", "desc": ""})
        x = x[x["url"].astype(str).str.len() > 0].reset_index(drop=True)
        
        self.stimuli_df = x
        logger.info(f"Loaded {len(self.stimuli_df)} stimuli from CSV")
    
    def _try_match_name(self, cn: str) -> Optional[int]:
        """
        Try to match a canonical stimulus name to CSV row index.
        Exact copy of try_match_name from original app.py.
        """
        # Check hard-coded mappings first
        for train_name, csv_title in HARD_MAP.items():
            if cn == canon(train_name):
                target = canon(csv_title)
                if target in self.csv_idx:
                    return self.csv_idx[target]
        
        # Direct match
        if cn in self.csv_idx:
            return self.csv_idx[cn]
        
        # Check aliases
        for k, vs in ALIASES.items():
            if cn == k or cn in vs:
                for v in vs:
                    vv = canon(v)
                    if vv in self.csv_idx:
                        return self.csv_idx[vv]
        
        # Fuzzy token matching
        st = set(cn.split())
        best_i, best_s = None, -1.0
        for ri, cc in self.csv_canon_rows:
            toks = set(cc.split())
            if not toks:
                continue
            inter = len(st & toks)
            if inter == 0:
                continue
            s = inter / max(1, len(st))
            if s > best_s:
                best_s = s
                best_i = ri
        
        if best_i is not None and best_s >= 0.5:
            return best_i
        
        # Substring matching
        for ri, cc in self.csv_canon_rows:
            if cn in cc or cc in cn:
                return ri
        
        return None
    
    def _build_stimulus_mapping(self):
        """Build mapping from STIM indices to CSV rows. Same as original app.py."""
        # Build CSV index by canonical name
        for i in range(len(self.stimuli_df)):
            name = self.stimuli_df.iloc[i].get("name", "")
            c = canon(name)
            if c:
                self.csv_idx[c] = i
                self.csv_canon_rows.append((i, c))
        
        # Map each STIM entry to CSV row (same as original IDX building)
        for si, sname in enumerate(STIM):
            c = canon(sname)
            idx = self._try_match_name(c)
            if idx is not None:
                self.stim_to_csv_idx[si] = idx
        
        matched = len(self.stim_to_csv_idx)
        logger.info(f"Matched {matched}/{len(STIM)} stimuli to CSV entries")
    
    def _build_answer_maps(self, H: Dict[str, Any]) -> Dict[str, Any]:
        """Build normalized answer map for feature lookup. Same as original."""
        A = {}
        for k, v in H.items():
            A[nkey(k)] = v
        return A
    
    def _map_answers_to_features(self, H: Dict[str, Any]) -> List[float]:
        """
        Map user answers to feature vector.
        Exact copy of map_answers_to_features from original app.py.
        """
        HN = self._build_answer_maps(H)
        m = []
        
        for fk in self.features:
            if fk == "Age":
                v = ag(H.get("Age", ""))
                m.append(v)
            elif fk.lower() == "stimulus":
                m.append(0.0)
            else:
                vv = None
                if fk in H:
                    vv = H.get(fk, None)
                if vv is None:
                    vv = HN.get(nkey(fk), None)
                if vv is None and "_" in fk:
                    vv = HN.get(nkey(fk.replace("_", " ")), None)
                if vv is None and "-" in fk:
                    vv = HN.get(nkey(fk.replace("-", " ")), None)
                
                if vv is None:
                    m.append(0.0)
                else:
                    try:
                        v = float(vv)
                    except:
                        v = ag(vv)
                    m.append(v)
        
        return m
    
    def _to_40x_matrix(self, v: List[float]) -> np.ndarray:
        """
        Convert feature vector to 40-row matrix (one per stimulus).
        Exact copy of to40X from original app.py.
        """
        # Get expected column names from preprocessor
        if hasattr(self.preprocessor, "feature_names_in_"):
            z = list(self.preprocessor.feature_names_in_)
        else:
            z = list(self.features) + ["Stimulus"]
        
        # Build a row for each stimulus
        rows = []
        for i in range(len(STIM)):
            h = {}
            for fi, fk in enumerate(self.features):
                h[fk] = v[fi] if fi < len(v) else 0
            for stim_key in ("Stimulus", "stimulus", "item"):
                if stim_key in z:
                    h[stim_key] = STIM[i]
            rows.append(h)
        
        df = pd.DataFrame(rows)
        
        # Ensure stimulus column exists
        for stim_key in ("Stimulus", "stimulus", "item"):
            if stim_key in z and stim_key not in df.columns:
                df[stim_key] = [STIM[i] for i in range(len(STIM))]
        
        # Transform with preprocessor
        try:
            X = self.preprocessor.transform(df.reindex(columns=z, fill_value=0))
        except Exception:
            # Fallback: convert to numeric
            for k in df.columns:
                try:
                    df[k] = pd.to_numeric(df[k], errors="coerce")
                except:
                    pass
            df = df.fillna(0)
            X = self.preprocessor.transform(df.reindex(columns=z, fill_value=0))
        
        if hasattr(X, "toarray"):
            X = X.toarray()
        
        return np.asarray(X, dtype=np.float32)
    
    def _topk(self, v: List[float], k: int = 1) -> List[Dict[str, Any]]:
        """
        Get top K predictions.
        Exact copy of topk logic from original app.py.
        """
        X = self._to_40x_matrix(v)
        out_defs = self.session.get_outputs()
        outs = [o.name for o in out_defs]
        yl = self.session.run(outs, {self.input_name: X})
        
        # Extract probabilities - same logic as original
        p = None
        
        # Look for 'probabilities' output first
        prob_idx = None
        for i, n in enumerate(outs):
            if "probabilities" in str(n).lower():
                prob_idx = i
                break
        
        if prob_idx is not None:
            y = yl[prob_idx]
            
            if isinstance(y, (list, tuple)):
                try:
                    head0 = y[0]
                except Exception as ex:
                    raise RuntimeError(f"'probabilities' is a sequence but empty/invalid: type={type(y)}") from ex
                arr = np.asarray(head0)
                if arr.ndim == 2 and arr.shape[0] == len(STIM) and arr.shape[1] >= 2:
                    p = arr[:, 1].astype(np.float32)
                elif arr.ndim == 1 and arr.shape[0] == len(STIM):
                    p = arr.astype(np.float32)
                else:
                    raise RuntimeError(f"Unexpected shape for CHILLS head0: {arr.shape}; expected (40,2) or (40,).")
            else:
                p = _extract_from_probabilities_struct(y)
                if p is None:
                    arr = np.asarray(y)
                    if arr.ndim == 2 and arr.shape[0] == len(STIM) and arr.shape[1] >= 2:
                        p = arr[:, 1].astype(np.float32)
                    elif arr.ndim == 1 and arr.shape[0] == len(STIM):
                        p = arr.astype(np.float32)
                    else:
                        raise RuntimeError(f"Could not parse 'probabilities' output. shape={getattr(y, 'shape', None)}")
        
        # Fallback: use _choose_chills_head_index
        if p is None:
            hi = _choose_chills_head_index(outs)
            y = yl[hi]
            arr = np.asarray(y)
            if arr.ndim == 2 and arr.shape[0] == len(STIM) and arr.shape[1] >= 2:
                p = arr[:, 1].astype(np.float32)
            elif arr.ndim == 1 and arr.shape[0] == len(STIM):
                p = arr.astype(np.float32)
            else:
                p = _extract_from_probabilities_struct(y)
                if p is None:
                    raise RuntimeError(
                        f"Could not resolve CHILLS probabilities. chosen_head_idx={hi}, "
                        f"head_shape={getattr(y, 'shape', None)}, outs={outs}"
                    )
        
        # Add epsilon for stable sorting (same as original)
        eps = (np.arange(len(STIM)) * 1e-9).astype(np.float32)
        p = p + eps
        
        # Sort by probability (same logic as original)
        if np.max(p) - np.min(p) < 1e-6:
            z = (p - np.mean(p)) / (np.std(p) + 1e-9)
            idx = np.argsort(-z)[:k]
        else:
            idx = np.argsort(-p)[:k]
        
        # Build results (same as original)
        o = []
        for j in idx:
            j = int(j)
            n0 = STIM[j]
            
            if j in self.stim_to_csv_idx and 0 <= self.stim_to_csv_idx[j] < len(self.stimuli_df):
                r = self.stimuli_df.iloc[self.stim_to_csv_idx[j]]
                u0 = str(r.get("url", "")).strip()
                n1 = str(r.get("name", n0)).strip()
                d0 = str(r.get("desc", ""))
            else:
                u0 = ""
                n1 = n0
                d0 = ""
            
            if u0 and not u0.lower().startswith(("http://", "https://")):
                u0 = "https://" + u0
            
            sid = nm(n1)
            o.append({
                "idx": j,
                "score": float(p[j]),
                "stimulus_id": sid,
                "url": u0,
                "name": n1,
                "desc": d0
            })
        
        return o
    
    def predict_top_k(
        self,
        answers: Dict[str, Any],
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Predict top K video recommendations for a user.
        
        Args:
            answers: Dictionary of questionnaire answers. Expected keys:
                - DPES_1: int (1-7)
                - NEO-FFI_10: int (1-5)
                - NEO-FFI_46: int (1-5)
                - NEO-FFI_16: int (1-5)
                - Age: str or int
                (and any other features in minimal_features.json)
            k: Number of recommendations to return
        
        Returns:
            List of dictionaries with keys:
                - rank: int (1 = top recommendation)
                - stimulus_name: str
                - stimulus_url: str
                - stimulus_description: str
                - score: float (probability score)
                - idx: int (index in STIM list)
                - stimulus_id: str (normalized name)
        """
        if not self._initialized:
            raise RuntimeError(f"MLPredictor not initialized: {self._error_message}")
        
        # Map answers to feature vector
        feature_vector = self._map_answers_to_features(answers)
        
        # Get predictions using original topk logic
        results = self._topk(feature_vector, k=k)
        
        # Add rank and standardize output keys
        for i, r in enumerate(results, start=1):
            r["rank"] = i
            r["stimulus_name"] = r["name"]
            r["stimulus_url"] = r["url"]
            r["stimulus_description"] = r["desc"]
        
        return results
    
    def get_video_for_day(
        self,
        answers: Dict[str, Any],
        day_number: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get the video recommendation for a specific day.
        
        Args:
            answers: User's questionnaire answers
            day_number: Day number (1 = first day, 2 = second day, etc.)
        
        Returns:
            Single video recommendation dict, or None if day exceeds predictions
        """
        # Get enough predictions to cover the day
        k = min(day_number + 5, len(STIM))  # Get extra for safety
        predictions = self.predict_top_k(answers, k=k)
        
        if day_number <= len(predictions):
            video = predictions[day_number - 1]
            video["rank"] = 1  # For this day, it's the #1 recommendation
            return video
        
        return None
    
    @property
    def is_initialized(self) -> bool:
        """Check if predictor is ready for use."""
        return self._initialized
    
    @property
    def error_message(self) -> Optional[str]:
        """Get initialization error message if any."""
        return self._error_message
    
    def get_all_stimuli(self) -> List[Dict[str, str]]:
        """Get list of all available stimuli."""
        results = []
        for i, name in enumerate(STIM):
            url = ""
            description = ""
            if i in self.stim_to_csv_idx:
                csv_row = self.stim_to_csv_idx[i]
                if csv_row < len(self.stimuli_df):
                    row = self.stimuli_df.iloc[csv_row]
                    url = str(row.get("url", "")).strip()
                    description = str(row.get("desc", "")).strip()
            
            results.append({
                "index": i,
                "name": name,
                "url": url,
                "description": description
            })
        
        return results


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

# Create singleton instance for use throughout the app
_predictor_instance: Optional[MLPredictor] = None


def get_predictor() -> MLPredictor:
    """
    Get the singleton MLPredictor instance.
    
    Returns:
        MLPredictor instance (creates one if not exists)
    """
    global _predictor_instance
    
    if _predictor_instance is None:
        _predictor_instance = MLPredictor()
    
    return _predictor_instance


def predict_videos_for_user(
    answers: Dict[str, Any],
    k: int = 5
) -> List[Dict[str, Any]]:
    """
    Convenience function to predict videos for a user.
    
    Args:
        answers: User questionnaire answers
        k: Number of recommendations
    
    Returns:
        List of video recommendations
    """
    predictor = get_predictor()
    return predictor.predict_top_k(answers, k=k)


def get_video_for_user_day(
    answers: Dict[str, Any],
    day_number: int
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to get video for a specific day.
    
    Args:
        answers: User questionnaire answers
        day_number: Day number (1-indexed)
    
    Returns:
        Video recommendation for that day
    """
    predictor = get_predictor()
    return predictor.get_video_for_day(answers, day_number)
