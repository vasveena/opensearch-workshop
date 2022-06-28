import os
import json
import tweepy
import pytz
from tweepy import OAuthHandler
from tweepy import StreamingClient
from textblob import TextBlob
from elasticsearch import Elasticsearch, RequestsHttpConnection
from datetime import datetime
import requests
from requests_aws4auth import AWS4Auth

class process_tweet(tweepy.StreamingClient):
  print("in process_tweet")
  def on_data(self, data):
    print("on_data")
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
    print("in handler")
    
    # create instance of elasticsearch
    print("create instance of opensearch")

    region = 'us-east-1'
    service = 'es'
    awsauth = AWS4Auth(os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY"), region, service)

    host = 'vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com'

    es = Elasticsearch(
      hosts = [{'host': host, 'port': 443}],
      http_auth = awsauth,
      use_ssl = True,
      verify_certs = True,
      connection_class = RequestsHttpConnection
    )
    print("opensearch instance created")
    est = pytz.timezone('US/Eastern')

    bt=os.environ.get("TWITTER_API_TOKEN")
    printer = process_tweet(bt)
    printer.sample()
