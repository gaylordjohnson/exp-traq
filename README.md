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

Command below will make it so that git push (see next) will only ask your GitHub credentials once
```
git config --global credential.helper store
```

Push changes back to the repository on GitHub:
```
git push // Will ask for GitHub credentials 
```

### 2. Using Google Cloud CLI

View info about current project:
```
$ gcloud info
```

Configure default project:
```
$ gcloud init 
```
...and follow prompts (e.g. which login you want to use, which project to apply commands to, etc.). Super easy!

Run project locally:
```
$ dev_appserver.py ./
```
Note: dev_appserver.py has a bunch of useful options, e.g. can browse datastore in browser - google it

Deploy project to Google Cloud:
```
$ gcloud app deploy // NOTE: this command creates a rolling list of versions, then eventually you hit a limit of 15 and need to delete some older versions. To overwrite a version insteadd, do
$ gcloud app deploy -v v1 //which will update the exsisting v1 version (which is the one serving)
```

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
