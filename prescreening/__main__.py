"""
prescreening/__main__.py — run with: py -3 -m prescreening chatbot | bgv
"""
import sys

# Guard: require Python 3
if sys.version_info[0] < 3:
    sys.stderr.write(
        "ERROR: This module requires Python 3. You are running Python {}.{}\n"
        "Use:  py -3 -m prescreening chatbot\n".format(
            sys.version_info[0], sys.version_info[1]
        )
    )
    sys.exit(1)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "chatbot"
    if mode == "chatbot":
        import uvicorn
        uvicorn.run(
            "prescreening.screening_chatbot:app",
            host="0.0.0.0",
            port=8001,
            reload=False,
        )
    elif mode == "bgv":
        from prescreening.background_checker import start_consumer
        start_consumer()
    else:
        print("Unknown mode: {}. Choose: chatbot | bgv".format(mode))
        sys.exit(1)


if __name__ == "__main__":
    main()

