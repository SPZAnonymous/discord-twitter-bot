from bot.utils.dataIO import fileIO
import os

os.chdir(os.path.dirname(__file__))
false_strings = ["false", "False", "f", "F", "0", "", "n", "N", "no", "No", "NO", "FALSE"]

if fileIO("config.json", "check"):
    config = fileIO("config.json", "load")
else:
    config = {
        "Twitter": {
            "consumer_key": os.environ.get("CONSUMER_KEY", None),
            "consumer_secret": os.environ.get("CONSUMER_SECRET", None),
            "access_token": os.environ.get("ACCESS_TOKEN", None),
            "access_token_secret": os.environ.get("ACCESS_TOKEN_SECRET", None)
        },
        "Discord": [{
            "IncludeReplyToUser": False if os.environ.get("INCLUDE_REPLY_TO_USER", None) in false_strings else True,
            "IncludeRetweet": False if os.environ.get("INCLUDE_RETWEET", None) in false_strings else True,
            "IncludeUserReply": False if os.environ.get("INCLUDE_USER_REPLY", None) in false_strings else True,
            "webhook_urls": os.environ.get("WEBHOOK_URL", "").replace(" ", "").split(","),
            "twitter_ids": os.environ.get("TWITTER_ID", "").replace(" ", "").split(","),
            "custom_message": os.environ.get("CUSTOM_MESSAGE", None),
            "keyword_sets": [keyword_set.split("+") for keyword_set in os.environ.get("KEYWORDS", "").replace(" ", "").split(",")]
        }]
    }

if __name__ == '__main__':
    print(config)
