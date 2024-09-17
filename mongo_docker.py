import bg_helper as bh
import settings_helper as sh
from sys import exit


settings = sh.get_all_settings().get('default')


def start_mongo_docker():
    """Start mongodb container for storing data"""
    bh.tools.docker_ok(exception=True)
    bh.tools.docker_mongo_start(
        settings['local_container_name'],
        data_dir=settings['local_db_data_dir'],
        show=True
    )


if __name__ == '__main__':
    start_mongo_docker()
