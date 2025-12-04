# # app/services/prompt.py
# from textwrap import dedent

# def build(j: dict) -> str:
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters to you today")
#     win = j.get("last_win", "you followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     local = (
#         f"In {pc}, consider a small nearby action. "
#         f"If outside, notice air and distant sounds; if inside, notice the light and your breath."
#         if pc else
#         "Consider a small nearby action. If outside, notice air and distant sounds; if inside, notice the light and your breath."
#     )

#     # **No stage directions**: explicitly forbid lines like "soft music", "[music]", "(music)" etc.
#     return dedent(f"""
#     Write a 90–120 second **second-person** spoken script for a supportive audio message.
#     Constraints:
#     - Do NOT include any stage directions or bracketed cues (no lines like [music], (music), "soft music begins", "sound of...", etc.).
#     - Output only the spoken words that a voice would say to the user.
#     - Warm, grounded, concise; natural cadence; use short sentences; sparingly use pauses as commas—no bracket tags.

#     Personalization:
#     - Current feeling: "{mood}", body: "{body}", energy: "{energy}", location: "{place}".
#     - Recently went well: "{win}".
#     - Today’s helpful step: "{goal}" because "{why}".
#     - Hard thing lately: "{hard}".
#     - Schema to gently validate first and then lightly reframe once: "{schema}".
#     - Local hint: "{local}".

#     Structure:
#     - 1) Warm validation of their experience and schema.
#     - 2) Gentle reframe (one time), linking meaning ("{why}") to today’s action ("{goal}").
#     - 3) Brief present-moment grounding (sensory focus; no bracketed cues).
#     - 4) One tiny implementation-intention prompt (when/where/how).
#     - 5) Close with one **present-tense** affirmation (one short sentence).
#     """).strip()
# app/services/prompt.py

# Best Code
# from textwrap import dedent

# def _day_theme(d: int | None) -> str:
#     if d == 1:
#         return ("Tone: cinematic rise from hardship; validate schema/negative emotion; "
#                 "acknowledge tough odds; shift to species-level hope; set week goals aligned to BA life areas.")
#     if d == 2:
#         return ("Tone: reflective psychoeducation on how the schema narrowed life; "
#                 "create distance from past; introduce new perspectives; end with today's concrete actions.")
#     if d == 3:
#         return ("Tone: expansion and discovery; brief relapse is okay; savor small wins; "
#                 "life is short yet long; possibilities widen; childlike curiosity; then focus on next action.")
#     if d == 4:
#         return ("Tone: long-form recovery tale; from darkness to light; belonging and community; "
#                 "others walked this path; contemplate progress and what's ahead; resolve to continue.")
#     if d == 5:
#         return ("Tone: emergence and rebirth; celebrate the week's successes; "
#                 "grieve the former self; welcome the new identity; gratitude and possibility.")
#     return ("Tone: grounded, warm, cinematic; validate schema then gentle contradiction; connect meaning to action; "
#             "avoid cringe; metaphor over instruction; universal 'we' over 'you' where natural.")

# def build(j: dict) -> str:
#     d = j.get("journey_day")
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters to you today")
#     win = j.get("last_win", "you followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     local = (
#         f"In {pc}, consider a small nearby action. "
#         f"If outside, notice air and distant sounds; if inside, notice the light and your breath."
#         if pc else
#         "Consider a small nearby action. If outside, notice air and distant sounds; if inside, notice the light and your breath."
#     )
#     theme = _day_theme(d)

#     # No stage directions. Output only spoken words.
#     return dedent(f"""
#     Write a ~100–120 second second-person spoken script for Journey Day {d or 0}.
#     {theme}
#     Constraints:
#     - Do NOT include any stage directions or bracketed cues (no [music], (music), "soft music begins", SFX, etc.).
#     - Output only spoken words.
#     - Warm, grounded, concise; short sentences; natural cadence; no bracket tags.

#     Personalization:
#     - Feeling "{mood}", body "{body}", energy "{energy}", location "{place}".
#     - Recent win: "{win}".
#     - Today's action: "{goal}" because "{why}".
#     - Hard thing: "{hard}".
#     - Validate schema "{schema}" first, then gently contradict once.
#     - Local hint: "{local}".

#     Structure:
#     1) Warm validation of their experience and schema.
#     2) Gentle reframe once, linking meaning ("{why}") to today’s action ("{goal}").
#     3) Brief present-moment grounding (sensory; no bracket cues).
#     4) One tiny implementation intention (when/where/how).
#     5) End with one present-tense affirmation (one short sentence).
#     """).strip()
# app/services/prompt.py

# Best code
# from textwrap import dedent

# def _day_theme(d: int | None) -> str:
#     if d == 1:
#         return ("Tone: cinematic rise from hardship; validate schema/negative emotion; "
#                 "acknowledge tough odds; shift to species-level hope; set week goals aligned to BA life areas.")
#     if d == 2:
#         return ("Tone: reflective psychoeducation on how the schema narrowed life; "
#                 "create distance from past; introduce new perspectives; end with today's concrete actions.")
#     if d == 3:
#         return ("Tone: expansion and discovery; brief relapse is okay; savor small wins; "
#                 "life is short yet long; possibilities widen; childlike curiosity; then focus on next action.")
#     if d == 4:
#         return ("Tone: long-form recovery tale; from darkness to light; belonging and community; "
#                 "others walked this path; contemplate progress and what's ahead; resolve to continue.")
#     if d == 5:
#         return ("Tone: emergence and rebirth; celebrate the week's successes; "
#                 "grieve the former self; welcome the new identity; gratitude and possibility.")
#     return ("Tone: grounded, warm, cinematic; validate schema then gentle contradiction; connect meaning to action; "
#             "avoid cringe; prefer metaphor; use inclusive “we” naturally.")

# def build(j: dict, target_words: int | None = None) -> str:
#     """
#     target_words: approximate desired length to match music duration; we forbid repetition
#     to prevent looped content.
#     """
#     d = j.get("journey_day")
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters to you today")
#     win = j.get("last_win", "you followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     local = (
#         f"In {pc}, consider a small nearby action. "
#         f"If outside, notice air and distant sounds; if inside, notice the light and your breath."
#         if pc else
#         "Consider a small nearby action. If outside, notice air and distant sounds; if inside, notice the light and your breath."
#     )
#     theme = _day_theme(d)

#     length_hint = ""
#     if target_words and target_words > 0:
#         length_hint = f"- Write ~{target_words} words (±10%).\n"

#     # Strict anti-repetition rules stop the LLM from reusing lines to “pad” the length.
#     return dedent(f"""
#     Write a single continuous second-person spoken script for Journey Day {d or 0}.
#     {theme}
#     Constraints:
#     {length_hint}- Output only spoken words (no stage directions; no [music], (music), SFX, etc.).
#     - Absolutely NO repetition of sentences, phrases, or ideas. Each sentence must add new meaning.
#     - No filler, no summaries of what you already said, no “as I said” references.
#     - Warm, grounded, concise sentences with natural cadence. Avoid cringe.
#     - End with a decisive, single closing sentence.

#     Personalization:
#     - Feeling "{mood}", body "{body}", energy "{energy}", location "{place}".
#     - Recent win: "{win}".
#     - Today's action: "{goal}" because "{why}".
#     - Hard thing: "{hard}".
#     - Validate schema "{schema}" once, then gently contradict once.
#     - Local hint: "{local}".

#     Structure:
#     1) Warm validation of their experience and schema.
#     2) Gentle reframe once, linking meaning ("{why}") to today’s action ("{goal}").
#     3) Brief present-moment grounding (sensory; no bracket cues).
#     4) One tiny implementation intention (when/where/how).
#     5) Close with one present-tense affirmation (one short sentence).
#     """).strip()


# Best code till now
# from textwrap import dedent

# def _day_theme(d: int | None) -> str:
#     if d == 1:
#         return ("Tone: cinematic rise from hardship; validate schema/negative emotion; "
#                 "acknowledge tough odds; shift to species-level hope; set week goals aligned to BA life areas.")
#     if d == 2:
#         return ("Tone: reflective psychoeducation on how the schema narrowed life; "
#                 "create distance from past; introduce new perspectives; end with today's concrete actions.")
#     if d == 3:
#         return ("Tone: expansion and discovery; brief relapse is okay; savor small wins; "
#                 "life is short yet long; possibilities widen; childlike curiosity; then focus on next action.")
#     if d == 4:
#         return ("Tone: long-form recovery tale; from darkness to light; belonging and community; "
#                 "others walked this path; contemplate progress and what's ahead; resolve to continue.")
#     if d == 5:
#         return ("Tone: emergence and rebirth; celebrate the week's successes; "
#                 "grieve the former self; welcome the new identity; gratitude and possibility.")
#     return ("Tone: grounded, warm, cinematic; validate schema then gentle contradiction; connect meaning to action; "
#             "avoid cringe; prefer metaphor; use inclusive “we” naturally.")

