![sample image](mysecretsanta.png)

Invite your buddies and do a secret santa draw. Trust me, it will be really random. Like, quantum physics level of random

## Dev environment

You'll need the following in your dev machine to get started

* pipenv
* Python 3.8
* Docker (CLI and daemon)
* docker-compose

### If your system Python is not 3.8
This is probably fine but can cause issues. In that case, just add the deadsnakes PPA and download Python 3.8. DO NOT try changing your system Python by updating the `python3` symlink. You WILL break things! If you had already created a virtualenv with pipenv, you'll have to remove it first and then create another virtualenv so it uses Python 3.8

## Run the test suite

Run the test script `./test.sh` to see if your dev environment is set up correctly. This script spawns all the necessary services like db, redis, celery workers etc and runs the test suite inside the app container. If the tests pass it means you're all set to contribute!