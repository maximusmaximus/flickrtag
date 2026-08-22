"""Default tag vocabulary for CLIP zero-shot classification."""

# Organized by category for maintainability.
# Users can extend this with custom YAML files.

DEFAULT_TAGS: list[str] = [
    # Nature & Landscapes
    "landscape", "mountain", "ocean", "forest", "river", "waterfall", "sunset",
    "sunrise", "clouds", "sky", "flowers", "trees", "desert", "beach", "lake",
    "snow", "rain", "fog", "stars", "moon", "valley", "cliff", "meadow",
    "jungle", "glacier", "volcano", "cave", "coral reef", "field", "garden",
    # Animals
    "dog", "cat", "bird", "horse", "fish", "butterfly", "insect", "wildlife",
    "pet", "reptile", "bear", "deer", "eagle", "owl", "whale", "dolphin",
    "elephant", "lion", "tiger", "monkey", "rabbit", "fox", "wolf", "snake",
    # Urban & Architecture
    "city", "architecture", "building", "bridge", "street", "skyscraper",
    "graffiti", "neon", "skyline", "window", "door", "staircase", "alley",
    "rooftop", "tower", "cathedral", "mosque", "pagoda", "modern architecture",
    "ruins", "abandoned", "industrial", "construction", "tunnel",
    # People & Portraits
    "portrait", "group", "crowd", "child", "family", "couple", "silhouette",
    "hands", "eyes", "smile", "elderly", "baby", "self portrait", "candid",
    "fashion", "model", "musician", "artist", "worker",
    # Travel & Culture
    "landmark", "temple", "church", "castle", "market", "festival", "train",
    "airplane", "boat", "harbor", "lighthouse", "statue", "monument",
    "museum", "village", "countryside", "island", "resort", "camping",
    # Food & Drink
    "food", "restaurant", "coffee", "dessert", "fruit", "cooking", "kitchen",
    "wine", "beer", "bread", "sushi", "pizza", "cake", "cocktail",
    "street food", "breakfast", "dinner",
    # Art & Abstract
    "abstract", "pattern", "texture", "reflection", "shadow", "symmetry",
    "minimalist", "colorful", "monochrome", "vintage", "retro", "geometric",
    "mural", "sculpture", "painting", "graffiti art", "light art",
    # Activities & Sports
    "sport", "music", "dance", "concert", "wedding", "celebration", "workout",
    "yoga", "hiking", "cycling", "surfing", "skiing", "swimming", "running",
    "climbing", "skateboarding", "fishing", "sailing", "camping",
    "martial arts", "basketball", "soccer", "tennis",
    # Technology & Vehicles
    "computer", "phone", "car", "motorcycle", "robot", "drone", "camera",
    "bicycle", "truck", "bus", "helicopter", "spaceship", "satellite",
    # Weather & Seasons
    "spring", "summer", "autumn", "winter", "storm", "rainbow", "lightning",
    "frost", "ice", "haze", "wind", "tornado", "aurora",
    # Photography Styles & Techniques
    "macro", "long exposure", "aerial", "underwater", "panorama", "HDR",
    "bokeh", "black and white", "night photography", "golden hour",
    "blue hour", "double exposure", "time lapse", "infrared", "tilt shift",
    "street photography", "documentary", "fine art", "astrophotography",
    # Objects & Still Life
    "book", "clock", "candle", "mirror", "chair", "table", "lamp",
    "typewriter", "glasses", "hat", "umbrella", "key", "map", "compass",
    "backpack", "tent", "guitar", "piano", "violin",
    # Emotions & Concepts
    "solitude", "freedom", "mystery", "adventure", "tranquility", "chaos",
    "love", "hope", "nostalgia", "wonder", "danger", "serenity",
]
