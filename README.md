I am a part of a "dynasty" fantasy football league, where the league members
each draft a team of NFL players to their rosters and hold onto them across
multiple seasons. After each season is over, there is a rookie draft and a free
agent draft. Our league is managed via the [Sleeper
App](https://sleeper.com/fantasy-football). Sleeper also provides a read-only
HTTP API that gives access to a subset of data available in the app. See:
<https://docs.sleeper.com>

**Check back periodically throughout this NFL season for more updates and
examples.**

## Prerequisites

- [Docker](https://www.docker.com) OR write access to a
  [MongoDB](https://www.mongodb.com) instance/cluster
- [Sleeper League
  ID](https://support.sleeper.com/en/articles/4121798-how-do-i-find-my-league-id)
    - *add it to the settings.ini file (next to `sleeper_league_id = `) or export
      the `SLEEPER_LEAGUE_ID` environment variable.*

## Why

This project was created to demonstrate some uses of a handful of Python
packages that I maintain:

- [webclient-helper](https://pypi.org/project/webclient-helper), a wrapper to
  the popular [requests](https://pypi.org/project/requests) package for making
  HTTP requests to resources online
- [settings-helper](https://pypi.org/project/settings-helper), a wrapper to the
  builtin [configparser
  module](https://docs.python.org/3/library/configparser.html) for loading
  configuration data from a settings.ini file
- [mongo-helper](https://pypi.org/project/mongo-helper), a wrapper to the
  [pymongo](https://pypi.org/project/pymongo) package for interacting with a
  MongoDB database
- [bg-helper](https://pypi.org/project/bg-helper), a wrapper to the builtin
  [subprocess module](https://docs.python.org/3/library/subprocess.html), that
  includes tools for using docker to manage database containers

> (9/16/24) A lot of the functionality of mongo-helper is not yet documented. I'm
> using this as an opportunity to update documentation, implement tests, improve
> compatibility, and add features that I wanted to add several years ago.
>
> See the [updated README for mongo-helper](https://github.com/kenjyco/mongo-helper/blob/c3c82c80f756595bebebcfd66ff4d0957afd0547/README.md) (not yet released):
>

## What

There is a `sleeper_client.py` file that loads the settings from the
settings.ini file (and environment variables), creates an instance of the
`Mongo` class from mongo-helper as **`mongo`** that is connected to your
`mongo_url`, defines a `SleeperClient` class that interacts with the API, and
creates an instance of that class as **`client`**.

There is a `start-sleeper-client.sh` shell script that will start the IPython
shell if it's installed to the venv (falling back to default python) with the
`sleeper_client.py` file loaded in interactive mode.

There is a `start-mongo-docker.sh` shell script that will start the MongoDB
container using the `local_container_name` and `local_db_data_dir` values in the
settings.ini file.

The `get_*` methods callable from the `client` instance are the ones that
interact with the Sleeper API and save the data it receives to the appropriate
collection in MongoDB.

Those methods all have default keyword args `store=True` and `debug=False` set.
If store is True, the data from the response will be presisted to the database
if the response status is 200 (OK).  If debug is True, you will drop into a
debugger (pdb or pdbpp) session right before the response object is returned.

- `get_league()`
- `get_rosters()`
    - *called by `get_users`*
- `get_players()`
    - *only meant to be called once per day*
    - *will also save it's JSON response to a local file defined in settings.ini*
- `get_users()`
- `get_season_state()`
    - *called by `get_matchups`*
- `get_matchups()`
    - *can pass in an optional week number*
- `get_trending()`

## Setup

Create a virtual environment using Python 3.9 (there is currently an issue with
mongo-helper for Python versions greater than 3.9), then use pip to install the
packages listed in the `requirements.txt` file.

```
venv-setup
```

The [venv-setup](https://github.com/kenjyco/base/blob/master/bin/venv-setup)
script (provided by my [base repo](https://github.com/kenjyco/base)) will create
a virtual environment named venv, use pip to install the dependencies listed in
`requirements.txt`, then use pip to also install the ipython, pytest, and pdbpp
packages. (*You can use `venv-setup-lite` to do all that except for adding the
last 3 packages if desired*).

## Running

Before loading the `sleeper_client.py` file in an interactive session, get your
[Sleeper League
ID](https://support.sleeper.com/en/articles/4121798-how-do-i-find-my-league-id)
and either add it to the settings.ini file (next to `sleeper_league_id = `) or
export the `SLEEPER_LEAGUE_ID` environment variable.

If you are connecting to a MongoDB instance/cluster outside of docker, be sure
to replace the `mongo_url` value in settings.ini or export the `MONGO_URL`
environment variable.

If you are going to use docker for running MongoDB locally, be sure that docker
is running and the database instance is started.

```
./start-mongo-docker.sh
```

## Usage

Use the `start-sleeper-client.sh` shell script to execute the
`sleeper_client.py` script in interactive mode.

```
./start-sleeper-client.sh
```

or

```
SLEEPER_LEAGUE_ID=1234567890 ./start-sleeper-client.sh
```

or

```
SLEEPER_LEAGUE_ID="123456789, 987654321" ./start-sleeper-client.sh
```

The primary objects you will be interacting with during the interactive session
are `client` or `mongo`.


- client

    ```
    client.get_league()

    client.get_rosters()

    client.get_players()

    client.get_users()

    client.get_season_state()

    client.get_matchups()

    client.get_trending()

    client.history_explorer()
    ```

- mongo

    ```
    mongo.db_stats()

    mongo.server_info()

    mongo.get_collections()

    [mongo.coll_stats(coll) for coll in sorted(mongo.get_collections())]

    mongo.first_obj(some_coll)

    mongo.last_obj(some_coll)

    mongo._find_one('players', {'player_id': '10226'})

    # Youngest 7 players with an injury
    cursor = mongo._find(
        'players',
        {'injury_status': {'$ne': None}},
        fields='full_name, birth_date, fantasy_positions, status, injury_status, injury_body_part',
        sort=[('birth_date', -1)],
        limit=7
    )
    [x for x in cursor]

    # Active players with the most years of experience
    cursor = mongo._find(
        'players',
        {'status': 'Active'},
        fields='full_name, news_updated, fantasy_positions, status, years_exp',
        sort=[('years_exp', -1)],
        limit=7
        )
    [x for x in cursor]

    # The weekly matchups for the 2024 season
    list(mongo._find(
        'matchups',
        {'season': '2024'},
        fields='week, points, roster_id, matchup_id',
        sort=[('week', 1), ('matchup_id', 1)]
    ))
    ```
