"""Human-friendly name generation.

Generates names like 'swift-river' or 'calm-meadow' for sessions, plans, etc.
~150 adjectives × ~150 nouns = ~22,500 combinations.
"""

import random
import uuid

# fmt: off
ADJECTIVES = [
    # Nature/weather
    "autumn", "blazing", "breezy", "bright", "calm", "clear", "cloudy", "cold",
    "cool", "crisp", "damp", "dawn", "dewy", "dry", "dusk", "dusty", "fading",
    "fair", "fiery", "foggy", "frosty", "frozen", "glowing", "golden", "hazy",
    "icy", "light", "misty", "morning", "muddy", "pale", "rainy", "rising",
    "rosy", "shady", "snowy", "spring", "stormy", "summer", "sunny", "twilight",
    "warm", "windy", "winter",
    # Character/quality
    "agile", "bold", "brave", "bright", "brisk", "clever", "daring", "eager",
    "earnest", "easy", "fair", "faithful", "fancy", "fast", "fearless", "fierce",
    "fine", "firm", "fleet", "free", "fresh", "gentle", "glad", "good", "grand",
    "great", "happy", "hardy", "hasty", "hearty", "honest", "humble", "jolly",
    "keen", "kind", "lively", "loyal", "lucky", "merry", "mighty", "modest",
    "noble", "patient", "peaceful", "plain", "pleasant", "polite", "proud",
    "pure", "quick", "quiet", "rapid", "ready", "rich", "royal", "rustic",
    "safe", "sharp", "silent", "simple", "sleek", "slim", "smart", "smooth",
    "snug", "soft", "solid", "sound", "spare", "speedy", "spry", "stable",
    "stark", "steady", "still", "stout", "strong", "sturdy", "subtle", "sunny",
    "sure", "sweet", "swift", "tender", "tidy", "tight", "tough", "trim",
    "true", "vivid", "warm", "wary", "wild", "wise", "witty", "young",
    # Colors/materials
    "amber", "azure", "bronze", "copper", "coral", "crimson", "crystal", "cyan",
    "ebony", "emerald", "flint", "gold", "green", "grey", "indigo", "iron",
    "ivory", "jade", "marble", "navy", "oak", "olive", "pearl", "red", "ruby",
    "rusty", "sage", "sandy", "scarlet", "silver", "slate", "steel", "tawny",
    "violet", "white",
]

NOUNS = [
    # Landforms
    "arch", "basin", "bay", "beach", "bend", "bluff", "canyon", "cape", "cave",
    "cliff", "coast", "cove", "crater", "creek", "crest", "delta", "dune",
    "falls", "field", "fjord", "glade", "glen", "gorge", "grove", "gulf",
    "harbor", "heath", "hedge", "hill", "hollow", "inlet", "island", "knoll",
    "lagoon", "lake", "ledge", "marsh", "meadow", "mesa", "moor", "mount",
    "oasis", "pass", "path", "peak", "plain", "plateau", "pond", "prairie",
    "rapids", "ravine", "reef", "ridge", "river", "rock", "sand", "shore",
    "slope", "spring", "stream", "summit", "swamp", "trail", "vale", "valley",
    "vista",
    # Plants
    "acorn", "alder", "ash", "aspen", "birch", "bloom", "blossom", "bramble",
    "branch", "briar", "cedar", "clover", "elm", "fern", "flower", "forest",
    "garden", "grass", "hazel", "hedge", "holly", "ivy", "laurel", "leaf",
    "lilac", "lily", "lotus", "maple", "moss", "nettle", "oak", "orchid",
    "palm", "petal", "pine", "poplar", "reed", "root", "rose", "rowan",
    "sage", "seed", "shrub", "spruce", "thistle", "thorn", "tree", "tulip",
    "vine", "violet", "willow", "wood", "wren",
    # Sky/weather
    "aurora", "beam", "blaze", "breeze", "cloud", "comet", "dawn", "dew",
    "dusk", "dust", "eclipse", "ember", "flame", "flare", "flash", "fog",
    "frost", "gale", "glow", "hail", "haze", "light", "lightning", "mist",
    "moon", "orbit", "rain", "rainbow", "ray", "shade", "shadow", "sky",
    "sleet", "snow", "spark", "star", "storm", "sun", "sunset", "thunder",
    "tide", "twilight", "wave", "wind", "zenith",
    # Animals
    "badger", "bear", "bee", "bird", "crane", "crow", "deer", "dove", "drake",
    "eagle", "elk", "falcon", "finch", "fox", "frog", "gull", "hare", "hawk",
    "heron", "horse", "hound", "jay", "lark", "lion", "lynx", "otter", "owl",
    "pike", "raven", "robin", "salmon", "seal", "shrike", "snake", "sparrow",
    "spider", "stag", "swan", "swift", "thrush", "tiger", "trout", "turtle",
    "viper", "wolf", "wren",
]
# fmt: on


def generate_name() -> str:
    """Generate a human-friendly name like 'swift-river'."""
    adj = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    return f"{adj}-{noun}"


def generate_unique_name(existing: set[str]) -> str:
    """Generate a name that doesn't collide with existing ones.

    Args:
        existing: Set of names already in use

    Returns:
        A unique name
    """
    for _ in range(10):
        name = generate_name()
        if name not in existing:
            return name
    # Fallback: append random suffix to guarantee uniqueness
    return f"{generate_name()}-{uuid.uuid4().hex[:4]}"
