import os
import tweepy
import logging
from openai import OpenAI
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_twitter_client():
    """Initialize Twitter client with API credentials."""
    try:
        client = tweepy.Client(
            consumer_key=os.getenv('TWITTER_API_KEY'),
            consumer_secret=os.getenv('TWITTER_API_SECRET'),
            access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        )
        return client
    except Exception as e:
        logger.error(f"Error initializing Twitter client: {e}")
        raise

def generate_tweet_content():
    """Generate cybersecurity-related tweet content using OpenAI."""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        prompt = """Generate a concise, informative tweet about cybersecurity. 
        Focus on one of these aspects:
        - Recent cybersecurity threats
        - Security best practices
        - Privacy tips
        - Data protection
        - Network security
        
        The tweet should be educational and include relevant hashtags.
        Maximum length: 280 characters."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a cybersecurity expert creating educational content."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        
        tweet_content = response.choices[0].message.content.strip()
        
        # Ensure tweet is within Twitter's character limit
        if len(tweet_content) > 280:
            tweet_content = tweet_content[:277] + "..."
            
        return tweet_content

    except Exception as e:
        logger.error(f"Error generating tweet content: {e}")
        raise

def post_tweet():
    """Generate and post a tweet."""
    try:
        # Get Twitter client
        twitter = get_twitter_client()
        
        # Generate tweet content
        tweet_content = generate_tweet_content()
        logger.info(f"Generated tweet: {tweet_content}")
        
        # Post tweet
        response = twitter.create_tweet(text=tweet_content)
        tweet_id = response.data['id']
        logger.info(f"Successfully posted tweet with ID: {tweet_id}")
        
        return tweet_id
        
    except Exception as e:
        logger.error(f"Error posting tweet: {e}")
        raise

if __name__ == "__main__":
    try:
        logger.info("Starting tweet bot...")
        tweet_id = post_tweet()
        logger.info("Tweet bot completed successfully")
    except Exception as e:
        logger.error(f"Tweet bot failed: {e}")
        raise 