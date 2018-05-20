#!/usr/bin/env python
"""
steps.py

Expose API for the website 10000stepsuk.com

This script may be run as a command line program or included as a python module in other scripts.

Run ./steps.py -h for command line usage.

TODO: Add non-walking activities nd take them into consideration for leaderboard.
"""

# Standard modules
import argparse
import os
import sys
import json
import time
import datetime
from pprint import pprint, pformat

# PyPi modules
import requests
from six.moves import configparser as ConfigParser


class Config():
    """
    The Configuration File
    """

    filename = '~/10kstepsrc'

    def __init__(self):
        """
        Reads configuration data from file.
        """
        self.cfg = ConfigParser.ConfigParser()
        if self.cfg.read(os.path.expanduser(self.filename)) == []:
            self._create_empty_config()
            print("Missing %s. A default has been created for editing." % self.filename)
            sys.exit(0)

    def _create_empty_config(self):
        """
        Creates a blank config file.
        """
        cfg = ConfigParser.RawConfigParser()
        cfg.add_section('auth')
        cfg.set('auth', 'username', 'my_username')
        cfg.set('auth', 'password', 'my_password')
        with open(os.path.expanduser(self.filename), 'w') as cfgfile:
            cfg.write(cfgfile)
        os.chmod(os.path.expanduser(self.filename), 0o600)

    def get(self, section, key):
        """
        Returns the value of the configuration variable identified by the
        given key within the given section of the configuration file. Raises
        ConfigParser exceptions if the section or key are invalid.
        """
        return self.cfg.get(section, key).strip()



class API:
    """
    The Website API
    """
    
    def __init__(self, debug=False):
        self.debug = debug
        self.username = Config().get('auth', 'username')
        self.password = Config().get('auth', 'password')
        self.base_url = 'https://www.members.10000stepsuk.com'
        self.session = None
        self._session()
    
    def _session(self):
        """
        Establish a user session by logging in to the website.
        """
        url = self.base_url + '/sessions'
        data = {'login': self.username, 'password': self.password}
        self.session = requests.Session()
        self.session.post(url, data=data)

    def _url(self, path):
        # Append 'ajax.timestamp=<milliscond_epoch>' to path
        delim = '?'
        if delim in path:
            delim = '&'
        path += delim + 'ajax.timestamp=%i' % int(time.time()*1000)
        # Prepend base_url
        url = self.base_url + path
        if self.debug:
            print('URL', url)
        return url

    def _post(self, path, data):
        """
        POST the payload in data dict to the resource specified by path.
        """
        url = self._url(path)
        if self.debug:
            pprint(data)
        resp = self.session.post(url, data=data)
        if self.debug:
            print('CODE', resp.status_code)

    def _get(self, path):
        """
        GET the resource specified by path and return the result as a json dict.
        """
        url = self._url(path)
        resp = self.session.get(url)
        dic = resp.json()
        if self.debug:
            print('CODE', resp.status_code)
            pprint(dic)
        return dic

    def get_activity_list(self):
        """
        Returns a dict describing the types of activities that can be added
        (running, cycling, swimming etc).
        """
        return self._get('/users/getActivityList')

    def get_walk_history(self, date=None):
        """
        Returns a dict containing the logged steps and activities for the user for all dates. 
        Can optionally specify a date (YYYY-MM-DD) and will only return data for that date.
        """
        path = '/users/logWalkHistory'
        if date:
            path += '?reloadDate=%s' % date
        return self._get(path)

    def get_leaderboard(self, recalc=False, date_check=None):
        """
        Returns the leaderboard.
        Not sure what recalc argument does.
        The date_check should contain a date (YYYY-MM-DD), to filter the result by date.
        """
        path = '/users/leaderboards'
        if recalc:
            path += '?recalc'
        if date_check:
            delim = '?'
            if delim in path:
                delim = '&'
            path += delim + 'dateCheck=%s' % date_check
        return self._get(path)

    def add_steps(self, step_count, date_string):
        """
        Add specified step_count for date in date_string (YYYY-MM-DD).
        """
        data = {
            'walking_log[date_string]': date_string,
            'walking_log[units]': step_count,
            'walking_log[steps]': step_count,
            'walking_log[unit_type]': 'steps',
        }
        self._post('/walking_logs.json', data)

    def delete_steps(self, logs_id):
        """
        Deletes a steps entry.
        The logs_id parameter refers to the data[date][logs][n][id] value.
        """
        self._get('/walking_logs/%s?_method=delete' % logs_id)

    def add_activity(self):
        pass


