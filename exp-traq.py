#!/usr/bin/env python
import os
import urllib
import datetime
import time
from google.appengine.api import users
from google.appengine.ext import ndb
import jinja2
import webapp2
import locale

JINJA_ENVIRONMENT = jinja2.Environment(
  loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
  extensions=['jinja2.ext.autoescape'],
  autoescape=True)

DEFAULT_EXP_TRAQ_NAME = 'default'
DEFAULT_FOR_TOP_N = 10

def exp_traq_key(exp_traq_name=DEFAULT_EXP_TRAQ_NAME):
  """Constructs a Datastore key for an exp-treq entity. We use exp_traq_name as the key.
  We set a parent key on the expense entries to ensure that they are all in the same entity group. 
  Queries across the single entity group will be consistent. However, the write rate should be 
  limited to ~1/second.
  """
  return ndb.Key('Exp-traq', exp_traq_name)

def runPayeeContentMigration():
  """Say, I messed up a payee name so now there are several different spellings, messing up my auto-suggest list
  Run this migration, which takes a urlsafe key and what the payee should be changed to, for as many entries
  as desired, and runs the update.
  """
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

def runPayeeTypeMigration(exp_traq_name):
  """First see my stackoverflow question for context: 
  https://stackoverflow.com/questions/53623464/gae-python-ndb-projection-query-working-in-development-but-not-in-production
  This migration takes all the old entries, reads them into the now updated class definition - where Entity.payee is indexed
  - and writes entries right back to the datastore, changing them from unindexed to indexed! Ta da!
  """
  entries_query = Entry.query(ancestor=exp_traq_key(exp_traq_name)).order(-Entry.datetime).order(-Entry.timestamp)
  entries = entries_query.fetch()
  for entry in entries:
    entry.put()

def getInfoAboutAllTrackers():
  """Returns a list of unique trackers and total number of entries across all trackers
  """
  entries = Entry.query().fetch() # Expensive operation, returns ALL entries, across ALL trackers
  count = len(entries)
  uniqueTrackers = set([])
  for entry in entries:
    uniqueTrackers.add(entry.key.parent().id())
  return list(uniqueTrackers), count

def getUniquePayees(exp_traq_name):
  """Get the list of unique payees.
  Note: payeeObjects are **Entry** objects with only payee property filled 
  (since we're doing a projection). Therefore using obj.payee to access payee name
  """    
  payeeObjects = Entry.query(ancestor=exp_traq_key(exp_traq_name), projection=[Entry.payee], distinct=True).order(Entry.payee).fetch()
  payees = []
  for obj in payeeObjects:
    payees.append(obj.payee)
  # Note: the order() call above sorts alphabetically in a way that capitals come before lower-case letters.
  # Seems (https://cloud.google.com/datastore/docs/concepts/queries#datastore-datastore-basic-query-python)
  # that case-insensitive ordering is not supported (if the link above applies to the stuff below; not 100% sure)
  # Therefore I'll do case-insensitive sort here in python, though is's not the most efficient thing to do.
  # Also note: if I'm doing the below, why am I keeping the order() call above? As mentioned elsewhere in this file,
  # the below way to sort may not work for all unicode situations (Cmd-F for 'unicode'), but maybe order() does...
  payees.sort(key = lambda x: x.lower())
  return payees

def getCanonicalPayeeSpelling(exp_traq_name, payee_from_form):
  """Get a list of all unique payees so we could see if payee_from_form matches any of them in a 
  case-INSENSITIVE way, then use the canonical one (from the db) instead of the one just submitted
  """
  canonical_payee = payee_from_form.strip()
  payees = getUniquePayees(exp_traq_name)
  for p in payees:
    if canonical_payee.lower() == p.lower():
      canonical_payee = p
      break
  # NOTE: the above logic is not guaranteed to work for more complex cases like foreign accented 
  # characters in unicode (see https://stackoverflow.com/a/29247821/1698938). Buf for my needs
  # it works fine (e.g. payees in English and potentially some Russian). I even tested it for
  # accented Russian characters like "i kratkoe" and "yo" (GAE barfed when I typed the actual
  # letters here, so changed them to their transliterations :-(
  return canonical_payee

