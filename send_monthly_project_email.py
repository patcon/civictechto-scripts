import dateparser
import csv
import emoji
import itertools
import os
import pprint
import pystache
import pytz
import random
import re
import requests
import time

from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta
from jinja2 import Template
from mailchimp3 import MailChimp
from trello import TrelloClient

from commands.slackclient import CustomSlackClient


TRELLO_APP_KEY = os.getenv('TRELLO_APP_KEY')
TRELLO_SECRET = os.getenv('TRELLO_SECRET')


# See: https://github.com/jonathandion/awesome-emails#templates
#
# 1. Get the CSV of pitch dataset, and filter for past month.
#
# 1. Fetch the template with default section content
#
#      GET /templates/{template_id}/default-content
#
# 1. Rebuild project section with data from CSV
#
# 1. Create campaign, and schedule to send later
#
#      POST /campaigns
#
# 1. Replace the template sections with data
#
#      PUT /campaigns/{campaign_id}/content
#
# 1. Schedule the campaign to send
#
#      POST /campaigns/{campaign_id}/actions/schedule
#
# 1. Notify slack of the scheduled campaign with archive_url to preview.

def str2bool(v):
  return v.lower() in ("yes", "true", "t", "1")

DEBUG = str2bool(os.getenv('DEBUG', ''))
MAILCHIMP_API_KEY = os.getenv('MAILCHIMP_API_KEY')
MAILCHIMP_API_USER = os.getenv('MAILCHIMP_API_USER')
MAILCHIMP_LIST_ID = os.getenv('MAILCHIMP_LIST_ID')
MAILCHIMP_TEMPLATE_ID = int(os.getenv('MAILCHIMP_TEMPLATE_ID'))
MAILCHIMP_SECTION_NAME = os.getenv('MAILCHIMP_SECTION_NAME')
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN')
SLACK_ANNOUNCE_CHANNEL = os.getenv('SLACK_ANNOUNCE_CHANNEL_ORG')

def get_project_data():
    projects = [
            {
                'name': 'HomeTO',
                'tags': [
                    'working group',
                    ],
                'description': 'We empower at risk, low income, and homeless individuals through inclusive digital tools.',
                },
            {
                'name': 'Women and Color',
                'tags': [
                    'working group',
                    ],
                'description': 'Online community of talented women and people of colour available for speaking opportunities at tech-related events. We’ve launched! We are now planning to expand into more cities in Canada and the USA.',
                },
            {
                'name': 'Civic Tech 101',
                'tags': [
                    'learning group',
                    ],
                'description': 'Introduce you to Civic Tech Toronto and learn about one another. Please go here if it’s your first time!',
                },
            ]

    return projects

projects = get_project_data()

mc_client = MailChimp(mc_api=MAILCHIMP_API_KEY, mc_user=MAILCHIMP_API_USER)

class ProjectUpdateEmail(object):
    client = None
    template_id = None
    template = None

    def __init__(self, mailchimp_client):
        self.client = mailchimp_client

    def _get_template(self):
        self.template = self.client.templates.default_content.all(template_id=MAILCHIMP_TEMPLATE_ID)
        return self.template


email = ProjectUpdateEmail(mc_client)
email.template_id = MAILCHIMP_TEMPLATE_ID
template = email._get_template()

sections_data = template['sections']

# TODO

template = """
{%- if learning_groups -%}
<h2>Learning Groups</h2>
<ul>
  {%- for group in learning_groups %}
  <li>
    <strong>{{ group.name }}.</strong>
    {{ group.description }}
  </li>
  {%- endfor %}
</ul>
{%- endif %}

{% if working_groups -%}
<h2>Working Groups</h2>
<ul>
  {%- for group in working_groups %}
  <li>
    <strong>{{ group.name }}.</strong>
    {{ group.description }}
  </li>
  {%- endfor %}
</ul>
{%- endif -%}
"""

template = Template(template.strip())

from commands.utils.trello import BreakoutGroup

