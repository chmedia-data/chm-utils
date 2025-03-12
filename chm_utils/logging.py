import logging, requests, os

class SlackHandler(logging.StreamHandler):

    def __init__(self):
        logging.StreamHandler.__init__(self)
        self.setLevel(logging.WARNING)
        self.stage = os.environ.get('STAGE','local').upper()
        self.setFormatter(logging.Formatter(f'%(asctime)s [%(levelname)s] {self.stage} - %(filename)s:%(funcName)s - %(message)s'))

    def emit(self, record):
        
        msg = self.format(record)
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            json = {
                "channel": os.environ.get("SLACK_CHANNEL_ID"),
                "text": f"*{os.environ.get('STAGE','').upper()}*:\n```{msg}```"
            },
            headers={
                "Authorization": f"Bearer {os.environ.get('SLACK_TOKEN')}"
            }
        )
        if r.status_code != 200:
            print("Slack error")
        

def getLogger(name):
    
    streamFormatter = logging.Formatter('[%(levelname)s] %(filename)s:%(funcName)s - %(message)s')
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(streamFormatter)

    logger = logging.getLogger(name)
    logger.propagate = False
    logger.addHandler(streamHandler)
    logger.addHandler(SlackHandler)
    
    return logger