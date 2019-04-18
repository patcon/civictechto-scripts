import click
import re
import requests
import textwrap
import urllib

from commands.common import common_params, parse_gdoc_url
from commands.utils.slackclient import CustomSlackClient
from commands.utils.gspread import CustomGSpread


CONTEXT_SETTINGS = dict(help_option_names=['--help', '-h'])

@click.command(context_settings=CONTEXT_SETTINGS)
@click.option('--gsheet',
              required=True,
              help='URL to publicly readable Google Spreadsheet.',
              )
@click.option('--slack-token',
              help='API token for any Slack user.',
              envvar='SLACK_API_TOKEN',
              )
@click.option('--channel', '-c',
              required=True,
              help='Name or ID of Slack channel in which to poll membership.',
              )
@common_params
def slack_organizing_checkin(gsheet, channel, slack_token, yes, verbose, debug, noop):
    """Poll members of Slack channel for team status."""
    sc = CustomSlackClient(slack_token)
    res = sc.api_call('conversations.info', channel=channel)
    # TODO: handle multiple channels
    # TODO: resolve channels from name
    channel = res['channel']

    ### Fetch spreadsheet

    spreadsheet_key, worksheet_id = parse_gdoc_url(gsheet)
    CSV_URL_TEMPLATE = 'https://docs.google.com/spreadsheets/d/{key}/export?format=csv&id={key}&gid={id}'
    csv_url = CSV_URL_TEMPLATE.format(key=spreadsheet_key, id=worksheet_id)
    # Fetch and parse shortlink CSV.
    r = requests.get(csv_url)
    if r.status_code != requests.codes.ok:
        raise click.Abort()
    # TODO: Clean up this.
    csv_content = r.content.decode('utf-8')
    csv_content = csv_content.split('\r\n')

    ### Confirm spreadsheet title

    # TODO: Move this into class.
    cd_header = r.headers.get('Content-Disposition')
    # See: https://tools.ietf.org/html/rfc5987#section-3.2.1 (ext-value definition)
    m = re.search("filename\*=(?P<charset>.+)'(?P<language>.*)'(?P<filename>.+)", cd_header)
    filename = m.group('filename')
    filename = urllib.parse.unquote(filename)
    # Remove csv filename suffix.
    filename = filename[:-len('.csv')]

    ### Output confirmation to user

    if verbose or not yes:
        confirmation_details = """\
            We are using the following configuration:
              * Slack Channel:           #{channel}
              * Spreadsheet - Worksheet: {name}
              * Spreadsheet URL:         {url}"""
              # TODO: Find and display spreadsheet title
              # Get from the file download name.
        confirmation_details = confirmation_details.format(channel=channel['name'], url=gsheet, name=filename)
        click.echo(textwrap.dedent(confirmation_details))

    if not yes:
        click.confirm('Do you want to continue?', abort=True)

    if noop:
        # TODO: Add no-op.
        raise NotImplementedError

    gspread = CustomGSpread()

    members = sc.get_user_members(channel['id'])
    for m in members:
        print(m)
        footer = """If not, you'll simply be moved from active to <http://civictech.ca/about-us/organizers/#past|past organizer list on the website>.

Re-activate yourself anytime by leaving and re-joining this channel :)""",
        res = sc.api_call('chat.postEphemeral',
                          channel=channel['id'],
                          user=m['id'],
                          text=':ctto: Time for the monthly update of the <http://civictech.ca/about-us/organizers/|organizer list on the website>! :tada:',
                          attachments=[
                              {
                                  'title': 'Do you still consider yourself an active organizer?',
                                  'footer': footer,
                                  'fallback': 'Do you still consider yourself an active organizer?',
                                  "callback_id": "organizer_update",
                                  "color": "#cccccc",
                                  "attachment_type": "default",
                                  "actions": [
                                      {
                                          "name": "yes",
                                          "text": "Yep!",
                                          "type": "button",
                                          "style": "primary",
                                          "value": "yes"
                                      },
                                      {
                                          "name": "no",
                                          "text": "No, not at the moment.",
                                          "type": "button",
                                          "value": "maze"
                                      }
                                  ],
                              }
                          ],
                          as_user=True)
        break

if __name__ == '__main__':
    slack_organizing_checkin()
