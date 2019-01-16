#!/usr/bin/env python
import os
import urllib
import datetime
import time
from google.appengine.api import users
from google.appengine.ext import ndb
import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
  loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)

DEFAULT_EXP_TRAQ_NAME = 'default'
DEFAULT_FOR_TOP_N = 10

# We set a parent key on the expense entries to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent. However, the write rate should be limited to
# ~1/second.
def exp_traq_key(exp_traq_name=DEFAULT_EXP_TRAQ_NAME):
  """Constructs a Datastore key for an exp-treq entity. We use exp_traq_name as the key."""
  return ndb.Key('Exp-traq', exp_traq_name)

# Say, I messed up a payee name so now there are several different spellings, messing up my auto-suggest list
# Run this migration, which takes a urlsafe key and what the payee should be changed to, for as many entries
# as desired, and runs the update.
def runPayeeContentMigration():
    changes = [
        # [<urlsafe key>,<new payee>,<new comment>]
        # NOTE: it's ok for these arrays to start at beginning of line, like in the comment below, and to have a trailing comma (I've tested it).
        # NOTE2: Set value to "" if want it empty.
        # NOTE3: payee can't be an empty string
# ["aghkZXZ-Tm9uZXInCxIIRXhwLXRyYXEiB2RlZmF1bHQMCxIFRW50cnkYgICAgIDA7wgM","BLAH PAYEE 2"],        
# ["aghkZXZ-Tm9uZXInCxIIRXhwLXRyYXEiB2RlZmF1bHQMCxIFRW50cnkYgICAgIDArwoM","BLAH PAYEE 3"],
    ]
    print('Running migration (' + str(len(changes)) + ' items):')
    for change in changes:
        print(change)
        key = ndb.Key(urlsafe = change[0])
        entry = key.get()
        entry.payee = change[1]
        entry.put()

# First see my stackoverflow question for context: 
#   https://stackoverflow.com/questions/53623464/gae-python-ndb-projection-query-working-in-development-but-not-in-production
# This migration takes all the old entries, reads them into the now updated class definition - where Entity.payee is indexed
# - and writes entries right back to the datastore, changing them from unindexed to indexed! Ta da!
def runPayeeTypeMigration(exp_traq_name):
  entries_query = Entry.query(ancestor=exp_traq_key(exp_traq_name)).order(-Entry.datetime).order(-Entry.timestamp)
  entries = entries_query.fetch()
  for entry in entries:
    entry.put()

# Returns a list of unique trackers and total number of entries across all trackers
def getInfoAboutAllTrackers():
  entries = Entry.query().fetch() # Expensive operation, returns ALL entries, across ALL trackers
  count = len(entries)
  uniqueTrackers = set([])
  for entry in entries:
    uniqueTrackers.add(entry.key.parent().id())
  return list(uniqueTrackers), count


class Author(ndb.Model):
  """Sub model for representing an author."""
  identity = ndb.StringProperty(indexed=False)
  email = ndb.StringProperty(indexed=False)

class Entry(ndb.Model):
  """A main model for representing an individual expense entry."""
  datetime = ndb.DateTimeProperty(indexed=True, required=True)
  amount = ndb.IntegerProperty(indexed=False, required=True)
  #payee = ndb.StringProperty(indexed=False, required=True)
  # Changed to indexed, which is required to do a projection (see below)
  # DAMN this was hard: see my Stackoverflow question, which I eventually figured out and answered myself:
  # https://stackoverflow.com/questions/53623464/gae-python-ndb-projection-query-working-in-development-but-not-in-production
  payee = ndb.StringProperty(indexed=True, required=True)
  comment = ndb.StringProperty(indexed=False)

  # Fields above will come from the form values submitted by user.
  # Fields below will be populated by our code.
  author = ndb.StructuredProperty(Author)
  timestamp = ndb.DateTimeProperty(auto_now_add=True)

#[mk:] from https://cloud.google.com/appengine/docs/python/datastore/typesandpropertyclasses#datetime
class EasternTZInfo(datetime.tzinfo):
  """Implementation of the Eastern timezone."""
  def utcoffset(self, dt):
    return datetime.timedelta(hours=-5) + self.dst(dt)

  def _FirstSunday(self, dt):
    """First Sunday on or after dt."""
    return dt + datetime.timedelta(days=(6-dt.weekday()))

  def dst(self, dt):
    # 2 am on the second Sunday in March
    dst_start = self._FirstSunday(datetime.datetime(dt.year, 3, 8, 2))
    # 1 am on the first Sunday in November
    dst_end = self._FirstSunday(datetime.datetime(dt.year, 11, 1, 1))

    if dst_start <= dt.replace(tzinfo=None) < dst_end:
      return datetime.timedelta(hours=1)
    else:
      return datetime.timedelta(hours=0)
  
  def tzname(self, dt):
    if self.dst(dt) == datetime.timedelta(hours=0):
      return "EST"
    else:
      return "EDT"

