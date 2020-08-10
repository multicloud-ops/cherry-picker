#!/usr/bin/env python3.6

from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.view import view_config, view_defaults
from pyramid.response import Response
from github import Github
import os, re
import subprocess
import time
import logging
import shutil

bug_label_prefix='bug'
release_label_prefix='release/'
release_version_label_prefix='release-'
bot_org='cp4mcmbo'
cherrypick_pr_title="Cherry-pick of #{0}: {1}" # to become "Cherry-pick of #pr: {master pr subject}"
cherrypicked_indicator="Cherry-pick of #{}:"
release_fix_branch='{0}-cherrypick-{1}'
# work_dir on bot server
work_dir='/root/cherry-picker/'
dryrun=False
ENDPOINT = "cherry-picker-bot"

logname='cherry-picker.log'
logging.basicConfig(filename=logname,
                            filemode='a',
                            format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%H:%M:%S',
                            level=logging.INFO)

# Check which PRs are candidates for cherry picking
access_token='7e9d454f1aad786b89f23433830728973601fd64'
baseurl='https://github.ibm.com/api/v3'
git = Github(base_url=baseurl, login_or_token=access_token)


# Change to work directory. 
def change_to_base_path():
    try:
        os.system("cd "+work_dir)
    except:
        logging.error("Failed to Change to base path "+work_dir)


# Erase the bot_repo folder without regard for errors. 
# There is a flaw in the  getcwd() that requires a reregistration
# of the pointer to the working directory.  Please pay no
# attention to the jumping around.  It's necessary. 
def clean_up_bot_repo(bot_repo):
    try:
        shutil.rmtree(work_dir+bot_repo)
    except:
        logging.error("Error while deleting "+work_dir+bot_repo)


# Clone release        
def clone_release(clone_html_url, repo):
    clone_html_url_with_token = clone_html_url.replace("https://", "https://"+access_token+"@")
    qualified_repo = work_dir+repo
    os.chdir(work_dir)
    logging.info("Current working dir : %s" % os.getcwd())
    cmd = ["git", "clone", "--origin", "upstream", clone_html_url_with_token, qualified_repo]
    if dryrun:
        print('dry-run: ' + ' '.join(cmd))
    else:
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            logging.info("Successfully cloned release:%s", cmd)
            return True
        except subprocess.CalledProcessError as err:
            logging.error("Error cloning: %s",clone_html_url_with_token)
            return False

def add_remote_fork(remote, name):
    # If it's https location add token
    remote_with_token = remote.replace("https://", "https://"+access_token+"@")
    cmd = ["git", "remote", "add", name, remote_with_token]
    if dryrun:
        print('dry-run: ' + ' '.join(cmd))
    else:
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            logging.info("Added remote:%s", cmd)
        except subprocess.CalledProcessError as err:
            logging.error("Error adding remote: %s",remote_with_token)
            logging.error(err)
            logging.error(err.output.decode())
            return False
    # Fetch
    cmd = ["git", "fetch", name]
    if dryrun:
        print('dry-run: ' + ' '.join(cmd))
    else:
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            logging.info("Fetched remote:%s", cmd)
            return True
        except subprocess.CalledProcessError as err:
            logging.error("Error fetching remote: %s",remote_with_token)
            logging.error(err)
            logging.error(err.output.decode())
            return False
             
def add_fix_branch(release_to_attach, pull_request):
    branch = release_fix_branch.format(release_to_attach, str(pull_request))
    cmd = ["git", "checkout", "-b", branch, "--track", "upstream/"+release_to_attach]
    if dryrun:
        print('dry-run: ' + ' '.join(cmd))
    else:
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            logging.info("Add fix branch:%s",cmd)
            return True, branch
        except subprocess.CalledProcessError as err:
            logging.error("Error creating fix branch:%s",cmd)
            logging.error(err)
            logging.error(err.output.decode())
            return False, None
            
def cherry_pick_commit(commit_sha):
    cmd = ["git", "cherry-pick", commit_sha]
    if dryrun:
        print('dry-run: ' + ' '.join(cmd))
    else:
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            logging.info("Cherry pick fix:%s",cmd)
            return True
        except subprocess.CalledProcessError as err:
            logging.error("Error cherry-picking:%s",cmd)
            logging.error(err)
            logging.error(err.output.decode())
            return False
        
# Push botfork
def push_botfork(branch):
    cmd = ["git", "push", "botfork", branch]
    if dryrun:
        print('dry-run: ' + ' '.join(cmd))
    else:
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
            logging.info("Pushfix branch:%s",cmd)
            return True
        except subprocess.CalledProcessError as err:
            logging.error("Error pushing fix branch:%s",cmd)
            logging.error(err)
            logging.error(err.output.decode())
            return False

# Open a pull request to push changes up to the release
def open_pr(branch, pr_title, pr_number, release, upstream_repo):
    body = "Automatic cherry-pick"
    title = cherrypick_pr_title.format(pr_number, pr_title)  
    # Strip off leading release/ prefix
    release=release.replace('release/', '')
    logging.info('Pull Request Details')
    logging.info('PR Number: '+str(pr_number))
    logging.info('PR Title: '+title)
    logging.info('body: '+body)
    logging.info('bot_org: '+bot_org)
    logging.info('branch: '+branch)
    logging.info('base: '+release) 
    try:
        new_pull_request = upstream_repo.create_pull(title=title, body=body, head='{}:{}'.format(bot_org, branch), base=release)
        logging.info("Created pull request against %s", release)
        return True
    except:
        logging.error("Error creating pull request for fix branch:%s",title)
        return False
                
