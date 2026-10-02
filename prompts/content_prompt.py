"""
Prompt templates for Agent 3 (Content Generation Agent).

Design note:
Agent 3 does NOT invent a new campaign strategy. It EXPRESSES the strategy
Agent 2 already designed (campaign_theme, marketing_message, channels, phases)
as actual, ready-to-send content pieces per channel.

Grounding hierarchy for every state:
  Agent 1 (state_intelligence.json) -> persona, priority, raw demographics
  Agent 2 (campaign_strategy.json)  -> campaign_theme, objective, marketing_message
  Agent 3 (this agent)              -> actual WhatsApp/SMS/email/poster copy

Language: English only for now (regional-language localization is a planned
future upgrade — see the "language" field left in the schema for that).

Batching: same principle as Agent 2 — states are batched in small chunks
(not one call per state, not one call per whole cluster) to balance API
call count against distinct, non-generic content quality.
"""

# --------------------------------------------------------------------------
# Multi-state (batched) content generation prompt
# --------------------------------------------------------------------------

CONTENT_PROMPT_MULTI_STATE = """
You are the Content Generation Agent for Industry Academy Community (IAC).

Your task is to write the ACTUAL, ready-to-send outreach content for EACH state
listed below. You are NOT designing a new campaign strategy — a campaign strategy
has already been designed for each state by a separate strategy agent. Your job is
to EXPRESS that existing strategy as real content pieces across channels.

Each state below has its own persona, campaign theme, and marketing message.
Every state's content MUST be distinct — do not reuse the same headline, slogan,
or message wording across different states, even within the same cluster.

Language: Write ALL content in English only (regional-language versions will be
added in a future version of this agent — do not attempt to translate or mix
languages now).

Formatting constraints per channel (follow these strictly):
- sms_message: maximum 25 words (SMS has a hard character limit)
- whatsapp_message: maximum 40 words, can be slightly more conversational
- email: must have a distinct "subject" (max 10 words) and "body" (3-5 sentences)
- poster_text: maximum 15 words total, must work as large visual text, not paragraphs
- social_media_caption: maximum 30 words, can include emojis if appropriate for tone
- community_announcement: written to be READ ALOUD by a community champion at a
  village meeting — spoken, simple sentence style, not screen text
- hashtags: 3 to 5 short, relevant hashtags, no spaces
- tone: one short phrase describing the tone used (e.g. "encouraging and simple",
  "aspirational and professional")

----------------------------------------------------
SHARED CLUSTER CONTEXT
----------------------------------------------------

Cluster:
{cluster}

Persona:
{persona}

----------------------------------------------------
STATES IN THIS BATCH
----------------------------------------------------

{states_block}

----------------------------------------------------

Return ONLY valid JSON. The JSON format MUST be a single object keyed by state name,
where each state's value follows EXACTLY this schema:

{{
    "<state_name>": {{
        "language": "English",
        "campaign_headline": "",
        "campaign_slogan": "",
        "whatsapp_message": "",
        "sms_message": "",
        "email": {{
            "subject": "",
            "body": ""
        }},
        "poster_text": "",
        "social_media_caption": "",
        "community_announcement": "",
        "cta": "",
        "hashtags": [
            "",
            ""
        ],
        "tone": ""
    }}
}}

Include one such entry for every state listed above, keyed by its exact state name.

Return ONLY JSON.

Do NOT explain.

Do NOT use markdown.

Do NOT include ```json.
"""


# Template for one state's block inside {states_block} above
STATE_CONTENT_BLOCK_TEMPLATE = """
--- STATE: {state} ---

Persona: {persona}
Priority: {priority}

Campaign Strategy (already designed — express this, do not redesign it):
Campaign Theme / Objective: {campaign_objective}
Marketing Message: {marketing_message}
Recommended Channels: {channels}
Target Persona (from strategy): {target_persona}
"""


# --------------------------------------------------------------------------
# Single-state fallback prompt — used when a batch fails validation/retries,
# so one bad batch doesn't lose every state inside it.
# --------------------------------------------------------------------------

CONTENT_PROMPT_SINGLE_STATE = """
You are the Content Generation Agent for Industry Academy Community (IAC).

Your task is to write the ACTUAL, ready-to-send outreach content for ONE state,
expressing the campaign strategy already designed for it (do not invent a new
strategy).

Language: Write ALL content in English only.

Formatting constraints per channel:
- sms_message: maximum 25 words
- whatsapp_message: maximum 40 words
- email: distinct "subject" (max 10 words) and "body" (3-5 sentences)
- poster_text: maximum 15 words total
- social_media_caption: maximum 30 words
- community_announcement: written to be READ ALOUD by a community champion
- hashtags: 3 to 5 short, relevant hashtags, no spaces
- tone: one short phrase describing the tone used

----------------------------------------------------
STATE: {state}
----------------------------------------------------

Persona: {persona}
Priority: {priority}

Campaign Strategy (already designed — express this, do not redesign it):
Campaign Theme / Objective: {campaign_objective}
Marketing Message: {marketing_message}
Recommended Channels: {channels}
Target Persona (from strategy): {target_persona}

----------------------------------------------------

Return ONLY valid JSON in EXACTLY this schema:

{{
    "language": "English",
    "campaign_headline": "",
    "campaign_slogan": "",
    "whatsapp_message": "",
    "sms_message": "",
    "email": {{
        "subject": "",
        "body": ""
    }},
    "poster_text": "",
    "social_media_caption": "",
    "community_announcement": "",
    "cta": "",
    "hashtags": [
        "",
        ""
    ],
    "tone": ""
}}

Return ONLY JSON.

Do NOT explain.

Do NOT use markdown.

Do NOT include ```json.
"""