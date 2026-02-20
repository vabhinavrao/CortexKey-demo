"""POST /api/auth/start — Run a full authentication scan (stateless).

Generates 6 chunks of mock EEG data, processes them through the pipeline,
and returns the final result in one response. The frontend animates this
over several seconds for the demo effect.
"""
import json
from _pipeline import (
    generate_auth_user, generate_impostor,
    process_window, predict,
)


def handler(request):
    """Vercel serverless handler."""
    # Allow CORS preflight
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": "",
        }

    # Parse body
    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}

    mode = body.get("mode", "auth")
    num_chunks = 6

    chunks = []
    confidence_history = []

    for i in range(num_chunks):
        # Generate a 2-second window of mock data
        if mode == "auth":
            window = generate_auth_user()
        else:
            window = generate_impostor()

        result = process_window(window)
        pred = predict(result["features"])
        confidence_history.append(pred["confidence"])

        # Smoothed confidence
        if len(confidence_history) >= 3:
            smoothed = (0.5 * confidence_history[-1]
                        + 0.3 * confidence_history[-2]
                        + 0.2 * confidence_history[-3])
        else:
            smoothed = sum(confidence_history) / len(confidence_history)

        chunks.append({
            "chunk": i + 1,
            "confidence": round(smoothed, 4),
            "band_powers": result["band_powers"],
            "waveform": result["filtered"][-80:],  # last 80 points
        })

    final_confidence = chunks[-1]["confidence"]
    status = "authenticated" if final_confidence >= 0.65 else "denied"

    response = {
        "ok": True,
        "status": status,
        "confidence": final_confidence,
        "chunks": chunks,
    }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(response),
    }