# def build(j: dict, target_words: int | None = None) -> str:
#     """
#     target_words: approximate desired length to match music duration; mixer will do a tiny,
#     pitch-preserving retime if needed to hit exact end alignment.
#     """
#     d = j.get("journey_day")
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters to you today")
#     win = j.get("last_win", "you followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     local = (
#         f"In {pc}, consider a small nearby action. "
#         f"If outside, notice air and distant sounds; if inside, notice the light and your breath."
#         if pc else
#         "Consider a small nearby action. If outside, notice air and distant sounds; if inside, notice the light and your breath."
#     )
#     theme = _day_theme(d)

#     length_hint = ""
#     if target_words and target_words > 0:
#         length_hint = f"- Write ~{target_words} words (±10%).\n"

#     # Strict anti-repetition rules stop the LLM from reusing lines to “pad” the length.
#     return dedent(f"""
#     Write a single continuous second-person spoken script for Journey Day {d or 0}.
#     {theme}
#     Constraints:
#     {length_hint}- Output only spoken words (no stage directions; no [music], (music), SFX, etc.).
#     - Absolutely NO repetition of sentences, phrases, or ideas. Each sentence must add new meaning.
#     - No filler, no summaries of what you already said, no “as I said” references.
#     - Warm, grounded, concise sentences with natural cadence. Avoid cringe.
#     - End with a decisive, single closing sentence.

#     Personalization:
#     - Feeling "{mood}", body "{body}", energy "{energy}", location "{place}".
#     - Recent win: "{win}".
#     - Today's action: "{goal}" because "{why}".
#     - Hard thing: "{hard}".
#     - Validate schema "{schema}" once, then gently contradict once.
#     - Local hint: "{local}".

#     Structure:
#     1) Warm validation of their experience and schema.
#     2) Gentle reframe once, linking meaning ("{why}") to today’s action ("{goal}").
#     3) Brief present-moment grounding (sensory; no bracket cues).
#     4) One tiny implementation intention (when/where/how).
#     5) Close with one present-tense affirmation (one short sentence).
#     """).strip()



# from textwrap import dedent

# def _day_theme(d: int | None) -> str:
#     if d == 1:
#         return ("Tone: cinematic rise from hardship; validate schema/negative emotion; "
#                 "acknowledge tough odds; shift to species-level hope; set week goals aligned to BA life areas.")
#     if d == 2:
#         return ("Tone: reflective psychoeducation on how the schema narrowed life; "
#                 "create distance from past; introduce new perspectives; end with today's concrete actions.")
#     if d == 3:
#         return ("Tone: expansion and discovery; brief relapse is okay; savor small wins; "
#                 "life is short yet long; possibilities widen; childlike curiosity; then focus on next action.")
#     if d == 4:
#         return ("Tone: long-form recovery tale; from darkness to light; belonging and community; "
#                 "others walked this path; contemplate progress and what's ahead; resolve to continue.")
#     if d == 5:
#         return ("Tone: emergence and rebirth; celebrate the week's successes; "
#                 "grieve the former self; welcome the new identity; gratitude and possibility.")
#     return ("Tone: grounded, warm, cinematic; validate schema then gentle contradiction; connect meaning to action; "
#             "avoid cringe; prefer metaphor; use inclusive “we” naturally.")


# def build(j: dict, target_words: int | None = None) -> str:
#     """
#     target_words: approximate desired length to match the SPOKEN portion of the music.
#     The mixer will do a tiny, pitch-preserving retime if needed to hit exact end alignment.
#     """
#     d = j.get("journey_day")
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters to you today")
#     win = j.get("last_win", "you followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     music_ms = j.get("music_ms")
#     spoken_target_ms = j.get("spoken_target_ms")

#     local = (
#         f"In {pc}, consider a small nearby action. "
#         f"If outside, notice air and distant sounds; if inside, notice the light and your breath."
#         if pc else
#         "Consider a small nearby action. If outside, notice air and distant sounds; if inside, notice the light and your breath."
#     )
#     theme = _day_theme(d)

#     length_hint = ""
#     if target_words and target_words > 0:
#         length_hint = f"- Write ~{target_words} words (±10%).\n"

#     timing_hint = ""
#     if music_ms and spoken_target_ms:
#         timing_hint = (
#             "- Imagine the music has a gentle build in the first third, a stronger build in the middle, "
#             "and a more cinematic swell/drop around the last third.\n"
#         )

#     # We now explicitly allow [pause] markers for timing with the music and TTS.
#     return dedent(f"""
#     Write a single continuous second-person spoken script for Journey Day {d or 0}.
#     {theme}
#     Constraints:
#     {length_hint}{timing_hint}- Output only spoken words. You MAY use the literal token "[pause]" occasionally where a slightly longer silence fits the emotion or music.
#     - No other stage directions or bracketed cues (no [music], SFX, etc.).
#     - Absolutely NO repetition of sentences, phrases, or ideas. Each sentence must add new meaning.
#     - No filler, no summaries of what you already said, no “as I said” references.
#     - Warm, grounded, concise sentences with natural cadence. Avoid cringe.
#     - End with a decisive, single closing sentence (no trailing fragments).

#     Personalization:
#     - Feeling "{mood}", body "{body}", energy "{energy}", location "{place}".
#     - Recent win: "{win}".
#     - Today's action: "{goal}" because "{why}".
#     - Hard thing: "{hard}".
#     - Validate schema "{schema}" once, then gently contradict once.
#     - Local hint: "{local}".

#     High-level pacing (to align with music):
#     - The first 1–2 spoken lines should feel like they come in after a short music-only intro: keep them short, simple, and spacious. You can place "[pause]" between a couple of early sentences to imply slower pacing.
#     - In the middle section, allow the pacing to pick up slightly: sentences can grow a bit longer and feel more fluid while still clear.
#     - Near the emotional “climax” (roughly two-thirds into the script), include ONE clearly cinematic, punchy sentence that feels like a turning point (e.g. “And then, everything began to turn around.”). After that line, you may add a "[pause]" to let it land.
#     - In the final section, gently land the energy and move toward a calm, grounded close.

#     Structure:
#     1) Warm validation of their experience and schema.
#     2) Gentle reframe once, linking meaning ("{why}") to today’s action ("{goal}").
#     3) Brief present-moment grounding (sensory; no bracket cues other than optional "[pause]").
#     4) One tiny implementation intention (when/where/how).
#     5) A short closing affirmation in the present tense (one short sentence).
#     """).strip()

#--------------------------------------------------------------------------------------------------
# from textwrap import dedent

# def _day_theme(d: int | None) -> str:
#     if d == 1:
#         return ("Tone: cinematic rise from hardship; validate schema/negative emotion; "
#                 "acknowledge tough odds; shift to species-level hope; set week goals aligned to BA life areas.")
#     if d == 2:
#         return ("Tone: reflective psychoeducation on how the schema narrowed life; "
#                 "create distance from past; introduce new perspectives; end with today's concrete actions.")
#     if d == 3:
#         return ("Tone: expansion and discovery; brief relapse is okay; savor small wins; "
#                 "life is short yet long; possibilities widen; childlike curiosity; then focus on next action.")
#     if d == 4:
#         return ("Tone: long-form recovery tale; from darkness to light; belonging and community; "
#                 "others walked this path; contemplate progress and what's ahead; resolve to continue.")
#     if d == 5:
#         return ("Tone: emergence and rebirth; celebrate the week's successes; "
#                 "grieve the former self; welcome the new identity; gratitude and possibility.")
#     return ("Tone: grounded, warm, cinematic; validate schema/negative emotion; then gentle contradiction; "
#             "connect meaning to action; avoid cringe; prefer metaphor; use inclusive “we” naturally.")


# def build(j: dict, target_words: int | None = None) -> str:
#     """
#     target_words: approximate desired length to match the SPOKEN portion of the music.
#     """
#     d = j.get("journey_day")
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters to you today")
#     win = j.get("last_win", "you followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     music_ms = j.get("music_ms")
#     spoken_target_ms = j.get("spoken_target_ms")
#     drop_ms = j.get("drop_ms")  # may be None if analysis failed

#     local = (
#         f"In {pc}, consider a small nearby action. "
#         f"If outside, notice air and distant sounds; if inside, notice the light and your breath."
#         if pc else
#         "Consider a small nearby action. If outside, notice air and distant sounds; if inside, notice the light and your breath."
#     )
#     theme = _day_theme(d)

#     length_hint = ""
#     if target_words and target_words > 0:
#         length_hint = f"- Write ~{target_words} words (±10%).\n"