class BreakoutGroup(object):
    CHAT_RE = re.compile('^(?:slack|chat): (\S+)$', flags=re.IGNORECASE)
    PITCHER_RE = re.compile('pitchers?:? ?(.+)', flags=re.IGNORECASE)
    CONTRIBUTE_LINK_RE = re.compile('contribute', flags=re.IGNORECASE)
    SECONDARY_LINK_RE = re.compile('secondary link:', flags=re.IGNORECASE)
    ANY_LINK_RE = re.compile('.* link:', flags=re.IGNORECASE)

    card = None
    name = str()
    chat_room = str()
    pitcher = str()
    pitches = []
    pitch_count = 0
    streak_count = 0
    is_new = False
    # If no record, assume very old.
    last_pitch_date = datetime(2016, 8, 1)

    def __init__(self, card):
        self.card = card
        self.generate_from_trello_card()

    def generate_from_trello_card(self):
        self.name = self.card.name
        self.chat_room = self._get_chat_room()
        self.pitcher = self._get_pitcher()
        self.link = self._get_link()

    def process_pitches(self, pitches):
        # Tally pitch count.
        self.pitch_count = 0
        self.pitches = []
        for row in pitches:
            if row['trello_card_id'] == self.card.id:
                self.pitches.append(row)
                self.pitch_count += 1

        if self.pitch_count == 0:
            self.is_new = True

        # Get last pitch date.
        for row in pitches:
            if row['trello_card_id'] == self.card.id:
                self.last_pitch_date = datetime.strptime(row['date'], '%Y-%m-%d')
                break

        # Tally streak count.
        self.streak_count = 0
        for key, group in itertools.groupby(pitches, key=lambda r: r['date']):
            matches = [p for p in group if p['trello_card_id'] == self.card.id]
            if matches:
                self.streak_count += 1
                continue
            else:
                break

    def _get_chat_room(self):
        attachments = self.card.get_attachments()
        for a in attachments:
            match = self.CHAT_RE.match(a.name)
            if match:
                return match.group(1)

        return ''

    def _get_link(self):
        attachments = self.card.get_attachments()
        for pattern in [self.CONTRIBUTE_LINK_RE, self.SECONDARY_LINK_RE, self.ANY_LINK_RE]:
            for a in attachments:
                if pattern.match(a.name):
                    return a.url

        return ''

    def _get_pitcher(self):
        comments = self.card.get_comments()
        comments.reverse()
        # Get most recent pitcher
        # TODO: Check whether comment made in past week.
        for c in comments:
            match = self.PITCHER_RE.match(c['data']['text'])
            if match:
                return match.group(1)

        return ''

class BreakoutGroupsProcessor(object):
    NONCE = int(time.time())

    months_ago = 0
    csv_url = 'https://raw.githubusercontent.com/CivicTechTO/dataset-civictechto-breakout-groups/master/data/civictechto-breakout-groups.csv?r={}'.format(NONCE)
    groups = []
    pitches = []

    trello = None
    board_id = 'EVvNEGK5'

    def __init__(self):
        self.trello = TrelloClient(api_key=TRELLO_APP_KEY, api_secret=TRELLO_SECRET)
        self._load_pitches_from_url()

    def populate_groups_from_trello(self):
        board = self.trello.get_board(self.board_id)
        cards = board.get_cards({'filter': 'visible'})
        for c in cards:
            print(c.name)
            g = BreakoutGroup(c)
            g.process_pitches(self.pitches)
            self.groups.append(g)

    def _load_pitches_from_url(self):
        r = requests.get(self.csv_url)
        csv_content = r.content.decode('utf-8')
        csv_content = csv_content.split('\r\n')
        reader = csv.DictReader(csv_content, delimiter=',')
        # TODO: Ensure these are sorted by date in reverse chronological order.
        self.pitches = list(reader)[::-1]

    def get_group_by_id(self, trello_id):
        matches = [g for g in self.groups if g.card.id == trello_id]
        if matches:
            return matches.pop()
        else:
            None

    def get_group_by_name(self, name):
        matches = [g for g in self.groups if g.card.name.lower() == name.lower()]
        if matches:
            return matches.pop()
        else:
            None

    def get_groups_over_month(self):
        d = datetime.utcnow() - relativedelta(months=self.months_ago)
        month_start = datetime(d.year, d.month, 1)
        month_end = datetime(d.year, d.month+1, 1)
        return self.get_groups_over_range(month_start, month_end)

    def get_groups_over_range(self, start_date, end_date):
        for g in self.groups:
            for p in g.pitches:
                date = dateparser.parse(p['date'])
                #days = (month_start + timedelta(days=i) for i in range((month_end - month_start).days + 1))
                if start_date <= date < end_date:
                    yield g
                    break


