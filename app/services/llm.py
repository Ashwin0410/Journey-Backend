from openai import OpenAI

def generate_text(prompt: str, key: str) -> str:
    c = OpenAI(api_key=key)
    m = c.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You write cinematic, compassionate motivational scripts that are emotionally grounded, "
                    "follow instructions exactly, avoid repetition, and maintain a natural spoken cadence."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        # More headroom so narration can cover long tracks (Inception-length)
        max_tokens=2200
    )
    return m.choices[0].message.content.strip()