#     timing_hint = ""
#     if music_ms and spoken_target_ms:
#         timing_hint = (
#             "- Imagine the music has a gentle build in the first third, a stronger build in the middle, "
#             "and a more cinematic swell/drop around the last third.\n"
#         )

#     drop_hint = ""
#     if isinstance(drop_ms, int) and drop_ms > 0 and music_ms:
#         frac = drop_ms / max(1, music_ms)
#         # rough human description
#         if frac < 0.4:
#             pos = "fairly early in the track"
#         elif frac < 0.7:
#             pos = "around the middle of the track"
#         else:
#             pos = "toward the later part of the track"
#         drop_hint = (
#             f"- There is a musical “drop” or stronger change in energy {pos}. "
#             "Place ONE clearly cinematic, punchy sentence shortly BEFORE that emotional high point, "
#             "so it feels like a turning point right before the music hits.\n"
#         )

#     # New: general wisdom tone, limited direct address
#     return dedent(f"""
#     Write a single continuous spoken script for Journey Day {d or 0}.
#     Speak in a warm, cinematic, reflective tone.

#     Voice & perspective:
#     - Mostly speak in general, universal statements (e.g. “Sometimes we…”, “There are moments when…”).
#     - Only some sentences (no more than about one in four) may directly address the listener as “you”.
#     - When you do say “you”, keep it gentle and invitational, never bossy or commanding.
#     - Never sound like you are giving strict instructions; prefer reflections, observations, and gentle invitations.

#     Constraints:
#     {length_hint}{timing_hint}{drop_hint}- Output only spoken words. You MAY use the literal token "[pause]" occasionally where a slightly longer silence fits the emotion or music.
#     - No other stage directions or bracketed cues (no [music], SFX, etc.).
#     - Absolutely NO repetition of sentences, phrases, or ideas. Each sentence must add new meaning.
#     - No filler, no summaries of what you already said, no “as I said” references.
#     - Warm, grounded, concise sentences with natural cadence. Avoid cringe.

#     Personalization:
#     - Feeling "{mood}", body "{body}", energy "{energy}", location "{place}".
#     - Recent win: "{win}".
#     - Today's action: "{goal}" because "{why}".
#     - Hard thing: "{hard}".
#     - Validate schema "{schema}" once, then gently contradict once.
#     - Local hint: "{local}".

#     High-level pacing (to align with music):
#     - The first 1–2 spoken lines should feel like they come in after a short music-only intro: keep them short, simple, and spacious. You can place "[pause]" between a couple of early sentences to imply slower pacing.
#     - In the middle section, allow the pacing to pick up slightly: sentences can grow a bit longer and feel more fluid while still clear.
#     - Near the emotional “climax”, include ONE clearly cinematic, punchy sentence that feels like a turning point (for example: “And then, everything began to turn around.”). Immediately after that line, you may add a "[pause]" to let it land.
#     - In the final section, gently land the energy and move toward a calm, grounded close.

#     Structure:
#     1) Warm validation of the experience and schema (mostly in general terms, not only directed at one person).
#     2) Gentle reframe once, linking meaning ("{why}") to today's action ("{goal}") without sounding like a command.
#     3) Brief present-moment grounding (sensory; no bracket cues other than optional "[pause]").
#     4) One tiny, softly-phrased implementation intention (a gentle suggestion of when/where/how, not an order).
#     5) A short closing affirmation in the present tense (one short sentence), which can be either general (“There is always room to begin again.”) or very gently addressed to the listener.
#     """).strip()
#----------------------------------------------------------------------------------------------
# from textwrap import dedent

# def _day_theme(d: int | None) -> str:
#     # Story-based tone variants per day
#     if d == 1:
#         return ("Opening chapter of a recovery story; the character is still close to hardship, "
#                 "but there is a quiet sense that something is beginning to shift.")
#     if d == 2:
#         return ("Reflective, like the character looking back on how their old patterns and schemas "
#                 "kept life small, while gently noticing how tiny actions start to open things up.")
#     if d == 3:
#         return ("Expansion and discovery; the character experiments, stumbles a bit, "
#                 "and finds small surprising moments of relief or connection.")
#     if d == 4:
#         return ("Long-form recovery tale; darkness to light; the character realises they are not alone, "
#                 "and that community, routines, and meaning slowly grew around them.")
#     if d == 5:
#         return ("Emergence and rebirth; the character can see both who they were and who they are becoming, "
#                 "with gratitude, grief, and quiet confidence coexisting.")
#     return ("Grounded, warm, cinematic story; subtle emotional depth without being preachy or didactic; "
#             "prefer metaphor and scenes over explanations; avoid textbook psychoeducation.")


# def build(j: dict, target_words: int | None = None) -> str:
#     """
#     target_words: approximate desired length to match the SPOKEN portion of the music.
#     """
#     d = j.get("journey_day")
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters today")
#     win = j.get("last_win", "they followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     music_ms = j.get("music_ms")
#     spoken_target_ms = j.get("spoken_target_ms")
#     drop_ms = j.get("drop_ms")  # may be None if analysis failed

#     local = (
#         f"In {pc}, a small nearby action feels possible. "
#         f"If they are outside, there are hints of air and distant sounds; if they are inside, there is light and breath."
#         if pc else
#         "A small nearby action feels possible. Outside there might be air and distant sounds; inside there is light and breath."
#     )
#     theme = _day_theme(d)

#     length_hint = ""
#     if target_words and target_words > 0:
#         length_hint = f"- Write ~{target_words} words (±10%).\n"

#     timing_hint = ""
#     if music_ms and spoken_target_ms:
#         timing_hint = (
#             "- Imagine the music has a gentle build in the first third, a stronger build in the middle, "
#             "and a more cinematic swell/drop around the last third.\n"
#         )

#     drop_hint = ""
#     if isinstance(drop_ms, int) and drop_ms > 0 and music_ms:
#         frac = drop_ms / max(1, music_ms)
#         if frac < 0.4:
#             pos = "fairly early in the track"
#         elif frac < 0.7:
#             pos = "around the middle of the track"
#         else:
#             pos = "toward the later part of the track"
#         drop_hint = (
#             f"- There is a musical “drop” or stronger change in energy {pos}. "
#             "Place ONE clearly cinematic, punchy sentence shortly BEFORE that emotional high point, "
#             "so it feels like a turning point right before the music hits.\n"
#         )

#     return dedent(f"""
#     Write a single continuous spoken script for Journey Day {d or 0}.
#     Speak in a warm, cinematic, reflective tone.

#     Overall tone for this story:
#     - {theme}

#     Core idea:
#     - Tell ONE short story about ONE fictional person whose inner world and struggles mirror the listener.
#     - The entire story happens within ONE slice of ONE day (for example, a morning and a short walk on the same day).
#     - Do NOT restart the day, jump to a completely new time, or start a second story later on.

#     Character and setting:
#     - The character is living with schema "{schema}", feeling "{mood}" in their body ("{body}"), with "{energy}" energy today.
#     - They are in a setting similar to "{place}" and roughly located near: {local}
#     - Today they try a small concrete action: "{goal}" because "{why}".
#     - They have had a recent small win: "{win}".
#     - The hard thing in the background is: "{hard}".

#     Voice & perspective:
#     - Use third person almost all the time (for example: "They wake up with a familiar heaviness...").
#     - Do NOT give the character a specific name; refer to them only as "they" / "them".
#     - Do NOT explain psychology, diagnoses, or symptoms. No textbook psychoeducation and no "sometimes we feel anxious" style lines.
#     - Show inner experience through scenes, sensations, and small choices instead of explaining it.
#     - Avoid imperative or prescriptive language (no "you should...", "do this...", "take a break now...").
#     - Only in the final 1–2 sentences, you MAY gently turn toward the listener with a single "you" sentence, as an invitation (not a command).
#     - Avoid repeating distinctive emotional words or metaphors. If you use a rare word (like "trepidation"), use it at most once.

#     Constraints:
#     {length_hint}{timing_hint}{drop_hint}- Output only spoken words. You MAY use the literal token "[pause]" occasionally where a slightly longer silence fits the emotion or music.
#     - No other stage directions or bracketed cues (no [music], SFX, etc.).
#     - Absolutely NO repetition of sentences, phrases, or ideas. Each sentence must add new meaning.
#     - No filler, no summaries of what you already said, no "as I said" references.
#     - Warm, grounded, concise sentences with natural cadence. Avoid cringe.
#     - Once the emotional arc has clearly landed and the closing image is given, STOP. Do not start a new paragraph, a new morning, or a new apartment after the ending.

#     Use of personalization:
#     - Weave the recent win "{win}" into the story as a quiet sign that change is already happening.
#     - Let the small action "{goal}" appear in one or two very concrete scenes (e.g., where they are, what time of day, what they actually do).
#     - Acknowledge schema "{schema}" only once, as something that used to narrow the character's world.
#     - Gently contradict it once by showing the character doing something that doesn’t fit the schema.
#     - Keep everything anchored in this one character’s lived day; no generic motivational speech.

