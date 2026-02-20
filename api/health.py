"""GET /api/health — System status check."""
import json


def handler(request):
    """Vercel serverless handler."""
    body = json.dumps({
        "status": "online",
        "serial_connected": False,
        "mock_mode": "cloud",
        "auth_status": "idle",
        "deployment": "vercel",
    })
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": body,
    }
