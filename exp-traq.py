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


# We set a parent key on the expense entries to ensure that they are all
# in the same entity group. Queries across the single entity group
# will be consistent. However, the write rate should be limited to
# ~1/second.

def exp_traq_key(exp_traq_name=DEFAULT_EXP_TRAQ_NAME):
    """Constructs a Datastore key for an exp-treq entity. We use exp_traq_name as the key."""
    return ndb.Key('Exp-traq', exp_traq_name)

class Author(ndb.Model):
    """Sub model for representing an author."""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)

class Entry(ndb.Model):
    """A main model for representing an individual expense entry."""
    datetime = ndb.DateTimeProperty(indexed=True, required=True)
    amount = ndb.IntegerProperty(indexed=False, required=True)
    payee = ndb.StringProperty(indexed=False, required=True)
    comment = ndb.StringProperty(indexed=False)

    # Stuff to be populated automatically
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

class MainPage(webapp2.RequestHandler):

    def get(self):
        exp_traq_name = self.request.get('exp_traq_name', DEFAULT_EXP_TRAQ_NAME)
        if self.request.get('showAs') == 'table':
            show_as_table = True
        else:
            show_as_table = False
        entries_query = Entry.query(ancestor=exp_traq_key(exp_traq_name)).order(-Entry.datetime).order(-Entry.timestamp)
        entries = entries_query.fetch()

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
            entry.dateOnly = datetime.datetime.strftime(entry.datetime, '%a %Y-%m-%d')


        template_values = {
            'show_as_table': show_as_table,
            'user': user,
            'entries': entries,
            'exp_traq_name': urllib.quote_plus(exp_traq_name),
            'url': url,
            'url_linktext': url_linktext,
        }

        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))


class SubmitEntry(webapp2.RequestHandler):

    def post(self):
        # We set the same parent key on the 'Entry' to ensure each
        # Entry is in the same entity group. Queries across the
        # single entity group will be consistent. However, the write
        # rate to a single entity group should be limited to
        # ~1/second.
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

        query_params = {'exp_traq_name': exp_traq_name}
        self.redirect('/?' + urllib.urlencode(query_params))


class DeleteEntry(webapp2.RequestHandler):
    """ Datastore reference https://cloud.google.com/appengine/docs/python/ndb/creating-entities """
    def delete(self, param1):
        # param1 contains id of entry to delete
        entry_key = ndb.Key(urlsafe=param1)
        entry_key.delete()


app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/submit', SubmitEntry),
    ('/entry/(.+)', DeleteEntry),
], debug=True)
# [END app]