#     High-level pacing (to align with music):
#     - Opening: a spacious beginning with short lines that drop us straight into a moment in the character’s day. Allow room for the music, maybe with one early "[pause]".
#     - Middle: the character experiments with their small action and notices subtle shifts (internal or external). Let the rhythm build a little here.
#     - Emotional "climax": include ONE clearly cinematic, punchy sentence that feels like a turning point in the story, shortly before the musical high point. You may place a "[pause]" immediately after it so it can land.
#     - Closing: gently land the story in a calmer, grounded place. The last one or two sentences can hint that the listener might carry something similar into their own day, using at most one "you" sentence.

#     Structure:
#     1) Introduce the character in the present, with their mood, body state, and energy.
#     2) Briefly touch on how life used to feel when schema "{schema}" drove everything, using one or two concrete memories.
#     3) Follow them through one small, specific action related to "{goal}", and show why it matters today ("{why}").
#     4) Let them notice a subtle shift or moment of meaning (a look, a breath, a sound, a thought) that contradicts the schema.
#     5) End with a short, grounded closing that feels like a soft invitation rather than advice.
#     """).strip()




# from textwrap import dedent

# # ---------- Emotional arc model (from story-shape paper) ----------

# # We keep the numeric curves for future use / experimentation if needed.
# # For now we mainly use the *qualitative* shapes in the prompt.
# EMOTIONAL_ARCS = {
#     "rags_to_riches":      [0.20, 0.30, 0.40, 0.55, 0.70, 0.80, 0.90, 1.00],
#     "tragedy":             [0.80, 0.75, 0.70, 0.60, 0.45, 0.35, 0.25, 0.15],
#     "man_in_a_hole":       [0.60, 0.50, 0.35, 0.25, 0.40, 0.60, 0.75, 0.85],
#     "icarus":              [0.30, 0.45, 0.60, 0.80, 0.90, 0.70, 0.45, 0.30],
#     "cinderella":          [0.30, 0.45, 0.65, 0.50, 0.35, 0.55, 0.75, 0.95],
#     "oedipus":             [0.70, 0.55, 0.35, 0.25, 0.50, 0.70, 0.60, 0.30],
# }


# def _arc_info(name: str) -> dict:
#     """
#     Qualitative descriptions + pacing guidance for each emotional arc.
#     """
#     name = name or "man_in_a_hole"
#     mapping = {
#         "rags_to_riches": {
#             "label": "Rags to riches",
#             "one_liner": "starts from heaviness and gradually rises toward strength, connection, and possibility.",
#             "pacing": (
#                 "- In the opening third, stay closer to the difficulty, letting the world feel tight and heavy.\n"
#                 "- In the middle third, let small experiments and subtle hope appear in concrete scenes.\n"
#                 "- In the final third, let the emotional space feel a bit wider and more grounded, with gentle relief "
#                 "and possibility (not a magical fix)."
#             ),
#         },
#         "tragedy": {
#             "label": "Tragedy",
#             "one_liner": "starts more level or hopeful and slowly moves into weight, complexity, and acceptance.",
#             "pacing": (
#                 "- In the opening third, allow some light or normality with hints of tension.\n"
#                 "- In the middle third, let the complexity and cost of their patterns become clearer.\n"
#                 "- In the final third, move toward a heavier but honest acceptance, with a calm, grounded tone "
#                 "instead of despair."
#             ),
#         },
#         "man_in_a_hole": {
#             "label": "Man in a hole",
#             "one_liner": "drops into a difficult place and then climbs back out into relief and a more workable day.",
#             "pacing": (
#                 "- In the opening third, let the character feel like they are sliding into the 'hole' of their pattern.\n"
#                 "- In the middle third, show one or two small actions or realizations that help them start climbing out.\n"
#                 "- In the final third, let them reach a noticeably better emotional place, still real and imperfect, "
#                 "but lighter than where they began."
#             ),
#         },
#         "icarus": {
#             "label": "Icarus",
#             "one_liner": "rises into intensity and power, then gently comes down and integrates what happened.",
#             "pacing": (
#                 "- In the opening third, let the energy and drive build, with a sense of \"maybe this is it\".\n"
#                 "- In the middle third, allow an emotional or situational peak that feels almost too bright or intense.\n"
#                 "- In the final third, gently bring things down into integration, honesty, and a more sustainable pace."
#             ),
#         },
#         "cinderella": {
#             "label": "Cinderella",
#             "one_liner": "rises, dips briefly, then rises higher than before into a more stable, earned hope.",
#             "pacing": (
#                 "- In the opening third, let something unexpectedly good or kind begin to appear.\n"
#                 "- In the middle, include a wobble or setback that briefly pulls the mood down without erasing the gains.\n"
#                 "- In the final third, let the character feel more rooted in a new, slightly larger life than they had before."
#             ),
#         },
#         "oedipus": {
#             "label": "Oedipus",
#             "one_liner": "moves through difficulty and insight and ends in a grounded but not purely 'happy' place.",
#             "pacing": (
#                 "- In the opening third, let the weight and confusion be clearly felt.\n"
#                 "- In the middle third, bring in one or two sharp realisations or truths that change how they see their story.\n"
#                 "- In the final third, settle into a more honest, complex emotional place with some stability and self-respect."
#             ),
#         },
#     }
#     return mapping.get(name, mapping["man_in_a_hole"])


# def choose_arc(j: dict) -> str:
#     """
#     Choose an emotional arc based on intake fields.
#     This is simple, hand-tuned logic and can be refined with Felix later.
#     """
#     mood = str(j.get("feeling") or "").lower()
#     hard = str(j.get("hard_thing") or "").lower()
#     goal = str(j.get("goal_today") or "").lower()
#     schema = str(j.get("schema_choice") or "").lower()
#     day = j.get("journey_day")

#     # Heavier / stuck moods -> upward journeys
#     if any(k in mood for k in ["stuck", "hopeless", "empty", "worthless", "numb"]):
#         return "rags_to_riches"

#     # Shame / guilt / defectiveness -> fall-then-rise journey
#     if any(k in mood for k in ["ashamed", "guilty", "failure", "embarrassed"]) or \
#        any(k in schema for k in ["defectiveness", "shame"]):
#         return "man_in_a_hole"

#     # High activation plus fear -> Icarus
#     if any(k in mood for k in ["excited", "pumped", "energised", "energized"]) and \
#        any(k in mood for k in ["afraid", "scared", "anxious", "nervous"]):
#         return "icarus"

#     # Processing / insight-focused days -> Oedipus
#     if any(k in goal for k in ["understand", "make sense", "see pattern"]) or \
#        "pattern" in hard or "why i" in hard:
#         return "oedipus"

#     # Grief and loss -> tragedy-style arc
#     if any(k in hard for k in ["loss", "grief", "bereavement", "breakup", "break-up"]):
#         return "tragedy"

#     # Rebirth / second chance language -> Cinderella
#     if any(k in goal for k in ["restart", "second chance", "new start", "fresh start"]):
#         return "cinderella"

#     # Optionally: bias by journey_day (early days more upward arcs)
#     if day == 1:
#         return "rags_to_riches"
#     if day == 2:
#         return "man_in_a_hole"

#     # Safe, flexible default
#     return "man_in_a_hole"


# def _day_theme(d: int | None) -> str:
#     # Story-based tone variants per day
#     if d == 1:
#         return ("Opening chapter of a recovery story; the character is still close to hardship, "
#                 "but there is a quiet sense that something is beginning to shift.")
#     if d == 2:
#         return ("Reflective, like the character looking back on how their old patterns and schemas "
#                 "kept life small, while gently noticing how tiny actions start to open things up.")
#     if d == 3:
#         return ("Expansion and discovery; the character experiments, stumbles a bit, "
#                 "and finds small surprising moments of relief or connection.")
#     if d == 4:
#         return ("Long-form recovery tale; darkness to light; the character realises they are not alone, "
#                 "and that community, routines, and meaning slowly grew around them.")
#     if d == 5:
#         return ("Emergence and rebirth; the character can see both who they were and who they are becoming, "
#                 "with gratitude, grief, and quiet confidence coexisting.")
#     return ("Grounded, warm, cinematic story; subtle emotional depth without being preachy or didactic; "
#             "prefer metaphor and scenes over explanations; avoid textbook psychoeducation.")


