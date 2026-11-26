import logging, requests, os

class SlackHandler(logging.Handler):

    def __init__(self, timeout=5):
        logging.Handler.__init__(self)
        self.setLevel(logging.WARNING)
        self.timeout = timeout
        self.stage = os.environ.get('STAGE','local').upper()
        self.setFormatter(logging.Formatter(f'%(asctime)s [%(levelname)s] {self.stage} - %(filename)s:%(funcName)s - %(message)s'))

    def emit(self, record):
        # A logging handler must never raise into the code that logged.
        try:
            msg = self.format(record)
            r = requests.post(
                "https://slack.com/api/chat.postMessage",
                json = {
                    "channel": os.environ.get("SLACK_CHANNEL_ID"),
                    "text": f"*{self.stage}*:\n```{msg}```"
                },
                headers={
                    "Authorization": f"Bearer {os.environ.get('SLACK_TOKEN')}"
                },
                timeout=self.timeout,
            )
            # Slack reports failures as HTTP 200 with ok=false.
            body = r.json() if r.status_code == 200 else {}
            if not body.get("ok"):
                print(f"Slack error: HTTP {r.status_code}, {body.get('error')}")
        except Exception as e:
            print(f"Slack error: {type(e).__name__}: {e}")


def getLogger(name, slack=True):

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    streamFormatter = logging.Formatter('[%(levelname)s] %(filename)s:%(funcName)s - %(message)s')
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(streamFormatter)

    logger.propagate = False
    logger.addHandler(streamHandler)
    if slack and os.environ.get("SLACK_TOKEN") and os.environ.get("SLACK_CHANNEL_ID"):
        logger.addHandler(SlackHandler())

    return logger
