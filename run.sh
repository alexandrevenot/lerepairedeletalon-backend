#!/bin/bash

cd app && uvicorn main:app --host localhost --port 3001
