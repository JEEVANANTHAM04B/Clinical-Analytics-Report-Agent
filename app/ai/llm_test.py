from app.ai.llm import generate_response


if __name__ == "__main__":
    prompt = "What is clinical analytics?"

    print("Sending prompt to Qwen3...")

    response = generate_response(prompt)

    print("\n=== Qwen3 Response ===\n")
    print(response)