# Handler class for managing the main page
class MainPage(webapp2.RequestHandler):
  def get(self):
    exp_traq_name = self.request.get('exp_traq_name', DEFAULT_EXP_TRAQ_NAME)

    fetchLimit = DEFAULT_FOR_TOP_N # Default value - this makes load time much speedier than loading everything
    showArg = self.request.get('show')
    if showArg:
      if showArg == 'all':
        fetchLimit = None
      else:
        fetchLimit = int(showArg)
    
    if self.request.get('showAs') == 'table':
      show_as_table = True
    else:
      show_as_table = False
    
    if self.request.get('runMigration') == 'PayeeContent':
      runPayeeContentMigration()
    elif self.request.get('runMigration') == 'PayeeType':
      runPayeeTypeMigration(exp_traq_name)

    # Optional tool for checking on all trackers.
    # Invoke by including the 'listTrackers' query-string parameter (doesn't need to have a value)
    uniqueTrackers = []
    entryCountAcrossAllTrackers = -1
    if 'listTrackers' in self.request.arguments(): # Checks for presence of 'listTrackers' param
      uniqueTrackers, entryCountAcrossAllTrackers = getInfoAboutAllTrackers()

    entries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).order(-Entry.datetime).order(-Entry.timestamp).fetch(fetchLimit)
    totalEntries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).count()

    # Get list of unique payees
    # Note: payeeObjects are **Entry** objects with only payee property filled (since we're doing a projection)
    # Therefore using obj.payee to access payee name
    payeeObjects = Entry.query(ancestor=exp_traq_key(exp_traq_name), projection=[Entry.payee], distinct=True).order(Entry.payee).fetch()
    payees = []
    for obj in payeeObjects:
      payees.append(obj.payee)

    user = users.get_current_user()
    if user:
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Log out'
    else:
      url = users.create_login_url(self.request.uri)
      url_linktext = 'Log in'

    # Convert all entries' datetime from UTC to Eastern
    for entry in entries:
      # Today's date --> convert from UTC to Eastern -- WTF is this so HARD?!
      entry.datetime = datetime.datetime.fromtimestamp(time.mktime(entry.datetime.timetuple()), EasternTZInfo())
      entry.dateYMD = datetime.datetime.strftime(entry.datetime, '%Y-%m-%d')
      entry.dateWeekday = datetime.datetime.strftime(entry.datetime, '%a')

    template_values = {
      'show_as_table': show_as_table,
      'user': user,
      'entries': entries,
      'totalEntries': totalEntries,
      'uniquePayees': payees,
      'exp_traq_name': urllib.quote_plus(exp_traq_name),
      'url': url,
      'url_linktext': url_linktext,
      'defaultForTopN': DEFAULT_FOR_TOP_N,
      'uniqueTrackers': uniqueTrackers,
      'entryCountAcrossAllTrackers': entryCountAcrossAllTrackers,
    }

    template = JINJA_ENVIRONMENT.get_template('index.html')
    self.response.write(template.render(template_values))

# Handler class for managing CRUD operations on individual entries
# We don't have get (it's handled by MainPage), but we have post, put, and delete
class EntryHandler(webapp2.RequestHandler):
  def post(self):
    print(str(self.request))

    # From GAE docs: "We set the same parent key on the 'Entry' to ensure each
    # Entry is in the same entity group. Queries across the
    # single entity group will be consistent. However, the write
    # rate to a single entity group should be limited to
    # ~1/second.""
    exp_traq_name = self.request.get('exp_traq_name', DEFAULT_EXP_TRAQ_NAME)
    entry = Entry(parent=exp_traq_key(exp_traq_name))

    if users.get_current_user():
      entry.author = Author(
        identity=users.get_current_user().user_id(),
        email=users.get_current_user().email())

    # Get submitted date, or use today's date
    if self.request.get('date'):
      naive = datetime.datetime.strptime(self.request.get('date'), '%Y-%m-%d')
      naiveAdjusted = naive - EasternTZInfo().utcoffset(naive)
      entry.datetime = naiveAdjusted
    else:
      entry.datetime = datetime.datetime.utcnow()

    entry.amount = int(self.request.get('amount'))
    entry.payee = self.request.get('payee')
    entry.comment = self.request.get('comment')
    entry.put()

    # If a cross-post was requested, create a copy of entry and post it into the other tracker
    if self.request.get('xpost'):
      entry2 = Entry(parent=exp_traq_key(self.request.get('xpost')))
      entry2.author = entry.author
      entry2.datetime = entry.datetime
      entry2.amount = entry.amount
      entry2.payee = entry.payee
      entry2.comment = entry.comment
      entry2.put()

    query_params = {'exp_traq_name': exp_traq_name}
    self.redirect('/?' + urllib.urlencode(query_params))

  def put(self, key): # key is the urlsafe ndb key of the entry being updated
    print(str(self.request))

    date = self.request.get('date') 
    amount = self.request.get('amount')
    payee = self.request.get('payee')
    comment = self.request.get('comment')

    # Get entry from db
    entry_key = ndb.Key(urlsafe = key)
    entry = entry_key.get()

    # Update entry with info from the client
    if date:
      naive = datetime.datetime.strptime(date, '%Y-%m-%d')
      naiveAdjusted = naive - EasternTZInfo().utcoffset(naive)
      entry.datetime = naiveAdjusted
    
    if amount:
      entry.amount = int(amount)
  
    if payee:
      entry.payee = payee
    
    if comment:
      entry.comment = comment
    
    # Write updated entry to db
    entry.put()

    # We're reloading page in JS. Nothing to do here; we're done

  def delete(self, key): # key is the urlsafe ndb key of the entry being deleted
    entry_key = ndb.Key(urlsafe = key)
    entry_key.delete()

app = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/submit', EntryHandler),
  ('/entry/(.+)', EntryHandler),
], debug=True)
