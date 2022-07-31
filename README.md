# Exp-traq

## Cheat sheet for me:

### 1. Reminder on how to use git with github

To download project from GitHub to local computer to make your changes to the project:
```
Go to public repository on GitHub, click Code on top-right, select HTTPS, copy the url
cd Documents/code
git clone https://github.com/gaylordjohnson/exp-traq.git // the URL you got above
```

The following is explained here: https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup
Note: The email below is how Github associates the commits to my account in a way that does not expose my actual email address
```
git config --global user.name "Gaylord Johnson" 
git config --global user.email gaylordjohnson@users.noreply.github.com
```

Also try:
```
git config --list
git config --global --list
```

Also:
```
git log // To see information about the commits, including the authors etc.
git diff // to see diff between latest code (unstaged) and staged code
git diff origin master // if I understand correctly, diffs between local staging and what's on GitHub
```

Making and committing code changes
```
<make some changes in the code>
git status
git add * // Adds changes you made to the "staging" thing
git commit -m "this is a commit message explaining what's in this commit"
// Alternatively use the following shortcut for git add and git commit:
git acm "this is a commit message blah blah"
```

The command below will make it so that git push (see next) will only ask your GitHub credentials once
```
git config --global credential.helper store
```

Push changes back to the repository on GitHub:
```
git push // Will ask for GitHub credentials 
```

### 2. SPECIAL NOTE on using datastore INDEXES in Google App Engine / Google Cloud (because it was pain in the butt to figure out...)

If your code is doing some new kind of querying, it may be required to create a new index. For example, for this feature (https://github.com/gaylordjohnson/exp-traq/issues/10) I created a "filter"
query by Payee. When I ran the code on my local dev setup, everything ran fine. But when I deployed my stuff to GCloud (gcloud app deploy - see next section) and attempted to run my code, I got a 500 with a stack trace, at the end of which was:
```
The suggested index for this query is:
- kind: Entry
  ancestor: yes
  properties:
  - name: payee
  - name: datetime
    direction: desc
  - name: timestamp
    direction: desc
```
I added this to index.yaml and redeployed, yet still got the same 500 error. So I dug around and found that I need to run the following command in my local terminal:
```
gcloud datastore indexes create index.yaml
```
...which initiates GCloud to create the index. I quickly tried to run my app again and got anotheer 500, this time ending in:
```
NeedIndexError: The index for this query is not ready to serve. See the Datastore Indexes page in the Admin Console.
The suggested index for this query is:
- kind: Entry
  ancestor: yes
  properties:
  - name: payee
  - name: datetime
    direction: desc
  - name: timestamp
    direction: desc
```
It sounded like GCloud was still working on creating the index. Yes, I confirmed it by going to https://console.cloud.google.com/datastore/indexes. This new index had a spinner spinning, indicating that indexing was still in progress. I waited for the spinner to finish, ran my app again, and this time everything worked.

### 3. Where is my app's data in GCloud?

Here: https://console.cloud.google.com/datastore

### 4. Using Google Cloud CLI

Install Google Cloud CLI on Mac
```
download tar.gz for 64-bit M1 processor from https://cloud.google.com/sdk/docs/install-sdk#mac
doubleclick it in Finder to extract it
move the resulting google-cloud-sdk folder to home folder /users/<MyUsername>
in terminal, cd into google-cloud-sdk
./install.sh // will add CLI to PATH etc. Follow prompts - super easy.
Then close terminal window and open a new one for the above changes to take effect. 
gcloud // lists all gcloud commands
```

Authenticate into Google Cloud and configure default project:
```
$ gcloud init 
```
...follow prompts (e.g. which login you want to use, which project to apply commands to, etc.). Super easy!

Cheat sheet of all gcloud commands:
```
$ gcloud cheat-sheet
```

View current environment details:
```
$ gcloud info
```

Run project locally:
```
cd <my project folder>
// On my new Mac couldn't be bothered to figure out how to add the above to PATH, so will run using full path instead:
// $ dev_appserver.py ./
$ /Users/gaylord/google-cloud-sdk/bin/dev_appserver.py ./
// NOTE: dev_appserver.py needs whatever version of python your project will be in as 'python', but it also needs python 2.7.12+ to be present on the machine as 'python2'. So I had to simlink one of my python 3 installations as 'python' and had to download and install python 2.7.12, which came out of the box as 'python2'. Then dev server finally worked.
```
Note: dev_appserver.py has a bunch of useful options, e.g. can browse datastore in browser - google it

Deploy project to Google Cloud:
```
$ gcloud app deploy // NOTE: this command creates a rolling list of versions, then eventually you hit a limit of 15 and need to delete some older versions. To overwrite a version insteadd, do
$ gcloud app deploy -v v1 //which will update the exsisting v1 version (which is the one serving)
```
On first deploy attempt on my 2021 mac, got error:
```
File upload done.
Updating service [default]...failed.                                                                                                                         
ERROR: (gcloud.app.deploy) Error Response: [9] Cloud build b947a5c4-7f41-4620-8e67-18af250d4be4 status: FAILURE
Build error details: Access to bucket staging.exp-traq.appspot.com denied. You must grant Storage Object Viewer permission to <gaylord redacted>@cloudbuild.gserviceaccount.com.
```
Granded the "Storage Object Viewer" role (not permission) to the email above, in IAM, and it was able to deploy.

Add'l helpful commands:
```
$ gcloud app versions list
$ gcloud app versions delete [list of versions]
```

If creating new indexes, should update index.yaml file andd run
```
$ gcloud datastore indexes create index.yaml
```
To check status of index creation, see https://console.cloud.google.com/datastore/indexes?project=exp-traq

To get rid of unused indexes, run
```
$ gcloud datastore indexes cleanup index.yaml
```


## Products
- [App Engine][1]

## Language
- [Python][2]

## APIs
- [NDB Datastore API][3]
- [Users API][4]

## Dependencies
- [webapp2][5]
- [jinja2][6]

[1]: https://developers.google.com/appengine
[2]: https://python.org
[3]: https://developers.google.com/appengine/docs/python/ndb/
[4]: https://developers.google.com/appengine/docs/python/users/
[5]: http://webapp-improved.appspot.com/
[6]: http://jinja.pocoo.org/docs/
