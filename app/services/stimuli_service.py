# app/services/stimuli_service.py
"""
Stimuli Service for ReWire

This service provides access to the curated library of YouTube videos
(stimuli) that are used for chills/frisson induction therapy.

The service loads Stimuli.csv and provides convenient methods to:
- Get all stimuli
- Get stimulus by name or index
- Extract YouTube video IDs
- Search stimuli by keywords
"""

import os
import re
import logging
import unicodedata
from typing import Dict, List, Optional, Any

import pandas as pd

# Setup logging
logger = logging.getLogger(__name__)

# ============================================================================
# PATH CONFIGURATION
# ============================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STIMULI_CSV_PATH = os.path.join(DATA_DIR, "Stimuli.csv")

# ============================================================================
# TEXT NORMALIZATION UTILITIES
# ============================================================================

def normalize_text(s: Optional[str]) -> str:
    """Normalize text for comparison (lowercase, alphanumeric, spaces)."""
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_youtube_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from various URL formats.
    
    Supports:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/embed/VIDEO_ID
    - https://www.youtube.com/v/VIDEO_ID
    
    Args:
        url: YouTube URL
    
    Returns:
        Video ID string or None if not found
    """
    if not url:
        return None
    
    url = str(url).strip()
    
    # Pattern for youtu.be/VIDEO_ID
    match = re.search(r"youtu\.be/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    
    # Pattern for youtube.com/watch?v=VIDEO_ID
    match = re.search(r"youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    
    # Pattern for youtube.com/embed/VIDEO_ID
    match = re.search(r"youtube\.com/embed/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    
    # Pattern for youtube.com/v/VIDEO_ID
    match = re.search(r"youtube\.com/v/([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    
    # Fallback: try to find any 11-character alphanumeric string after youtube domain
    match = re.search(r"youtube\.com.*[?&/]([a-zA-Z0-9_-]{11})", url)
    if match:
        return match.group(1)
    
    return None


def get_youtube_embed_url(video_id: str) -> str:
    """
    Get YouTube embed URL for iframe.
    
    Args:
        video_id: YouTube video ID
    
    Returns:
        Embed URL string
    """
    return f"https://www.youtube.com/embed/{video_id}"


def get_youtube_thumbnail_url(video_id: str, quality: str = "hqdefault") -> str:
    """
    Get YouTube video thumbnail URL.
    
    Args:
        video_id: YouTube video ID
        quality: Thumbnail quality - 'default', 'hqdefault', 'mqdefault', 'sddefault', 'maxresdefault'
    
    Returns:
        Thumbnail URL string
    """
    return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"


# ============================================================================
# STIMULUS DATA CLASS
# ============================================================================

class Stimulus:
    """Represents a single stimulus (video) item."""
    
    def __init__(
        self,
        index: int,
        name: str,
        description: str,
        url: str
    ):
        self.index = index
        self.name = name
        self.description = description
        self.url = url
        self._video_id: Optional[str] = None
    
    @property
    def video_id(self) -> Optional[str]:
        """Get YouTube video ID (cached)."""
        if self._video_id is None:
            self._video_id = extract_youtube_id(self.url)
        return self._video_id
    
    @property
    def embed_url(self) -> Optional[str]:
        """Get YouTube embed URL for iframe."""
        vid = self.video_id
        if vid:
            return get_youtube_embed_url(vid)
        return None
    
    @property
    def thumbnail_url(self) -> Optional[str]:
        """Get video thumbnail URL."""
        vid = self.video_id
        if vid:
            return get_youtube_thumbnail_url(vid)
        return None
    
    @property
    def is_audio_only(self) -> bool:
        """Check if this is an audio-only stimulus."""
        return "(audio)" in self.name.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "index": self.index,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "video_id": self.video_id,
            "embed_url": self.embed_url,
            "thumbnail_url": self.thumbnail_url,
            "is_audio_only": self.is_audio_only
        }
    
    def __repr__(self) -> str:
        return f"Stimulus(index={self.index}, name='{self.name}')"


# ============================================================================
# STIMULI SERVICE CLASS
# ============================================================================

class StimuliService:
    """
    Service for accessing and managing stimuli data.
    
    Loads stimuli from Stimuli.csv and provides convenient access methods.
    """
    
    def __init__(self):
        """Initialize the service by loading stimuli data."""
        self._initialized = False
        self._error_message: Optional[str] = None
        
        self._stimuli: List[Stimulus] = []
        self._by_name: Dict[str, Stimulus] = {}
        self._by_normalized_name: Dict[str, Stimulus] = {}
        self._by_video_id: Dict[str, Stimulus] = {}
        
        try:
            self._load_stimuli()
            self._initialized = True
            logger.info(f"StimuliService initialized with {len(self._stimuli)} stimuli")
        except Exception as e:
            self._error_message = str(e)
            logger.error(f"Failed to initialize StimuliService: {e}")
    
    def _load_stimuli(self):
        """Load stimuli from CSV file."""
        if not os.path.exists(STIMULI_CSV_PATH):
            raise FileNotFoundError(f"Stimuli CSV not found: {STIMULI_CSV_PATH}")
        
        # Try utf-8 first, fallback to latin-1
        try:
            df = pd.read_csv(STIMULI_CSV_PATH, encoding="utf-8")
        except Exception:
            df = pd.read_csv(STIMULI_CSV_PATH, encoding="latin-1")
        
        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # Find columns by pattern matching
        def nn(x):
            return re.sub(r"[^a-z0-9]+", "", str(x).lower())
        
        col_map = {nn(c): c for c in df.columns}
        
        def find_col(exact_matches: List[str], contains_matches: List[str]) -> Optional[str]:
            for k in exact_matches:
                if k in col_map:
                    return col_map[k]
            for k in contains_matches:
                for col_norm, col_orig in col_map.items():
                    if k in col_norm:
                        return col_orig
            return None
        
        name_col = find_col(
            ["stimulusname", "name", "title"],
            ["name", "title", "stimulus"]
        )
        desc_col = find_col(
            ["description", "desc"],
            ["description", "desc"]
        )
        url_col = find_col(
            ["url", "youtube", "link"],
            ["url", "youtube", "link", "video"]
        )
        
        if not name_col:
            raise ValueError("Could not find name column in Stimuli.csv")
        if not url_col:
            raise ValueError("Could not find URL column in Stimuli.csv")
        
        # Load each row as a Stimulus
        for idx, row in df.iterrows():
            name = str(row.get(name_col, "")).strip()
            desc = str(row.get(desc_col, "")).strip() if desc_col else ""
            url = str(row.get(url_col, "")).strip()
            
            # Skip rows without name or URL
            if not name or not url:
                continue
            
            # Fix URL if needed
            if url and not url.lower().startswith(("http://", "https://")):
                url = "https://" + url
            
            stimulus = Stimulus(
                index=len(self._stimuli),
                name=name,
                description=desc,
                url=url
            )
            
            self._stimuli.append(stimulus)
            self._by_name[name] = stimulus
            self._by_normalized_name[normalize_text(name)] = stimulus
            
            if stimulus.video_id:
                self._by_video_id[stimulus.video_id] = stimulus
    
    @property
    def is_initialized(self) -> bool:
        """Check if service is ready for use."""
        return self._initialized
    
    @property
    def error_message(self) -> Optional[str]:
        """Get initialization error message if any."""
        return self._error_message
    
    @property
    def count(self) -> int:
        """Get total number of stimuli."""
        return len(self._stimuli)
    
    def get_all(self) -> List[Stimulus]:
        """
        Get all stimuli.
        
        Returns:
            List of all Stimulus objects
        """
        return self._stimuli.copy()
    
    def get_all_as_dicts(self) -> List[Dict[str, Any]]:
        """
        Get all stimuli as dictionaries (for API responses).
        
        Returns:
            List of stimulus dictionaries
        """
        return [s.to_dict() for s in self._stimuli]
    
    def get_by_index(self, index: int) -> Optional[Stimulus]:
        """
        Get stimulus by index.
        
        Args:
            index: Zero-based index
        
        Returns:
            Stimulus object or None if not found
        """
        if 0 <= index < len(self._stimuli):
            return self._stimuli[index]
        return None
    
    def get_by_name(self, name: str, fuzzy: bool = True) -> Optional[Stimulus]:
        """
        Get stimulus by name.
        
        Args:
            name: Stimulus name (exact or fuzzy match)
            fuzzy: If True, try normalized matching if exact match fails
        
        Returns:
            Stimulus object or None if not found
        """
        # Try exact match first
        if name in self._by_name:
            return self._by_name[name]
        
        if fuzzy:
            # Try normalized match
            normalized = normalize_text(name)
            if normalized in self._by_normalized_name:
                return self._by_normalized_name[normalized]
            
            # Try partial match
            for norm_name, stimulus in self._by_normalized_name.items():
                if normalized in norm_name or norm_name in normalized:
                    return stimulus
        
        return None
    
    def get_by_video_id(self, video_id: str) -> Optional[Stimulus]:
        """
        Get stimulus by YouTube video ID.
        
        Args:
            video_id: YouTube video ID (11 characters)
        
        Returns:
            Stimulus object or None if not found
        """
        return self._by_video_id.get(video_id)
    
    def get_by_url(self, url: str) -> Optional[Stimulus]:
        """
        Get stimulus by URL.
        
        Args:
            url: YouTube URL
        
        Returns:
            Stimulus object or None if not found
        """
        video_id = extract_youtube_id(url)
        if video_id:
            return self.get_by_video_id(video_id)
        return None
    
    def search(self, query: str, limit: int = 10) -> List[Stimulus]:
        """
        Search stimuli by query string.
        
        Searches in name and description.
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of matching Stimulus objects
        """
        query_norm = normalize_text(query)
        query_words = set(query_norm.split())
        
        results = []
        for stimulus in self._stimuli:
            name_norm = normalize_text(stimulus.name)
            desc_norm = normalize_text(stimulus.description)
            
            # Calculate simple relevance score
            score = 0
            
            # Exact name match
            if query_norm == name_norm:
                score += 100
            # Name contains query
            elif query_norm in name_norm:
                score += 50
            # Description contains query
            elif query_norm in desc_norm:
                score += 20
            else:
                # Word overlap
                name_words = set(name_norm.split())
                desc_words = set(desc_norm.split())
                
                name_overlap = len(query_words & name_words)
                desc_overlap = len(query_words & desc_words)
                
                if name_overlap > 0:
                    score += name_overlap * 10
                if desc_overlap > 0:
                    score += desc_overlap * 2
            
            if score > 0:
                results.append((score, stimulus))
        
        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        
        return [s for _, s in results[:limit]]
    
    def get_videos_only(self) -> List[Stimulus]:
        """
        Get only video stimuli (not audio-only).
        
        Returns:
            List of video Stimulus objects
        """
        return [s for s in self._stimuli if not s.is_audio_only]
    
    def get_audio_only(self) -> List[Stimulus]:
        """
        Get only audio-only stimuli.
        
        Returns:
            List of audio-only Stimulus objects
        """
        return [s for s in self._stimuli if s.is_audio_only]


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_service_instance: Optional[StimuliService] = None


def get_stimuli_service() -> StimuliService:
    """
    Get the singleton StimuliService instance.
    
    Returns:
        StimuliService instance (creates one if not exists)
    """
    global _service_instance
    
    if _service_instance is None:
        _service_instance = StimuliService()
    
    return _service_instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_all_stimuli() -> List[Dict[str, Any]]:
    """
    Get all stimuli as dictionaries.
    
    Returns:
        List of stimulus dictionaries
    """
    service = get_stimuli_service()
    return service.get_all_as_dicts()


def get_stimulus_by_name(name: str) -> Optional[Dict[str, Any]]:
    """
    Get stimulus by name.
    
    Args:
        name: Stimulus name
    
    Returns:
        Stimulus dictionary or None
    """
    service = get_stimuli_service()
    stimulus = service.get_by_name(name)
    return stimulus.to_dict() if stimulus else None


def get_stimulus_by_index(index: int) -> Optional[Dict[str, Any]]:
    """
    Get stimulus by index.
    
    Args:
        index: Zero-based index
    
    Returns:
        Stimulus dictionary or None
    """
    service = get_stimuli_service()
    stimulus = service.get_by_index(index)
    return stimulus.to_dict() if stimulus else None


def get_stimulus_by_video_id(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Get stimulus by YouTube video ID.
    
    Args:
        video_id: YouTube video ID
    
    Returns:
        Stimulus dictionary or None
    """
    service = get_stimuli_service()
    stimulus = service.get_by_video_id(video_id)
    return stimulus.to_dict() if stimulus else None


def search_stimuli(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search stimuli by query.
    
    Args:
        query: Search query
        limit: Maximum results
    
    Returns:
        List of matching stimulus dictionaries
    """
    service = get_stimuli_service()
    results = service.search(query, limit=limit)
    return [s.to_dict() for s in results]


def get_video_embed_url(stimulus_name: str) -> Optional[str]:
    """
    Get YouTube embed URL for a stimulus.
    
    Args:
        stimulus_name: Name of the stimulus
    
    Returns:
        Embed URL or None if not found
    """
    service = get_stimuli_service()
    stimulus = service.get_by_name(stimulus_name)
    return stimulus.embed_url if stimulus else None
