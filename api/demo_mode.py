"""POST /api/demo/mode — Mode switch (acknowledged, stateless)."""
import json


def handler(request):
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

    try:
        body = json.loads(request.body) if request.body else {}
    except Exception:
        body = {}
    mode = body.get("mode", "auth")

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"ok": True, "mode": mode}),
    }
