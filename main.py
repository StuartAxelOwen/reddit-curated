__author__ = 'stuart'

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
from concurrent.futures import ThreadPoolExecutor
import random

# TODOs:
# - score based on comment length
# - score based on comment sentiment

BASE_URL = 'http://reddit.com'
DAYS_TO_LOOK = 120
def HEADERS():
    return {'User-Agent': 'reddit-curator-' + str(random.randint(0, 20))}


class Link(object):
    def __init__(self, url: str, comments: list, title: str, created_at: datetime,
                 score: int):
        self.url = url
        self.comments = comments
        self.title = title
        self.created_at = created_at
        self.score = score

    def __hash__(self):
        return hash(self.url)

    @staticmethod
    def from_user_page_node(node):
        url = node.find('a', {'class': 'comments'}).get('href')
        comments = []
        title = node.find('p', {'class': 'title'}).a.text
        created_at = datetime.strptime(node.find('time').get('datetime').replace(':', ''),
                                       '%Y-%m-%dT%H%M%S%z')
        score = int(node.find(attrs={'class': 'score unvoted'}).text.split(' ')[0])
        return Link(url, comments, title, created_at, score)

    @staticmethod
    def from_page_node(node):
        url = node.find('a', {'class': 'comments'}).get('href')
        comments = []
        title = node.find('p', {'class': 'title'}).a.text
        created_at = datetime.strptime(node.find('time').get('datetime').replace(':', ''),
                                       '%Y-%m-%dT%H%M%S%z')
        score = int(node.find(attrs={'class': 'score unvoted'}).text.split(' ')[0])
        return Link(url, comments, title, created_at, score)


class User(object):
    def __init__(self, name: str):
        self.name = name
        self.comments = []
        self.links = []
        self.posts = []

    def __repr__(self):
        return 'User {} with {} comments and {} links in the last {} days'.format(
            self.name, len(self.comments), len(self.links), DAYS_TO_LOOK)

    def __hash__(self):
        return hash(self.name)

class Comment(object):
    def __init__(self, url: str, link: Link, author: User, content: str, created_at: datetime,
                 score: int, parent=None):
        self.link = link
        self.author = author
        self.content = content
        self.url = url
        self.created_at = created_at
        self.score = score
        self.parent = parent

    def __repr__(self):
        return '{} said:\n{}\n{}'.format(self.author, self.content, self.link)

    def __hash__(self):
        return hash(self.url)

    @staticmethod
    def from_user_page_node(node):
        link_node = node.p.find_all('a', {'class', 'title'})[0]
        link = Link(node.find_all('li')[2].a.get('href'), [], link_node.text,
                    None, 0)
        author = User(node.find('div', {'class': 'entry'}).find(attrs={'class': 'author'}).text)
        content = node.find(attrs={'class': 'usertext'}).text
        created_at = datetime.strptime(node.find('time').get('datetime').replace(':', ''),
                                       '%Y-%m-%dT%H%M%S%z')
        url = node.find('li', {'class': 'first'}).a.get('href')
        score = int(node.find(attrs={'class': 'score unvoted'}).text.split(' ')[0])
        return Comment(url, link, author, content, created_at, score)

def post_from_user_page_node(node):
    if 'comment' in node.get('class'):
        return Comment.from_user_page_node(node)
    elif 'link' in node.get('class'):
        return Link.from_user_page_node(node)
    else:
        raise ValueError("Provided node is not a comment or link:\n{}".format(node))

sauce = None
def get_user(username: str):
    user = User(username)
    user_page = requests.get('http://reddit.com/u/{}'.format(username), headers=HEADERS())
    soup = BeautifulSoup(user_page.content)
    global sauce
    sauce = BeautifulSoup(user_page.content)
    for _ in range(5):
        # Fetch 5 pages max
        posts = list(map(post_from_user_page_node,
                         soup.find(id='siteTable').find_all(attrs={'class': 'thing'})))
        recent_posts = filter(lambda p: datetime.utcnow().replace(tzinfo=pytz.utc) - p.created_at < timedelta(days=DAYS_TO_LOOK),
                              posts)
        recent_posts = list(recent_posts)

        for post in recent_posts:
            if isinstance(post, Comment):
                user.comments.append(post)
            elif isinstance(post, Link):
                user.links.append(post)
            else:
                raise ValueError('Post must be either Link or Comment.\n{}'.format(post))
            user.posts.append(post)

        if len(posts) != len(recent_posts):
            break
        else:
            next_url = list(filter(lambda a: 'next' in a.text,
                                   soup.find_all('a')))[0].get('href')
            soup = BeautifulSoup(requests.get(next_url, headers=HEADERS()).content)

    return user

def get_link(url: str):
    soup = BeautifulSoup(requests.get(url).content)
    return soup

def get_links(urls: list):
    with ThreadPoolExecutor(24) as executor:
        return list(executor.map(get_link, urls))


def walk(username: str):
    """ Find all users connected to the root user through comments in the last N days """
    user = get_user(username)
    link_urls = list(map(lambda link: link.url, user.links))
    link_urls += list(map(lambda comment: comment.link.url, user.comments))
    return get_links(link_urls)



username = 'blowjobtransistor'
# me = get_user(username)
links = walk(username)
