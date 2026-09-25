"""Meta Messenger webhook verification and fast acknowledgement endpoint."""

from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, current_app, jsonify, request

from app.services import messenger_service


MESSENGER_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="messenger")

webhook_bp = Blueprint("webhook", __name__, url_prefix="/webhook")


@webhook_bp.get("")
def verify_webhook():
    if not messenger_service.is_configured(current_app.config):
        return jsonify({"error": "Messenger integration is not configured."}), 503
    if request.args.get("hub.mode") != "subscribe":
        return jsonify({"error": "Unsupported verification mode."}), 400
    if request.args.get("hub.verify_token") != current_app.config["META_VERIFY_TOKEN"]:
        return jsonify({"error": "Invalid verification token."}), 403
    return request.args.get("hub.challenge", ""), 200, {"Content-Type": "text/plain"}


@webhook_bp.post("")
def receive_webhook():
    if not messenger_service.is_configured(current_app.config):
        return jsonify({"error": "Messenger integration is not configured."}), 503
    raw_body = request.get_data(cache=True)
    if not messenger_service.valid_signature(
        raw_body, request.headers.get("X-Hub-Signature-256"), current_app.config["META_APP_SECRET"]
    ):
        return jsonify({"error": "Invalid webhook signature."}), 403
    payload = request.get_json(silent=True) or {}
    if payload.get("object") != "page":
        return jsonify({"error": "Unsupported webhook object."}), 404
    app = current_app._get_current_object()
    for entry in payload.get("entry") or []:
        for event in entry.get("messaging") or []:
            message = event.get("message") or {}
            if message.get("is_echo") or not message.get("text") or not message.get("mid"):
                continue
            MESSENGER_EXECUTOR.submit(messenger_service.process_incoming_event, app, {"messaging": event})
    return jsonify({"status": "EVENT_RECEIVED"}), 200
