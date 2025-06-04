import os
import time
import tweepy
import logging
import openai
import requests
import json
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging with more detail
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
        logger.info("Starting Reddit fetch...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        url = 'https://www.reddit.com/r/cybersecurity/hot.json?limit=15'
        
        logger.info(f"Fetching from Reddit URL: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        logger.info(f"Reddit response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            posts = data['data']['children']
            logger.info(f"Found {len(posts)} total Reddit posts")
            
            # Filter out pinned posts and get relevant ones
            valid_posts = []
            for post in posts:
                post_data = post['data']
                if (not post_data['stickied'] and 
                    post_data['title'] and 
                    len(post_data['title']) > 10 and
                    post_data['score'] > 10 and
                    not post_data['title'].startswith('Weekly') and
                    not post_data['title'].startswith('Monthly')):
                    valid_posts.append(post_data)
                    logger.info(f"Found valid Reddit post: {post_data['title']}")
            
            if valid_posts:
                top_post = valid_posts[0]
                logger.info(f"Selected Reddit post: {top_post['title']}")
                
                # Get post text or first comment if no text
                description = top_post.get('selftext', '')
                if not description and top_post.get('num_comments', 0) > 0:
                    comment_url = f"https://www.reddit.com{top_post['permalink']}.json"
                    comment_response = requests.get(comment_url, headers=headers, timeout=10)
                    if comment_response.status_code == 200:
                        comment_data = comment_response.json()
                        if len(comment_data) > 1 and comment_data[1]['data']['children']:
                            first_comment = comment_data[1]['data']['children'][0]['data']['body']
                            description = first_comment[:250]
                
                return {
                    'title': top_post['title'],
                    'description': description[:250] if description else top_post['title'],
                    'url': f"https://reddit.com{top_post['permalink']}",
                    'source': 'Reddit'
                }
            else:
                logger.warning("No valid Reddit posts found after filtering")
        
        return None
    except Exception as e:
        logger.error(f"Error fetching from Reddit: {str(e)}")
        return None

def fetch_hackernews_cybersecurity():
    """Fetch relevant stories from HackerNews."""
    try:
        logger.info("Starting HackerNews fetch...")
        response = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
        logger.info(f"HackerNews initial response status: {response.status_code}")
        
        if response.status_code == 200:
            story_ids = response.json()[:30]  # Get top 30 stories
            logger.info(f"Found {len(story_ids)} HackerNews story IDs")
            
            security_keywords = ['security', 'cyber', 'hack', 'vulnerability', 'breach', 'privacy', 'malware', 'ransomware']
            
            for story_id in story_ids:
                story_url = f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json'
                logger.info(f"Fetching HackerNews story: {story_url}")
                story_response = requests.get(story_url, timeout=10)
                
                if story_response.status_code == 200:
                    story = story_response.json()
                    title = story.get('title', '')
                    logger.info(f"Checking HackerNews story: {title}")
                    
                    # Check if story is security related
                    title_lower = title.lower()
                    if any(keyword in title_lower for keyword in security_keywords):
                        logger.info(f"Found relevant HackerNews story: {title}")
                        
                        # Try to get text from URL if available
                        description = ''
                        if story.get('url'):
                            try:
                                url_response = requests.get(story['url'], timeout=5)
                                if url_response.status_code == 200:
                                    # Try to get meta description
                                    from bs4 import BeautifulSoup
                                    soup = BeautifulSoup(url_response.text, 'html.parser')
                                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                                    if meta_desc:
                                        description = meta_desc.get('content', '')[:250]
                            except:
                                pass
                        
                        if not description:
                            description = story.get('text', '')[:250]
                        
                        return {
                            'title': title,
                            'description': description if description else title,
                            'url': story.get('url', f'https://news.ycombinator.com/item?id={story_id}'),
                            'source': 'HackerNews'
                        }
        
        logger.warning("No relevant HackerNews stories found")
        return None
    except Exception as e:
        logger.error(f"Error fetching from HackerNews: {str(e)}")
        return None

def fetch_cybersecurity_news():
    """Fetch recent cybersecurity news from multiple sources."""
    try:
        # Try Reddit first
        logger.info("Attempting to fetch news from Reddit...")
        news = fetch_reddit_cybersecurity()
        
        # If no Reddit news, try HackerNews
        if not news:
            logger.info("No Reddit news found, trying HackerNews...")
            news = fetch_hackernews_cybersecurity()
        
        if news:
            logger.info(f"Successfully found news from {news['source']}:")
            logger.info(f"Title: {news['title']}")
            logger.info(f"URL: {news['url']}")
            logger.info(f"Description length: {len(news['description'])}")
            return news
            
        logger.warning("No news found from any source")
        return None
        
    except Exception as e:
        logger.error(f"Error in main news fetch: {str(e)}")
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