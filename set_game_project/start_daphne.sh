#!/bin/bash

export DJANGO_SETTINGS_MODULE=set_game_project.settings
exec daphne -b 0.0.0.0 -p 8000 set_game_project.asgi:application > daphne.log 2>&1