# Force a change to the bot repo
def change_focus_to_bot_repo(repo):
    if dryrun:
        print('dry-run: cd '+repo)
    else:
        os.chdir(work_dir+repo)
        logging.info("Changed directory to the bot_repo:%s", repo)

def get_bot_fork(upstream_repo):
    # Current behavior seems to be if we already have a fork it is returned, so it's safe to do so
    # If this should change, we can always do something like 
    # for fork in upstream_repo.get_forks():
    #     if fork.owner.login == BOT_GITHUB_USER:
    #         return fork.ssh_url
    fork = upstream_repo.create_fork()
    return fork.ssh_url
    
    
def process_cherry_pick(repo, pr_number, upstream_repo_url, upstreamorg, pr_title, release):
    logging.info("****** STARTING NEW CHERRY-PICK ******")
    # Create a connection object to github upstream repo
    upstream_repo = git.get_repo("%s/%s" % (upstreamorg, repo))
    pr=upstream_repo.get_pull(pr_number)
    
    #Initialze environment
    clean_up_bot_repo(repo)
    change_to_base_path()
    if (clone_release(upstream_repo_url, repo)):
        cherry_pick_success=True
        logging.info("Cloned release")
        change_focus_to_bot_repo(repo)
        logging.info("Change focus.")
        commits = pr.get_commits()
        logging.info("Got commits.")
        # If we're cherry-picking from remote repo before anything is merged, we also need the head repo, since the commit hashes do not exist in what we have cloned yet
        if (add_remote_fork(pr.head.repo.clone_url, "head")):
            logging.info("Add remote fork.")
            # We also need to add our own forked version of the repo
            botfork=get_bot_fork(upstream_repo)
            if (add_remote_fork(botfork, "botfork")):                
                logging.info("Add remote botfork.")
                for label in pr.labels:
                    if (label.name.startswith(release_label_prefix)):
                        # Add and check out fix branch
                        success, branch = add_fix_branch(label.name.replace(release_label_prefix,""), pr_number)
                        if branch != None:
                            logging.info("Added and checked out fix branch.")
                            # Cherry-pick the commits from the PR
                            for commit in commits:
                                if(cherry_pick_commit(commit.sha)):
                                    logging.info("Successfully cherry picked sha.")
                                else:
                                    logging.info("failed to cherry picked sha.")
                                    cherry_pick_success=False
                            # Pushing the change content to the botfork branch
                            if (cherry_pick_success):   
                                if (push_botfork(branch)):                                
                                    # Push the commits to updated repo
                                    open_pr(branch, pr_title, pr_number, release, upstream_repo)
    
@view_defaults(
    route_name=ENDPOINT, renderer="json", request_method="POST"
)
class PayloadView(object):
    """
    View receiving of Github payload. By default, this view it's fired only if
    the request is json and method POST.
    """
    
    # Constructor of this class (self, request)
    def __init__(self, request):
        self.request = request
        # Payload from Github, it's a dict
        self.payload = self.request.json   

    # Below is the filter that triggers all cherry-picker action.
    # Currently a webhook pointed at http://9.30.119.148:6543/cherry-picker-bot
    # Will result in a payload that is delivered to the following code.
    
    @view_config(header="X-Github-Event:pull_request")
    def payload_pull_request(self):
        if (self.payload['action'] == 'labeled'):
            for i in range(len(self.payload['pull_request']['labels'])):
                if (self.payload['pull_request']['labels'][i]['name'].split('-')[0] == 'release/release'):
                    release=self.payload['pull_request']['labels'][i]['name']                
                    for j in range(len(self.payload['pull_request']['labels'])):
                        if (self.payload['pull_request']['labels'][j]['name'] == 'bug'):
                            pr_title=self.payload['pull_request']['title']
                            pr_number=self.payload['pull_request']['number']
                            upstreamorg=self.payload['repository']['full_name'].split('/')[0]
                            print("upstreamorg="+upstreamorg)
                            upstream_repo_url=self.payload['pull_request']['base']['repo']['clone_url']
                            print("upstream_repo_url: "+upstream_repo_url)                            
                            repo=self.payload['repository']['full_name'].split('/')[1]
                            print("repo="+repo)                            
                            org=upstreamorg
                            print("org="+org)                            
                            print("Found correct pr.")
                            print("PR", self.payload['action'])
                            print("No. Commits in PR:", self.payload['pull_request']['commits'])                            
                            # process cherry-pick here...
                            if process_cherry_pick(repo, pr_number, upstream_repo_url, upstreamorg, pr_title, release):
                                return Response("payload successfully processed")
                            else:
                                return Response("cherry-pick failure")          
        else:
            logging.error("Failed to process pull request.  Payload json data incorrect to trigger this action.")
            return Response("No cherry-pick possible with the current pr json data")
            
                                 
if __name__ == "__main__":
    config = Configurator()
    config.add_route(ENDPOINT, "/{}".format(ENDPOINT))
    config.scan()
    app = config.make_wsgi_app()
    server = make_server("9.30.119.148", 6543, app)
    server.serve_forever()
