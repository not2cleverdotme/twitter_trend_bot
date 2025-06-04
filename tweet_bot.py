import os
import time
import tweepy
import logging
import openai
import requests
import json
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

def fetch_reddit_cybersecurity():
    """Fetch recent posts from r/cybersecurity."""
    try:
        headers = {'User-Agent': 'CybersecurityNewsBot/1.0'}
        url = 'https://www.reddit.com/r/cybersecurity/hot.json?limit=10'
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            posts = data['data']['children']
            
            # Filter out pinned posts and get relevant ones
            valid_posts = [
                post['data'] for post in posts
                if not post['data']['stickied']
                and post['data']['title']
                and len(post['data']['title']) > 10
                and post['data']['score'] > 10  # Has some upvotes
            ]
            
            if valid_posts:
                top_post = valid_posts[0]
                return {
                    'title': top_post['title'],
                    'description': top_post.get('selftext', '')[:250],
                    'url': f"https://reddit.com{top_post['permalink']}",
                    'source': 'Reddit'
                }
        
        return None
    except Exception as e:
        logger.warning(f"Error fetching from Reddit: {e}")
        return None

def fetch_hackernews_cybersecurity():
    """Fetch relevant stories from HackerNews."""
    try:
        # First get top stories
        response = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
        if response.status_code == 200:
            story_ids = response.json()[:20]  # Get top 20 stories
            
            for story_id in story_ids:
                # Get story details
                story_url = f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json'
                story_response = requests.get(story_url, timeout=10)
                
                if story_response.status_code == 200:
                    story = story_response.json()
                    
                    # Check if story is security related
                    security_keywords = ['security', 'cyber', 'hack', 'vulnerability', 'breach', 'privacy']
                    title_lower = story.get('title', '').lower()
                    
                    if any(keyword in title_lower for keyword in security_keywords):
                        return {
                            'title': story.get('title'),
                            'description': story.get('text', '')[:250],
                            'url': story.get('url', f'https://news.ycombinator.com/item?id={story_id}'),
                            'source': 'HackerNews'
                        }
        
        return None
    except Exception as e:
        logger.warning(f"Error fetching from HackerNews: {e}")
        return None

def fetch_cybersecurity_news():
    """Fetch recent cybersecurity news from multiple sources."""
    try:
        # Try Reddit first
        logger.info("Fetching news from Reddit...")
        news = fetch_reddit_cybersecurity()
        
        # If no Reddit news, try HackerNews
        if not news:
            logger.info("Fetching news from HackerNews...")
            news = fetch_hackernews_cybersecurity()
        
        if news:
            logger.info(f"Found news from {news['source']}: {news['title']}")
            return news
            
        logger.warning("No news found from any source")
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
            logger.info(f"Using {news_article['source']} article for tweet generation")
            
            source_link = f"\nSource: {news_article['url']}"
            
            prompt = f"""Create an engaging tweet about this cybersecurity news:

Article: {news_article['title']}
Details: {news_article['description']}
Source: {news_article['source']}

Your task is to:
1. Start with 🚨 and a compelling hook from the article
2. Add key impact or takeaway
3. End with relevant hashtag
4. Leave room for the source URL
5. Keep it natural and engaging

Format example:
🚨 [Compelling hook]
[Key impact/takeaway]
#cybersecurity"""

        else:
            logger.info("No news found, using default cybersecurity topics")
            prompt = """Generate an engaging cybersecurity tweet about one of these current topics:
            - Zero-day vulnerabilities
            - Ransomware prevention
            - Multi-factor authentication
            - Social engineering threats
            - Password security best practices
            
            Format:
            🚨 Start with an attention-grabbing fact or tip
            Add a brief, practical explanation
            End with #cybersecurity
            
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
        
        # If we have a news article, append the source URL
        if news_article:
            # Ensure we have room for the URL by truncating if necessary
            max_length = 280 - len(news_article['url']) - 2  # 2 chars for newline
            if len(tweet_content) > max_length:
                tweet_content = tweet_content[:max_length-3] + "..."
            tweet_content = f"{tweet_content}\n{news_article['url']}"
        
        # Final length check
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