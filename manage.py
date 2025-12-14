"""
Command-line interface for Twilio Chat Application.

Provides CLI commands for:
- Sending individual SMS messages
- Generating and sending AI-powered responses
- Testing Twilio integration
"""

from __future__ import annotations

import argparse
import sys

from app import create_app
from app.twilio_client import TwilioService
from app.database import get_ai_config, insert_message
from app.ai_service import AIResponder
from app.exceptions import TwilioChatError


def main() -> int:
    """
    Main CLI entry point.
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = argparse.ArgumentParser(
        description="Twilio Chat App CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send a simple SMS
  python manage.py send --to +48123456789 --body "Hello from CLI"
  
  # Send AI-generated message
  python manage.py ai-send --to +48123456789 --latest "Hi there"
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # send command
    send_parser = subparsers.add_parser(
        "send",
        help="Send single message via Twilio",
    )
    send_parser.add_argument(
        "--to",
        required=True,
        help="Recipient phone number (E.164 format: +48123456789)",
    )
    send_parser.add_argument(
        "--body",
        required=True,
        help="Message body (max 1600 characters)",
    )
    send_parser.add_argument(
        "--use-messaging-service",
        action="store_true",
        help="Use Messaging Service SID instead of default from number",
    )

    # ai-send command
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
        help="Number of recent messages to include when building AI context (default: 20)",
    )
    ai_send_parser.add_argument(
        "--use-messaging-service",
        action="store_true",
        help="Use Messaging Service SID instead of default from number",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    app = create_app()

    try:
        with app.app_context():
            twilio_client: TwilioService = app.config["TWILIO_CLIENT"]

            if args.command == "send":
                return handle_send(twilio_client, args)

            if args.command == "ai-send":
                return handle_ai_send(twilio_client, args)

    except TwilioChatError as exc:
        print(f"❌ Error: {exc.message}", file=sys.stderr)
        if exc.details:
            print(f"Details: {exc.details}", file=sys.stderr)
        return exc.status_code // 100  # Convert HTTP status to exit code

    except Exception as exc:
        print(f"❌ Unexpected error: {exc}", file=sys.stderr)
        return 1

    return 0


def handle_send(twilio_client: TwilioService, args: argparse.Namespace) -> int:
    """Handle 'send' command."""
    message = twilio_client.send_message(
        to=args.to,
        body=args.body,
        use_messaging_service=args.use_messaging_service,
    )
    print(f"✅ Message sent. SID={message.sid}, Status={message.status}")
    return 0


def handle_ai_send(twilio_client: TwilioService, args: argparse.Namespace) -> int:
    """Handle 'ai-send' command."""
    from app.exceptions import ConfigurationError
    
    cfg = get_ai_config()
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        raise ConfigurationError(
            "Brak zapisanego klucza OpenAI. Ustaw OPENAI_API_KEY lub zapisz go w panelu."
        )

    target_number = (args.to or cfg.get("target_number") or "").strip()
    if not target_number:
        raise ConfigurationError(
            "Podaj numer odbiorcy (--to) lub skonfiguruj AI target w panelu."
        )

    responder = AIResponder(
        api_key=api_key,
        model=(cfg.get("model") or "gpt-4o-mini").strip(),
        system_prompt=cfg.get("system_prompt") or "",
        temperature=float(cfg.get("temperature", 0.7) or 0.7),
        history_limit=max(1, args.history_limit),
    )

    print(f"🤖 Generating AI reply for {target_number}...")
    reply = responder.build_reply(
        participant=target_number,
        latest_user_message=args.latest,
    )

    if not reply:
        raise ConfigurationError("AI nie zwróciła treści wiadomości.")

    print(f"📝 Generated reply: {reply[:100]}{'...' if len(reply) > 100 else ''}")

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

    print(f"✅ AI message sent to {target_number}. SID={message.sid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

if __name__ == "__main__":
    sys.exit(main())
