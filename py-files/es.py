import json
import tweepy
import pytz
from tweepy import OAuthHandler
from tweepy import StreamingClient
from textblob import TextBlob
from elasticsearch import Elasticsearch
from datetime import datetime

# create instance of elasticsearch
es = Elasticsearch(
    hosts=[{"host": "ip-80-0-18-136.ec2.internal", "port": 9200},
           {"host": "ip-80-0-29-251.ec2.internal", "port": 9200},
           {"host": "ip-80-0-30-161.ec2.internal", "port": 9200},
           {"host": "ip-80-0-28-34.ec2.internal", "port": 9200},
          ],
    http_auth=["elastic", "changeme"],
)
est = pytz.timezone('US/Eastern')

class IDPrinter(tweepy.StreamingClient):
  def on_data(self, data):
    # decode json
    dict_data = json.loads(data)

    # pass tweet into TextBlob
    tweet_id = TextBlob(dict_data['data']['id'])
    timestamp = datetime.now().astimezone(est).strftime("%Y-%m-%d %H:%M:%S")
    tweet = TextBlob(dict_data['data']['text'])
    tweetstr = str(tweet)
    user_name = tweetstr[tweetstr.find('@')+1 : tweetstr.find(':')]

    # determine if sentiment is positive, negative, or neutral
    if tweet.sentiment.polarity < 0:
        sentiment = "negative"
    elif tweet.sentiment.polarity == 0:
        sentiment = "neutral"
    else:
        sentiment = "positive"

    # output values
    print("tweet_id: "+ str(tweet_id))
    print("timestamp: " +timestamp)
    print("user_name: " + user_name)
    print("tweet_polarity: " + str(tweet.sentiment.polarity))
    print("tweet_subjectivity: " + str(tweet.sentiment.subjectivity))
    print("sentiment: " + sentiment)

    # index values into OSS Elasticsearch
    es.index(index="data_sentiment",
                 doc_type="test-type",
                 body={"user": user_name,
                       "timestamp": timestamp,
                       "message": dict_data["data"]["text"],
                       "polarity": tweet.sentiment.polarity,
                       "subjectivity": tweet.sentiment.subjectivity,
                       "sentiment": sentiment})
    
if __name__ == '__main__':

    bt=os.environ.get("TWITTER_API_TOKEN")
    printer = IDPrinter(bt)
    printer.sample()
