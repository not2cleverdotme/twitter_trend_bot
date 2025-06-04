import os
import time
import tweepy
import logging
import openai
import requests
from datetime import datetime, timedelta
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

def fetch_cybersecurity_news():
    """Fetch recent cybersecurity news from various sources."""
    try:
        # Using NewsAPI to fetch cybersecurity news
        api_key = os.getenv('NEWS_API_KEY')
        if not api_key:
            logger.warning("NEWS_API_KEY not found, using default cybersecurity topics")
            return None

        # Calculate date for last 24 hours
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        url = 'https://newsapi.org/v2/everything'
        params = {
            'q': 'cybersecurity OR "cyber security" OR "cyber attack" OR "data breach"',
            'from': yesterday,
            'sortBy': 'relevancy',
            'language': 'en',
            'pageSize': 5,  # Get top 5 articles
            'apiKey': api_key
        }
        
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            news_data = response.json()
            if news_data.get('articles'):
                # Filter out articles without proper content
                valid_articles = [
                    article for article in news_data['articles']
                    if article.get('title') and article.get('description') and
                    'null' not in article['title'].lower() and
                    len(article['description']) > 50
                ]
                if valid_articles:
                    logger.info(f"Found {len(valid_articles)} valid news articles")
                    return valid_articles[0]
                else:
                    logger.warning("No valid articles found")
            else:
                logger.warning("No articles found in the response")
        else:
            logger.warning(f"News API returned status code: {response.status_code}")
        
        return None
    except Exception as e:
        logger.warning(f"Error fetching news: {e}")
        return None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def generate_tweet_content():
    """Generate cybersecurity-related tweet content using OpenAI with retry logic."""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable")
            
        # Ensure API key is a clean string without any encoding issues
        api_key = api_key.strip()
        if not api_key.startswith('sk-'):
            raise ValueError("Invalid OpenAI API key format. Key should start with 'sk-'")

        openai.api_key = api_key
        
        # Fetch recent news
        news_article = fetch_cybersecurity_news()
        
        if news_article:
            logger.info("Using news article for tweet generation")
            logger.info(f"Article title: {news_article['title']}")
            
            prompt = f"""Create an engaging tweet about this cybersecurity news:

Article: {news_article['title']}
Details: {news_article['description']}

Your task is to:
1. Start with a hook or key finding
2. Add a brief but impactful explanation
3. End with 2 relevant hashtags
4. Keep the entire tweet under 280 characters
5. Make it sound natural, not like a news headline

Example format:
🚨 Key finding/hook
Brief explanation or impact
#relevanthashtag1 #relevanthashtag2"""

        else:
            logger.info("No news article found, using default cybersecurity topics")
            prompt = """Generate an engaging cybersecurity tweet about one of these current topics:
            - Zero-day vulnerabilities
            - Ransomware prevention
            - Multi-factor authentication
            - Social engineering threats
            - Password security best practices
            
            Format:
            🚨 Start with an attention-grabbing fact or tip
            Add a brief, practical explanation
            End with 2 relevant hashtags
            
            Keep it under 280 characters and make it conversational."""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a cybersecurity expert who creates engaging, informative social media content. Your style is authoritative but conversational."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
            request_timeout=30
        )
        
        tweet_content = response.choices[0].message['content'].strip()
        
        # Ensure tweet is within Twitter's character limit
        if len(tweet_content) > 280:
            tweet_content = tweet_content[:277] + "..."
        
        logger.info(f"Generated tweet content: {tweet_content}")
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