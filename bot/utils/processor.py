from html import unescape
import re
from discord import Webhook, RequestsWebhookAdapter, Embed
import discord
import random
from datetime import datetime



COLORS = [
    0xFFFF00
]
WH_REGEX = r"discord(app)?\.com\/api\/webhooks\/(?P<id>\d+)\/(?P<token>.+)"


def worth_posting_location(location, coordinates, retweeted, include_retweet):
    location = [location[i : i + 4] for i in range(0, len(location), 4)]

    for box in location:
        for coordinate in coordinates:
            if box[0] < coordinate[0] < box[2] and box[1] < coordinate[1] < box[3]:
                if not include_retweet and retweeted:
                    return False
                return True
    return False


def worth_posting_track(track, hashtags, text, retweeted, include_retweet):
    for t in track:
        if t.startswith("#"):
            if t[1:] in map(lambda x: x["text"], hashtags):
                if not include_retweet and retweeted:
                    return False
                return True
        elif t in text:
            if not include_retweet and retweeted:
                return False
            return True
    return False


def worth_posting_follow(
    tweeter_id,
    twitter_ids,
    in_reply_to_twitter_id,
    retweeted,
    include_reply_to_user,
    include_user_reply,
    include_retweet,
):
    if tweeter_id not in twitter_ids:
        worth_posting = False
        if include_reply_to_user:
            if in_reply_to_twitter_id in twitter_ids:
                worth_posting = True
    else:
        worth_posting = True
        if not include_user_reply and in_reply_to_twitter_id is not None:
            worth_posting = False

    if not include_retweet:
        if retweeted:
            worth_posting = False
    return worth_posting


def keyword_set_present(keyword_sets, text):
    for keyword_set in keyword_sets:
        keyword_present = [keyword.lower() in text.lower() for keyword in keyword_set]
        keyword_set_present = all(keyword_present)
        if keyword_set_present:
            return True
    return False


def blackword_set_present(blackword_sets, text):
    if blackword_sets == [[""]]:
        return False
    for blackword_set in blackword_sets:
        blackword_present = [blackword.lower() in text.lower() for blackword in blackword_set]
        blackword_set_present = all(blackword_present)
        if blackword_set_present:
            return True
    return False


