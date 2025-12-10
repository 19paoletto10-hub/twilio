import argparse

from app import create_app
from app.twilio_client import TwilioService
from app.database import get_ai_config, insert_message
from app.ai_service import AIResponder


def main():
    parser = argparse.ArgumentParser(description="Twilio Chat App CLI")
    subparsers = parser.add_subparsers(dest="command")

    send_parser = subparsers.add_parser("send", help="Send single message via Twilio")
    send_parser.add_argument("--to", required=True, help="Recipient phone number")
    send_parser.add_argument("--body", required=True, help="Message body")
    send_parser.add_argument(
        "--use-messaging-service",
        action="store_true",
        help="Use Messaging Service SID instead of default from number",
    )

    ai_send_parser = subparsers.add_parser(
        "ai-send",
        help="Generate a reply with AIResponder and send it via Twilio",
    )
    ai_send_parser.add_argument(
        "--to",
        help="Recipient phone number (defaults to AI target number from configuration)",
    )
    ai_send_parser.add_argument(
        "--latest",
        help="Optional user message passed to the AI as the latest input",
    )
    ai_send_parser.add_argument(
        "--history-limit",
        type=int,
        default=20,
        help="Number of recent messages to include when building AI context",
    )
    ai_send_parser.add_argument(
        "--use-messaging-service",
        action="store_true",
        help="Use Messaging Service SID instead of default from number",
    )

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        twilio_client: TwilioService = app.config["TWILIO_CLIENT"]

        if args.command == "send":
            message = twilio_client.send_message(
                to=args.to,
                body=args.body,
                use_messaging_service=args.use_messaging_service,
            )
            print(f"Message sent. SID={message.sid}")
            return

        if args.command == "ai-send":
            cfg = get_ai_config()
            api_key = (cfg.get("api_key") or "").strip()
            if not api_key:
                raise RuntimeError("Brak zapisanego klucza OpenAI. Ustaw OPENAI_API_KEY lub zapisz go w panelu.")

            target_number = (args.to or cfg.get("target_number") or "").strip()
            if not target_number:
                raise RuntimeError("Podaj numer odbiorcy (--to) lub skonfiguruj AI target w panelu.")

            responder = AIResponder(
                api_key=api_key,
                model=(cfg.get("model") or "gpt-4o-mini").strip(),
                system_prompt=cfg.get("system_prompt") or "",
                temperature=float(cfg.get("temperature", 0.7) or 0.7),
                history_limit=max(1, args.history_limit),
            )

            reply = responder.build_reply(participant=target_number, latest_user_message=args.latest)
            if not reply:
                raise RuntimeError("AI nie zwróciła treści wiadomości.")

            message = twilio_client.send_message(
                to=target_number,
                body=reply,
                use_messaging_service=args.use_messaging_service,
            )

            insert_message(
                direction="outbound",
                sid=getattr(message, "sid", None),
                to_number=target_number,
                from_number=getattr(message, "from_", twilio_client.settings.default_from),
                body=reply,
                status=getattr(message, "status", None),
            )

            print(f"AI message sent to {target_number}. SID={message.sid}")


if __name__ == "__main__":
    main()
