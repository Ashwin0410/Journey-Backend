"""
prompt.py — Schema Surgery Style Script Generation

Generates therapeutic audio scripts following the Schema Surgery research methodology:
- Direct second-person address (like Chaplin's Great Dictator speech)
- Schema Validation → Schema Contradiction structure
- Personalized to user's dominant maladaptive schema
- Designed to induce peak emotional experiences (chills) that shift schemas

Based on: Schoeller et al. "Schema Surgery: AI-generated Peak Positive Emotional 
Stimuli Deactivate Maladaptive Schema" (2024)
"""

from textwrap import dedent


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

SCHEMA_INFO = {
    "defectiveness_shame": {
        "name": "Defectiveness / Shame",
        "core_belief": "I am fundamentally flawed, unlovable, or worthless",
        "validation_themes": [
            "feeling inherently broken or defective",
            "hiding your true self for fear of rejection",
            "believing you are not worthy of love",
            "the exhaustion of performing 'normal'",
            "shame that lives in your bones",
        ],
        "contradiction_themes": [
            "your flaws are not the truth of you",
            "you were handed a story before you could refuse it",
            "worthiness is not earned — it exists",
            "the cracks are where light enters",
            "you are not what happened to you",
        ],
    },
    "failure": {
        "name": "Failure",
        "core_belief": "I am inadequate and will inevitably fail compared to others",
        "validation_themes": [
            "never feeling good enough no matter what you achieve",
            "the constant comparison to others",
            "believing success is for other people",
            "the weight of falling short again and again",
            "waiting for everyone to see you're a fraud",
        ],
        "contradiction_themes": [
            "your worth is not measured by output",
            "the voice that calls you failure learned someone else's words",
            "you have already survived things you thought would break you",
            "showing up imperfectly is still showing up",
            "you are not behind — you are exactly where you are",
        ],
    },
    "emotional_deprivation": {
        "name": "Emotional Deprivation",
        "core_belief": "My emotional needs will never be met by others",
        "validation_themes": [
            "the loneliness of being surrounded by people",
            "learning to need nothing so you wouldn't be disappointed",
            "caring for everyone else while running on empty",
            "the ache of never quite being seen",
            "teaching yourself that wanting is weakness",
        ],
        "contradiction_themes": [
            "your needs are not too much — they are human",
            "you learned to shrink, but you don't have to stay small",
            "there are people who want to know the real you",
            "receiving is not taking — it is allowing",
            "you are allowed to be held",
        ],
    },
    "abandonment_instability": {
        "name": "Abandonment / Instability",
        "core_belief": "People I love will leave me or let me down",
        "validation_themes": [
            "bracing for the goodbye that always comes",
            "holding people at arm's length to survive their leaving",
            "the hypervigilance of waiting for shoes to drop",
            "loving with one foot out the door",
            "trusting has never felt safe",
        ],
        "contradiction_themes": [
            "some people stay — and you are learning to let them",
            "your fear of loss is proof of your capacity to love",
            "you can survive endings and still risk beginnings",
            "not everyone will leave the way they did",
            "you are not too much to stay for",
        ],
    },
    "negativity_pessimism": {
        "name": "Negativity / Pessimism",
        "core_belief": "Things will go wrong; good things won't last",
        "validation_themes": [
            "waiting for the other shoe to drop",
            "not trusting good moments because they always end",
            "the exhaustion of bracing for disaster",
            "hope feeling dangerous, even naive",
            "scanning for what could go wrong",
        ],
        "contradiction_themes": [
            "your vigilance kept you safe, but you don't need armor everywhere",
            "good things are allowed to simply be good",
            "hope is not naive — it is courageous",
            "you can hold joy without waiting for it to be taken",
            "this moment is real, even if it changes",
        ],
    },
}

# Fallback for schemas not in the list (e.g., old data or custom entries)
DEFAULT_SCHEMA = {
    "name": "Self-Protection",
    "core_belief": "I must protect myself from pain",
    "validation_themes": [
        "building walls to stay safe",
        "the weight of carrying everything alone",
        "learning to expect less so you wouldn't be hurt",
    ],
    "contradiction_themes": [
        "your walls kept you alive, but you can choose doors now",
        "you are stronger than the stories you were told",
        "safety can exist alongside openness",
    ],
}


# =============================================================================
# INTENSITY / ARC SELECTION (replaces narrative arcs)
# =============================================================================

def choose_arc(j: dict) -> str:
    """
    Choose the emotional intensity profile for the speech.
    
    Instead of narrative arcs (man_in_a_hole, etc.), we now have
    speech intensity profiles that affect how quickly we move
    from validation to contradiction.
    
    Returns: "gradual", "intense", or "gentle"
    """
    mood = str(j.get("feeling") or "").lower()
    schema = str(j.get("schema_choice") or "").lower()
    chills_level = str(j.get("chills_level") or "").lower()
    had_chills = j.get("had_chills", False)
    day = j.get("journey_day")
    
    # If user had strong chills before, they respond to intensity
    if had_chills and chills_level == "high":
        return "intense"
    
    # Early days: be gentler
    if day and day <= 2:
        return "gradual"
    
    # If feeling very low, start gentler
    if any(k in mood for k in ["hopeless", "numb", "empty", "exhausted"]):
        return "gentle"
    
    # If feeling anxious/activated, use gradual build
    if any(k in mood for k in ["anxious", "restless", "overwhelmed"]):
        return "gradual"
    
    # Default to gradual (works for most)
    return "gradual"


