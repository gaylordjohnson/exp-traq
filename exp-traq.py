#!/usr/bin/env python
import os
import urllib
import datetime
import time
from google.appengine.api import users
from google.appengine.ext import ndb
import jinja2
import webapp2
import logging
import time

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
    # [<urlsafe key>,<new payee>],
    # It's ok for these arrays to start at beginning of line, like in the comment below, 
    # and to have a trailing comma (I've tested it). Payee can't be empty.

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

def getUniquePayeesFromDbAndSort(exp_traq_name):
  """Get the list of unique payees.
  Note: payeeObjects are **Entry** objects with only payee property filled 
  (since we're doing a projection). Therefore using obj.payee to access payee name
  """    
  fetchPayeesStart = time.time()
  payeeObjects = Entry.query(ancestor=exp_traq_key(exp_traq_name), projection=[Entry.payee], distinct=True).order(Entry.payee).fetch()
  fetchPayeesElapsed = time.time() - fetchPayeesStart

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

  return payees, fetchPayeesElapsed

def getCanonicalPayeeSpelling(exp_traq_name, payee_from_form):
  """Get a list of all unique payees so we could see if payee_from_form matches any of them in a 
  case-INSENSITIVE way, then use the canonical one (from the db) instead of the one just submitted
  """
  canonical_payee = payee_from_form.strip()
  payees, fetchPayeesElapsed = getUniquePayeesFromDbAndSort(exp_traq_name)
  for p in payees:
    if canonical_payee.lower() == p.lower():
      canonical_payee = p
      break
  # NOTE: the above logic is not guaranteed to work for more complex cases like foreign accented 
  # characters in unicode (see https://stackoverflow.com/a/29247821/1698938). Buf for my needs
  # it works fine (e.g. payees in English and potentially some Russian). I even tested it for
  # accented Russian characters like "i kratkoe" and "yo" (GAE barfed when I typed the actual
  # letters here, so changed them to their transliterations :-(
  return canonical_payee, fetchPayeesElapsed

def getTotalAndAvgAmount(entries):
  '''Calculate total and avg amounts.
  '''
  totalAmt = 0
  avgAmt = 0
  for entry in entries:
    totalAmt += entry.amount
  if len(entries):
    avgAmt = float(totalAmt) / len(entries)
  return totalAmt, avgAmt

def getSummaryDataByYear(entries):
  '''Returns a map of total, # entries, and avg by year
  '''
  yearMap = {}
  for entry in entries:
    year = entry.datetime.strftime('%Y')
    if year not in yearMap:
      yearMap[year] = [entry.amount, 1] # Initiate the running total and entry count
    else:
      yearMap[year][0] += entry.amount
      yearMap[year][1] += 1
  # The below is stupid, because I could do this calc in the jinja template in index.heml.
  # But jinja is being difficult, throws exception if I call a function, e.g. float().
  # I'm sure there's a way to make it work, but not worth it to me right now.
  for year in yearMap.keys():
    # The third entry in the list will be the average spend during that year.
    yearMap[year].append( float(yearMap[year][0]) / yearMap[year][1] )
  return yearMap

def populatePayeeMap(entries):
  '''Cycle through all entries and return a map of per-payee total amounts, 
  as well as the overall total
  '''
  payeeMap = {}
  totalAmount = 0
  for entry in entries:
    totalAmount += entry.amount
    if entry.payee not in payeeMap:
      payeeMap[entry.payee] = [entry.amount, 1] # Initialize amount and count of entries
    else:
      payeeMap[entry.payee][0] += entry.amount
      payeeMap[entry.payee][1] += 1
  return payeeMap, totalAmount

