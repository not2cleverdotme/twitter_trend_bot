import os
import time
import tweepy
import logging
import backoff
from openai import OpenAI
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_twitter_client():
    """Initialize Twitter client with API credentials."""
    try:
        # Verify all required environment variables are present
        required_env_vars = [
            'TWITTER_API_KEY',
            'TWITTER_API_SECRET',
            'TWITTER_ACCESS_TOKEN',
            'TWITTER_ACCESS_TOKEN_SECRET'
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

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

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def generate_tweet_content():
    """Generate cybersecurity-related tweet content using OpenAI with retry logic."""
    try:
        if not os.getenv('OPENAI_API_KEY'):
            raise ValueError("Missing OPENAI_API_KEY environment variable")

        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        prompt = """Generate a concise, informative tweet about cybersecurity. 
        Focus on one of these aspects:
        - Recent cybersecurity threats
        - Security best practices
        - Privacy tips
        - Data protection
        - Network security
        
        The tweet should be educational and include relevant hashtags.
        Maximum length: 280 characters.
        
        Format: Clear message followed by 2-3 relevant hashtags."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a cybersecurity expert creating educational content."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7,
            timeout=30.0  # Add timeout
        )
        
        tweet_content = response.choices[0].message.content.strip()
        
        # Ensure tweet is within Twitter's character limit
        if len(tweet_content) > 280:
            tweet_content = tweet_content[:277] + "..."
            
        return tweet_content

    except Exception as e:
        logger.error(f"Error generating tweet content: {str(e)}")
        raise

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def post_tweet():
    """Generate and post a tweet with retry logic."""
    try:
        # Get Twitter client
        twitter = get_twitter_client()
        
        # Generate tweet content
        tweet_content = generate_tweet_content()
        logger.info(f"Generated tweet: {tweet_content}")
        
        # Add small delay before posting
        time.sleep(2)
        
        # Post tweet
        response = twitter.create_tweet(text=tweet_content)
        tweet_id = response.data['id']
        logger.info(f"Successfully posted tweet with ID: {tweet_id}")
        
        return tweet_id
        
    except Exception as e:
        logger.error(f"Error posting tweet: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logger.info("Starting tweet bot...")
        
        # Verify all environment variables are set
        required_vars = [
            'TWITTER_API_KEY',
            'TWITTER_API_SECRET',
            'TWITTER_ACCESS_TOKEN',
            'TWITTER_ACCESS_TOKEN_SECRET',
            'OPENAI_API_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        tweet_id = post_tweet()
        logger.info("Tweet bot completed successfully")
    except Exception as e:
        logger.error(f"Tweet bot failed: {str(e)}")
        raise 