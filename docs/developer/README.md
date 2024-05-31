# Development
========================

If you're new to Django, see [Getting Started with Django](https://www.djangoproject.com/start/) for an introduction to the framework.

## Local Setup

* Install Docker <https://docs.docker.com/get-docker/>
* Initialize the application:

  ```shell
  cd src
  docker-compose build
  ```
* Run the server: `docker-compose up`

  Press Ctrl-c when you'd like to exit or pass `-d` to run in detached mode.

Visit the running application at [http://localhost:8080](http://localhost:8080).


### Troubleshooting 

* If you are using Windows, you may need to change your [line endings](https://docs.github.com/en/get-started/getting-started-with-git/configuring-git-to-handle-line-endings). If not, you may not be able to run manage.py. 
* Unix based operating systems (like macOS or Linux) handle line separators [differently than Windows does](https://superuser.com/questions/374028/how-are-n-and-r-handled-differently-on-linux-and-windows). This can break bash scripts in particular. In the case of manage.py, it uses *#!/usr/bin/env python* to access the Python executable. Since the script is still thinking in terms of unix line seperators, it may look for the executable *python\r* rather than *python* (since Windows cannot read the carriage return on its own) - thus leading to the error `usr/bin/env: 'python\r' no such file or directory` 
* If you'd rather not change this globally, add a `.gitattributes` file in the project root with `* text eol=lf` as the text content, and [refresh the repo](https://docs.github.com/en/get-started/getting-started-with-git/configuring-git-to-handle-line-endings#refreshing-a-repository-after-changing-line-endings)
* If you are using a Mac with a M1 chip, and see this error `The chromium binary is not available for arm64.` or an error involving `puppeteer`, try adding this line below into your `.bashrc` or `.zshrc`. 

```
export DOCKER_DEFAULT_PLATFORM=linux/amd64
```

When completed, don't forget to rerun `docker-compose up`! 

## Branch Conventions

We use the branch convention of `initials/branch-topic` (ex: `lmm/fix-footer`). This allows for automated deployment to a developer sandbox namespaced to the initials.

## Merging and PRs

History preservation and merge contexts are more important to us than a clean and linear history, so we will merge instead of rebasing. 
To bring your feature branch up-to-date wih main:

```
git checkout main
git pull
git checkout <feature-branch>
git merge orgin/main
git push
```

Resources:
- [https://frontend.turing.edu/lessons/module-3/merge-vs-rebase.html](https://frontend.turing.edu/lessons/module-3/merge-vs-rebase.html)
- [https://www.atlassian.com/git/tutorials/merging-vs-rebasing](https://www.atlassian.com/git/tutorials/merging-vs-rebasing)
- [https://www.simplilearn.com/git-rebase-vs-merge-article](https://www.simplilearn.com/git-rebase-vs-merge-article)

## Setting Vars

Non-secret environment variables for local development are set in [src/docker-compose.yml](../../src/docker-compose.yml).

Secrets (for example, if you'd like to have a working Login.gov authentication) go in `.env` in [src/](../../src/) with contents like this:

```
DJANGO_SECRET_LOGIN_KEY="<...>"
```

You'll need to create the `.env` file yourself. Get started by running:

```shell
cd src
cp ./.env-example .env
```

Get the secrets from Cloud.gov by running `cf env getgov-YOURSANDBOX`. More information is available in [rotate_application_secrets.md](../operations/runbooks/rotate_application_secrets.md).

## Getting access to /admin on all development sandboxes (also referred to as "adding to fixtures")

The endpoint /admin can be used to view and manage site content, including but not limited to user information and the list of current applications in the database. However, access to this is limited to analysts and full-access users with regular domain requestors and domain managers not being able to see this page.

While on production (the sandbox referred to as `stable`), an existing analyst or full-access user typically grants access /admin as part of onboarding ([see these instructions](../django-admin/roles.md)), doing this for all development sandboxes is very time consuming. Instead, to get access to /admin on all development sandboxes and when developing code locally, refer to the following sections depending on what level of user access you desire.


### Adding full-access user to /admin

 To get access to /admin on every non-production sandbox and to use /admin in local development, do the following:

1. Login via login.gov
2. Go to the home page and make sure you can see the part where you can submit a domain request
3. Go to /admin and it will tell you that your UUID is not authorized (it shows a very long string, this is your UUID). Copy that UUID for use in 4.
4. (Designers) Message in #getgov-dev that you need access to admin as a `superuser` and send them this UUID along with your desired email address. Please see the "Adding an Analyst to /admin" section below to complete similiar steps if you also desire an `analyst` user account. Engineers will handle the remaining steps for designers, stop here.

(Engineers) In src/registrar/fixtures_users.py add to the `ADMINS` list in that file by adding your UUID as your username along with your first and last name. See below:

```
 ADMINS = [
        {
            "username": "<UUID here>",
            "first_name": "",
            "last_name": "",
        },
        ...
 ]
```

5. (Engineers) In the browser, navigate to /admin. To verify that all is working correctly, under "domain requests" you should see fake domains with various fake statuses.
6. (Engineers) Add an optional email key/value pair

### Adding an analyst-level user to /admin
Analysts are a variant of the admin role with limited permissions. The process for adding an Analyst is much the same as adding an admin:

1. Login via login.gov (if you already exist as an admin, you will need to create a separate login.gov account for this: i.e. first.last+1@email.com)
2. Go to the home page and make sure you can see the part where you can submit a domain request
3. Go to /admin and it will tell you that UUID is not authorized, copy that UUID for use in 4 (this will be a different UUID than the one obtained from creating an admin)
4. (Designers) Message in #getgov-dev that you need access to admin as a `superuser` and send them this UUID along with your desired email address. Engineers will handle the remaining steps for designers, stop here.

5. (Engineers) In src/registrar/fixtures_users.py add to the `STAFF` list in that file by adding your UUID as your username along with your first and last name. See below:

```
 STAFF = [
        {
            "username": "<UUID here>",
            "first_name": "",
            "last_name": "",
        },
        ...
 ]
```

5. (Engineers) In the browser, navigate to /admin. To verify that all is working correctly, verify that you can only see a sub-section of the modules and some are set to view-only.
6. (Engineers) Add an optional email key/value pair

Do note that if you wish to have both an analyst and admin account, append `-Analyst` to your first and last name, or use a completely different first/last name to avoid confusion. Example: `Bob-Analyst`

## Adding to CODEOWNERS (optional)

The CODEOWNERS file sets the tagged individuals as default reviewers on any Pull Request that changes files that they are marked as owners of.

1. Go to [.github\CODEOWNERS](../../.github/CODEOWNERS)
2. Following the [CODEOWNERS documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners), add yourself as owner to files that you wish to be automatically requested as reviewer for.
   
   For example, if you wish to add yourself as a default reviewer for all pull requests, add your GitHub username to the same line as the `*` designator:  

   ```diff
   - * @abroddrick
   + * @abroddrick @YourGitHubUser
   ```

3. Create a pull request to finalize your changes

## Viewing Logs

If you run via `docker-compose up`, you'll see the logs in your terminal.

If you run via `docker-compose up -d`, you can get logs with `docker-compose logs -f`.

You can change the logging verbosity, if needed. Do a web search for "django log level".

## Mock data

[load.py](../../src/registrar/management/commands/load.py) called from docker-compose (locally) and reset-db.yml (upper) loads the fixtures from [fixtures_user.py](../../src/registrar/fixtures_users.py) and [fixtures_domain_requests.py](../../src/registrar/fixtures_domain_requests.py), giving you some test data to play with while developing.

See the [database-access README](./database-access.md) for information on how to pull data to update these fixtures.

## Running tests

Crash course on Docker's `run` vs `exec`: in order to run the tests inside of a container, a container must be running. If you already have a container running, you can use `exec`. If you do not, you can use `run`, which will attempt to start one.

To get a container running:

```shell
cd src
docker-compose build
docker-compose up -d
```

Django's test suite:

```shell
docker-compose exec app ./manage.py test
```

OR

```shell
docker-compose exec app python -Wa ./manage.py test  # view deprecation warnings
```

Linters:

```shell
docker-compose exec app ./manage.py lint
```

### Testing behind logged in pages

To test behind logged in pages with external tools, like `pa11y-ci` or `OWASP Zap`, add

```
"registrar.tests.common.MockUserLogin"
```

to MIDDLEWARE in settings.py. **Remove it when you are finished testing.**

### Reducing console noise in tests

Some tests, particularly when using Django's test client, will print errors.

These errors do not indicate test failure, but can make the output hard to read.

To silence them, we have a helper function `less_console_noise`:

```python
from .common import less_console_noise
...
        with less_console_noise():
            # <test code goes here>
```

Or alternatively, if you prefer using a decorator, just use:

```python
from .common import less_console_noise_decorator

@less_console_noise_decorator
def some_function():
  # <test code goes here>
```

### Accessibility Testing in the browser

We use the [ANDI](https://www.ssa.gov/accessibility/andi/help/install.html) browser extension 
from ssa.gov for accessibility testing outside the pipeline. 

ANDI will get blocked by our CSP settings, so you will need to install the 
[Disable Content-Security-Policy extension](https://chrome.google.com/webstore/detail/disable-content-security/ieelmcmcagommplceebfedjlakkhpden) 
and activate it for the page you'd like to test.

Note - refresh after enabling the extension on a page but before clicking ANDI.

### Accessibility Scanning

The tool `pa11y-ci` is used to scan pages for compliance with a set of
accessibility rules. The scan runs as part of our CI setup (see
`.github/workflows/test.yaml`) but it can also be run locally. To run locally,
type

```shell
docker-compose run pa11y npm run pa11y-ci
```

The URLs that `pa11y-ci` will scan are configured in `src/.pa11yci`. When new
views and pages are added, their URLs should also be added to that file.

### Security Scanning

The tool OWASP Zap is used for scanning the codebase for compliance with
security rules. The scan runs as part of our CI setup (see
`.github/workflows/test.yaml`) but it can also be run locally. To run locally,
type

```shell
docker-compose run owasp
```

## Images, stylesheets, and JavaScript

We use the U.S. Web Design System (USWDS) for styling our applications.

Static files (images, CSS stylesheets, JavaScripts, etc) are known as "assets".

Assets are stored in `registrar/assets` during development and served from `registrar/public`. During deployment, assets are copied from `registrar/assets` into `registrar/public`. Any assets which need processing, such as USWDS Sass files, are processed before copying.

**Note:** Custom images are added to `/registrar/assets/img/registrar`, keeping them separate from the images copied over by USWDS. However, because the `/img/` directory is listed in `.gitignore`, any files added to `/registrar/assets/img/registrar` will need to be force added (i.e. `git add --force <img-file>`) before they can be deployed. 

We utilize the [uswds-compile tool](https://designsystem.digital.gov/documentation/getting-started/developers/phase-two-compile/) from USWDS to compile and package USWDS assets.

### Making and viewing style changes

When you run `docker-compose up` the `node` service in the container will begin to watch for changes in the `registrar/assets` folder, and will recompile once any changes are made.

Within the `registrar/assets` folder, the `_theme` folder contains three files initially generated by `uswds-compile`:
1. `_uswds-theme-custom-styles` contains all the custom styles created for this application
2. `_uswds-theme` contains all the custom theme settings (e.g. primary colors, fonts, banner color, etc..)
3. `styles.css` a entry point or index for the styles, forwards all of the other style files used in the project (i.e. the USWDS source code, the settings, and all custom stylesheets).

You can also compile the **Sass** at any time using `npx gulp compile`. Similarly, you can copy over **other static assets** (images and javascript files), using `npx gulp copyAssets`.

### CSS class naming conventions

We use the [CSS Block Element Modifier (BEM)](https://getbem.com/naming/) naming convention for our custom classes. This is in line with how USWDS [approaches](https://designsystem.digital.gov/whats-new/updates/2019/04/08/introducing-uswds-2-0/) their CSS class architecture and helps keep our code cohesive and readable.

### Upgrading USWDS and other JavaScript packages

Version numbers can be manually controlled in `package.json`. Edit that, if desired.

Now run `docker-compose run node npm update`.

Then run `docker-compose up` to recompile and recopy the assets.

Examine the results in the running application (remember to empty your cache!) and commit `package.json` and `package-lock.json` if all is well.

## Finite State Machines

In an effort to keep our domain logic centralized, we are representing the state of 
objects in the application using the [django-fsm](https://github.com/viewflow/django-fsm)
library. See the [ADR number 15](../architecture/decisions/0015-use-django-fs.md) for
more information on the topic.

## Login Time Bug

If you are seeing errors related to openid complaining about issuing a token from the future like this:

```
ERROR [djangooidc.oidc:243] Issued in the future
```

it may help to resync your laptop with time.nist.gov: 

```
sudo sntp -sS time.nist.gov
```

### Settings
The config for the connection pool exists inside the `settings.py` file.
| Name                     | Purpose                                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------------------- |
| EPP_CONNECTION_POOL_SIZE | Determines the number of concurrent sockets that should exist in the pool.                        |
| POOL_KEEP_ALIVE          | Determines the interval in which we ping open connections in seconds. Calculated as POOL_KEEP_ALIVE / EPP_CONNECTION_POOL_SIZE |
| POOL_TIMEOUT             | Determines how long we try to keep a pool alive for, before restarting it.                        |

Consider updating the `POOL_TIMEOUT` or `POOL_KEEP_ALIVE` periods if the pool often restarts. If the pool only restarts after a period of inactivity, update `POOL_KEEP_ALIVE`. If it restarts during the EPP call itself, then `POOL_TIMEOUT` needs to be updated.

## Adding a S3 instance to your sandbox
This can either be done through the CLI, or through the cloud.gov dashboard. Generally, it is better to do it through the dashboard as it handles app binding for you. 

To associate a S3 instance to your sandbox, follow these steps:
1. Navigate to https://dashboard.fr.cloud.gov/login
2. Select your sandbox from the `Applications` tab
3. Click `Services` on the application nav bar
4. Add a new service (plus symbol)
5. Click `Marketplace Service`
6. For Space, put in your sandbox initials 
7. On the `Select the service` dropdown, select `s3`
8. Under the dropdown on `Select Plan`, select `basic-sandbox`
9. Under `Service Instance` enter `getgov-s3` for the name and leave the other fields empty

See this [resource](https://cloud.gov/docs/services/s3/) for information on associating an S3 instance with your sandbox through the CLI.

### Testing your S3 instance locally
To test the S3 bucket associated with your sandbox, you will need to add four additional variables to your `.env` file. These are as follows:

```
AWS_S3_ACCESS_KEY_ID = "{string value of `access_key_id` in getgov-s3}"
AWS_S3_SECRET_ACCESS_KEY = "{string value of `secret_access_key` in getgov-s3}"
AWS_S3_REGION = "{string value of `region` in getgov-s3}"
AWS_S3_BUCKET_NAME = "{string value of `bucket` in getgov-s3}"
```

You can view these variables by running the following command:
```
cf env getgov-{app name}
```

Then, copy the variables under the section labled `s3`.

## Signals 
The application uses [Django signals](https://docs.djangoproject.com/en/5.0/topics/signals/). In particular, it uses a subset of prebuilt signals called [model signals](https://docs.djangoproject.com/en/5.0/ref/signals/#module-django.db.models.signals). 

Per Django, signals "[...allow certain senders to notify a set of receivers that some action has taken place.](https://docs.djangoproject.com/en/5.0/topics/signals/#module-django.dispatch)" 

In other words, signals are a mechanism that allows different parts of an application to communicate with each other by sending and receiving notifications when events occur. When an event occurs (such as creating, updating, or deleting a record), signals can automatically trigger specific actions in response. This allows different parts of an application to stay synchronized without tightly coupling the component. 

### Rules of use
When using signals, try to adhere to these guidelines:
1. Don't use signals when you can use another method, such as an override of `save()` or `__init__`.   
2. Document its usage in this readme (or another centralized location), as well as briefly on the underlying class it is associated with. For instance, since the `handle_profile` directly affects the class `Contact`, the class description notes this and links to [signals.py](../../src/registrar/signals.py).
3. Where possible, avoid chaining signals together (i.e. a signal that calls a signal). If this has to be done, clearly document the flow.
4. Minimize logic complexity within the signal as much as possible.

### When should you use signals?
Generally, you would use signals when you want an event to be synchronized across multiple areas of code at once (such as with two models or more models at once) in a way that would otherwise be difficult to achieve by overriding functions.

However, in most scenarios, if you can get away with avoiding signals - you should. The reasoning for this is that [signals give the appearance of loose coupling, but they can quickly lead to code that is hard to understand, adjust and debug](https://docs.djangoproject.com/en/5.0/topics/signals/#module-django.dispatch).

Consider using signals when:
1. Synchronizing events across multiple models or areas of code.
2. Performing logic before or after saving a model to the database (when otherwise difficult through `save()`).
3. Encountering an import loop when overriding functions such as `save()`.
4. You are otherwise unable to achieve the intended behavior by overrides or other means.
5. (Rare) Offloading tasks when multi-threading.

For the vast majority of use cases, the [pre_save](https://docs.djangoproject.com/en/5.0/ref/signals/#pre-save) and [post_save](https://docs.djangoproject.com/en/5.0/ref/signals/#post-save) signals are sufficient in terms of model-to-model management.

### Where should you use them?
This project compiles signals in a unified location to maintain readability. If you are adding a signal or otherwise utilizing one, you should always define them in [signals.py](../../src/registrar/signals.py). Except under rare circumstances, this should be adhered to for the reasons mentioned above. 

### How are we currently using signals?
At the time of writing, we currently only use signals for the Contact and User objects when synchronizing data returned from Login.gov. This is because the `Contact` object holds information that the user specified in our system, whereas the `User` object holds information that was specified in Login.gov.

To keep our signal usage coherent and well-documented, add to this document when a new function is added for ease of reference and use.

#### handle_profile
This function is triggered by the post_save event on the User model, designed to manage the synchronization between User and Contact entities. It operates under the following conditions:

1. For New Users: Upon the creation of a new user, it checks for an existing `Contact` by email. If no matching contact is found, it creates a new Contact using the user's details from Login.gov. If a matching contact is found, it associates this contact with the user. In cases where multiple contacts with the same email exist, it logs a warning and associates the first contact found.

2. For Existing Users: For users logging in subsequent times, the function ensures that any updates from Login.gov are applied to the associated User record. However, it does not alter any existing Contact records.

## Disable email sending (toggling the disable_email_sending flag)
1. On the app, navigate to `\admin`.
2. Under models, click `Waffle flags`.
3. Click the `disable_email_sending` record. This should exist by default, if not - create one with that name.
4. (Important) Set the field `everyone` to `Yes`. This field overrides all other settings 