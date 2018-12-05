# Exp-traq

## Cheat sheet for me:

View info about current project:
$ gcloud info

Configure default project:
$ gcloud init 
...and follow prompts (e.g. which login you want to use, which project to apply commands to, etc.). Super easy!

Run project locally:
$ dev_appserver.py ./
Note: dev_appserver.py has a bunch of useful options, e.g. can browse datastore in browser - google it

Deploy project to Google Cloud:
$ gcloud app deploy // NOTE: this command creates a rolling list of versions, then eventually you hit a limit of 15 and need to delete some older versions. To overwrite a version insteadd, do
$ gcloud app deploy -v v1 //which will update the exsisting v1 version (which is the one serving)
Add'l helpful commands:
$ gcloud app versions list
$ gcloud app versions delete [list of versions]

If creating new indexes, should update index.yaml file andd run
$ gcloud datastore indexes create index.yaml
To check status of index creation, see https://console.cloud.google.com/datastore/indexes?project=exp-traq

To get rid of unused indexes, run
$ gcloud datastore indexes cleanup index.yaml

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