def getTotalAndAvgAmountStrings(entries):
  '''Calculate total and avg amounts and format them as currency strings,
  the total with no decimal places, the avg with 2 decimal places.
  '''
  totalAmt = 0
  avgAmt = 0
  for entry in entries:
    totalAmt += entry.amount
  if len(entries):
    avgAmt = float(totalAmt) / len(entries)

  # Using locale is the *right* way, and this worked in python in terminal,
  # BUT GAE barfed with a bunch of exceptions; not worth spending the time to figure it out...
  # locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
  # return locale.currency(totalAmt, grouping=True), locale.currency(avgAmt, grouping=True)

  # Instead, will use this alternative (from https://bit.ly/3Q8sZ2c)
  return "{:0,.0f}".format(totalAmt), "{:0,.2f}".format(avgAmt)

class Author(ndb.Model):
  """Sub model for representing an author.
  """
  identity = ndb.StringProperty(indexed=False)
  email = ndb.StringProperty(indexed=False)

class Entry(ndb.Model):
  """A main model for representing an individual expense entry.
  """
  datetime = ndb.DateTimeProperty(indexed=True, required=True)
  amount = ndb.IntegerProperty(indexed=False, required=True)

  # Changing to indexed, which is required to do a projection (see below and https://cloud.google.com/appengine/docs/legacy/standard/python/datastore/projectionqueries)
  # DAMN this was hard: see my Stackoverflow question, which I eventually figured out and answered myself:
  # https://stackoverflow.com/questions/53623464/gae-python-ndb-projection-query-working-in-development-but-not-in-production
  #payee = ndb.StringProperty(indexed=False, required=True)
  payee = ndb.StringProperty(indexed=True, required=True)
  comment = ndb.StringProperty(indexed=False)

  # Fields above will come from the form values submitted by user.
  # Fields below will be populated by our code.
  author = ndb.StructuredProperty(Author)
  timestamp = ndb.DateTimeProperty(auto_now_add=True)

class EasternTZInfo(datetime.tzinfo):
  """Implementation of the Eastern timezone. 
  Source: https://cloud.google.com/appengine/docs/python/datastore/typesandpropertyclasses#datetime
  """
  def utcoffset(self, dt):
    return datetime.timedelta(hours=-5) + self.dst(dt)

  def _FirstSunday(self, dt):
    """First Sunday on or after dt.
    """
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

