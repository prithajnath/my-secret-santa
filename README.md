![sample image](mysecretsanta.png)

Invite your buddies and do a secret santa draw. Trust me, it will be really random. Like, quantum physics level of random

## Dev environment

You'll need the following in your dev machine to get started

* pipenv
* Python 3.8
* Docker (CLI and daemon)
* docker-compose

### Clone and repository and `cd` into it
```
git clone git@github.com:prithajnath/my-secret-santa.git && cd secret-santa-2018
```
### Create and start a virtual environment
```
$ pipenv shell
```
### Install dependencies

```
$ pipenv install
```
### Run the test suite

Run the test script to see if your dev environment is set up correctly. This script spawns all the necessary services like db, redis, celery workers etc and runs the test suite inside the app container. If the tests pass it means your dev environment is all set!

```
$ ./test.sh
```

### Add the pre-commit hook
The container uses a `requirements.txt` to keep its Python dependencies in check, but in our local environment we use `Pipfile` or `Pipfile.lock`. Every time you add a new dependency with `pipenv install ...` you need to update `requirements.txt`

Copy the commit hook `.githooks/pre-commit` to your `.git` directory

```
cp .githooks/pre-commit .git/hooks/pre-commit
```
This aborts a commit if your `requirements.txt` is out of sync. Update `requirements.txt` with the following command and try commiting again

```
$ pipenv lock -r > requirements.txt
$ git commit -m "hey hey ho ho"
```
### NOTE: If your system Python is not 3.8
This is probably fine but can cause issues. In that case, just add the deadsnakes PPA and download Python 3.8. DO NOT try changing your system Python by updating the `python3` symlink. If you had already created a virtualenv with pipenv, you'll have to remove it first and then create another virtualenv that uses Python 3.8

```
$ sudo apt install software-properties-common
$ sudo add-apt-repository ppa:deadsnakes/ppa
$ sudo apt update
$ sudo apt install python3.8
```
