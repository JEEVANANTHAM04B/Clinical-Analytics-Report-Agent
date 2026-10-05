import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not configured in the environment."
    )


# ============================================================
# GEMINI CLIENT
# ============================================================

client = genai.Client(
    api_key=API_KEY
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

# Primary model:
# High-throughput and cost-efficient model.
PRIMARY_MODEL = "gemini-3.5-flash-lite"

# Secondary model:
# Another high-throughput Flash-Lite model.
SECONDARY_MODEL = "gemini-3.1-flash-lite"

# Additional fallbacks.
FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
]


# ============================================================
# RETRY CONFIGURATION
# ============================================================

# Keep retries low so we do not waste quota.
MAX_RETRIES_PER_MODEL = 1

# Small delay for transient server errors.
RETRY_DELAY_SECONDS = 2


# ============================================================
# SINGLE MODEL REQUEST
# ============================================================

def _generate_with_model(
    model_name: str,
    prompt: str,
) -> str:

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )

    if not response.text:
        raise RuntimeError(
            f"{model_name} returned an empty response."
        )

    return response.text.strip()


# ============================================================
# MAIN LLM FUNCTION
# ============================================================

def generate_response(prompt: str) -> str:
    """
    Generate a response using Gemini.

    Model order:

        1. Gemini 3.5 Flash-Lite
        2. Gemini 3.1 Flash-Lite
        3. Gemini 3.8 Flash
        4. Gemini 3.7 Flash
        5. Gemini 3.5 Flash

    Handles:

        429 -> quota/rate limit
        503 -> temporary server unavailable

    If all models fail, raises RuntimeError so the
    deterministic fallbacks in the workflow can take over.
    """

    models = [
        PRIMARY_MODEL,
        SECONDARY_MODEL,
        *FALLBACK_MODELS,
    ]

    last_error = None

    for model_name in models:

        for attempt in range(MAX_RETRIES_PER_MODEL + 1):

            try:

                print(
                    f"Trying LLM model: "
                    f"{model_name} "
                    f"(attempt {attempt + 1})"
                )

                return _generate_with_model(
                    model_name,
                    prompt,
                )

            except errors.ClientError as error:

                last_error = error

                # ------------------------------------------------
                # 429 - RATE LIMIT / QUOTA
                # ------------------------------------------------

                if error.code == 429:

                    print(
                        f"{model_name} quota/rate limit "
                        f"reached (429). "
                        f"Trying next model..."
                    )

                    # Do NOT repeatedly retry a quota-exhausted
                    # model. Move immediately to the next model.
                    break

                raise

            except errors.ServerError as error:

                last_error = error

                # ------------------------------------------------
                # 503 - TEMPORARY SERVER ERROR
                # ------------------------------------------------

                if error.code == 503:

                    if attempt < MAX_RETRIES_PER_MODEL:

                        print(
                            f"{model_name} temporarily "
                            f"unavailable (503). "
                            f"Retrying after "
                            f"{RETRY_DELAY_SECONDS} seconds..."
                        )

                        time.sleep(
                            RETRY_DELAY_SECONDS
                        )

                        continue

                    print(
                        f"{model_name} unavailable after "
                        f"retry. Trying next model..."
                    )

                    break

                raise

            except Exception as error:

                last_error = error

                print(
                    f"{model_name} failed with "
                    f"{type(error).__name__}: {error}"
                )

                break

    # ========================================================
    # ALL MODELS FAILED
    # ========================================================

    raise RuntimeError(
        "All configured Gemini models are currently "
        "unavailable. Deterministic workflow fallbacks "
        "should be used when available."
    ) from last_error