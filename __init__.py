from .nodes import HeartMuLaLoader, HeartMuLaGenerator, HeartMuLaPreview

NODE_CLASS_MAPPINGS = {
    "HeartMuLaLoader": HeartMuLaLoader,
    "HeartMuLaGenerator": HeartMuLaGenerator,
    "HeartMuLaPreview": HeartMuLaPreview
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HeartMuLaLoader": "HeartMuLa Loader",
    "HeartMuLaGenerator": "HeartMuLa Generator",
    "HeartMuLaPreview": "HeartMuLa Preview/Save"
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
