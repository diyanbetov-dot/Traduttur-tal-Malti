import os

print("1. Script started")

openai_key = os.getenv("OPENAI_API_KEY", "")
gemini_key = os.getenv("GEMINI_API_KEY", "") or openai_key
provider = os.getenv("TRANSLATOR_AI_PROVIDER", "gemini").strip().lower()

print(f"2. Provider selected: {provider}")

if provider == "gemini":
    if not gemini_key:
        raise RuntimeError("No Gemini key found. Set GEMINI_API_KEY or put the Gemini key in OPENAI_API_KEY.")

    from google import genai

    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    client = genai.Client(api_key=gemini_key)

    print(f"3. Sending request to Gemini model {model}")
    try:
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: Gemini connection successful",
        )
        print("4. Response received")
        print(response.text)
    except Exception as error:
        print("REQUEST FAILED")
        print("Error type:", type(error).__name__)
        print("Error:", str(error))
else:
    if not openai_key:
        raise RuntimeError("OPENAI_API_KEY was not found.")

    from openai import OpenAI

    client = OpenAI(api_key=openai_key, timeout=20.0)

    print("3. Sending request to OpenAI")
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input="Reply with exactly: OpenAI connection successful",
        )
        print("4. Response received")
        print(response.output_text)
    except Exception as error:
        print("REQUEST FAILED")
        print("Error type:", type(error).__name__)
        print("Error:", str(error))