# def build(j: dict, target_words: int | None = None) -> str:
#     """
#     target_words: approximate desired length to match the SPOKEN portion of the music.
#     We now also condition on an explicit emotional arc (Reagan et al. style).
#     """
#     d = j.get("journey_day")
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters today")
#     win = j.get("last_win", "they followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     # Emotional arc selection: either provided by caller, or chosen here.
#     arc_name = j.get("arc_name") or choose_arc(j)
#     arc = _arc_info(arc_name)
#     arc_label = arc["label"]
#     arc_one = arc["one_liner"]
#     arc_pacing = arc["pacing"]

#     music_ms = j.get("music_ms")
#     spoken_target_ms = j.get("spoken_target_ms")
#     drop_ms = j.get("drop_ms")  # may be None if analysis failed

#     local = (
#         f"In {pc}, a small nearby action feels possible. "
#         f"If they are outside, there are hints of air and distant sounds; if they are inside, there is light and breath."
#         if pc else
#         "A small nearby action feels possible. Outside there might be air and distant sounds; inside there is light and breath."
#     )
#     theme = _day_theme(d)

#     length_hint = ""
#     if target_words and target_words > 0:
#         length_hint = f"- Write ~{target_words} words (±10%).\n"

#     timing_hint = ""
#     if music_ms and spoken_target_ms:
#         timing_hint = (
#             "- Imagine the music has a gentle build in the first third, a stronger build in the middle, "
#             "and a more cinematic swell/drop around the last third.\n"
#         )

#     drop_hint = ""
#     if isinstance(drop_ms, int) and drop_ms > 0 and music_ms:
#         frac = drop_ms / max(1, music_ms)
#         if frac < 0.4:
#             pos = "fairly early in the track"
#         elif frac < 0.7:
#             pos = "around the middle of the track"
#         else:
#             pos = "toward the later part of the track"
#         drop_hint = (
#             f"- There is a musical “drop” or stronger change in energy {pos}. "
#             "Place ONE clearly cinematic, punchy sentence shortly BEFORE that emotional high point, "
#             "so it feels like a turning point right before the music hits.\n"
#         )

#     return dedent(f"""
#     Write a single continuous spoken script for Journey Day {d or 0}.
#     Speak in a warm, cinematic, reflective tone.

#     Overall tone for this story:
#     - {theme}

#     Emotional arc for this story:
#     - Arc type: {arc_label} — it {arc_one}
#     - Follow this emotional shape over the course of the script:
#       {arc_pacing}

#     Core idea:
#     - Tell ONE short story about ONE fictional person whose inner world and struggles mirror the listener.
#     - The entire story happens within ONE slice of ONE day (for example, a morning and a short walk on the same day).
#     - Do NOT restart the day, jump to a completely new time, or start a second story later on.

#     Character and setting:
#     - The character is living with schema "{schema}", feeling "{mood}" in their body ("{body}"), with "{energy}" energy today.
#     - They are in a setting similar to "{place}" and roughly located near: {local}
#     - Today they try a small concrete action: "{goal}" because "{why}".
#     - They have had a recent small win: "{win}".
#     - The hard thing in the background is: "{hard}".

#     Voice & perspective:
#     - Use third person almost all the time (for example: "They wake up with a familiar heaviness...").
#     - Do NOT give the character a specific name; refer to them only as "they" / "them".
#     - Vary sentence openings. Avoid starting more than two sentences in a row with "They".
#       Often begin with the environment, the body, a sound, or a moment in time instead of repeating "They ...".
#     - Do NOT explain psychology, diagnoses, or symptoms. No textbook psychoeducation and no "sometimes we feel anxious" style lines.
#     - Show inner experience through scenes, sensations, and small choices instead of explaining it.
#     - Avoid imperative or prescriptive language (no "you should...", "do this...", "take a break now...").
#     - Only in the final 1–2 sentences, you MAY gently turn toward the listener with a single "you" sentence, as an invitation (not a command).
#       After you have written that optional "you" sentence, you may add at most ONE short third-person closing sentence and then STOP.
#     - Avoid repeating distinctive emotional words or metaphors. If you use a rare word (like "trepidation"), use it at most once.

#     Constraints:
#     {length_hint}{timing_hint}{drop_hint}- Output only spoken words. You MAY use the literal token "[pause]" occasionally where a slightly longer silence fits the emotion or music.
#     - No other stage directions or bracketed cues (no [music], SFX, etc.).
#     - Absolutely NO repetition of sentences or sentence fragments, especially in the ending. Each sentence must add new meaning.
#     - Do NOT let paragraphs become a chain of sentences all starting with "They". Mix subject position and structure so the narration feels natural.
#     - Do not introduce new heaviness, a new scene, or a second beginning after the final "you" invitation. End the script within one or two sentences after it.
#     - No filler, no summaries of what you already said, no "as I said" references.
#     - Warm, grounded, concise sentences with natural cadence. Avoid cringe.
#     - Once the emotional arc has clearly landed and the closing image is given, STOP. Do not start a new paragraph, a new morning, or a new apartment after the ending.

#     Use of personalization:
#     - Weave the recent win "{win}" into the story as a quiet sign that change is already happening.
#     - Let the small action "{goal}" appear in one or two very concrete scenes (e.g., where they are, what time of day, what they actually do).
#     - Acknowledge schema "{schema}" only once, as something that used to narrow the character's world.
#     - Gently contradict it once by showing the character doing something that doesn’t fit the schema.
#     - Keep everything anchored in this one character’s lived day; no generic motivational speech.

#     High-level pacing (to align with music and the emotional arc above):
#     - Opening: a spacious beginning with short lines that drop us straight into a moment in the character’s day. Allow room for the music, maybe with one early "[pause]". Let this part match the starting point of the {arc_label} arc.
#     - Middle: the character experiments with their small action and notices subtle shifts (internal or external). Let the rhythm build a little here in line with the arc’s middle section.
#     - Emotional "climax": include ONE clearly cinematic, punchy sentence that feels like a turning point in the story, shortly before the musical high point. You may place a "[pause]" immediately after it so it can land.
#     - Closing: gently land the story in a calmer, grounded place that matches the final part of the {arc_label} arc. The last one or two sentences can hint that the listener might carry something similar into their own day, using at most one "you" sentence.

#     Structure:
#     1) Introduce the character in the present, with their mood, body state, and energy.
#     2) Briefly touch on how life used to feel when schema "{schema}" drove everything, using one or two concrete memories.
#     3) Follow them through one small, specific action related to "{goal}", and show why it matters today ("{why}").
#     4) Let them notice a subtle shift or moment of meaning (a look, a breath, a sound, a thought) that contradicts the schema.
#     5) End with a short, grounded closing that feels like a soft invitation rather than advice.
#     """).strip()





# The Previous Code
# from textwrap import dedent

# # ---------- Emotional arc model (from story-shape paper) ----------

# # We keep the numeric curves for future use / experimentation if needed.
# # For now we mainly use the *qualitative* shapes in the prompt.
# EMOTIONAL_ARCS = {
#     "rags_to_riches":      [0.20, 0.30, 0.40, 0.55, 0.70, 0.80, 0.90, 1.00],
#     "tragedy":             [0.80, 0.75, 0.70, 0.60, 0.45, 0.35, 0.25, 0.15],
#     "man_in_a_hole":       [0.60, 0.50, 0.35, 0.25, 0.40, 0.60, 0.75, 0.85],
#     "icarus":              [0.30, 0.45, 0.60, 0.80, 0.90, 0.70, 0.45, 0.30],
#     "cinderella":          [0.30, 0.45, 0.65, 0.50, 0.35, 0.55, 0.75, 0.95],
#     "oedipus":             [0.70, 0.55, 0.35, 0.25, 0.50, 0.70, 0.60, 0.30],
# }


