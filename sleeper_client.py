import json
import dt_helper as dh
import input_helper as ih
import mongo_helper as mh
import settings_helper as sh
import webclient_helper as wh
from pprint import pprint


settings = sh.get_all_settings().get('default')
mongo = mh.Mongo(
    url=settings['mongo_url'],
    db=settings['mongo_db_name']
)

print('mongo.db_stats():')
pprint(mongo.db_stats())


def _get_league_ids_from_settings():
    """Return a list of stringified sleeper_league_id values from settings.ini

    You may also set the SLEEPER_LEAGUE_ID environment variable.
    Multiple league IDs may be specified by separating them with a comma.
    """
    league_id_raw = settings['sleeper_league_id']
    assert league_id_raw, (
        'You must set sleeper_league_id in settings.ini '
        'or the SLEEPER_LEAGUE_ID environment variable.'
        '\n\nYou may specify multiple league IDs by separating them '
        'with a comma.'
    )
    if type(league_id_raw) == list:
        return [str(league_id) for league_id in league_id_raw]
    else:
        return [str(league_id_raw)]


class SleeperClient(wh.WebClient):
    """
    - read-only HTTP API to access a user's leagues, drafts, and rosters
    - see Sleeper API docs online: https://docs.sleeper.com
    - no API token necessary
    - all requests are GET requests
    - stay under 1000 API calls per minute
        - status code 429 returned if too many requests
    """
    _league_ids = _get_league_ids_from_settings()
    _league_id = _league_ids[0]

    def get_league(self, store=True, debug=False):
        """Get the response object from the league endpoint

        - store: if True, save the data to database
        - debug: if True, enter debugger before returning the response object
        """
        response = self.GET(
            f'/league/{self._league_id}',
            debug=debug,
            retry=True
        )
        if store and response.status_code == 200:
            match_query = {'league_id': self._league_id}
            update_statement = {'$set': response.json()}
            mongo._update_one(
                settings['league_collection'],
                match_query,
                update_statement,
                upsert=True
            )
        return response

    def get_rosters(self, store=True, debug=False):
        """Get the response object from the league rosters list endpoint

        - store: if True, save the data to database
        - debug: if True, enter debugger before returning the response object
        """
        response = self.GET(
            f'/league/{self._league_id}/rosters',
            debug=debug,
            retry=True
        )
        if store and response.status_code == 200:
            for roster in response.json():
                match_query = {
                    'league_id': self._league_id,
                    'owner_id': roster['owner_id']
                }
                update_statement = {'$set': roster}
                mongo._update_one(
                    settings['roster_collection'],
                    match_query,
                    update_statement,
                    upsert=True
                )
        return response

    def get_players(self, store=True, debug=False):
        """Get the response object from the players list endpoint

        - store: if True, save the data to database
        - debug: if True, enter debugger before returning the response object

        Only allowed to call this endpoint once per day

        - check collection at settings['last_fetch_time_collection'] to be sure
          it has been 24 hours since last fetch for players endpoint
        """
        two_days_ago = dh.days_ago(2)
        now = dh.utc_now_localized()
        match_query = {'players': {'$exists': True}}
        update_statement = {'$set': {'players': now}}
        found = mongo._find_one(
            settings['last_fetch_time_collection'],
            match_query,
            fields='players'
        )
        if not found:
            update_statement = {'$set': {'players': two_days_ago}}
            mongo._update_one(
                settings['last_fetch_time_collection'],
                match_query,
                update_statement,
                upsert=True
            )
            found = mongo._find_one(
                settings['last_fetch_time_collection'],
                match_query,
                fields='players'
            )
            update_statement = {'$set': {'players': now}}

        time_diff_seconds = (now.replace(tzinfo=None) - found).total_seconds()
        time_diff_pretty = ih.seconds_to_timestamps(time_diff_seconds)['pretty']
        if time_diff_seconds < 60 * 60 * 24:
            print('It has not been 24 hours since the last fetch')
            print(f'Only {time_diff_pretty}')
            return

        print(f'Last fetched {time_diff_pretty} ago')
        mongo._update_one(
            settings['last_fetch_time_collection'],
            match_query,
            update_statement,
            upsert=True
        )
        print('Getting response from /players/nfl endpoint')
        response = self.GET(
            f'/players/nfl',
            debug=debug,
            retry=True
        )
        if response.status_code == 200:
            data = response.json()
            print(f"Saving data to {settings['player_json_file']}")
            with open(settings['player_json_file'], 'w') as fp:
                json.dump(data, fp, indent=2)
            if store:
                print('Writing data to mongodb')
                #
                # TODO: Update to use bulk_write later
                #
                for player_id in data:
                    match_query = {'player_id': player_id}
                    update_statement = {'$set': data[player_id]}
                    mongo._update_one(
                        settings['player_collection'],
                        match_query,
                        update_statement,
                        upsert=True
                    )
        else:
            print('Status code was not 200 for /players/nfl endpoint, see response')
            breakpoint()
        return response

    def get_users(self, store=True, debug=False):
        """Get response object from the user endpoint for each owner_id from rosters

        - store: if True, save the data to database
        - debug: if True, enter debugger before returning the response object
        """
        self.get_rosters()
        responses = []
        for user_id in mongo._distinct(settings['roster_collection'], 'owner_id'):
            response = self.GET(
                f'/user/{user_id}',
                debug=debug,
                retry=True
            )
            responses.append(response)
            if store and response.status_code == 200:
                data = response.json()
                match_query = {'user_id': data['user_id']}
                update_statement = {'$set': data}
                mongo._update_one(
                    settings['user_collection'],
                    match_query,
                    update_statement,
                    upsert=True
                )
        return responses

    def get_season_state(self, store=True, debug=False):
        """Get response object from the nfl state endpoint

        - store: if True, save the data to database
        - debug: if True, enter debugger before returning the response object
        """
        response = self.GET(
            f'/state/nfl',
            debug=debug,
            retry=True
        )
        if store and response.status_code == 200:
            data = response.json()
            match_query = {'season': data['season'], 'week': data['week']}
            update_statement = {'$set': data}
            mongo._update_one(
                settings['season_state_collection'],
                match_query,
                update_statement,
                upsert=True
            )
        return response

    def get_matchups(self, week=None, store=True, debug=False):
        """Get response object from the matchup endpoint for the current week

        - week: specific week number, if not the current week
        - store: if True, save the data to database
        - debug: if True, enter debugger before returning the response object
        """
        self.get_season_state()
        current_season_state = mongo.last_obj(settings['season_state_collection'])
        if not week:
            week = current_season_state['week']
        extra = {
            'week': week,
            'league_id': self._league_id,
            'season': current_season_state['season'],
        }
        response = self.GET(
            f'/league/{self._league_id}/matchups/{week}',
            debug=debug,
            retry=True
        )
        if store and response.status_code == 200:
            for matchup in response.json():
                matchup.update(extra)
                match_query = {
                    'matchup_id': matchup['matchup_id'],
                    'roster_id': matchup['roster_id'],
                    'league_id': extra['league_id'],
                    'week': extra['week'],
                    'season': extra['season']
                }
                update_statement = {'$set': matchup}
                mongo._update_one(
                    settings['matchup_collection'],
                    match_query,
                    update_statement,
                    upsert=True
                )
        return response

    def get_trending(self, store=True, debug=False):
        """Get response objects from the trending add/drop endpoints

        - store: if True, save the data to database
        - debug: if True, enter debugger before appending each response object
          to responses list
        """
        today = dh.days_ago(0)
        responses = []
        
        # Trending add
        response = self.GET(
            '/players/nfl/trending/add',
            debug=debug,
            retry=True
        )
        responses.append(response)
        if store and response.status_code == 200:
            data = response.json()
            #
            # TODO: Update to use bulk_write later
            #
            for item in data:
                item['day'] = today
                item['type'] = 'add'
                match_query = {'player_id': item['player_id'], 'day': today, 'type': 'add'}
                update_statement = {'$set': item}
                mongo._update_one(
                    settings['trend_collection'],
                    match_query,
                    update_statement,
                    upsert=True
                )

        # Trending drop
        response = self.GET(
            '/players/nfl/trending/drop',
            debug=debug,
            retry=True
        )
        responses.append(response)
        if store and response.status_code == 200:
            data = response.json()
            #
            # TODO: Update to use bulk_write later
            #
            for item in data:
                item['day'] = today
                item['type'] = 'drop'
                match_query = {'player_id': item['player_id'], 'day': today, 'type': 'drop'}
                update_statement = {'$set': item}
                mongo._update_one(
                    settings['trend_collection'],
                    match_query,
                    update_statement,
                    upsert=True
                )

        return responses


client = SleeperClient(
    base_url='https://api.sleeper.app/v1'
)