if __name__ == '__main__':
    api = None

    # Default date is yesterday
    default_date = datetime.date.today() - datetime.timedelta(1)
    default_date_string = default_date.strftime('%Y-%m-%d')

    def initialise(args):
        # called before each subcommand
        global api
        api = API(debug=args.debug)

    parser = argparse.ArgumentParser()
    parser.add_argument('-D', '--debug', action='store_true', default=False, help='Prints full JSON data.')

    subparsers = parser.add_subparsers(title='subcommands', help = 'run <subcommand> -h for additional help')

    p = subparsers.add_parser('activities', help='Display the types of activities other than walking.')
    def activities(args):
        dic = api.get_activity_list()
        data = dic['data']
        activity_list = [a for a in data['else_used'].keys()]
        activity_list.sort()
        print('\n'.join(activity_list))
    p.set_defaults(func=activities)

    p = subparsers.add_parser('history', help='Display complete walk history.')
    def history(args):
        dic = api.get_walk_history()
        data = dic['data']
        dates = data.keys()
        dates.sort()
        print("Date       Steps")
        print("---------- -----")
        for date in dates:
            steps = 0
            if 'logs' in data[date]:
                for log_id in data[date]['logs']:
                    steps += data[date]['logs'][log_id]['steps']
            print("%s %s" % (date, steps))
    p.set_defaults(func=history)

    p = subparsers.add_parser('leaders', help='Display the leaderboard.')
    def leaders(args):
        data = api.get_leaderboard();
        # Ranking list contains a tuple for each user (user_id, total)
        ranking = []
        # Team totals dict indexed by team_id contains team total
        team_totals = {}
        for team_id in data['indexUsersByTeam']:
            team_totals[team_id] = 0
        # Fill rankings
        for stat in data['statistics'].values():
            ranking.append( (stat['user_id'], int(stat['total']) ) )
            team_totals[stat['team_id']] += int(stat['total'])
        # Sort ranking based on total
        ranking.sort(key=lambda x: x[1], reverse=True)
        # Print individual leaderboard in order of ranking
        rank = 1
        print("Individual Leaderboard")
        print("Rank Total      Name")
        print("---- ---------- ----------")
        for uid, total in ranking:
            name = data['users'][uid]['first_name']
            name += ' ' + data['users'][uid]['last_name']
            name += ' (' + data['users'][uid]['login'] + ')'
            print("%4s %10s %s" % (rank, total, name))
            rank += 1
        # Print team leaderboard
        print("")
        print("Team Leaderboard")
        print("Rank Total        Team")
        print("---- ------------ ------------")
        rank = 1
        for team_id in sorted(team_totals, key=lambda x: team_totals[x], reverse=True):
            total = team_totals[team_id]
            name = data['teams'][team_id]['name']
            print("%4s %12s %s" % (rank, team_totals[team_id], name))
            rank += 1
    p.set_defaults(func=leaders)

    p = subparsers.add_parser('add', help='Add steps for specified date')
    p.add_argument('steps', type=int)
    p.add_argument('-d', '--date', action='store', type=str, default=default_date_string, help='Specify the date (default: %(default)s).')
    def add(args):
        api.add_steps(args.steps, args.date)
        # After the steps are added, the website does the following two things (so we do too)
        foo = api.get_walk_history(date=args.date)
        bar = api.get_leaderboard(recalc=True, date_check=args.date)
    p.set_defaults(func=add)

    p = subparsers.add_parser('delete', help='Delete all steps for a specified date')
    p.add_argument('-d', '--date', action='store', type=str, default=default_date_string, help='Specify the date (default: %(default)s).')
    def delete(args):
        dic = api.get_walk_history(date=args.date)
        for log in dic['data'][args.date]['logs'].values():
            api.delete_steps(log['id'])
        foo = api.get_walk_history(date=args.date)
    p.set_defaults(func=delete)

    args = parser.parse_args()
    initialise(args)
    args.func(args)