# def _arc_info(name: str) -> dict:
#     """
#     Qualitative descriptions + pacing guidance for each emotional arc.
#     """
#     name = name or "man_in_a_hole"
#     mapping = {
#         "rags_to_riches": {
#             "label": "Rags to riches",
#             "one_liner": "starts from heaviness and gradually rises toward strength, connection, and possibility.",
#             "pacing": (
#                 "- In the opening third, stay closer to the difficulty, letting the world feel tight and heavy.\n"
#                 "- In the middle third, let small experiments and subtle hope appear in concrete scenes.\n"
#                 "- In the final third, let the emotional space feel a bit wider and more grounded, with gentle relief "
#                 "and possibility (not a magical fix)."
#             ),
#         },
#         "tragedy": {
#             "label": "Tragedy",
#             "one_liner": "starts more level or hopeful and slowly moves into weight, complexity, and acceptance.",
#             "pacing": (
#                 "- In the opening third, allow some light or normality with hints of tension.\n"
#                 "- In the middle third, let the complexity and cost of their patterns become clearer.\n"
#                 "- In the final third, move toward a heavier but honest acceptance, with a calm, grounded tone "
#                 "instead of despair."
#             ),
#         },
#         "man_in_a_hole": {
#             "label": "Man in a hole",
#             "one_liner": "drops into a difficult place and then climbs back out into relief and a more workable day.",
#             "pacing": (
#                 "- In the opening third, let the character feel like they are sliding into the 'hole' of their pattern.\n"
#                 "- In the middle third, show one or two small actions or realizations that help them start climbing out.\n"
#                 "- In the final third, let them reach a noticeably better emotional place, still real and imperfect, "
#                 "but lighter than where they began."
#             ),
#         },
#         "icarus": {
#             "label": "Icarus",
#             "one_liner": "rises into intensity and power, then gently comes down and integrates what happened.",
#             "pacing": (
#                 "- In the opening third, let the energy and drive build, with a sense of \"maybe this is it\".\n"
#                 "- In the middle third, allow an emotional or situational peak that feels almost too bright or intense.\n"
#                 "- In the final third, gently bring things down into integration, honesty, and a more sustainable pace."
#             ),
#         },
#         "cinderella": {
#             "label": "Cinderella",
#             "one_liner": "rises, dips briefly, then rises higher than before into a more stable, earned hope.",
#             "pacing": (
#                 "- In the opening third, let something unexpectedly good or kind begin to appear.\n"
#                 "- In the middle, include a wobble or setback that briefly pulls the mood down without erasing the gains.\n"
#                 "- In the final third, let the character feel more rooted in a new, slightly larger life than they had before."
#             ),
#         },
#         "oedipus": {
#             "label": "Oedipus",
#             "one_liner": "moves through difficulty and insight and ends in a grounded but not purely 'happy' place.",
#             "pacing": (
#                 "- In the opening third, let the weight and confusion be clearly felt.\n"
#                 "- In the middle third, bring in one or two sharp realisations or truths that change how they see their story.\n"
#                 "- In the final third, settle into a more honest, complex emotional place with some stability and self-respect."
#             ),
#         },
#     }
#     return mapping.get(name, mapping["man_in_a_hole"])


# def choose_arc(j: dict) -> str:
#     """
#     Choose an emotional arc based on intake fields.
#     This is simple, hand-tuned logic and can be refined with Felix later.
#     """
#     mood = str(j.get("feeling") or "").lower()
#     hard = str(j.get("hard_thing") or "").lower()
#     goal = str(j.get("goal_today") or "").lower()
#     schema = str(j.get("schema_choice") or "").lower()
#     day = j.get("journey_day")

#     # Heavier / stuck moods -> upward journeys
#     if any(k in mood for k in ["stuck", "hopeless", "empty", "worthless", "numb"]):
#         return "rags_to_riches"

#     # Shame / guilt / defectiveness -> fall-then-rise journey
#     if any(k in mood for k in ["ashamed", "guilty", "failure", "embarrassed"]) or \
#        any(k in schema for k in ["defectiveness", "shame"]):
#         return "man_in_a_hole"

#     # High activation plus fear -> Icarus
#     if any(k in mood for k in ["excited", "pumped", "energised", "energized"]) and \
#        any(k in mood for k in ["afraid", "scared", "anxious", "nervous"]):
#         return "icarus"

#     # Processing / insight-focused days -> Oedipus
#     if any(k in goal for k in ["understand", "make sense", "see pattern"]) or \
#        "pattern" in hard or "why i" in hard:
#         return "oedipus"

#     # Grief and loss -> tragedy-style arc
#     if any(k in hard for k in ["loss", "grief", "bereavement", "breakup", "break-up"]):
#         return "tragedy"

#     # Rebirth / second chance language -> Cinderella
#     if any(k in goal for k in ["restart", "second chance", "new start", "fresh start"]):
#         return "cinderella"

#     # Optionally: bias by journey_day (early days more upward arcs)
#     if day == 1:
#         return "rags_to_riches"
#     if day == 2:
#         return "man_in_a_hole"

#     # Safe, flexible default
#     return "man_in_a_hole"


# def _day_theme(d: int | None) -> str:
#     # Story-based tone variants per day
#     if d == 1:
#         return ("Opening chapter of a recovery story; the character is still close to hardship, "
#                 "but there is a quiet sense that something is beginning to shift.")
#     if d == 2:
#         return ("Reflective, like the character looking back on how their old patterns and schemas "
#                 "kept life small, while gently noticing how tiny actions start to open things up.")
#     if d == 3:
#         return ("Expansion and discovery; the character experiments, stumbles a bit, "
#                 "and finds small surprising moments of relief or connection.")
#     if d == 4:
#         return ("Long-form recovery tale; darkness to light; the character realises they are not alone, "
#                 "and that community, routines, and meaning slowly grew around them.")
#     if d == 5:
#         return ("Emergence and rebirth; the character can see both who they were and who they are becoming, "
#                 "with gratitude, grief, and quiet confidence coexisting.")
#     return ("Grounded, warm, cinematic story; subtle emotional depth without being preachy or didactic; "
#             "prefer metaphor and scenes over explanations; avoid textbook psychoeducation.")


# def build(j: dict, target_words: int | None = None) -> str:
#     """
#     target_words: approximate desired length to match the SPOKEN portion of the music.
#     We now also condition on an explicit emotional arc (Reagan et al. style).
#     """
#     d = j.get("journey_day")
#     mood = j.get("feeling", "calm")
#     body = j.get("body", "relaxed")
#     energy = j.get("energy", "medium")
#     goal = j.get("goal_today", "one helpful step")
#     why = j.get("why_goal", "it matters today")
#     win = j.get("last_win", "they followed through recently")
#     hard = j.get("hard_thing", "overthinking")
#     schema = j.get("schema_choice", "unseen")
#     pc = j.get("postal_code", "")
#     place = j.get("place", "indoors")

#     # Emotional arc selection: either provided by caller, or chosen here.
#     arc_name = j.get("arc_name") or choose_arc(j)
#     arc = _arc_info(arc_name)
#     arc_label = arc["label"]
#     arc_one = arc["one_liner"]
#     arc_pacing = arc["pacing"]

#     music_ms = j.get("music_ms")
#     spoken_target_ms = j.get("spoken_target_ms")
#     drop_ms = j.get("drop_ms")  # may be None if analysis failed

#     local = (
#         f"In {pc}, a small nearby action feels possible. "
#         f"If they are outside, there are hints of air and distant sounds; if they are inside, there is light and breath."
#         if pc else
#         "A small nearby action feels possible. Outside there might be air and distant sounds; inside there is light and breath."
#     )
#     theme = _day_theme(d)

#     length_hint = ""
#     if target_words and target_words > 0:
#         length_hint = f"- Write ~{target_words} words (±10%).\n"

#     timing_hint = ""
#     if music_ms and spoken_target_ms:
#         timing_hint = (
#             "- Imagine the music has a gentle build in the first third, a stronger build in the middle, "
#             "and a more cinematic swell/drop around the last third.\n"
#         )

#     drop_hint = ""
#     if isinstance(drop_ms, int) and drop_ms > 0 and music_ms:
#         frac = drop_ms / max(1, music_ms)
#         if frac < 0.4:
#             pos = "fairly early in the track"
#         elif frac < 0.7:
#             pos = "around the middle of the track"
#         else:
#             pos = "toward the later part of the track"
#         drop_hint = (
#             f"- There is a musical “drop” or stronger change in energy {pos}. "
#             "Place ONE clearly cinematic, punchy sentence shortly BEFORE that emotional high point, "
#             "so it feels like a turning point right before the music hits.\n"
#         )

#     return dedent(f"""
#     Write a single continuous spoken script for Journey Day {d or 0}.
#     Speak in a warm, cinematic, reflective tone.

#     Overall tone for this story:
#     - {theme}

#     Emotional arc for this story:
#     - Arc type: {arc_label} — it {arc_one}
#     - Follow this emotional shape over the course of the script:
#       {arc_pacing}

#     Core idea:
#     - Tell ONE short story about ONE fictional person whose inner world and struggles mirror the listener.
#     - The entire story happens within ONE slice of ONE day (for example, a morning and a short walk on the same day).
#     - Do NOT restart the day, jump to a completely new time, or start a second story later on.

#     Character and setting:
#     - The character is living with schema "{schema}", feeling "{mood}" in their body ("{body}"), with "{energy}" energy today.
#     - They are in a setting similar to "{place}" and roughly located near: {local}
#     - Today they try a small concrete action: "{goal}" because "{why}".
#     - They have had a recent small win: "{win}".
#     - The hard thing in the background is: "{hard}".