processor = BreakoutGroupsProcessor()
processor.populate_groups_from_trello()
#sample_group = processor.get_group_by_name('Toronto Meshnet')
#print(vars(sample_group))
#pprint.pprint([vars(g) for g in july_groups])

context = {
        'learning_groups': [p for p in projects if 'learning group' in p['tags']],
        'working_groups': [p for p in projects if 'working group' in p['tags']],
        }

class EmailRenderer(object):
    EMOJI_PITCH = ':black_medium_square:'
    EMOJI_NOPITCH = ':white_medium_square:'
    EMOJI_STREAK = ':fire:'
    EMOJI_NEW = ':hatching_chick:'
    EMOJIS_COUNT = [':one:', ':two:', ':three:', ':four:', ':five:', ':six:', ':seven:', ':eight:', ':nine:', ':ten:', ':double_vertical_bar:']

    year = 2018
    month = 7
    event_count = 0
    active_groups = []
    pitch_data = []

    def __init__(self):
        pass

    def render(self):
        self._render_header()
        for g in self.active_groups:
            emojis = self._render_emojis(g)
            output = '{emojis} {name}'.format(emojis=emojis, name=g.name)
            if g.link:
                output = '{output} | [more...]({link})'.format(output=output, link=g.link)
            print(output)
        self._render_header()

    def _render_header(self):
        events = self._get_event_dates()
        output = " ".join(self.EMOJIS_COUNT[:len(events)])
        output = emoji.emojize(output, use_aliases=True)
        print(output)

    def _render_emojis(self, group):
        emojis = []
        for d in self._get_event_dates():
            match = [p for p in group.pitches if dateparser.parse(p['date']).date() == d]
            if match:
                emojis.append(self.EMOJI_PITCH)
            else:
                emojis.append(self.EMOJI_NOPITCH)
        emojis = " ".join(emojis)
        emojis = emoji.emojize(emojis)
        return emojis

    def _get_event_dates(self):
        return [
            date(2018, 7, 3),
            date(2018, 7, 10),
            date(2018, 7, 17),
            date(2018, 7, 24),
            date(2018, 7, 31),
        ]


processor.months_ago = 8
july_groups = processor.get_groups_over_month()

renderer = EmailRenderer()
renderer.active_groups = july_groups
print('-- JULY')
renderer.render()

raise


content = template.render(**context)

if DEBUG:
    print(content)
    exit(0)

sections_data['projects'] = content

campaign_data = {
        'recipients': {
            'list_id': MAILCHIMP_LIST_ID,
            },
        'settings': {
            'subject_line': 'Pitch recap for {}'.format('March'),
            'from_name': 'Civic Tech Toronto',
            'reply_to': 'hi@civictech.ca',
            'template_id': MAILCHIMP_TEMPLATE_ID,
            },
        'type': 'regular',
        }
campaign = mc_client.campaigns.create(campaign_data)

content_data = {
        'template': {
            'id': MAILCHIMP_TEMPLATE_ID,
            'sections': sections_data,
            }
        }
mc_client.campaigns.content.update(campaign_id=campaign['id'], data=content_data)

def calculate_send_time():
    d = timedelta(days=1)
    send_time = datetime.utcnow().replace(tzinfo=pytz.utc) + d
    return send_time

send_time = calculate_send_time()
rounded_send_time = send_time.replace(minute=15*(send_time.minute // 15))
mc_client.campaigns.actions.schedule(campaign_id=campaign['id'], data={'schedule_time': rounded_send_time})

list_data = mc_client.lists.get(MAILCHIMP_LIST_ID)

tmpl_vars = {
    'subscriber_count': list_data['stats']['member_count'],
    # TODO: Convert this time from UTC to ET
    'send_date': rounded_send_time.strftime('%a, %b %-m @ %-I:%M') + rounded_send_time.strftime('%p').lower(),
    'preview_url': campaign['archive_url'],
}
thread_template = open('templates/send_monthly_project_email.txt').read()
thread_content = pystache.render(thread_template, tmpl_vars)

if DEBUG or not SLACK_API_TOKEN:
    print(thread_content)
else:
    sc = CustomSlackClient(SLACK_API_TOKEN)
    sc.bot_thread(
        channel=SLACK_ANNOUNCE_CHANNEL,
        thread_content=thread_content,
    )