def convertEntriesToEastern(entries):
  """The entries were fetched from the datastore, where all datetimes are in UTC. 
  Convert all entry.datetime to eastern TZ for display in the app.
  """
  for entry in entries:
    # Today's date --> convert from UTC to Eastern -- WTF is this so HARD?!
    entry.datetime = datetime.datetime.fromtimestamp(time.mktime(entry.datetime.timetuple()), EasternTZInfo())
    entry.dateYMD = datetime.datetime.strftime(entry.datetime, '%Y-%m-%d')
    entry.dateWeekday = datetime.datetime.strftime(entry.datetime, '%a')

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

  def runOptionalToolsIfRequested(self, exp_traq_name):
    if self.request.get('runMigration') == 'PayeeContent':
      runPayeeContentMigration()
    elif self.request.get('runMigration') == 'PayeeType':
      runPayeeTypeMigration(exp_traq_name)
    uniqueTrackers = []
    entryCountAcrossAllTrackers = -1
    if 'listTrackers' in self.request.arguments(): # Checks for presence of 'listTrackers' param
      uniqueTrackers, entryCountAcrossAllTrackers = getInfoAboutAllTrackers()    
    return uniqueTrackers, entryCountAcrossAllTrackers


  def generateBasicView(self, template_values, exp_traq_name, fetchLimit):
    # Fetch up to fetchLimit entries from the datastore
    fetchEntriesStart = time.time()
    entries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).order(-Entry.datetime).order(-Entry.timestamp).fetch(fetchLimit)
    logging.debug('GET method -> generateBasicView() -> fetch entries from datastore: %.3f s' % (time.time() - fetchEntriesStart))

    # Fetch the totalEntryCount
    fetchEntryCountStart = time.time()
    totalEntries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).count()
    logging.debug('GET method -> generateBasicView() -> fetch entry count from datastore: %.3f s' % (time.time() - fetchEntryCountStart))

    # Get list of unique payees for our auto-suggest dropdown
    # Note: payeeObjects are **Entry** objects with only payee property filled (since we're doing a projection)
    # Therefore we use obj.payee to access payee name
    fetchUniquePayeesStart = time.time()
    payeeObjects = Entry.query(ancestor=exp_traq_key(exp_traq_name), projection=[Entry.payee], distinct=True).order(Entry.payee).fetch()
    logging.debug('GET method -> generateBasicView() -> fetch unique payees from datastore: %.3f s' % (time.time() - fetchUniquePayeesStart))
    uniquePayees = []
    for obj in payeeObjects:
      uniquePayees.append(obj.payee)

    # Convert entries' datetime from UTC to Eastern
    convertEntriesToEastern(entries)

    template_values['entries'] = entries
    template_values['totalEntries'] = totalEntries
    template_values['uniquePayees'] = uniquePayees


  def generateAdvancedView(self, template_values, exp_traq_name, fetchLimit):
    payeeToFilter = self.request.get('payeefilter')
    if payeeToFilter:
      filteringByPayee = True
    else:
      filteringByPayee = False

    # Get all entries
    fetchEntriesStart = time.time()
    entries = Entry.query(ancestor=exp_traq_key(exp_traq_name)).order(-Entry.datetime).order(-Entry.timestamp).fetch()
    logging.debug('GET method -> generateAdvancedView() -> fetch entries from datastore: %.3f s' % (time.time() - fetchEntriesStart))

    # Create a map of total amounts etc per payee
    payeeMap, totalAmtBeforePayeeFilter = populatePayeeMap(entries)
    # Get unique list of payees sorted by descending values of their total
    uniquePayees = sorted(payeeMap.keys(), key=lambda x: payeeMap[x], reverse=True)
    
    # If payee filter was requested, filter entries down to those from that payee
    if filteringByPayee:
      entries = [entry for entry in entries if entry.payee == payeeToFilter] # 'List comprehension' syntax

    # Calc the stats for the remaining entries (e.g. either for a payee, or overall)
    totalEntriesAfterPayeeFilter = len(entries)
    totalAmtAfterPayeeFilter, avgAmtAfterPayeeFilter = getTotalAndAvgAmount(entries)

    # Convert entries' datetime from UTC to Eastern
    convertEntriesToEastern(entries)

    # Get a map of summary data (total, # entries, avg.) by year
    yearMap = getSummaryDataByYear(entries)

    # If LastN was requested, prune entries to keep only the first fetchLimit entries
    if fetchLimit:
      entries = entries[:fetchLimit]

    template_values['payeeToFilter'] = payeeToFilter
    template_values['filteringByPayee'] = filteringByPayee
    template_values['entries'] = entries
    template_values['payeeMap'] = payeeMap
    template_values['totalAmtBeforePayeeFilter'] = totalAmtBeforePayeeFilter
    template_values['uniquePayees'] = uniquePayees
    template_values['totalEntries'] = totalEntriesAfterPayeeFilter
    template_values['totalAmtAfterPayeeFilter'] = totalAmtAfterPayeeFilter
    template_values['avgAmtAfterPayeeFilter'] = avgAmtAfterPayeeFilter
    template_values['yearMap'] = yearMap
    template_values['sortedYears'] = sorted(yearMap.keys(), reverse=True)

  #===================================== GET =====================================
  def get(self):
    """Handler for HTTP GET. This gets the content of our application. POST, PUT, and DELETE
    are implemented in the next class below. In some cases they redirect back to the main page
    to get the page content updated. A more efficient approach would be to do everything via AJAX
    and dynamically update the relevant parts of the DOM. BUT it's hard to do since my app uses
    a backend framework. This would have been a breeze in Vue, React, or another FE framework.
    As it is, that all is not worth it; it's easier to simply reload the entire page.
    """
    # print(str(self.request))
    getMethodStart = time.time()

    exp_traq_name = self.request.get('exp_traq_name', DEFAULT_EXP_TRAQ_NAME)

    # Let's get this out of the way before the core code of this method.
    uniqueTrackers, entryCountAcrossAllTrackers = self.runOptionalToolsIfRequested(exp_traq_name)

    user = users.get_current_user()
    if user:
      url = users.create_logout_url(self.request.uri)
      url_linktext = 'Log out'
    else:
      url = users.create_login_url(self.request.uri)
      url_linktext = 'Log in'

    fetchLimit = DEFAULT_FOR_TOP_N 
    show = self.request.get('show')
    if show:
      if show == 'all':
        fetchLimit = None
      else:
        fetchLimit = int(show)
    
    if 'advanced' not in self.request.arguments():
      advancedView = False
    else:
      advancedView = True

    # We init the map here, then the generate<blah> methods below will add more view-specific items to it.
    template_values = {
      'exp_traq_name': urllib.quote_plus(exp_traq_name),
      'user': user,
      'url': url,
      'url_linktext': url_linktext,
      'show': show,
      'showAs': self.request.get('showAs'),
      'defaultForTopN': DEFAULT_FOR_TOP_N,
      'advancedView': advancedView,
      'uniqueTrackers': uniqueTrackers,
      'entryCountAcrossAllTrackers': entryCountAcrossAllTrackers,
    }
    # If we just added an entry and xposted it to another tracker, add the target tracker
    # name to template values so we can give user a handy link to that tracker to check things
    if 'lastXpost' in self.request.arguments(): # Was 'lastXpost' query string parameter defined?
      template_values['lastXpost'] = self.request.get('lastXpost')

    # Bifurcate between generating an advanced view and a basic view.
    # Up until a month ago, exp-traq had a simple and fast interface: CRUD operations 
    # on payment entries and a fast view option, load the last 10 entries, and a slower
    # option: load all entries. Then I added features like summary stats on all
    # entries and summary stats on all payees, which require always fetching all entries
    # and doing calculations in python. This became noticeably slow. Now I'm bringing back the
    # basic view. The default view for everyday use will be basic view -> show last 10 entries.
    if not advancedView:
      self.generateBasicView(template_values, exp_traq_name, fetchLimit) 
    else:
      self.generateAdvancedView(template_values, exp_traq_name, fetchLimit)

    template = JINJA_ENVIRONMENT.get_template('index.html')
    self.response.write(template.render(template_values))

    logging.debug('GET method: %.3f s' % (time.time() - getMethodStart))


