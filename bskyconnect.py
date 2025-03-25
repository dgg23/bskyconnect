#!/usr/bin/env python3
#title           : bskyconnect.py
#description     : Automated connection management
#author          : tellynumner
#date            : 03/21/25
#version         : 1.3
#usage           : ./bskyconnect.py --account ACCOUNT --program PROGRAM --limit LIMIT
#notes           :
#python_version  : 3.12.3
#=============================================================================

import argparse
from atproto import Client
import datetime
from my_data import *
import sys
import time

client = Client()
client.login(my_user, pasw)

def my_args():
    '''Argument parser'''
    parser = argparse.ArgumentParser(description='bskyconnect')
    parser.add_argument("--account", help="Pass a Bluesky account username.")
    parser.add_argument("--program", help="follows, followers, both, connect")
    parser.add_argument("--limit", help="Pass a numeric limit for the connect program.")
    args = parser.parse_args()
    return args

def logger(level, message):
    '''Logs a message to a file and prints it to the screen.'''
    now = datetime.datetime.now()
    ts = '[' + now.strftime("%y/%m/%d %H:%M:%S") + ']'
    copy = ts + ' ' + level + ' ' + message
    with open('bskyconnect.log', 'a') as lf:
        lf.write(copy + '\n')
    print(copy)
    return None

def get_followers(user):
    '''Collects profile data on the list of accounts following us.'''
    followers = []
    response = client.get_followers(user, None, 100)
    followers.extend(response.followers)
    while response.cursor:
        response = client.get_followers(user, response.cursor, 100)
        followers.extend(response.followers)
    return followers

def get_follows(user):
    '''Collects profile data on the list of accounts we follow.'''
    follows = []
    response = client.get_follows(user, None, 100)
    follows.extend(response.follows)
    while response.cursor:
        response = client.get_follows(user, response.cursor, 100)
        follows.extend(response.follows)
    return follows

def follow_user(user):
    '''Follows a user'''
    try:
        client.follow(user.did)
        time.sleep(2)
        logger('FOLLOWED', user.handle)
    except:
        logger('FAILED', 'Failed to follow ' + user.handle + '.' )
    return None

def unfollow_user(user):
    '''Unfollows a user'''
    try:
        client.delete_follow(user.viewer['following'])
        time.sleep(2)
        logger('REMOVED', user.handle)
    except:
        logger('FAILED', 'Failed to unfollow ' + user.handle + '.' )
    return None

def follow_check(user):
    '''Checks to see if we follow a user.'''
    try:
        follow = user.viewer['following']
    except:
        logger('FAILED', "We failed get the follow status for " + user.handle + '.')
        return 'FOLLOWING'
    if follow is not None:
        return 'FOLLOWING'
    else:
        return None

def follower_check(user):
    '''Checks to see if a user follows us.'''
    try:
        follows = user.viewer['followed_by']
    except:
        logger('FAILED', "We failed to get the follow status for " + user.handle + '.')
        return "FOLLOWS"
    if follows != None:
        return "FOLLOWS"
    else:
        return 'NOFOLLOWS'

def last_post_date(user, days_ago):
    """
    Gets the date of the last post of a user. Reports if the last post was more recent than some
    days ago or if it is older.
    """
    days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_ago)
    try:
        response = client.get_author_feed(user.handle)
    except:
        logger('FAILED', "We failed to scan " + user.handle + " feed! Skipping the last post date check.")
        return 'CURRENT'
    if len(response.feed) > 0:
        try:
            last_post = datetime.datetime.fromisoformat(response.feed[1].post.indexed_at)
        except:
            logger('BOTALERT', user.handle + ' only has 1 post!')
            return 'BOTALERT'
    else:
        logger('BOTALERT', user.handle + ' has never posted!')
        return 'BOTALERT'
    if last_post > days_ago:
        return 'CURRENT'
    else:
        return 'OLD'

def influencer_check(user, ratio):
    """
    Checks a user's profile for their follower/following count to try to determine their follower
    to follower ratio which determines whether or not they are an influencer.
    """
    profile = client.get_profile(user.did)
    followers = int(profile.followers_count)
    follows = int(profile.follows_count)
    if followers == 0 or follows == 0:
        logger('BOTALERT', user.handle)
        return 'BOTALERT'
    follower_ratio = followers / follows
    if follower_ratio >= ratio and followers > 10000:
        return 'INFLUENCER'
    else:
        return 'REGULAR_JOE'
    