#     Voice & perspective:
#     - Use third person almost all the time (for example: "They wake up with a familiar heaviness...").
#     - Do NOT give the character a specific name; refer to them only as "they" / "them".
#     - Vary sentence openings. Avoid starting more than two sentences in a row with "They".
#       Often begin with the environment, the body, a sound, or a moment in time instead of repeating "They ...".
#     - Do NOT explain psychology, diagnoses, or symptoms. No textbook psychoeducation and no "sometimes we feel anxious" style lines.
#     - Show inner experience through scenes, sensations, and small choices instead of explaining it.
#     - Avoid imperative or prescriptive language (no "you should...", "do this...", "take a break now...").
#     - Only in the final 1–2 sentences, you MAY gently turn toward the listener with a single "you" sentence, as an invitation (not a command).
#       After you have written that optional "you" sentence, you may add at most ONE short third-person closing sentence and then STOP.
#     - Avoid repeating distinctive emotional words or metaphors. If you use a rare word (like "trepidation"), use it at most once.

#     Constraints:
#     {length_hint}{timing_hint}{drop_hint}- Output only spoken words.
#     - Use the literal token "[pause]" regularly where a slightly longer silence fits the emotion or music.
#       Aim for at least 4 and at most 8 "[pause]" tokens in total, especially at scene changes, emotional shifts, or after key lines.
#     - No other stage directions or bracketed cues (no [music], SFX, etc.).
#     - Absolutely NO repetition of sentences or sentence fragments, especially in the ending.
#       Do not repeat the same clause (for example, "can lead to something new") more than once in the script.
#     - Do NOT let paragraphs become a chain of sentences all starting with "They". Mix subject position and structure so the narration feels natural.
#     - Do not introduce new heaviness, a new scene, or a second beginning after the final "you" invitation. End the script within one or two sentences after it.
#     - Vary sentence length: mix short cinematic lines with medium-length reflective lines so the rhythm never feels rushed or monotonous.
#     - No filler, no summaries of what you already said, no "as I said" references.
#     - Warm, grounded, concise sentences with natural cadence. Avoid cringe.
#     - Once the emotional arc has clearly landed and the closing image is given, STOP. You may leave the ending slightly open or gently unresolved, but do not start a new scene.

#     Use of personalization:
#     - Weave the recent win "{win}" into the story as a quiet sign that change is already happening.
#     - Let the small action "{goal}" appear in one or two very concrete scenes (e.g., where they are, what time of day, what they actually do).
#     - Acknowledge schema "{schema}" only once, as something that used to narrow the character's world.
#     - Gently contradict it once by showing the character doing something that doesn’t fit the schema.
#     - Keep everything anchored in this one character’s lived day; no generic motivational speech.

#     High-level pacing (to align with music and the emotional arc above):
#     - Opening: a spacious beginning with short lines that drop us straight into a moment in the character’s day. Allow room for the music, with at least one early "[pause]". Let this part match the starting point of the {arc_label} arc.
#     - Middle: the character experiments with their small action and notices subtle shifts (internal or external). Let the rhythm build a little here in line with the arc’s middle section, including a few "[pause]" beats so the listener can feel the shifts.
#     - Emotional "climax": include ONE clearly cinematic, punchy sentence that feels like a turning point in the story, shortly before the musical high point. Place a "[pause]" immediately after it so it can land.
#     - Closing: gently land the story in a calmer, grounded place that matches the final part of the {arc_label} arc. The last one or two sentences can hint that the listener might carry something similar into their own day, using at most one "you" sentence.

#     Structure:
#     1) Introduce the character in the present, with their mood, body state, and energy.
#     2) Briefly touch on how life used to feel when schema "{schema}" drove everything, using one or two concrete memories.
#     3) Follow them through one small, specific action related to "{goal}", and show why it matters today ("{why}").
#     4) Let them notice a subtle shift or moment of meaning (a look, a breath, a sound, a thought) that contradicts the schema.
#     5) End with a short, grounded closing that feels like a soft invitation rather than advice.
#     """).strip()


from textwrap import dedent

# ---------- Emotional arc model (from story-shape paper) ----------

# We keep the numeric curves for future use / experimentation if needed.
# For now we mainly use the *qualitative* shapes in the prompt.
EMOTIONAL_ARCS = {
    "rags_to_riches":      [0.20, 0.30, 0.40, 0.55, 0.70, 0.80, 0.90, 1.00],
    "tragedy":             [0.80, 0.75, 0.70, 0.60, 0.45, 0.35, 0.25, 0.15],
    "man_in_a_hole":       [0.60, 0.50, 0.35, 0.25, 0.40, 0.60, 0.75, 0.85],
    "icarus":              [0.30, 0.45, 0.60, 0.80, 0.90, 0.70, 0.45, 0.30],
    "cinderella":          [0.30, 0.45, 0.65, 0.50, 0.35, 0.55, 0.75, 0.95],
    "oedipus":             [0.70, 0.55, 0.35, 0.25, 0.50, 0.70, 0.60, 0.30],
}


def _arc_info(name: str) -> dict:
    """
    Qualitative descriptions + pacing guidance for each emotional arc.
    """
    name = name or "man_in_a_hole"
    mapping = {
        "rags_to_riches": {
            "label": "Rags to riches",
            "one_liner": "starts from heaviness and gradually rises toward strength, connection, and possibility.",
            "pacing": (
                "- In the opening third, stay close to the difficulty and let the world feel a bit tight and heavy.\n"
                "- In the middle third, let small experiments and subtle hope appear in concrete scenes.\n"
                "- In the final third, let the emotional space feel wider and more grounded, with gentle relief "
                "and possibility (not a magical fix)."
            ),
        },
        "tragedy": {
            "label": "Tragedy",
            "one_liner": "starts more level or hopeful and slowly moves into weight, complexity, and acceptance.",
            "pacing": (
                "- In the opening third, allow some light or normality with hints of tension.\n"
                "- In the middle third, let the complexity and cost of their patterns become clearer.\n"
                "- In the final third, move toward a heavier but honest acceptance, with a calm, grounded tone "
                "instead of despair."
            ),
        },
        "man_in_a_hole": {
            "label": "Man in a hole",
            "one_liner": "drops into a difficult place and then climbs back out into relief and a more workable day.",
            "pacing": (
                "- In the opening third, let the character feel like they are sliding into the 'hole' of their pattern.\n"
                "- In the middle third, show one or two small actions or realizations that help them start climbing out.\n"
                "- In the final third, let them reach a noticeably better emotional place, still real and imperfect, "
                "but lighter than where they began."
            ),
        },
        "icarus": {
            "label": "Icarus",
            "one_liner": "rises into intensity and power, then gently comes down and integrates what happened.",
            "pacing": (
                "- In the opening third, let the energy and drive build, with a sense of \"maybe this is it\".\n"
                "- In the middle third, allow an emotional or situational peak that feels almost too bright or intense.\n"
                "- In the final third, gently bring things down into integration, honesty, and a more sustainable pace."
            ),
        },
        "cinderella": {
            "label": "Cinderella",
            "one_liner": "rises, dips briefly, then rises higher than before into a more stable, earned hope.",
            "pacing": (
                "- In the opening third, let something unexpectedly good or kind begin to appear.\n"
                "- In the middle, include a wobble or setback that briefly pulls the mood down without erasing the gains.\n"
                "- In the final third, let the character feel more rooted in a new, slightly larger life than they had before."
            ),
        },
        "oedipus": {
            "label": "Oedipus",
            "one_liner": "moves through difficulty and insight and ends in a grounded but not purely 'happy' place.",
            "pacing": (
                "- In the opening third, let the weight and confusion be clearly felt.\n"
                "- In the middle third, bring in one or two sharp realisations or truths that change how they see their story.\n"
                "- In the final third, settle into a more honest, complex emotional place with some stability and self-respect."
            ),
        },
    }
    return mapping.get(name, mapping["man_in_a_hole"])


def choose_arc(j: dict) -> str:
    """
    Choose an emotional arc based on intake fields.
    This is simple, hand-tuned logic and can be refined with Felix later.
    """
    mood = str(j.get("feeling") or "").lower()
    hard = str(j.get("hard_thing") or "").lower()
    goal = str(j.get("goal_today") or "").lower()
    schema = str(j.get("schema_choice") or "").lower()
    day = j.get("journey_day")

    # Heavier / stuck moods -> upward journeys
    if any(k in mood for k in ["stuck", "hopeless", "empty", "worthless", "numb"]):
        return "rags_to_riches"

    # Shame / guilt / defectiveness -> fall-then-rise journey
    if any(k in mood for k in ["ashamed", "guilty", "failure", "embarrassed"]) or \
       any(k in schema for k in ["defectiveness", "shame"]):
        return "man_in_a_hole"

    # High activation plus fear -> Icarus
    if any(k in mood for k in ["excited", "pumped", "energised", "energized"]) and \
       any(k in mood for k in ["afraid", "scared", "anxious", "nervous"]):
        return "icarus"

    # Processing / insight-focused days -> Oedipus
    if any(k in goal for k in ["understand", "make sense", "see pattern"]) or \
       "pattern" in hard or "why i" in hard:
        return "oedipus"

    # Grief and loss -> tragedy-style arc
    if any(k in hard for k in ["loss", "grief", "bereavement", "breakup", "break-up"]):
        return "tragedy"

    # Rebirth / second chance language -> Cinderella
    if any(k in goal for k in ["restart", "second chance", "new start", "fresh start"]):
        return "cinderella"

    # Optionally: bias by journey_day (early days more upward arcs)
    if day == 1:
        return "rags_to_riches"
    if day == 2:
        return "man_in_a_hole"

    # Safe, flexible default
    return "man_in_a_hole"


