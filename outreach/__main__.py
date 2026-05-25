"""
outreach/__main__.py — run with: py -3 -m outreach email | rejection | followup
"""
import sys

# Guard: require Python 3
if sys.version_info[0] < 3:
    sys.stderr.write(
        "ERROR: This module requires Python 3. You are running Python {}.{}\n"
        "Use:  py -3 -m outreach email\n".format(
            sys.version_info[0], sys.version_info[1]
        )
    )
    sys.exit(1)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "email"
    if mode == "email":
        from outreach.email_sender import start_consumer
        start_consumer()
    elif mode == "rejection":
        from outreach.rejection_emailer import start_consumer
        start_consumer()
    elif mode == "followup":
        print("Use: py -3 -m celery -A outreach.followup_manager worker --loglevel=info")
    else:
        print("Unknown mode: {}. Choose: email | rejection | followup".format(mode))
        sys.exit(1)


if __name__ == "__main__":
    main()

