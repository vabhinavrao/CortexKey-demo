"""GET /api/auth/status — Returns current status (stateless stub for Vercel)."""
import json


def handler(request):
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "status": "idle",
            "confidence": 0.0,
            "chunks": 0,
            "waveform": [],
        }),
    }
