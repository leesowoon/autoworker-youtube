"""Bori Universe - World definition and character registry.

The single source of truth for all characters, locations, and style rules.
All image/video generation must reference this to maintain consistency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class Character:
    """A character in the Bori universe."""

    id: str
    name_ko: str
    name_en: str
    species: str
    role: str
    family: str  # family group id
    appearance: str  # detailed visual description for AI prompts
    personality: str
    accessories: str  # key visual identifiers
    sheet_file: str  # filename in characters/ dir


@dataclass
class Location:
    """A location/background in the Bori universe."""

    id: str
    name_ko: str
    name_en: str
    description: str  # visual description for AI prompts
    mood: str  # lighting/atmosphere
    sheet_file: str = ""


@dataclass
class StyleGuide:
    """Art style rules for the universe."""

    eyes: str = "small round solid black dot eyes, NO sparkle, NO reflection"
    cheeks: str = "pink circle blush on both cheeks always visible"
    outline: str = "clean uniform black outline, consistent thickness"
    body_ratio: str = "head:body = 1:1, very round chubby proportions"
    colors: str = "flat solid colors only, NO gradients, NO shading, NO shadow"
    style: str = "Korean children's animation (Pororo-like), extremely simple and cute"
    background: str = "clean simple backgrounds, soft pastel colors"
    reference: str = "MUST match the exact art style from the reference images"

    def to_prompt(self) -> str:
        """Generate style specification string for AI prompts."""
        return f"""CRITICAL STYLE RULES (must follow exactly):
