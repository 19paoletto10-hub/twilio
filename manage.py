import argparse
from app import create_app
from app.twilio_client import TwilioService


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

    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        twilio_service: TwilioService = app.config["TWILIO_SERVICE"]

        if args.command == "send":
            message = twilio_service.send_message(
                to=args.to,
                body=args.body,
                use_messaging_service=args.use_messaging_service,
            )
            print(f"Message sent. SID={message.sid}")


if __name__ == "__main__":
    main()
