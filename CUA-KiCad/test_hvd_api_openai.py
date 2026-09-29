import requests
import json


def call_hvd_api_response(model: str, input_text: str) -> dict:
    """
    Call the Harvard API responses endpoint with a given input.

    Args:
        model: The model name to use (e.g., "gpt-4.1-nano-2025-04-14")
        input_text: The input text/prompt to send to the model

    Returns:
        dict: The API response as a dictionary
    """
    url = "https://go.apis.huit.harvard.edu/ais-openai-direct/v1/responses"
    payload = json.dumps(
        {
            "model": model,
            "input": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {
                    "role": "user",
                    "content": input_text,
                },
            ],
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
    result = call_hvd_api_response(
        "gpt-5-mini", "Tell me a ten-sentence story about a unicorn."
    )
    print(json.dumps(result, indent=4))