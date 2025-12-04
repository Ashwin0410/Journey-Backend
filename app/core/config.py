from pathlib import Path
from typing import List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _p(x: str) -> str:
    return str(Path(x).resolve())


class Cfg(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore", 
    )

   
    OPENAI_API_KEY: str             
    ELEVENLABS_API_KEY: str
    GOOGLE_MAPS_API_KEY: Optional[str] = None

   
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = (
        "http://localhost:8000/api/auth/google/callback"
    )

   
    FRONTEND_BASE_URL: str = "http://localhost:5174"

    
    JWT_SECRET_KEY: str = "change-this-in-env"   
    JWT_ALGORITHM: str = "HS256"

  
    CHILL_ROOT: str = "./chillsdb"
    OUT_DIR: str = "./app/out"
    PUBLIC_BASE_URL: str = "https://beta.rewire.bio"
    DB_URL: str = "sqlite:///./app/journey.db"

   
    ALLOWED_ORIGINS: List[str] = [
        "https://beta.rewire.bio",
        "https://rewire.bio",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8000",
        "http://127.0.0.1:5500",      
        "http://localhost:5500",      
        "http://localhost:8000",
    ]

    
    VOICE_INCEPTION_PRIMARY: Optional[str] = "qNkzaJoHLLdpvgh5tISm"
    VOICE_INCEPTION_SECONDARY: Optional[str] = "bU2VfAdiOb2Gv2eZWlFq"
    VOICE_INTERSTELLAR_PRIMARY: Optional[str] = "bU2VfAdiOb2Gv2eZWlFq"
    VOICE_INTERSTELLAR_SECONDARY: Optional[str] = "qNkzaJoHLLdpvgh5tISm"

  
    VOICE_THINK_PRIMARY: Optional[str] = "eL7xfWghif0oJwtmX2qs"
    VOICE_THINK_SECONDARY: Optional[str] = "Qggl4b0xRMiqOwhPtVWT"


    VOICE_JJ: Optional[str] = "9DY0k6JS3lZaUAIvDlAA"
    VOICE_SEVAN: Optional[str] = "bTEswxYhpv7UDkQg5VRu"
    VOICE_CARTER: Optional[str] = "bU2VfAdiOb2Gv2eZWlFq"

   
    FFMPEG_BIN: Optional[str] = None
    FFPROBE_BIN: Optional[str] = None

    @field_validator("CHILL_ROOT", "OUT_DIR", mode="before")
    @classmethod
    def _norm_paths(cls, v: str) -> str:
        try:
            return _p(v) if isinstance(v, str) else v
        except Exception:
            return v

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v]
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("[") and s.endswith("]"):
                try:
                    import json
                    arr = json.loads(s)
                    return [str(x).strip() for x in arr]
                except Exception:
                    pass
            return [x.strip() for x in s.split(",") if x.strip()]
        return ["http://localhost:5173", "http://localhost:8000"]

    @property
    def chill_root_path(self) -> Path:
        return Path(self.CHILL_ROOT)

    @property
    def out_dir_path(self) -> Path:
        return Path(self.OUT_DIR)


cfg = Cfg()
c = cfg
__all__ = ["cfg", "c", "Cfg"]