- Eyes: {self.eyes}
- Cheeks: {self.cheeks}
- Outline: {self.outline}
- Body ratio: {self.body_ratio}
- Colors: {self.colors}
- Style: {self.style}
- Background: {self.background}
- {self.reference}"""


# ============================================================
# Character Registry
# ============================================================

CHARACTERS: dict[str, Character] = {}
LOCATIONS: dict[str, Location] = {}
STYLE = StyleGuide()


def _register_characters():
    """Register all characters in the Bori universe."""
    chars = [
        # === 보리 가족 ===
        Character(
            id="bori", name_ko="보리", name_en="Bori",
            species="rabbit", role="protagonist", family="bori_family",
            appearance="small white rabbit with pure white fluffy fur, pink inner ears",
            personality="curious, warm-hearted, brave, loves exploring",
            accessories="yellow scarf around neck",
            sheet_file="bori_main.png",
        ),
        Character(
            id="bori_dad", name_ko="보리 아빠", name_en="Bori's Dad",
            species="rabbit", role="parent", family="bori_family",
            appearance="gray rabbit, slightly taller than Bori, round glasses",
            personality="kind, wise, patient carpenter",
            accessories="round glasses, green vest",
            sheet_file="bori_dad.png",
        ),
        Character(
            id="bori_mom", name_ko="보리 엄마", name_en="Bori's Mom",
            species="rabbit", role="parent", family="bori_family",
            appearance="white rabbit like Bori, slightly taller, warm maternal look",
            personality="warm, loving, great cook",
            accessories="pink apron, daisy flower headband",
            sheet_file="bori_mom.png",
        ),
        Character(
            id="ppori", name_ko="뽀리", name_en="Ppori",
            species="rabbit", role="sibling", family="bori_family",
            appearance="very tiny white rabbit, much smaller than Bori",
            personality="silly, cute, follows big brother everywhere",
            accessories="big red ribbon bow on head, no scarf",
            sheet_file="ppori.png",
        ),

        # === 도토리 가족 ===
        Character(
            id="dotori", name_ko="도토리", name_en="Dotori",
            species="squirrel", role="best_friend", family="dotori_family",
            appearance="brown squirrel with bushy striped tail",
            personality="shy but loyal, Bori's closest friend",
            accessories="acorn-shaped hat on head",
            sheet_file="dotori_main.png",
        ),
        Character(
            id="dotori_dad", name_ko="도토리 아빠", name_en="Dotori's Dad",
            species="squirrel", role="parent", family="dotori_family",
            appearance="dark brown squirrel, taller than Dotori",
            personality="hardworking, diligent forest mailman",
            accessories="leaf-shaped hat, delivery backpack",
            sheet_file="dotori_dad.png",
        ),
        Character(
            id="dotori_mom", name_ko="도토리 엄마", name_en="Dotori's Mom",
            species="squirrel", role="parent", family="dotori_family",
            appearance="light brown squirrel, same height as dad",
            personality="worries a lot, nags but full of love",
            accessories="purple muffler/scarf",
            sheet_file="dotori_mom.png",
        ),
        Character(
            id="dobam", name_ko="도밤", name_en="Dobam",
            species="squirrel", role="sibling", family="dotori_family",
            appearance="very small brown squirrel, much smaller than Dotori",
            personality="prankster, copies everything big brother does",
            accessories="half-acorn hat (tiny version of Dotori's)",
            sheet_file="dobam.png",
        ),

        # === 하늘이 가족 ===
        Character(
            id="haneul", name_ko="하늘이", name_en="Haneul",
            species="fox", role="friend", family="haneul_family",
            appearance="orange fox with pointy ears and fluffy tail",
            personality="clever, playful, idea maker",
            accessories="blue bow tie",
            sheet_file="haneul_main.png",
        ),
        Character(
            id="haneul_dad", name_ko="하늘이 아빠", name_en="Haneul's Dad",
            species="fox", role="parent", family="haneul_family",
            appearance="deep orange fox, taller than Haneul",
            personality="artistic, dreamy, creative village painter",
            accessories="black beret hat, paint brush",
            sheet_file="haneul_dad.png",
        ),
        Character(
            id="haneul_mom", name_ko="하늘이 엄마", name_en="Haneul's Mom",
            species="fox", role="parent", family="haneul_family",
            appearance="light orange fox, similar size to dad",
            personality="musical, elegant, village music teacher",
            accessories="yellow dress, music sheet",
            sheet_file="haneul_mom.png",
        ),
        Character(
            id="byeoli", name_ko="별이", name_en="Byeoli",
            species="fox", role="sibling", family="haneul_family",
            appearance="light orange fox, slightly taller than Haneul",
            personality="loves astronomy, dreams of being explorer",
            accessories="star-shaped hair pin, small telescope",
            sheet_file="byeoli.png",
        ),

        # === 곰디 가족 ===
        Character(
            id="gomdi", name_ko="곰디", name_en="Gomdi",
            species="bear", role="friend", family="gomdi_family",
            appearance="brown bear cub, chubby round body",
            personality="strong but gentle, reliable big brother type",
            accessories="red vest",
            sheet_file="gomdi_main.png",
        ),
        Character(
            id="gomdi_dad", name_ko="곰디 아빠", name_en="Gomdi's Dad",
            species="bear", role="parent", family="gomdi_family",
            appearance="large brown bear, much bigger than other characters",
            personality="quiet but deeply caring woodcutter",
            accessories="blue overalls/suspenders, axe on shoulder",
            sheet_file="gomdi_dad.png",
        ),
        Character(
            id="gomdi_mom", name_ko="곰디 엄마", name_en="Gomdi's Mom",
            species="bear", role="parent", family="gomdi_family",
            appearance="light brown bear, large like dad",
            personality="warm, cozy, village's best honey cook",
            accessories="checkered pattern apron",
            sheet_file="gomdi_mom.png",
        ),
        Character(
            id="gomsuni", name_ko="곰순이", name_en="Gomsuni",
            species="bear", role="sibling", family="gomdi_family",
            appearance="light brown bear, slightly taller than Gomdi",
            personality="caring, loves animals, future veterinarian",
            accessories="daisy flower hair decoration",
            sheet_file="gomsuni.png",
        ),

        # === 거북이 가족 ===
        Character(
            id="geobuki", name_ko="거북이", name_en="Geobuki",
            species="turtle", role="friend", family="geobuki_family",
            appearance="green turtle with hexagon shell pattern",
            personality="slow but wise, thoughtful advisor",
            accessories="small round glasses",
            sheet_file="geobuki_main.png",
        ),
        Character(
            id="geobuki_grandpa", name_ko="거북이 할아버지", name_en="Geobuki's Grandpa",
            species="turtle", role="elder", family="geobuki_family",
            appearance="dark green old turtle, larger than Geobuki",
            personality="oldest in village, knows many legends",
            accessories="big round glasses, long white beard, wooden walking cane",
            sheet_file="geobuki_grandpa.png",
        ),
        Character(
            id="geobuki_grandma", name_ko="거북이 할머니", name_en="Geobuki's Grandma",
            species="turtle", role="elder", family="geobuki_family",
            appearance="light green old turtle",
            personality="herb specialist, heals sick animals",
            accessories="small floral pattern shawl",
            sheet_file="geobuki_grandma.png",
        ),

        # === 마을 어른들 ===
        Character(
            id="owl_elder", name_ko="부엉이 할아버지", name_en="Owl Elder",
            species="owl", role="village_chief", family="village",
            appearance="brown owl with big round eyes behind glasses",
            personality="wise village chief and teacher",
            accessories="round glasses, brown vest, wooden walking cane",
            sheet_file="owl_elder.png",
        ),
        Character(
            id="hedgehog_auntie", name_ko="고슴도치 아줌마", name_en="Hedgehog Auntie",
            species="hedgehog", role="shopkeeper", family="village",
            appearance="cute round hedgehog with spines, beige body",
            personality="generous baker, gives free bread to kids",
            accessories="pink headscarf, white flour-dusted apron",
            sheet_file="hedgehog_auntie.png",
        ),
    ]

    for c in chars:
        CHARACTERS[c.id] = c


def _register_locations():
    """Register all locations in the Bori universe."""
    locs = [
        Location(
            id="bori_house", name_ko="보리의 버섯 집", name_en="Bori's Mushroom House",
            description="a cute red-and-white mushroom-shaped house with round door, flower garden, small fence, mailbox",
            mood="warm cozy morning light",
        ),
        Location(
            id="bori_room", name_ko="보리의 방", name_en="Bori's Room",
            description="cozy bedroom inside mushroom house, small bed with carrot pillow, window showing outside, bookshelf with picture books",
            mood="warm candlelight at night, soft moonlight through window",
        ),
        Location(
            id="forest_path", name_ko="마법의 숲길", name_en="Magic Forest Path",
            description="enchanted forest trail with tall colorful trees, wildflowers on both sides, butterflies, sunbeams filtering through leaves",
            mood="golden morning sunlight, dreamy atmosphere",
        ),
        Location(
            id="town_square", name_ko="숲속 광장", name_en="Forest Town Square",
            description="open grassy area with tree stumps as seats, small wooden stage, hanging lanterns, notice board",
            mood="bright cheerful daylight",
        ),
        Location(
            id="stream_bridge", name_ko="시냇물 다리", name_en="Crystal Stream Bridge",
            description="cute small arched wooden bridge over a sparkling clear stream, lily pads, dragonflies, smooth pebbles",
            mood="peaceful afternoon light with sparkles on water",
        ),
        Location(
            id="magic_tree", name_ko="마법 사과나무", name_en="Magic Apple Tree",
            description="a magnificent enormous apple tree with glowing sparkling red apples, golden magical particles in air",
            mood="magical golden glow, ethereal atmosphere",
        ),
        Location(
            id="bakery", name_ko="고슴도치 빵집", name_en="Hedgehog Bakery",
            description="a warm cozy bakery shaped like a bread loaf, display window showing pastries, chimney with bread-scented smoke",
            mood="warm golden interior light, inviting",
        ),
        Location(
            id="forest_rain", name_ko="비 오는 숲", name_en="Rainy Forest",
            description="the forest during gentle rain, puddles reflecting sky, mushroom umbrellas, rainbow forming in distance",
            mood="soft gray light with rainbow colors breaking through",
        ),
        Location(
            id="forest_snow", name_ko="겨울 숲", name_en="Snowy Forest",
            description="the forest in winter, snow on tree branches, frozen stream, soft snowfall, animal footprints in snow",
            mood="quiet peaceful white, soft cool blue tones",
        ),
        Location(
            id="forest_night", name_ko="밤의 숲", name_en="Night Forest",
            description="the forest at night, fireflies glowing, stars visible through tree canopy, crescent moon",
            mood="dark blue with warm firefly dots, magical nighttime",
        ),
    ]

    for loc in locs:
        LOCATIONS[loc.id] = loc


# Initialize on import
_register_characters()
_register_locations()


# ============================================================
# Universe API
# ============================================================

class BoriUniverse:
    """Main interface for the Bori Universe world-building system."""

    def __init__(self, assets_dir: Path | None = None):
        """Initialize with path to character sheet assets.

        Args:
            assets_dir: Directory containing character sheet PNGs.
                        If None, searches standard locations.
        """
        self.assets_dir = assets_dir or self._find_assets_dir()
        self.style = STYLE
        self.characters = CHARACTERS
        self.locations = LOCATIONS

    def _find_assets_dir(self) -> Path:
        """Find the character assets directory."""
        candidates = [
            Path("workspace/fairy_tale/universe/characters_v2"),
            Path("universe/characters"),
            Path.cwd() / "universe" / "characters",
        ]
        for c in candidates:
            if c.exists():
                return c
        # Create default
        default = Path("workspace/fairy_tale/universe/characters_v2")
        default.mkdir(parents=True, exist_ok=True)
        return default

    def get_character(self, char_id: str) -> Character | None:
        """Get a character by ID."""
        return self.characters.get(char_id)

    def get_characters_in_scene(self, char_ids: list[str]) -> list[Character]:
        """Get multiple characters for a scene."""
        return [self.characters[cid] for cid in char_ids if cid in self.characters]

    def get_character_sheet(self, char_id: str) -> Path | None:
        """Get the character sheet image path."""
        char = self.characters.get(char_id)
        if not char:
            return None
        path = self.assets_dir / char.sheet_file
        return path if path.exists() else None

    def get_reference_sheets(self, char_ids: list[str]) -> list[Path]:
        """Get character sheet paths for multiple characters (for AI reference)."""
        sheets = []
        for cid in char_ids:
            sheet = self.get_character_sheet(cid)
            if sheet:
                sheets.append(sheet)
        return sheets

    def get_location(self, loc_id: str) -> Location | None:
        """Get a location by ID."""
        return self.locations.get(loc_id)

    def build_scene_prompt(
        self,
        scene_description: str,
        char_ids: list[str],
        location_id: str | None = None,
        extra_direction: str = "",
    ) -> str:
        """Build a complete AI image prompt for a scene.

        Combines character descriptions, location, style guide, and scene direction
        into one comprehensive prompt.
        """
        parts = []

        # Scene description
        parts.append(f"Scene: {scene_description}")

        # Characters
        chars = self.get_characters_in_scene(char_ids)
        if chars:
            parts.append("\nCharacters in this scene:")
            for c in chars:
                parts.append(
                    f"- {c.name_en} ({c.name_ko}): {c.appearance}, "
                    f"wearing {c.accessories}. Personality: {c.personality}"
                )

        # Location
        if location_id:
            loc = self.get_location(location_id)
            if loc:
                parts.append(
                    f"\nLocation: {loc.name_en} ({loc.name_ko}) - {loc.description}"
                )
                parts.append(f"Atmosphere: {loc.mood}")

        # Extra direction
        if extra_direction:
            parts.append(f"\nDirection: {extra_direction}")

        # Style guide
        parts.append(f"\n{self.style.to_prompt()}")

        # Consistency reminder
        parts.append(
            "\nIMPORTANT: All characters MUST look exactly like their reference sheets. "
            "Same proportions, same colors, same accessories. 16:9 aspect ratio."
        )

        return "\n".join(parts)

    def get_family(self, family_id: str) -> list[Character]:
        """Get all characters in a family."""
        return [c for c in self.characters.values() if c.family == family_id]

    def get_main_cast(self) -> list[Character]:
        """Get the 5 main characters (kids)."""
        return [
            self.characters[cid]
            for cid in ["bori", "dotori", "haneul", "gomdi", "geobuki"]
        ]

    def list_all_characters(self) -> list[Character]:
        """List all characters."""
        return list(self.characters.values())

    def list_all_locations(self) -> list[Location]:
        """List all locations."""
        return list(self.locations.values())