class Processor:
    def __init__(self, status_tweet, discord_config):
        self.status_tweet = status_tweet
        self.discord_config = discord_config
        self.text = ""
        self.url = ""
        self.user = ""
        self.embed = None
        self.initialize()

    def worth_posting_location(self):
        if (
            self.status_tweet.get("coordinates", None) is not None
            and self.status_tweet["coordinates"].get("coordinates", None) is not None
        ):
            coordinates = [self.status_tweet["coordinates"]["coordinates"]]
        else:
            coordinates = []

        if (
            self.status_tweet.get("place", None) is not None
            and self.status_tweet["place"].get("bounding_box", None) is not None
            and self.status_tweet["place"]["bounding_box"].get("coordinates", None) is not None
        ):
            tmp = self.status_tweet["place"]["bounding_box"]["coordinates"]
        else:
            tmp = []

        for (
            tmp_
        ) in tmp:  # for some reason Twitter API places the coordinates into a triple array.......
            for c in tmp_:
                coordinates.append(c)

        return worth_posting_location(
            location=self.discord_config.get("location", []),
            coordinates=coordinates,
            retweeted=self.status_tweet["retweeted"] or "retweeted_status" in self.status_tweet,
            include_retweet=self.discord_config.get("IncludeRetweet", True),
        )

    def worth_posting_track(self):
        if "extended_tweet" in self.status_tweet:
            hashtags = sorted(
                self.status_tweet["extended_tweet"]["entities"]["hashtags"],
                key=lambda k: k["text"],
                reverse=True,
            )
        else:
            hashtags = sorted(
                self.status_tweet["entities"]["hashtags"], key=lambda k: k["text"], reverse=True
            )

        return worth_posting_track(
            track=self.discord_config.get("track", []),
            hashtags=hashtags,
            text=self.text,
            retweeted=self.status_tweet["retweeted"] or "retweeted_status" in self.status_tweet,
            include_retweet=self.discord_config.get("IncludeRetweet", True),
        )

    def worth_posting_follow(self):
        return worth_posting_follow(
            tweeter_id=self.status_tweet["user"]["id_str"],
            twitter_ids=self.discord_config.get("twitter_ids", []),
            in_reply_to_twitter_id=self.status_tweet["in_reply_to_user_id_str"],
            retweeted=self.status_tweet["retweeted"] or "retweeted_status" in self.status_tweet,
            include_reply_to_user=self.discord_config.get("IncludeReplyToUser", True),
            include_user_reply=self.discord_config.get("IncludeUserReply", True),
            include_retweet=self.discord_config.get("IncludeRetweet", True),
        )

    def initialize(self):
        if "retweeted_status" in self.status_tweet:
            if "extended_tweet" in self.status_tweet["retweeted_status"]:
                self.text = self.status_tweet["retweeted_status"]["extended_tweet"]["full_text"]
            elif "full_text" in self.status_tweet["retweeted_status"]:
                self.text = self.status_tweet["retweeted_status"]["full_text"]
            else:
                self.text = self.status_tweet["retweeted_status"]["text"]
        elif "extended_tweet" in self.status_tweet:
            self.text = self.status_tweet["extended_tweet"]["full_text"]
        elif "full_text" in self.status_tweet:
            self.text = self.status_tweet["full_text"]
        else:
            self.text = self.status_tweet["text"]

        for url in self.status_tweet["entities"].get("urls", []):
            if url["expanded_url"] is None:
                continue
            self.text = self.text.replace(
                url["url"], "[%s](%s)" % (url["display_url"], url["expanded_url"])
            )

        for userMention in self.status_tweet["entities"].get("user_mentions", []):
            self.text = self.text.replace(
                "@%s" % userMention["screen_name"],
                "[@%s](https://twitter.com/%s)"
                % (userMention["screen_name"], userMention["screen_name"]),
            )

        if "extended_tweet" in self.status_tweet:
            for hashtag in sorted(
                self.status_tweet["extended_tweet"]["entities"].get("hashtags", []),
                key=lambda k: k["text"],
                reverse=True,
            ):
                self.text = self.text.replace(
                    "#%s" % hashtag["text"],
                    "[#%s](https://twitter.com/hashtag/%s)" % (hashtag["text"], hashtag["text"]),
                )

        for hashtag in sorted(
            self.status_tweet["entities"].get("hashtags", []),
            key=lambda k: k["text"],
            reverse=True,
        ):
            self.text = self.text.replace(
                "#%s" % hashtag["text"],
                "[#%s](https://twitter.com/hashtag/%s)" % (hashtag["text"], hashtag["text"]),
            )
        self.text = unescape(self.text)
        self.url = "https://twitter.com/{}/status/{}".format(
            self.status_tweet["user"]["screen_name"], self.status_tweet["id_str"]
        )
        self.user = self.status_tweet["user"]["name"]

    def keyword_set_present(self):
        return keyword_set_present(self.discord_config.get("keyword_sets", [[""]]), self.text)

    def blackword_set_present(self):
        return blackword_set_present(self.discord_config.get("blackword_sets", [[""]]), self.text)

    def attach_field(self):
        if self.discord_config.get("IncludeQuote", True) and "quoted_status" in self.status_tweet:
            if self.status_tweet["quoted_status"].get("text"):
                text = self.status_tweet["quoted_status"]["text"]
                for url in self.status_tweet["quoted_status"]["entities"].get("urls", []):
                    if url["expanded_url"] is None:
                        continue
                    text = text.replace(
                        url["url"], "[%s](%s)" % (url["display_url"], url["expanded_url"])
                    )

                for userMention in self.status_tweet["quoted_status"]["entities"].get(
                    "user_mentions", []
                ):
                    text = text.replace(
                        "@%s" % userMention["screen_name"],
                        "[@%s](https://twitter.com/%s)"
                        % (userMention["screen_name"], userMention["screen_name"]),
                    )

                for hashtag in sorted(
                    self.status_tweet["quoted_status"]["entities"].get("hashtags", []),
                    key=lambda k: k["text"],
                    reverse=True,
                ):
                    text = text.replace(
                        "#%s" % hashtag["text"],
                        "[#%s](https://twitter.com/hashtag/%s)"
                        % (hashtag["text"], hashtag["text"]),
                    )

                text = unescape(text)
                self.embed.add_field(
                    name=self.status_tweet["quoted_status"]["user"]["screen_name"], value=text
                )

    def attach_media(self):
        if (
            self.discord_config.get("IncludeAttachment", True)
            and "retweeted_status" in self.status_tweet
        ):
            if (
                "extended_tweet" in self.status_tweet["retweeted_status"]
                and "media" in self.status_tweet["retweeted_status"]["extended_tweet"]["entities"]
            ):
                for media in self.status_tweet["retweeted_status"]["extended_tweet"]["entities"][
                    "media"
                ]:
                    if media["type"] == "photo":
                        self.embed.set_image(url=media["media_url_https"])
                    elif media["type"] == "video":
                        pass
                    elif media["type"] == "animated_gif":
                        pass

            if "media" in self.status_tweet["retweeted_status"]["entities"]:
                for media in self.status_tweet["retweeted_status"]["entities"]["media"]:
                    if media["type"] == "photo":
                        self.embed.set_image(url=media["media_url_https"])
                    elif media["type"] == "video":
                        pass
                    elif media["type"] == "animated_gif":
                        pass

            if (
                "extended_entities" in self.status_tweet["retweeted_status"]
                and "media" in self.status_tweet["retweeted_status"]["extended_entities"]
            ):
                for media in self.status_tweet["retweeted_status"]["extended_entities"]["media"]:
                    if media["type"] == "photo":
                        self.embed.set_image(url=media["media_url_https"])
                    elif media["type"] == "video":
                        pass
                    elif media["type"] == "animated_gif":
                        pass
        else:
            if (
                "extended_tweet" in self.status_tweet
                and "media" in self.status_tweet["extended_tweet"]["entities"]
            ):
                for media in self.status_tweet["extended_tweet"]["entities"]["media"]:
                    if media["type"] == "photo":
                        self.embed.set_image(url=media["media_url_https"])
                    elif media["type"] == "video":
                        pass
                    elif media["type"] == "animated_gif":
                        pass

            if "media" in self.status_tweet["entities"]:
                for media in self.status_tweet["entities"]["media"]:
                    if media["type"] == "photo":
                        self.embed.set_image(url=media["media_url_https"])
                    elif media["type"] == "video":
                        pass
                    elif media["type"] == "animated_gif":
                        pass

            if (
                "extended_entities" in self.status_tweet
                and "media" in self.status_tweet["extended_entities"]
            ):
                for media in self.status_tweet["extended_entities"]["media"]:
                    if media["type"] == "photo":
                        self.embed.set_image(url=media["media_url_https"])
                    elif media["type"] == "video":
                        pass
                    elif media["type"] == "animated_gif":
                        pass

    def create_embed(self):
        self.embed = Embed(
            colour=random.choice(COLORS),
            url="https://twitter.com/{}/status/{}".format(
                self.status_tweet["user"]["screen_name"], self.status_tweet["id_str"]
            ),
            title=self.status_tweet["user"]["name"],
            description=self.text,
            timestamp=datetime.strptime(
                self.status_tweet["created_at"], "%a %b %d %H:%M:%S +0000 %Y"
            ),
        )

        self.embed.set_author(
            name=self.status_tweet["user"]["screen_name"],
            url="https://twitter.com/" + self.status_tweet["user"]["screen_name"],
            icon_url=self.status_tweet["user"]["profile_image_url"],
        )
        self.embed.set_footer(
            text="Tweet criado às",
            icon_url="https://th.bing.com/th/id/R.cdeea32c97161a151a317e63c3ad618c?rik=6%2b17a9P7uYA18g&pid=ImgRaw&r=0",
        )

    def send_message(self, wh_url):
        match = re.search(WH_REGEX, wh_url)

        if match:
            webhook = Webhook.partial(
                int(match.group("id")), match.group("token"), adapter=RequestsWebhookAdapter()
            )
            try:
                if self.discord_config.get("CreateEmbed", True):
                    webhook.send(
                        embed=self.embed,
                        content=self.discord_config.get("custom_message", "").format(
                            user=self.user, text=self.text, url=self.url
                        ),
                    )
                else:
                    webhook.send(
                        content=self.discord_config.get("custom_message", "").format(
                            user=self.user, text=self.text, url=self.url
                        )
                    )
            except discord.errors.NotFound as error:
                print(
                    f"---------Error---------\n"
                    f"discord.errors.NotFound\n"
                    f"The Webhook does not exist."
                    f"{error}\n"
                    f"-----------------------"
                )
            except discord.errors.Forbidden as error:
                print(
                    f"---------Error---------\n"
                    f"discord.errors.Forbidden\n"
                    f"The authorization token of your Webhook is incorrect."
                    f"{error}\n"
                    f"-----------------------"
                )
            except discord.errors.InvalidArgument as error:
                print(
                    f"---------Error---------\n"
                    f"discord.errors.InvalidArgument\n"
                    f"You modified the code. You can't mix embed and embeds."
                    f"{error}\n"
                    f"-----------------------"
                )
            except discord.errors.HTTPException as error:
                print(
                    f"---------Error---------\n"
                    f"discord.errors.HTTPException\n"
                    f"Your internet connection is whack."
                    f"{error}\n"
                    f"-----------------------"
                )
        else:
            print(
                f"---------Error---------\n"
                f"The following webhook URL is invalid:\n"
                f"{wh_url}\n"
                f"-----------------------"
            )


if __name__ == "__main__":
    p = Processor({}, {"keyword_sets": [[""]]})
    p.text = "Hello World!"
    print(p.keyword_set_present())
