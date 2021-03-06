# CivicTechTO Scripts
[![Run scripts](https://img.shields.io/badge/scheduled%20scripts-RUN-44cc11.svg)][circleci-proj]
[![CircleCI Status](https://img.shields.io/circleci/project/github/CivicTechTO/civictechto-scripts.svg?label=CircleCI)][circleci-proj]

Helper scripts for CivicTechTO organizing tasks.

We use this as a catch-all for simple scripts that help with organizing
tasks. Many of them run automatically each week.

## Technologies Used

- **Python.** A programming langauge common in scripting.
- [**Click.**][click] A Python library for writing simple command-line
  tools.
- [**CircleCI.**][circleci] A script-running service that [runs scheduled
  tasks][circleci-cron] for us in the cloud.
- [**Trello.**][trello] A flexible organizing and project management
  tool that we [use to track breakout groups][trello-board].

## About these Automated Scripts

Some of these scripts are automatically run before and after hacknight,
using CircleCI's workflow feature. The schedule is set in the
[`.circleci/config.yml`][circleci-config] file within this repo.

Here's a diagram showing how project pitch information flows into, through and out of the Trello board, in part via scripts:

<sub>(Click to see expanded view.)</sub><br/>
[![Process Flow Diagram](https://docs.google.com/drawings/d/e/2PACX-1vSNrFFElzvRuHQM44PU--wO3kyDwhR54gnj6mHoXbJ_1CkRzgB2murOhFNM9DxIcnYSYGSk5naJH2p5/pub?w=600)](https://docs.google.com/drawings/d/1h9hY9eyfZzdVbIu-4pihQ6RBgrjj8PbUsHE4oHbGYUY/edit)

## :computer: Local Development

### Setup

We recommend using `virtualenvwrapper` for isolating your Python
environment. Then just follow these steps.

1. Install the required packages:

    ```
    $ pip install -r requirements.txt
    ```

2. Copy the configuration file:

    ```
    $ cp sample.env .env
    ```

3. Edit the file according to its comments.

## Scripts

### `clean_pitch_list.py`

On the [Trello board][trello-board], this moves all cards from one list to another.

> eg. `Tonight's Pitches` :arrow_right: `Recently Pitched`

Runs pre-hacknight.

```
python clean_pitch_list.py
```

### `update_pitch_csv.py`

This updates the [historical dataset of breakout
groups][breakout-dataset] who pitched each week, based on the [Trello
board][trello-board].

Runs post-hacknight.

### `notify_slack_pitches.py`

This takes data from the [Trello board][trello-board], and drops a
message in Slack's `#general` channel, announcing who pitched this week.

Runs post-hacknight.

![Screenshot of Slack post](https://i.imgur.com/M1y4Yi6.png)

### `notify_slack_roles.py`

This takes data from the [Hacknight Roles spreadsheet][hacknight-roles-sheet], and drops a
message in Slack's `#organizing-open` channel, announcing who signed up for each hacknight-organizing role this month. If a role is unclaimed, it solicits help.

Runs day before hacknight.

![Screenshot of Slack post](https://i.imgur.com/PLUi7Lh.png)

### `send_monthly_project_email.py`

This take data from the [historical dataset of breakout
groups][breakout-dataset] (generated via [`update_pitch_csv.py`](#update_pitch_csvpy)), and sends out a MailChimp update once/month, using [this MailChimp template][mailchimp-template].

This is a work in progress, and doesn't yet work or run regularly.

<!-- Links -->
   [click]: http://click.pocoo.org/5/
   [circleci]: https://circleci.com/docs/2.0/about-circleci/
   [circleci-cron]: https://support.circleci.com/hc/en-us/articles/115015481128-Scheduling-jobs-cron-for-builds-
   [circleci-proj]: https://circleci.com/gh/CivicTechTO/civictechto-scripts
   [circleci-config]:.circleci/config.yml#L6-L31
   [breakout-dataset]: https://github.com/CivicTechTO/dataset-civictechto-breakout-groups/blob/master/data/civictechto-breakout-groups.csv
   [trello]: https://trello.com/about
   [trello-board]: https://trello.com/b/EVvNEGK5/hacknight-projects
   [hacknight-roles-sheet]: https://docs.google.com/spreadsheets/d/1v9xUqaSqgvDDlTpFqWtBXDPLKw6HsaFU5DfSO0d_9_0/edit
   [mailchimp-template]: https://us11.admin.mailchimp.com/templates/design?tid=364745