class MainPage(webapp2.RequestHandler):
  """Handler class for managing the main page
  """

  def get(self):
    """Handler for HTTP GET. This gets the content of our application. Note: POST, PUT, and DELETE
    are implemented in the next class below. In some cases they redirect back to the main page
    to get the page content updated. A more efficient approach would be to do everything via AJAX
    and dynamically update the relevant parts of the DOM. BUT it's hard to do since my app uses
    a backend framework. This would have been a breeze in Vue, React, or another FE framework.
    As it is, that all is not worth it; it's easier to simply reload the entire page.
    """
    # print(str(self.request))

    exp_traq_name = self.request.get('exp_traq_name', DEFAULT_EXP_TRAQ_NAME)

    # Default value - this makes load time much speedier than loading everything
    fetchLimit = DEFAULT_FOR_TOP_N 
    show = self.request.get('show')
    if show:
      if show == 'all':
        fetchLimit = None
      else:
        fetchLimit = int(show)
    
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

    payeeToFilter = self.request.get('payee')
    if payeeToFilter:
      filteringByPayee = True
      # Note: to filter all values by a payee, we need to do a "filter" query.
      # Documentation: https://cloud.google.com/appengine/docs/legacy/standard/python/ndb/queries#filter_by_prop

      # Removing fetchLimit arg and commenting out the count() query - see explanation below
      # entries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).filter(Entry.payee == payeeToFilter).order(-Entry.datetime).order(-Entry.timestamp).fetch(fetchLimit)
      entries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).filter(Entry.payee == payeeToFilter).order(-Entry.datetime).order(-Entry.timestamp).fetch()
      # totalEntries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).filter(Entry.payee == payeeToFilter).count()
    else:
      filteringByPayee = False

      # Removing fetchLimit arg and commenting out the count() query - see explanation below
      # entries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).order(-Entry.datetime).order(-Entry.timestamp).fetch(fetchLimit)
      entries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).order(-Entry.datetime).order(-Entry.timestamp).fetch()
      # totalEntries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).count()

    #xx IMPORTANT
    # I had implemented the "show last 10" logic because getting all entries was slow. But now I want to 
    # display data such as total amount and avg. amount, even when showing only last 10 entries. Don't 
    # think there's a way to do so easily in the DB (maybe via a projection query on amount; let
    # me leave it as 'to try later'). So I'll need to retrieve all, calculate total and avg, and only 
    # display 'last 10'. I don't know where the 'show all' slowness originated: from the query taking 
    # a long time? or from me passing ALL entries down to the browser? My hunch is it might be
    # the latter. So I'll calculate total and avg here in Python, then prune the list of entries, and
    # only pass the 'last 10' to the browser. Maybe that will let me calc what I need and still be fast.
    # THEREFORE, I'm doing the following above ^
    # -- removing the 'fetchLimit' arg from the queries above
    # -- commenting out the 'count()' queries above
    # -- then calculating stats and pruning the list of entries, below.
    # If it proves slow, I'll have to undo these changes.
    totalEntries = len(entries)
    totalAmount, avgAmount = getTotalAndAvgAmountStrings(entries)
    if fetchLimit:
      # Prune entries to keep only the first fetchLimit entries
      entries = entries[:fetchLimit]

    # Get a list of all unique payees so we can create the auto-suggest list for the user
    payees = getUniquePayees(exp_traq_name)

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
      'showAs': self.request.get('showAs'),
      'show': show,
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
      'filteringByPayee': filteringByPayee,
      'payeeToFilter': payeeToFilter,
      'totalAmount': totalAmount,
      'avgAmount': avgAmount,
    }

    # If we just added an entry and xposted it to another tracker, add the target tracker
    # name to template values so we can give user a handy link to that tracker to check things
    if 'lastXpost' in self.request.arguments(): # Was 'lastXpost' query string parameter defined?
      template_values['lastXpost'] = self.request.get('lastXpost')

    template = JINJA_ENVIRONMENT.get_template('index.html')
    self.response.write(template.render(template_values))

class EntryHandler(webapp2.RequestHandler):
  '''Handler class for managing CRUD operations on individual entries
  We don't have get (it's handled by MainPage, above), but we have post, put, and delete
  '''

  def post(self):
    #print(str(self.request))

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
    entry.payee = getCanonicalPayeeSpelling(exp_traq_name, self.request.get('payee'))
    entry.comment = self.request.get('comment')
    entry.put()

    # If a cross-post was requested, create a copy of entry and post it into the other tracker
    xpostTo = self.request.get('xpost')
    if xpostTo:
      entry2 = Entry(parent=exp_traq_key(xpostTo))
      entry2.author = entry.author
      entry2.datetime = entry.datetime
      entry2.amount = entry.amount
      entry2.payee = entry.payee
      entry2.comment = entry.comment
      entry2.put()

    query_params = {
      'exp_traq_name': exp_traq_name, 
      'show': self.request.get('show'),
      'showAs': self.request.get('showAs')
    }
    if xpostTo:
      query_params['lastXpost'] = xpostTo
    self.redirect('/?' + urllib.urlencode(query_params))

  def put(self, key): 
    '''key is the urlsafe ndb key of the entry being updated
    '''

    # print(str(self.request))
    exp_traq_name = self.request.get('exp_traq_name', DEFAULT_EXP_TRAQ_NAME)

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
      entry.payee = getCanonicalPayeeSpelling(exp_traq_name, payee)
        
    if comment:
      entry.comment = comment
    
    # Write updated entry to db
    entry.put()

    # We're reloading page in JS. Nothing to do here; we're done

  def delete(self, key): 
    '''key is the urlsafe ndb key of the entry being deleted
    '''
    # print(str(self.request))

    entry_key = ndb.Key(urlsafe = key)
    entry_key.delete()

app = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/submit', EntryHandler),
  ('/entry/(.+)', EntryHandler),
], debug=True)