def manage_followers(follower_list, days_ago, limit=None):
    """
    Takes the follower list and, for each follwer, checks to see if their post history is current.
    If it is, we check to see if we are following them. If so, we log that information and move 
    on to the next follower. If not, we follow the user. If the user's post history is not current,
    and if we are following the user, we unfollow the user.
    """
    count = 0
    for follower in follower_list:
        following = follow_check(follower)
        last_post = last_post_date(follower, days_ago)
        logger('BSKYFOLLOWERS', 'Start ' + follow.handle)
        if last_post == 'CURRENT':
            if following == 'FOLLOWING':
                logger('ALREADYFOLLOW', follower.handle)
            else:
                follow_user(follower)
                count += 1
                if limit != None:
                    if count >= int(limit):
                        logger('CONNECTDONE', follower.handle)
                        sys.exit(0)
        else:
            logger('HASNTPOSTED', follower.handle)
            if following == 'FOLLOWING':
                unfollow_user(follower)
    return None
    
def manage_follows(follows_list):
    '''
    Takes the follow list and, for each follow, checks to see if the user is an influencer. If so,
    the connection is preserved else we check if the user's post history is current. If it is, the 
    connection is preserved else we unfollow the user. Next we check to see if the user follows us 
    back, and if so, the connection is preserved else we unfollow the user.
    '''
    for follow in follows_list:
        last_post = last_post_date(follow, 14)
        follower_ratio = influencer_check(follow, 3)
        following = follower_check(follow)
        logger('BSKYFOLLOWS', 'Start ' + follow.handle)
        if follower_ratio == 'INFLUENCER':
            logger('INFLUENCER', follow.handle)
        else:
            logger('REGULARJOE', follow.handle)
            if last_post == 'CURRENT':
                logger('POSTSCURRENT', follow.handle)
            elif last_post == 'OLD':
                logger('HASNTPOSTED', follow.handle)
                unfollow_user(follow)
            elif last_post == 'BOTALERT':
                unfollow_user(follow)
            if following == 'FOLLOWS':
                logger('FOLLOWSUS', follow.handle)
            else:
                logger('DOESNTFOLLOW', follow.handle)
                if follower_ratio == 'REGULAR_JOE':
                    unfollow_user(follow)
                elif follower_ratio == 'BOTALERT':
                    logger('BOTALERT', follow.handle)
                    unfollow_user(follow)
    return None

def main():
    '''Main processing function'''
    args = my_args()
    if not args.account or not args.program:
        logger('ARGUMENTS', 'Please pass both an account username and a program type.')
        sys.exit(1)
    if args.program == 'followers':
        logger('BSKYFOLLOWERS', 'Beginning follower management for ' + my_user + '.')
        followers = get_followers(my_user)
        manage_followers(followers, 14)
        logger('BSKYFOLLOWERS', 'Follower management complete for ' + my_user + '.')
    elif args.program == 'follows':
        logger('BSKYFOLLOWS', 'Beginning follows management for ' + my_user + '.')
        following = get_follows(my_user)
        manage_follows(following)
        logger('BSKYFOLLOWS', 'Follows management complete for ' + my_user + '.')
    elif args.program == 'both':
        logger('BSKYFOLLOWER', 'Beginning follower management for ' + my_user + '.')
        followers = get_followers(my_user)
        manage_followers(followers, 14)
        logger('BSKYFOLLOWER', 'Follower management complete for ' + my_user + '.')
        logger('BSKYFOLLOWS', 'Beginning follows management for ' + my_user + '.')
        following = get_follows(my_user)
        manage_follows(following)
        logger('BSKYFOLLOWS', 'Follows management complete for ' + my_user + '.')
    elif args.program == 'connect':
        if not args.limit:
            logger('ARGUMENTS', 'Please pass a limit for the connect program.')
            sys.exit(1)
        logger('BSKYCONNECT', 'Beginning BlueskyConnect for ' + my_user + '.')
        logger('BSKYCONNECT', 'Targeting the connections of ' + args.account + '.')
        target = get_followers(args.account)
        manage_followers(target, 2, args.limit)
        logger('BSKYCONNECT', 'Follower selection complete for ' + my_user + '.')
    logger('BSKYCONNECT', 'Finished!')

if __name__ == '__main__':
    main()