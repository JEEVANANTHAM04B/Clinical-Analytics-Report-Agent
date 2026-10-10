from app.ai.llm import generate_response


if __name__ == "__main__":
    prompt = "What is clinical analytics?"

    print("Sending prompt to Gemini...")

    response = generate_response(prompt)

    print("\n=== Gemini Response ===\n")
    print(response)