def _day_theme(d: int | None) -> str:
    """
    High-level flavour per day. Keep it simple and spoken, not poetic.
    """
    if d == 1:
        return ("Opening chapter of recovery; the character is still close to hardship, "
                "but something small is beginning to shift.")
    if d == 2:
        return ("More reflective; they can see their old patterns and also notice a few ways life is opening up.")
    if d == 3:
        return ("Experiment and discovery; they try new things, stumble a bit, and find small moments of relief or connection.")
    if d == 4:
        return ("Slow, steady recovery; routines, people, and meaning are starting to support them more regularly.")
    if d == 5:
        return ("Emergence; they can see both who they were and who they are becoming, with some gratitude and honesty.")
    return ("Grounded, warm story with emotional depth but no drama for drama’s sake. "
            "Prefer clear scenes over abstract explanations.")


def build(j: dict, target_words: int | None = None) -> str:
    """
    target_words: approximate desired length to match the SPOKEN portion of the music.
    We now also condition on an explicit emotional arc.
    """
    d = j.get("journey_day")
    mood = j.get("feeling", "calm")
    body = j.get("body", "relaxed")
    energy = j.get("energy", "medium")
    goal = j.get("goal_today", "one helpful step")
    why = j.get("why_goal", "it matters today")
    win = j.get("last_win", "they followed through recently")
    hard = j.get("hard_thing", "overthinking")
    schema = j.get("schema_choice", "unseen")
    pc = j.get("postal_code", "")
    place = j.get("place", "indoors")

    # Emotional arc selection: either provided by caller, or chosen here.
    arc_name = j.get("arc_name") or choose_arc(j)
    arc = _arc_info(arc_name)
    arc_label = arc["label"]
    arc_one = arc["one_liner"]
    arc_pacing = arc["pacing"]

    music_ms = j.get("music_ms")
    spoken_target_ms = j.get("spoken_target_ms")
    drop_ms = j.get("drop_ms")  # may be None if analysis failed

    local = (
        f"In {pc}, a small nearby action feels possible. "
        f"If they are outside, there are hints of air and distant sounds; if they are inside, there is light and breath."
        if pc else
        "A small nearby action feels possible. Outside there might be air and distant sounds; inside there is light and breath."
    )
    theme = _day_theme(d)

    length_hint = ""
    if target_words and target_words > 0:
        length_hint = f"- Write around {target_words} words (±10%). Use mostly short and medium spoken sentences.\n"

    timing_hint = ""
    if music_ms and spoken_target_ms:
        timing_hint = (
            "- Imagine the music has a gentle build in the first third, a stronger build in the middle, "
            "and a more cinematic swell/drop around the last third.\n"
        )

    drop_hint = ""
    if isinstance(drop_ms, int) and drop_ms > 0 and music_ms:
        frac = drop_ms / max(1, music_ms)
        if frac < 0.4:
            pos = "fairly early in the track"
        elif frac < 0.7:
            pos = "around the middle of the track"
        else:
            pos = "toward the later part of the track"
        drop_hint = (
            f"- There is a musical “drop” or stronger change in energy {pos}. "
            "Place ONE punchy, memorable sentence shortly BEFORE that emotional high point, "
            "then add a [pause] so it can land.\n"
        )

    return dedent(f"""
    Write a single continuous spoken script for Journey Day {d or 0}.
    Speak in a warm, human, conversational tone with a light cinematic feel.
    Write as if one real person is reading this slowly to another real person.

    Overall tone for this story:
    - {theme}

    Emotional arc for this story:
    - Arc type: {arc_label} — it {arc_one}
    - Follow this emotional shape over the course of the script:
      {arc_pacing}

    Core idea:
    - Tell ONE short story about ONE fictional person whose inner world and struggles mirror the listener.
    - The entire story happens within ONE slice of ONE day (for example, a morning and a short walk on the same day).
    - Do NOT restart the day, jump to a completely new time, or start a second story later on.

    Character and setting:
    - The character is living with schema "{schema}", feeling "{mood}" in their body ("{body}"), with "{energy}" energy today.
    - They are in a setting similar to "{place}" and roughly located near: {local}
    - Today they try a small concrete action: "{goal}" because "{why}".
    - They have had a recent small win: "{win}".
    - The hard thing in the background is: "{hard}".

    Voice & perspective:
    - Use third person almost all the time (for example: "They wake up with a familiar heaviness...").
    - Do NOT give the character a specific name; refer to them only as "they" / "them".
    - Vary sentence openings. Avoid starting more than two sentences in a row with "They".
      Often begin with the environment, the body, a sound, or a moment in time instead of repeating "They ...".
    - Language must feel spoken and simple: avoid rare or academic words and long, winding sentences.
    - Do NOT explain psychology, diagnoses, or symptoms. No textbook psychoeducation and no "sometimes we feel anxious" style lines.
    - Show inner experience through scenes, sensations, and small choices instead of explaining it.
    - Avoid imperative or prescriptive language (no "you should...", "do this...", "take a break now...").
    - Only in the final 1–2 sentences, you MAY gently turn toward the listener with a single "you" sentence, as an invitation (not a command).
      After you have written that optional "you" sentence, you may add at most ONE short third-person closing sentence and then STOP.
    - Avoid repeating distinctive emotional words or metaphors. If you use a rare word (like "trepidation"), use it at most once.

    Constraints:
    {length_hint}{timing_hint}{drop_hint}- Output only spoken words.
    - Use the literal token "[pause]" regularly where a slightly longer silence fits the emotion or music.
      Aim for at least 4 and at most 8 "[pause]" tokens in total, especially at scene changes, emotional shifts, or after key lines.
    - No other stage directions or bracketed cues (no [music], SFX, etc.).
    - Absolutely NO repetition of sentences or sentence fragments, especially in the ending.
      Do not repeat the same clause (for example, "can lead to something new") more than once in the script.
    - Do NOT let paragraphs become a chain of sentences all starting with "They". Mix subject position and structure so the narration feels natural.
    - Do not introduce new heaviness, a new scene, or a second beginning after the final "you" invitation. End the script within one or two sentences after it.
    - Vary sentence length: mix short cinematic lines with medium-length reflective lines so the rhythm never feels rushed or monotonous.
    - No filler, no summaries of what you already said, no "as I said" references.
    - Warm, grounded, concise sentences with natural cadence. Avoid cringe and avoid over-poetic language.
    - Once the emotional arc has clearly landed and the closing image is given, STOP. You may leave the ending slightly open or gently unresolved, but do not start a new scene.

    Use of personalization:
    - Weave the recent win "{win}" into the story as a quiet sign that change is already happening.
    - Let the small action "{goal}" appear in one or two very concrete scenes (where they are, what time of day, what they actually do).
    - Acknowledge schema "{schema}" only once, as something that used to narrow the character's world.
    - Gently contradict it once by showing the character doing something that doesn’t fit the schema.
    - Use phrases and details that feel close to the intake answers instead of generic self-help language.

    High-level pacing (to align with music and the emotional arc above):
    - Opening: a spacious beginning with short lines that drop us straight into a moment in the character’s day. Allow room for the music, with at least one early "[pause]". Let this part match the starting point of the {arc_label} arc.
    - Middle: the character experiments with their small action and notices subtle shifts (internal or external). Let the rhythm build a little here in line with the arc’s middle section, including a few "[pause]" beats so the listener can feel the shifts.
    - Emotional "climax": include ONE clearly cinematic, punchy sentence that feels like a turning point in the story, shortly before the musical high point. Place a "[pause]" immediately after it so it can land.
    - Closing: gently land the story in a calmer, grounded place that matches the final part of the {arc_label} arc. The last one or two sentences can hint that the listener might carry something similar into their own day, using at most one "you" sentence.

    Structure:
    1) Introduce the character in the present, with their mood, body state, and energy.
    2) Briefly touch on how life used to feel when schema "{schema}" drove everything, using one or two concrete memories.
    3) Follow them through one small, specific action related to "{goal}", and show why it matters today ("{why}").
    4) Let them notice a subtle shift or moment of meaning (a look, a breath, a sound, a thought) that contradicts the schema.
    5) End with a short, grounded closing that feels like a soft invitation rather than advice.
    """).strip()
