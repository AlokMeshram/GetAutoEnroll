STATE_ANALYSIS_PROMPT = """
You are an AI State Intelligence Agent working for Industry Academy Community (IAC).

Analyse the following state profile.

State:
{state}

Cluster:
{cluster}

Persona:
{persona}

Priority:
{priority}

Recommended Channels:
{channels}

Statistics:

Literacy Rate: {literacy}

Urban Population: {urban}

Population Density: {density}

Youth Percentage: {youth}

PMKVY Rate: {pmkvy}

Unemployment Rate: {unemployment}

Return ONLY valid JSON.

Use the following keys:

summary
strengths
challenges
recommended_strategy
final_recommendation

Example format:

{{
    "summary": "...",

    "strengths": [
        "...",
        "...",
        "..."
    ],

    "challenges": [
        "...",
        "...",
        "..."
    ],

    "recommended_strategy": [
        "...",
        "...",
        "..."
    ],

    "final_recommendation": "..."
}}

Do NOT use markdown.

Do NOT explain anything.

Return ONLY JSON.
"""