def _get_intensity_guidance(intensity: str) -> str:
    """Return pacing guidance based on intensity profile."""
    
    if intensity == "intense":
        return """
    Pacing: Move through validation quickly (first 25%), then build with increasing 
    emotional intensity toward the contradiction. Use shorter, punchier sentences 
    as you approach the peak. The contradiction should feel like a wave crashing.
    """
    
    if intensity == "gentle":
        return """
    Pacing: Spend more time in validation (first 40%), with a soft, understanding tone.
    The contradiction should emerge gently, like sunrise — not dramatic, but undeniable.
    Use longer, flowing sentences. The peak should feel like relief, not intensity.
    """
    
    # Default: gradual
    return """
    Pacing: Balanced validation (first 30%) with steady build toward contradiction.
    Let the emotional intensity rise naturally. The peak should feel earned —
    a moment of clarity that lands because you've built to it honestly.
    """


# =============================================================================
# PERSONALIZATION CONTEXT BUILDERS
# =============================================================================

def _build_chills_context(j: dict) -> str:
    """
    Build a prompt section that incorporates chills-based personalization
    from the user's last session feedback.
    """
    emotion_word = j.get("emotion_word")
    chills_detail = j.get("chills_detail")
    last_insight = j.get("last_insight")
    chills_level = j.get("chills_level")
    had_chills = j.get("had_chills", False)
    
    if not had_chills and not last_insight:
        return ""
    
    lines = []
    
    if had_chills and emotion_word:
        lines.append(f"- Last session, they felt \"{emotion_word}\" at a peak moment. Echo this emotional frequency.")
    
    if chills_detail:
        detail_short = chills_detail[:200] + "..." if len(chills_detail) > 200 else chills_detail
        lines.append(f"- What triggered that moment: \"{detail_short}\". Weave similar language/imagery.")
    
    if last_insight:
        insight_short = last_insight[:200] + "..." if len(last_insight) > 200 else last_insight
        lines.append(f"- Their recent reflection: \"{insight_short}\". The speech should feel like a response to this.")
    
    if chills_level == "high":
        lines.append("- They respond strongly to emotional intensity. Include one line that could raise goosebumps.")
    elif chills_level == "medium":
        lines.append("- They respond to subtle, meaningful moments. Include quiet but resonant turns of phrase.")
    
    if not lines:
        return ""
    
    return "\n    Personalization from last session:\n    " + "\n    ".join(lines) + "\n"


def _build_therapist_guidance(j: dict) -> str:
    """
    Build a prompt section that incorporates therapist's AI guidance
    for this specific patient.
    """
    guidance = j.get("therapist_guidance")
    
    if not guidance or not guidance.strip():
        return ""
    
    # Truncate if excessively long
    if len(guidance) > 500:
        guidance = guidance[:500] + "..."
    
    return f"""
    Therapist guidance for this patient:
    The patient's therapist has provided specific guidance. Incorporate naturally:
    "{guidance}"
    """


def _get_schema_content(schema_key: str) -> dict:
    """Get schema info, with fallback for unknown schemas."""
    
    # Normalize the key
    key = (schema_key or "").lower().strip()
    
    # Direct match
    if key in SCHEMA_INFO:
        return SCHEMA_INFO[key]
    
    # Try partial matches for legacy/variant keys
    for k, v in SCHEMA_INFO.items():
        if key in k or k in key:
            return v
    
    # Check for keyword matches
    if any(word in key for word in ["defect", "shame", "unlov", "flaw"]):
        return SCHEMA_INFO["defectiveness_shame"]
    if any(word in key for word in ["fail", "inadequ", "not good"]):
        return SCHEMA_INFO["failure"]
    if any(word in key for word in ["depriv", "nurtur", "emption", "unseen"]):
        return SCHEMA_INFO["emotional_deprivation"]
    if any(word in key for word in ["abandon", "leave", "instab"]):
        return SCHEMA_INFO["abandonment_instability"]
    if any(word in key for word in ["negativ", "pessim", "doom", "worst"]):
        return SCHEMA_INFO["negativity_pessimism"]
    
    return DEFAULT_SCHEMA


# =============================================================================
# MAIN PROMPT BUILDER
# =============================================================================

