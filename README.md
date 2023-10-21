![sample image](mysecretsanta.png)

Invite your buddies and do a secret santa draw. Trust me, it will be really random. Like, quantum physics level of random

## Dev environment

You'll need the following in your dev machine to get started

* pipenv
* Python 3.10
* Docker (CLI and daemon)
* docker-compose

### Clone and repository and `cd` into it
```
git clone git@github.com:prithajnath/my-secret-santa.git && cd my-secret-santa
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
### NOTE: If your system Python is not 3.10
This is probably fine but can cause issues. In that case, just add the deadsnakes PPA and download Python 3.10. DO NOT try changing your system Python by updating the `python3` symlink. If you had already created a virtualenv with pipenv, you'll have to remove it first and then create another virtualenv that uses Python 3.10

```
$ sudo apt install software-properties-common
$ sudo add-apt-repository ppa:deadsnakes/ppa
$ sudo apt update
$ sudo apt install python3.8
```

### NOTE: NGINX

Initially I exposed gunicorn workers to direct Internet traffic from ELB. This setup suffered multiple worker shutdowns. Most suggestions online said I needed to use a gevent or eventlet worker pool but I decided to expose an NGINX container to ELB traffic and send that traffic upstream (gunicorn workers). Almost immediately I saw drastically better response times

EDIT: I migrated to an L7 load balancer so I could do HTTPS redirects, which caused some regression in the benchmark numbers so I ended up adding gevent workers because almost all of the work in this app is I/O bound

Before gevent

```
loadtest  -n 1000 -c 6 -k https://app.mysecretsanta.io
```

```
INFO 
INFO Target URL:          https://app.mysecretsanta.io
INFO Max requests:        10000
INFO Concurrency level:   6
INFO Agent:               keepalive
INFO 
INFO Completed requests:  10000
INFO Total errors:        0
INFO Total time:          421.516164677 s
INFO Requests per second: 24
INFO Mean latency:        252.7 ms
INFO 
INFO Percentage of the requests served within a certain time
INFO   50%      248 ms
INFO   90%      261 ms
INFO   95%      279 ms
INFO   99%      318 ms
INFO  100%      1066 ms (longest request)

```

After gevent

```
loadtest -n 1000 -c 100 -k https://app.mysecretsanta.io
```

```
INFO Requests: 0 (0%), requests per second: 0, mean latency: 0 ms
INFO 
INFO Target URL:          https://app.mysecretsanta.io
INFO Max requests:        1000
INFO Concurrency level:   100
INFO Agent:               keepalive
INFO 
INFO Completed requests:  1000
INFO Total errors:        0
INFO Total time:          4.762389858000001 s
INFO Requests per second: 210
INFO Mean latency:        457.4 ms
INFO 
INFO Percentage of the requests served within a certain time
INFO   50%      277 ms
INFO   90%      1133 ms
INFO   95%      1290 ms
INFO   99%      1423 ms
INFO  100%      1453 ms (longest request)
```