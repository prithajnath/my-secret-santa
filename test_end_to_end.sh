#!/usr/bin/env bash

# We don't want these tests to run in parallel so we can't just do npm run test

npm run test tests/js/user_auth.test.js
npm run test tests/js/user_edit_profile.test.js