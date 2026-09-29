import requests
import json


def call_hvd_gemini_api(model: str, input_text: str) -> dict:
    """
    Call the Harvard HUIT Gemini API endpoint with a given input.

    Ref: https://portal.apis.huit.harvard.edu/docs/ais-gemini-llm/1/overview
    Gateway base path: ais-google-gemini

    Args:
        model: The Gemini model name to use (e.g., "gemini-2.0-flash")
        input_text: The input text/prompt to send to the model

    Returns:
        dict: The API response as a dictionary
    """
    url = f"https://go.apis.huit.harvard.edu/ais-google-gemini/v1beta/models/{model}:generateContent"
    payload = json.dumps(
        {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": input_text}],
                },
            ],
            "systemInstruction": {
                "parts": [{"text": "You are a helpful assistant."}],
            },
            "generationConfig": {
                "temperature": 1.0,
                "maxOutputTokens": 8192,
            },
        }
    )
    headers = {
        "Content-Type": "application/json",
        "api-key": "jzmwbIL1QJG1vT2AC8yTZzJJFA80xeBGVtrTxfkTHmGu5GIE",
    }
    response = requests.request("POST", url, headers=headers, data=payload)
    return response.json()


if __name__ == "__main__":
    # Example usage
    result = call_hvd_gemini_api(
        "gemini-2.0-flash", "Tell me a ten-sentence story about a unicorn."
    )
    print(json.dumps(result, indent=4))