def build(j: dict, target_words: int | None = None) -> str:
    """
    Build a prompt for generating a Schema Surgery style therapeutic speech.
    
    This generates a direct address (second-person "you") that:
    1. Validates the user's schema (acknowledges their pain)
    2. Contradicts the schema (offers a new truth)
    3. Builds to an emotional peak designed to induce chills
    
    Args:
        j: Dictionary with user context (schema, mood, chills history, etc.)
        target_words: Target word count for the script
    
    Returns:
        Prompt string for LLM
    """
    
    # Extract user context
    day = j.get("journey_day")
    mood = j.get("feeling", "present")
    body = j.get("body", "here")
    energy = j.get("energy", "steady")
    goal = j.get("goal_today", "show up")
    why = j.get("why_goal", "it matters")
    win = j.get("last_win", "you took a step forward")
    hard = j.get("hard_thing", "carrying weight")
    schema_key = j.get("schema_choice", "negativity_pessimism")
    
    # Get schema-specific content
    schema = _get_schema_content(schema_key)
    schema_name = schema["name"]
    core_belief = schema["core_belief"]
    validation_themes = schema["validation_themes"]
    contradiction_themes = schema["contradiction_themes"]
    
    # Get intensity profile
    intensity = j.get("arc_name") or choose_arc(j)
    intensity_guidance = _get_intensity_guidance(intensity)
    
    # Build personalization sections
    chills_context = _build_chills_context(j)
    therapist_guidance = _build_therapist_guidance(j)
    
    # Word count guidance
    length_hint = ""
    if target_words and target_words > 0:
        length_hint = f"- Write approximately {target_words} words (±10%).\n"
    
    # Format theme lists for the prompt
    validation_list = "\n      ".join(f"• {t}" for t in validation_themes)
    contradiction_list = "\n      ".join(f"• {t}" for t in contradiction_themes)
    
    return dedent(f"""
    Write a spoken therapeutic address for Journey Day {day or 1}.
    
    This is NOT a story about a character. This is a direct speech TO the listener.
    Think of Chaplin's Great Dictator speech — passionate, building, transformative.
    
    THE LISTENER'S SCHEMA: {schema_name}
    Core belief to address: "{core_belief}"
    
    Current state:
    - Feeling: {mood}
    - Body: {body}  
    - Energy: {energy}
    - Today's intention: {goal} (because {why})
    - Recent win: {win}
    - Current struggle: {hard}
    {chills_context}{therapist_guidance}
    === STRUCTURE: SCHEMA VALIDATION → SCHEMA CONTRADICTION ===
    
    PART 1 — VALIDATION (acknowledge their pain, make them feel deeply seen):
    Themes to draw from:
      {validation_list}
    
    In this section:
    - Speak directly to their experience: "I know what it's like to..."
    - Use "you" and "I" — this is intimate, not clinical
    - Name the feeling precisely — they should think "yes, exactly"
    - Don't rush past the pain; honor it
    - This builds trust before you ask them to believe something new
    
    PART 2 — CONTRADICTION (offer a new truth, build to emotional peak):
    Themes to draw from:
      {contradiction_list}
    
    In this section:
    - Pivot with conviction: "But here's what I need you to hear..."
    - Challenge the schema directly but with compassion
    - Build intensity through repetition and rhythm (like Chaplin: "You are not machines! You are not cattle! You are men!")
    - Include ONE powerful, memorable line near the peak — something they could carry with them
    - The peak should feel like breaking through, not lecturing
    
    PART 3 — LANDING (ground them gently, invite action):
    - Bring the energy down softly
    - Connect to their specific intention for today: "{goal}"
    - End with invitation, not instruction
    - Final line should feel like a gift, not a command
    
    {intensity_guidance}
    
    === VOICE & STYLE ===
    
    - Speak as a wise friend who has been through darkness, not as a therapist or coach
    - Use "I" statements that show you understand: "I've been there", "I know this place"
    - Use "you" to address them directly throughout
    - Vary sentence length: short punchy lines for impact, longer flowing lines for reflection
    - Use concrete imagery over abstract concepts
    - Repetition for emphasis is powerful (use sparingly but deliberately)
    - NO psychoeducation, NO explaining depression, NO clinical language
    - NO phrases like "it's okay to feel", "be kind to yourself", "self-care" — these are hollow
    - Write like poetry that happens to be spoken, not like a script that tries to sound poetic
    - Warm, raw, human. Not polished corporate wellness content.
    
    === TECHNICAL REQUIREMENTS ===
    
    {length_hint}- Use the literal token "[pause]" where silence adds power (4-8 times total)
      Place [pause] after emotionally significant lines, at transitions, before the peak moment
    - Output ONLY spoken words and [pause] tokens
    - No stage directions, no [music], no descriptions
    - Must end on a complete thought with proper punctuation
    - Do NOT repeat sentences or key phrases — each line should be unique
    - Avoid cliché endings like "one step at a time" or "you've got this"
    
    === WHAT SUCCESS LOOKS LIKE ===
    
    The listener should:
    1. Feel seen in the validation ("how do they know exactly what this feels like?")
    2. Feel something shift during the contradiction (goosebumps, tears, a catch in the throat)
    3. Feel quietly hopeful at the end — not fixed, but less alone
    
    Write the speech now. Begin directly with the opening line — no preamble.
    """).strip()


# =============================================================================
# EXPORTS (maintain same interface as original)
# =============================================================================

__all__ = ["build", "choose_arc", "SCHEMA_INFO"]