class EntryHandler(webapp2.RequestHandler):
  '''Handler class for managing CRUD operations on individual entries
  We don't have get (it's handled by MainPage, above), but we have post, put, and delete
  '''

  #===================================== POST =====================================
  def post(self):
    #print(str(self.request))
    postMethodStart = time.time()

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
      targetDateStr = self.request.get('date')
      targetYear = int(targetDateStr[:4])
      targetMonth = int(targetDateStr[5:7])
      targetDay = int(targetDateStr[8:10])

      # WTF: though in terminal now() returns my current time and utcnow() returns the current UTC time,
      # in this code here both return UTC time!!!! So I can't just take now() and replace 
      # the date part with target date. Commenting out:
      # naive = datetime.datetime.now().replace(year=targetYear, month=targetMonth, day=targetDay)

      # Instead, I have to take UTC time, add easern TZ offset (which is negative) to convert to local time,
      # then replace the date part with the target date, then convert back to UTC (by subtracting eastern TZ offset),
      # then store that in entry.datetime. Then, in get(), I convert all entry.datetime to eastern time.
      # (Per GAE documentation, all time info must be stored in UTC and converted to local time on retrieval 
      # https://cloud.google.com/appengine/docs/legacy/standard/python/ndb/entity-property-reference#Date_and_Time)
      utcNow = datetime.datetime.utcnow()
      easternNow = utcNow + EasternTZInfo().utcoffset(utcNow)
      targetEasternNow = easternNow.replace(year=targetYear, month=targetMonth, day=targetDay)
      targetUtcNow = targetEasternNow - EasternTZInfo().utcoffset(targetEasternNow)
      entry.datetime = targetUtcNow
    else:
      entry.datetime = datetime.datetime.utcnow()

    entry.amount = int(self.request.get('amount'))

    entry.payee, fetchPayeesElapsed = getCanonicalPayeeSpelling(exp_traq_name, self.request.get('payee'))
    logging.debug('POST method -> fetch canonical payees from datastore: %.3f s' % fetchPayeesElapsed)

    entry.comment = self.request.get('comment')

    writeEntryStart = time.time()
    entry.put()
    logging.debug('POST method -> write entry to datastore: %.3f s' % (time.time() - writeEntryStart))

    # If a cross-post was requested, create a copy of entry and post it into the other tracker
    xpostTo = self.request.get('xpost')
    if xpostTo:
      entry2 = Entry(parent=exp_traq_key(xpostTo))
      entry2.author = entry.author
      entry2.datetime = entry.datetime
      entry2.amount = entry.amount
      entry2.payee = entry.payee
      entry2.comment = entry.comment
      
      writeEntryStart = time.time()
      entry2.put()
      logging.debug('POST method -> x-post entry to datastore: %.3f s' % (time.time() - writeEntryStart))

    # Preserve query params so the state is preserved once a user submits a new entry
    query_params = {
      'exp_traq_name': exp_traq_name, 
      'show': self.request.get('show'),
      'showAs': self.request.get('showAs'),
    }
    if xpostTo:
      query_params['lastXpost'] = xpostTo
    if 'advanced' in self.request.arguments():
      query_params['advanced'] = "" # Remember, we need the QS param simply to be present
    query_params['payeefilter'] = self.request.get('payeefilter')

    self.redirect('/?' + urllib.urlencode(query_params))

    logging.debug('POST method: %.3f s' % (time.time() - postMethodStart))

  #===================================== PUT =====================================
  def put(self, key): 
    '''key is the urlsafe ndb key of the entry being updated
    '''
    # print(str(self.request))
    putMethodStart = time.time()

    exp_traq_name = self.request.get('exp_traq_name', DEFAULT_EXP_TRAQ_NAME)

    targetDateStr = self.request.get('date') 
    amount = self.request.get('amount')
    payee = self.request.get('payee')
    comment = self.request.get('comment')

    # Get entry from db
    entry_key = ndb.Key(urlsafe = key)
    fetchEntryStart = time.time()
    entry = entry_key.get()
    logging.debug('PUT method -> fetch entry from datastore: %.3f s' % (time.time() - fetchEntryStart))

    # Update entry with info from the client

    if amount: # the 'if' is redundant since FE ensures there will always be an amount
      entry.amount = int(amount)
  
    if payee: # the 'if' is redundant since FE ensures there will always be a payee
      entry.payee, fetchPayeesElapsed = getCanonicalPayeeSpelling(exp_traq_name, payee)
      logging.debug('PUT method -> fetch canonical payees from datastore: %.3f s' % fetchPayeesElapsed)
        
    # If user has edited the date, take the datetime that came from the Datastore (is in UTC),
    # convert to Eastern, adjust its Y-M-D to the new date specified by the user (this preserves
    # the H-M-S part), convert the result back to UTC, and assign this datetime into the entry.
    originalUtc = entry.datetime
    originalEastern = originalUtc + EasternTZInfo().utcoffset(originalUtc)
    originalEasternDateStr = str(originalEastern)[:10]
    if targetDateStr != originalEasternDateStr: # User has edited date
      targetYear = int(targetDateStr[:4])
      targetMonth = int(targetDateStr[5:7])
      targetDay = int(targetDateStr[8:10])
      targetEastern = originalEastern.replace(year=targetYear, month=targetMonth, day=targetDay)
      targetUtc = targetEastern - EasternTZInfo().utcoffset(targetEastern)
      entry.datetime = targetUtc

    if comment:
      entry.comment = comment
    
    # Write updated entry to db
    writeEntryStart = time.time()
    entry.put()
    logging.debug('PUT method -> write entry to datastore: %.3f s' % (time.time() - writeEntryStart))

    logging.debug('PUT method: %.3f s' % (time.time() - putMethodStart))

    # We're reloading page in JS. Nothing to do here; we're done

  #===================================== DELETE =====================================
  def delete(self, key): 
    '''key is the urlsafe ndb key of the entry being deleted
    '''
    # print(str(self.request))

    entry_key = ndb.Key(urlsafe = key)
    deleteEntryStart = time.time()
    entry_key.delete()
    logging.debug('DELETE method: %.3f s' % (time.time() - deleteEntryStart))


app = webapp2.WSGIApplication([
  ('/', MainPage),
  ('/submit', EntryHandler),
  ('/entry/(.+)', EntryHandler),
], debug=True)